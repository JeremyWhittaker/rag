"""Enhanced FastAPI server with legal-specific endpoints."""

from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from pathlib import Path
import json

from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain

from .config import INDEX_DIR, CHAT_MODEL, EMBED_MODEL
from .query import build_legal_aware_retriever
from .legal_query import LegalQueryEnhancer, create_legal_prompt_template
from .legal_metadata import MetadataIndex
from .citation_resolver import CitationResolver, CitationEnhancer
from .legal_processor import LegalDocumentProcessor


app = FastAPI(
    title="Legal RAG Assistant",
    description="AI-powered legal research assistant for ADRE/OAH cases",
    version="2.0.0"
)


class LegalQueryRequest(BaseModel):
    """Request model for legal queries."""
    question: str = Field(..., description="The legal question to answer")
    projects: List[str] = Field(..., description="List of projects to search")
    enable_hierarchy: bool = Field(default=True, description="Use authority hierarchy")
    include_citations: bool = Field(default=True, description="Include citation references")
    verbose: bool = Field(default=False, description="Include detailed metadata")


class LegalQueryResponse(BaseModel):
    """Response model for legal queries."""
    answer: str
    query_type: str
    sources: List[Dict[str, Any]]
    citations: Optional[Dict[str, str]] = None
    metadata: Optional[Dict[str, Any]] = None


class CitationLookupRequest(BaseModel):
    """Request model for citation lookup."""
    citation: str = Field(..., description="The citation to look up")
    projects: List[str] = Field(..., description="Projects to search in")
    include_citing_docs: bool = Field(default=False, description="Include documents that cite this")


class MetadataSearchRequest(BaseModel):
    """Request model for metadata search."""
    project: str = Field(..., description="Project to search in")
    document_type: Optional[str] = None
    case_number: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    violation_type: Optional[str] = None


@app.get("/")
async def root():
    """API information endpoint."""
    return {
        "name": "Legal RAG Assistant",
        "version": "2.0.0",
        "endpoints": {
            "/ask": "General legal query (enhanced)",
            "/legal-query": "Advanced legal query with full analysis",
            "/citation-lookup": "Look up specific citations",
            "/metadata-search": "Search documents by metadata",
            "/projects": "List available projects",
            "/statistics": "Get index statistics"
        }
    }


@app.get("/ask")
async def ask(
    q: str = Query(..., description="Legal question"),
    projects: str = Query(..., description="Comma-separated project names")
):
    """Simple legal query endpoint (backwards compatible)."""
    project_list = [p.strip() for p in projects.split(",")]
    
    # Build retriever
    retriever = build_legal_aware_retriever(project_list, INDEX_DIR)
    
    # Create chain
    llm = ChatOpenAI(model=CHAT_MODEL, temperature=0)
    enhancer = LegalQueryEnhancer()
    query_info = enhancer.enhance_query(q)
    
    prompt = create_legal_prompt_template(query_info['query_type'])
    combine_docs_chain = create_stuff_documents_chain(llm, prompt)
    rag_chain = create_retrieval_chain(retriever, combine_docs_chain)
    
    # Invoke
    result = rag_chain.invoke({
        "input": q,
        "query_type": query_info['query_type'],
        "focus": query_info.get('focus', 'general'),
        "expanded_terms": ", ".join(query_info.get('expanded_terms', []))
    })
    
    return {"answer": result["answer"]}


@app.post("/legal-query", response_model=LegalQueryResponse)
async def legal_query(request: LegalQueryRequest):
    """Advanced legal query with full analysis."""
    try:
        # 1. Query enhancement
        enhancer = LegalQueryEnhancer()
        query_info = enhancer.enhance_query(request.question)
        
        # 2. Build retriever
        if request.enable_hierarchy:
            retriever = build_legal_aware_retriever(request.projects, INDEX_DIR)
        else:
            from .query import build_retriever
            from langchain.retrievers.merger_retriever import MergerRetriever
            retrievers = [build_retriever(p, INDEX_DIR) for p in request.projects]
            retriever = MergerRetriever(retrievers=retrievers)
        
        # 3. Create chain with legal prompt
        llm = ChatOpenAI(model=CHAT_MODEL, temperature=0)
        prompt = create_legal_prompt_template(query_info['query_type'])
        combine_docs_chain = create_stuff_documents_chain(llm, prompt)
        rag_chain = create_retrieval_chain(retriever, combine_docs_chain)
        
        # 4. Invoke chain
        result = rag_chain.invoke({
            "input": request.question,
            "query_type": query_info['query_type'],
            "focus": query_info.get('focus', 'general'),
            "expanded_terms": ", ".join(query_info.get('expanded_terms', []))
        })
        
        # 5. Process citations if requested
        answer = result["answer"]
        citations_dict = None
        
        if request.include_citations:
            resolver = CitationResolver(INDEX_DIR)
            enhancer = CitationEnhancer(resolver)
            answer = enhancer.enhance_response(answer, request.projects)
            
            # Extract resolved citations
            processor = LegalDocumentProcessor()
            found_citations = processor.extract_citations(answer)
            citations_dict = {}
            for cit_type, cit_list in found_citations.items():
                for entity in cit_list:
                    doc = resolver.resolve_citation(entity.citation, request.projects)
                    if doc:
                        citations_dict[entity.citation] = doc.metadata.get("source", "Found")
        
        # 6. Prepare sources
        sources = []
        seen_sources = set()
        
        if "context" in result:
            for doc in result["context"]:
                source = doc.metadata.get("source", "Unknown")
                if source not in seen_sources:
                    seen_sources.add(source)
                    sources.append({
                        "filename": source,
                        "document_type": doc.metadata.get("document_type", "unknown"),
                        "is_primary_authority": doc.metadata.get("is_primary_authority", False),
                        "authority_weight": doc.metadata.get("authority_weight", 1),
                        "case_number": doc.metadata.get("case_number")
                    })
        
        # 7. Prepare response
        response = LegalQueryResponse(
            answer=answer,
            query_type=query_info['query_type'],
            sources=sources,
            citations=citations_dict
        )
        
        if request.verbose:
            response.metadata = {
                "query_analysis": query_info,
                "total_sources": len(sources),
                "primary_authorities": sum(1 for s in sources if s["is_primary_authority"])
            }
        
        return response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/citation-lookup")
async def citation_lookup(request: CitationLookupRequest):
    """Look up a specific citation."""
    try:
        resolver = CitationResolver(INDEX_DIR)
        
        # Resolve the citation
        doc = resolver.resolve_citation(request.citation, request.projects)
        
        response = {
            "citation": request.citation,
            "found": doc is not None
        }
        
        if doc:
            response["document"] = {
                "source": doc.metadata.get("source"),
                "document_type": doc.metadata.get("document_type"),
                "case_number": doc.metadata.get("case_number"),
                "excerpt": doc.page_content[:500] + "..." if len(doc.page_content) > 500 else doc.page_content
            }
        
        if request.include_citing_docs:
            citing_docs = resolver.find_citing_documents(request.citation, request.projects)
            response["citing_documents"] = [
                {
                    "project": project,
                    "source": doc.metadata.get("source"),
                    "document_type": doc.metadata.get("document_type")
                }
                for project, doc in citing_docs
            ]
        
        return response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/metadata-search")
async def metadata_search(request: MetadataSearchRequest):
    """Search documents by metadata."""
    try:
        proj_dir = INDEX_DIR / request.project
        if not proj_dir.exists():
            raise HTTPException(status_code=404, detail=f"Project '{request.project}' not found")
        
        metadata_index = MetadataIndex(proj_dir)
        
        # Build search criteria
        criteria = {}
        if request.document_type:
            criteria["document_type"] = request.document_type
        if request.case_number:
            criteria["case_number"] = request.case_number
        if request.violation_type:
            criteria["violation_type"] = request.violation_type
        
        # Search
        results = metadata_index.search(**criteria)
        
        # Filter by date if provided
        if request.date_from or request.date_to:
            from datetime import datetime
            date_from = datetime.fromisoformat(request.date_from) if request.date_from else None
            date_to = datetime.fromisoformat(request.date_to) if request.date_to else None
            
            filtered_results = []
            for result in results:
                if result.date_filed:
                    if date_from and result.date_filed < date_from:
                        continue
                    if date_to and result.date_filed > date_to:
                        continue
                    filtered_results.append(result)
            results = filtered_results
        
        # Format response
        return {
            "total_results": len(results),
            "documents": [
                {
                    "filename": r.file_name,
                    "document_type": r.document_type,
                    "case_number": r.case_number,
                    "date_filed": r.date_filed.isoformat() if r.date_filed else None,
                    "authority_weight": r.authority_weight,
                    "violation_type": r.violation_type,
                    "penalty": r.penalty
                }
                for r in results[:50]  # Limit to 50 results
            ]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/projects")
async def list_projects():
    """List all available projects."""
    try:
        projects = []
        if INDEX_DIR.exists():
            for proj_dir in INDEX_DIR.iterdir():
                if proj_dir.is_dir() and (proj_dir / "chroma.sqlite3").exists():
                    # Get project info
                    metadata_file = proj_dir / "metadata_index.json"
                    doc_count = 0
                    
                    if metadata_file.exists():
                        with open(metadata_file) as f:
                            metadata = json.load(f)
                            doc_count = len(metadata)
                    
                    projects.append({
                        "name": proj_dir.name,
                        "document_count": doc_count,
                        "has_metadata": metadata_file.exists()
                    })
        
        return {
            "total_projects": len(projects),
            "projects": projects
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/statistics/{project}")
async def project_statistics(project: str):
    """Get statistics for a specific project."""
    try:
        proj_dir = INDEX_DIR / project
        if not proj_dir.exists():
            raise HTTPException(status_code=404, detail=f"Project '{project}' not found")
        
        metadata_index = MetadataIndex(proj_dir)
        stats = metadata_index.get_statistics()
        
        # Add project name
        stats["project"] = project
        
        return stats
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
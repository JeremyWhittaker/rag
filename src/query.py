"""Query one or many projects with a retrieval-augmented chain and legal enhancements."""

from __future__ import annotations
import argparse
from pathlib import Path
from typing import List, Dict, Optional

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain.retrievers.merger_retriever import MergerRetriever
from langchain.retrievers.ensemble import EnsembleRetriever
from langchain.prompts import ChatPromptTemplate
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains import create_retrieval_chain
from langchain.schema import Document

from .config import INDEX_DIR, CHAT_MODEL, EMBED_MODEL
from .legal_query import LegalQueryEnhancer, LegalSystemPrompt, create_legal_prompt_template
from .legal_metadata import MetadataIndex


def build_retriever(project: str, root: Path, search_kwargs: Optional[Dict] = None):
    """Open a project-specific Chroma collection and return its retriever."""
    if search_kwargs is None:
        search_kwargs = {"k": 4}
    
    db = Chroma(
        persist_directory=str(root / project),
        collection_name=project,
        embedding_function=OpenAIEmbeddings(model=EMBED_MODEL),
    )
    return db.as_retriever(search_kwargs=search_kwargs)


def build_legal_aware_retriever(projects: List[str], root: Path, 
                              authority_hierarchy: bool = True) -> MergerRetriever:
    """Build a retriever that understands legal authority hierarchy."""
    retrievers = []
    weights = []
    
    for project in projects:
        retriever = build_retriever(project, root, search_kwargs={"k": 6})
        retrievers.append(retriever)
        
        # Assign weights based on project type
        if "statute" in project.lower():
            weights.append(0.4)  # Highest weight for statutes
        elif "regulation" in project.lower() or "aac" in project.lower():
            weights.append(0.3)  # High weight for regulations
        elif "adre" in project.lower() or "oah" in project.lower():
            weights.append(0.25)  # Medium-high for administrative
        else:
            weights.append(0.05)  # Lower weight for other documents
    
    # Normalize weights
    total_weight = sum(weights)
    weights = [w / total_weight for w in weights]
    
    if authority_hierarchy and len(retrievers) > 1:
        # Use ensemble retriever with weights
        return EnsembleRetriever(
            retrievers=retrievers,
            weights=weights
        )
    else:
        # Use simple merger without weights
        return MergerRetriever(retrievers=retrievers)


def main() -> None:
    ap = argparse.ArgumentParser(description="Query one or multiple RAG projects with legal enhancements")
    ap.add_argument("question", help="Natural-language prompt")
    ap.add_argument("--projects", nargs="+", required=True,
                    help="Project name(s) given at ingest time")
    ap.add_argument("--root-index", type=Path, default=INDEX_DIR)
    ap.add_argument("--disable-legal", action="store_true",
                    help="Disable legal query enhancements")
    ap.add_argument("--no-hierarchy", action="store_true",
                    help="Disable authority hierarchy weighting")
    ap.add_argument("--verbose", action="store_true",
                    help="Show query analysis and metadata")
    args = ap.parse_args()

    # 1️⃣  Enhance query with legal understanding
    if not args.disable_legal:
        enhancer = LegalQueryEnhancer()
        query_info = enhancer.enhance_query(args.question)
        
        if args.verbose:
            print(f"\n📊 Query Analysis:")
            print(f"  Type: {query_info['query_type']}")
            print(f"  Focus: {query_info.get('focus', 'general')}")
            if query_info['extracted_citations']:
                print(f"  Citations found: {query_info['extracted_citations']}")
            if query_info['expanded_terms']:
                print(f"  Expanded terms: {query_info['expanded_terms']}")
            print()
    else:
        query_info = {
            'query_type': 'general',
            'focus': 'general',
            'expanded_terms': []
        }

    # 2️⃣  Build appropriate retriever
    if not args.disable_legal and not args.no_hierarchy:
        retriever = build_legal_aware_retriever(
            args.projects, args.root_index, authority_hierarchy=True
        )
    else:
        retrievers = [build_retriever(p, args.root_index) for p in args.projects]
        retriever = MergerRetriever(retrievers=retrievers)

    # 3️⃣  Build the combine-documents chain with appropriate prompt
    llm = ChatOpenAI(model=CHAT_MODEL, temperature=0)
    
    if not args.disable_legal:
        # Use legal-specific prompt
        prompt = create_legal_prompt_template(query_info['query_type'])
    else:
        # Use standard prompt
        prompt = ChatPromptTemplate.from_template(
            "Use the following context to answer the question.\n\n{context}\n\nQuestion: {input}"
        )
    
    combine_docs_chain = create_stuff_documents_chain(llm, prompt)

    # 4️⃣  Assemble the full retrieval chain
    rag_chain = create_retrieval_chain(retriever, combine_docs_chain)

    # 5️⃣  Prepare input with enhanced information
    chain_input = {
        "input": args.question,
        "query_type": query_info.get('query_type', 'general'),
        "focus": query_info.get('focus', 'general analysis'),
        "expanded_terms": ", ".join(query_info.get('expanded_terms', []))
    }
    
    # 6️⃣  Invoke and display results
    result = rag_chain.invoke(chain_input)
    
    print("\n📋 ANSWER:")
    print("=" * 80)
    print(result["answer"])
    print("=" * 80)
    
    # 7️⃣  Show source documents if verbose
    if args.verbose and "context" in result:
        print("\n📚 Sources Used:")
        seen_sources = set()
        for doc in result["context"]:
            source = doc.metadata.get("source", "Unknown")
            if source not in seen_sources:
                seen_sources.add(source)
                doc_type = doc.metadata.get("document_type", "unknown")
                authority = doc.metadata.get("is_primary_authority", False)
                print(f"  - {source} (Type: {doc_type}, Primary Authority: {authority})")


if __name__ == "__main__":
    main()

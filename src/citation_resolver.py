"""Citation resolver for cross-referencing legal documents."""

from __future__ import annotations
import re
from typing import Dict, List, Optional, Tuple
from pathlib import Path

from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain.schema import Document

from .config import INDEX_DIR, EMBED_MODEL
from .legal_processor import LegalEntity
from .legal_metadata import MetadataIndex


class CitationResolver:
    """Resolves citations to actual documents in the index."""
    
    def __init__(self, root_index: Path = INDEX_DIR):
        self.root_index = root_index
        self.citation_cache: Dict[str, Optional[Document]] = {}
        
        # Citation normalization patterns
        self.normalization_rules = [
            # Remove extra spaces
            (r'\s+', ' '),
            # Normalize section symbols
            (r'§§?', '§'),
            # Normalize dashes
            (r'[-–—]', '-'),
            # Remove trailing periods from citations
            (r'\.$', ''),
        ]
    
    def normalize_citation(self, citation: str) -> str:
        """Normalize a citation for matching."""
        normalized = citation.strip()
        for pattern, replacement in self.normalization_rules:
            normalized = re.sub(pattern, replacement, normalized)
        return normalized
    
    def resolve_citation(self, citation: str, projects: List[str]) -> Optional[Document]:
        """Resolve a citation to a document in the index."""
        normalized = self.normalize_citation(citation)
        
        # Check cache first
        if normalized in self.citation_cache:
            return self.citation_cache[normalized]
        
        # Search in each project
        for project in projects:
            doc = self._search_project_for_citation(normalized, project)
            if doc:
                self.citation_cache[normalized] = doc
                return doc
        
        self.citation_cache[normalized] = None
        return None
    
    def _search_project_for_citation(self, citation: str, project: str) -> Optional[Document]:
        """Search a specific project for a citation."""
        proj_dir = self.root_index / project
        if not proj_dir.exists():
            return None
        
        # Load metadata index
        metadata_index = MetadataIndex(proj_dir)
        
        # Search by citation in metadata
        results = metadata_index.search(
            statutes_cited=[citation],
            cases_cited=[citation],
            regulations_cited=[citation]
        )
        
        if results:
            # Get the document with highest authority
            best_match = results[0]
            
            # Load from vector store
            db = Chroma(
                persist_directory=str(proj_dir),
                collection_name=project,
                embedding_function=OpenAIEmbeddings(model=EMBED_MODEL),
            )
            
            # Search by SHA256
            docs = db.get(where={"sha256": best_match.sha256})
            if docs and docs["documents"]:
                return Document(
                    page_content=docs["documents"][0],
                    metadata=docs["metadatas"][0]
                )
        
        # Fallback to text search
        return self._text_search_citation(citation, project)
    
    def _text_search_citation(self, citation: str, project: str) -> Optional[Document]:
        """Search for citation in document text."""
        proj_dir = self.root_index / project
        
        db = Chroma(
            persist_directory=str(proj_dir),
            collection_name=project,
            embedding_function=OpenAIEmbeddings(model=EMBED_MODEL),
        )
        
        # Use similarity search with the citation as query
        results = db.similarity_search(citation, k=1)
        
        if results and citation.lower() in results[0].page_content.lower():
            return results[0]
        
        return None
    
    def resolve_all_citations(self, text: str, projects: List[str]) -> Dict[str, Optional[Document]]:
        """Resolve all citations found in a text."""
        from .legal_processor import LegalDocumentProcessor
        
        processor = LegalDocumentProcessor()
        citations = processor.extract_citations(text)
        
        resolved = {}
        
        # Process each type of citation
        for citation_type, citation_list in citations.items():
            for entity in citation_list:
                doc = self.resolve_citation(entity.citation, projects)
                resolved[entity.citation] = doc
        
        return resolved
    
    def create_citation_graph(self, projects: List[str]) -> Dict[str, List[str]]:
        """Create a graph of citation relationships between documents."""
        citation_graph = {}
        
        for project in projects:
            proj_dir = self.root_index / project
            if not proj_dir.exists():
                continue
            
            metadata_index = MetadataIndex(proj_dir)
            
            for sha256, metadata in metadata_index.index.items():
                doc_key = f"{project}:{metadata.file_name}"
                citations = []
                
                # Collect all citations
                citations.extend(metadata.statutes_cited)
                citations.extend(metadata.cases_cited)
                citations.extend(metadata.regulations_cited)
                
                if citations:
                    citation_graph[doc_key] = citations
        
        return citation_graph
    
    def find_citing_documents(self, citation: str, projects: List[str]) -> List[Tuple[str, Document]]:
        """Find all documents that cite a given citation."""
        citing_docs = []
        normalized = self.normalize_citation(citation)
        
        for project in projects:
            proj_dir = self.root_index / project
            if not proj_dir.exists():
                continue
            
            metadata_index = MetadataIndex(proj_dir)
            
            # Search for documents containing this citation
            for sha256, metadata in metadata_index.index.items():
                all_citations = (
                    metadata.statutes_cited + 
                    metadata.cases_cited + 
                    metadata.regulations_cited
                )
                
                # Check if any citation matches
                for doc_citation in all_citations:
                    if self.normalize_citation(doc_citation) == normalized:
                        # Load the document
                        db = Chroma(
                            persist_directory=str(proj_dir),
                            collection_name=project,
                            embedding_function=OpenAIEmbeddings(model=EMBED_MODEL),
                        )
                        
                        docs = db.get(where={"sha256": sha256})
                        if docs and docs["documents"]:
                            doc = Document(
                                page_content=docs["documents"][0],
                                metadata=docs["metadatas"][0]
                            )
                            citing_docs.append((project, doc))
                            break
        
        return citing_docs


class CitationEnhancer:
    """Enhances query results with resolved citations."""
    
    def __init__(self, citation_resolver: CitationResolver):
        self.resolver = citation_resolver
    
    def enhance_response(self, response: str, projects: List[str], 
                        include_full_text: bool = False) -> str:
        """Enhance a response by resolving and adding citation information."""
        # Extract citations from response
        from .legal_processor import LegalDocumentProcessor
        processor = LegalDocumentProcessor()
        citations = processor.extract_citations(response)
        
        # Resolve each citation
        enhanced_response = response
        citation_appendix = []
        
        for citation_type, citation_list in citations.items():
            for entity in citation_list:
                doc = self.resolver.resolve_citation(entity.citation, projects)
                if doc:
                    # Create citation reference
                    ref_num = len(citation_appendix) + 1
                    ref_marker = f"[{ref_num}]"
                    
                    # Add reference marker after citation in text
                    enhanced_response = enhanced_response.replace(
                        entity.citation,
                        f"{entity.citation}{ref_marker}"
                    )
                    
                    # Add to appendix
                    appendix_entry = f"\n[{ref_num}] {entity.citation}"
                    if doc.metadata.get("case_number"):
                        appendix_entry += f" (Case No. {doc.metadata['case_number']})"
                    
                    if include_full_text:
                        # Include relevant excerpt
                        excerpt = self._extract_relevant_excerpt(
                            doc.page_content, entity.citation
                        )
                        appendix_entry += f"\n    Excerpt: {excerpt}"
                    
                    citation_appendix.append(appendix_entry)
        
        # Add citation appendix if any were found
        if citation_appendix:
            enhanced_response += "\n\n📎 Citation References:"
            enhanced_response += "".join(citation_appendix)
        
        return enhanced_response
    
    def _extract_relevant_excerpt(self, text: str, citation: str, 
                                context_chars: int = 200) -> str:
        """Extract relevant excerpt around a citation."""
        # Find citation in text
        citation_lower = citation.lower()
        text_lower = text.lower()
        
        pos = text_lower.find(citation_lower)
        if pos == -1:
            # Try normalized version
            normalized = self.resolver.normalize_citation(citation).lower()
            pos = text_lower.find(normalized)
        
        if pos == -1:
            return "..."
        
        # Extract context
        start = max(0, pos - context_chars)
        end = min(len(text), pos + len(citation) + context_chars)
        
        excerpt = text[start:end].strip()
        
        # Add ellipsis if truncated
        if start > 0:
            excerpt = "..." + excerpt
        if end < len(text):
            excerpt = excerpt + "..."
        
        return excerpt
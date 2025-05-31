"""Hybrid retriever that handles case numbers and metadata searches better."""

import re
from typing import List, Dict, Any, Optional
from langchain.schema import Document
from langchain_core.retrievers import BaseRetriever
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from .config import EMBED_MODEL, OPENAI_API_KEY

class HybridLegalRetriever(BaseRetriever):
    """Hybrid retriever that combines metadata and semantic search."""
    
    def __init__(self, projects: List[str], root_dir):
        super().__init__()
        self.projects = projects
        self.root_dir = root_dir
        self.embeddings = OpenAIEmbeddings(model=EMBED_MODEL, openai_api_key=OPENAI_API_KEY)
        
        # Build database connections
        self.databases = {}
        for project in projects:
            try:
                db = Chroma(
                    persist_directory=str(root_dir / project),
                    collection_name=project,
                    embedding_function=self.embeddings
                )
                self.databases[project] = db
            except Exception as e:
                print(f"Warning: Could not load project {project}: {e}")
    
    def get_relevant_documents(self, query: str, k: int = 6) -> List[Document]:
        """Retrieve relevant documents using hybrid approach."""
        
        # Check for case number patterns
        case_number = self._extract_case_number(query)
        
        if case_number:
            # Use metadata-first search for case numbers
            metadata_results = self._search_by_metadata(case_number, k)
            if metadata_results:
                return metadata_results
        
        # Check for specific attorney names
        attorney_name = self._extract_attorney_name(query)
        if attorney_name:
            attorney_results = self._search_by_attorney(attorney_name, k)
            if attorney_results:
                return attorney_results
        
        # Fallback to semantic search
        return self._semantic_search(query, k)
    
    def _extract_case_number(self, query: str) -> Optional[str]:
        """Extract case number from query."""
        # ADRE case number patterns
        patterns = [
            r'\b(\d{2}[A-Z]-[A-Z]\d+(?:-REL)?(?:-RHG)?)\b',
            r'\bcase\s+(?:number\s+)?(\d{2}[A-Z]-[A-Z]\d+(?:-REL)?(?:-RHG)?)\b',
            r'\b(\d{2}[A-Z]-[A-Z]\d+)\b'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                return match.group(1).upper()
        
        return None
    
    def _extract_attorney_name(self, query: str) -> Optional[str]:
        """Extract attorney name from query."""
        # Look for attorney name patterns
        attorney_patterns = [
            r'attorney\s+([A-Z][a-z]+(?:\s+[A-Z]\.?\s*)?[A-Z][a-z]+)',
            r'([A-Z][a-z]+(?:\s+[A-Z]\.?\s*)?[A-Z][a-z]+),?\s+(?:Esq|attorney)',
            r'lawyer\s+([A-Z][a-z]+(?:\s+[A-Z]\.?\s*)?[A-Z][a-z]+)'
        ]
        
        for pattern in attorney_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    def _search_by_metadata(self, case_number: str, k: int) -> List[Document]:
        """Search by case number in filename/metadata."""
        all_docs = []
        
        for project, db in self.databases.items():
            try:
                # Get all documents and filter by filename
                collection = db._collection
                all_data = collection.get(include=['documents', 'metadatas'])
                
                matching_docs = []
                for i, metadata in enumerate(all_data['metadatas']):
                    source = metadata.get('source', '')
                    stored_case = metadata.get('case_number', '')
                    
                    # Check filename or stored case number
                    if (case_number in source or 
                        case_number == stored_case or
                        case_number.replace('-REL', '') in source):
                        
                        doc = Document(
                            page_content=all_data['documents'][i],
                            metadata=metadata
                        )
                        
                        # Add priority for better chunks
                        priority = metadata.get('chunk_priority', 999)
                        matching_docs.append((priority, doc))
                
                # Sort by priority and add to results
                matching_docs.sort(key=lambda x: x[0])
                all_docs.extend([doc for _, doc in matching_docs])
                
            except Exception as e:
                print(f"Error searching {project}: {e}")
        
        return all_docs[:k]
    
    def _search_by_attorney(self, attorney_name: str, k: int) -> List[Document]:
        """Search for documents mentioning specific attorney."""
        all_docs = []
        
        for project, db in self.databases.items():
            try:
                # Use semantic search for attorney name
                results = db.similarity_search(attorney_name, k=k//len(self.databases))
                all_docs.extend(results)
            except Exception as e:
                print(f"Error searching {project} for attorney: {e}")
        
        return all_docs[:k]
    
    def _semantic_search(self, query: str, k: int) -> List[Document]:
        """Standard semantic search across all projects."""
        all_docs = []
        
        for project, db in self.databases.items():
            try:
                # Distribute k across projects
                project_k = max(1, k // len(self.databases))
                results = db.similarity_search(query, k=project_k)
                all_docs.extend(results)
            except Exception as e:
                print(f"Error in semantic search for {project}: {e}")
        
        return all_docs[:k]


def build_hybrid_legal_retriever(projects: List[str], root_dir) -> HybridLegalRetriever:
    """Build a hybrid legal retriever."""
    return HybridLegalRetriever(projects, root_dir)
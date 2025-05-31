#!/usr/bin/env python3
"""Fix case search issue by implementing hybrid search for case numbers."""

import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from src.config import EMBED_MODEL, OPENAI_API_KEY

class HybridCaseSearcher:
    """Hybrid searcher that handles case numbers better."""
    
    def __init__(self, collection_path: str):
        self.embeddings = OpenAIEmbeddings(model=EMBED_MODEL, openai_api_key=OPENAI_API_KEY)
        self.db = Chroma(
            persist_directory=collection_path,
            collection_name='adre_decisions_complete',
            embedding_function=self.embeddings
        )
        
    def search_case(self, query: str, k: int = 6) -> List[Dict[str, Any]]:
        """Search with hybrid approach: metadata first, then semantic."""
        
        # Check if query contains a case number pattern
        case_number_pattern = r'\b(\d{2}[A-Z]-[A-Z]\d+(?:-REL)?(?:-RHG)?)\b'
        case_match = re.search(case_number_pattern, query, re.IGNORECASE)
        
        if case_match:
            case_number = case_match.group(1)
            print(f"Detected case number: {case_number}")
            
            # First try: exact filename match
            filename_results = self._search_by_filename(case_number)
            if filename_results:
                print(f"Found {len(filename_results)} chunks from target case file")
                return filename_results[:k]
        
        # Fallback: regular semantic search
        print("Using semantic search")
        results = self.db.similarity_search(query, k=k)
        return [{"content": doc.page_content, "metadata": doc.metadata} for doc in results]
    
    def _search_by_filename(self, case_number: str) -> List[Dict[str, Any]]:
        """Search for documents by filename containing case number."""
        
        # Get all documents from the collection
        collection = self.db._collection
        all_docs = collection.get(include=['documents', 'metadatas'])
        
        # Filter by filename
        matching_docs = []
        for i, metadata in enumerate(all_docs['metadatas']):
            source = metadata.get('source', '')
            if case_number in source:
                matching_docs.append({
                    'content': all_docs['documents'][i],
                    'metadata': metadata
                })
        
        # Sort by chunk priority if available
        def get_priority(doc):
            return doc['metadata'].get('chunk_priority', 999)
        
        matching_docs.sort(key=get_priority)
        return matching_docs

def test_hybrid_search():
    """Test the hybrid search approach."""
    searcher = HybridCaseSearcher('index/adre_decisions_complete')
    
    test_queries = [
        "Tell me about case 24F-H036-REL",
        "What happened in case 24F-H036-REL?",
        "Case 24F-H036-REL details",
        "24F-H036-REL Anh Jung"
    ]
    
    for query in test_queries:
        print(f"\n{'='*60}")
        print(f"Query: {query}")
        print('='*60)
        
        results = searcher.search_case(query, k=3)
        
        for i, result in enumerate(results):
            metadata = result['metadata']
            content = result['content']
            source = metadata.get('source', 'unknown')
            
            print(f"\n{i+1}. Source: {source}")
            if '24F-H036-REL' in source:
                print("   ✓ CORRECT CASE!")
            else:
                print("   ✗ Wrong case")
            print(f"   Content: {content[:200]}...")

if __name__ == "__main__":
    test_hybrid_search()
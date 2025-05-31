"""Simple hybrid search implementation for case numbers."""

import re
from typing import List, Dict, Any, Optional
from langchain.schema import Document
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from .config import EMBED_MODEL, OPENAI_API_KEY


def search_with_case_number_priority(projects: List[str], root_dir, query: str, k: int = 6) -> List[Document]:
    """Search with priority for case numbers."""
    
    # Check for case number patterns
    case_number_pattern = r'\b(\d{2}[A-Z]-[A-Z]\d+(?:-REL)?(?:-RHG)?)\b'
    case_match = re.search(case_number_pattern, query, re.IGNORECASE)
    
    embeddings = OpenAIEmbeddings(model=EMBED_MODEL, openai_api_key=OPENAI_API_KEY)
    
    if case_match:
        case_number = case_match.group(1).upper()
        print(f"Detected case number: {case_number}")
        
        # Search for exact filename matches first
        for project in projects:
            try:
                db = Chroma(
                    persist_directory=str(root_dir / project),
                    collection_name=project,
                    embedding_function=embeddings
                )
                
                # Get documents by filename
                collection = db._collection
                all_data = collection.get(include=['documents', 'metadatas'])
                
                matching_docs = []
                for i, metadata in enumerate(all_data['metadatas']):
                    source = metadata.get('source', '')
                    if case_number in source:
                        doc = Document(
                            page_content=all_data['documents'][i],
                            metadata=metadata
                        )
                        priority = metadata.get('chunk_priority', 999)
                        matching_docs.append((priority, doc))
                
                if matching_docs:
                    # Sort by priority and return top results
                    matching_docs.sort(key=lambda x: x[0])
                    result_docs = [doc for _, doc in matching_docs[:k]]
                    print(f"Found {len(result_docs)} chunks from exact case file")
                    return result_docs
                    
            except Exception as e:
                print(f"Error searching {project}: {e}")
    
    # Fallback to semantic search
    print("Using semantic search fallback")
    all_docs = []
    for project in projects:
        try:
            db = Chroma(
                persist_directory=str(root_dir / project),
                collection_name=project,
                embedding_function=embeddings
            )
            results = db.similarity_search(query, k=k//len(projects))
            all_docs.extend(results)
        except Exception as e:
            print(f"Error in semantic search for {project}: {e}")
    
    return all_docs[:k]


def create_hybrid_retrieval_chain(projects: List[str], root_dir, llm, prompt):
    """Create a retrieval chain with hybrid search."""
    from langchain.chains.combine_documents import create_stuff_documents_chain
    
    # Create a custom retrieval function
    def hybrid_retrieve(query: str) -> List[Document]:
        return search_with_case_number_priority(projects, root_dir, query)
    
    # Create combine docs chain
    combine_docs_chain = create_stuff_documents_chain(llm, prompt)
    
    # Custom chain that uses hybrid search
    class HybridRetrievalChain:
        def __init__(self, retriever_func, combine_chain):
            self.retriever_func = retriever_func
            self.combine_chain = combine_chain
        
        def invoke(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
            query = inputs.get("input", "")
            
            # Hybrid search
            docs = self.retriever_func(query)
            
            # Combine documents
            result = self.combine_chain.invoke({
                "context": docs,
                "input": query
            })
            
            # Format response to match expected structure
            return {
                "answer": result,
                "input": query,
                "context": docs
            }
    
    return HybridRetrievalChain(hybrid_retrieve, combine_docs_chain)
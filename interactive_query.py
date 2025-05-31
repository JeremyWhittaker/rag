#!/usr/bin/env python3
"""Interactive query tool for testing ADRE data."""

import requests
import json
import sys
from typing import Dict, Any

BASE_URL = "http://localhost:8000"

def test_connection():
    """Test if server is running."""
    try:
        response = requests.get(f"{BASE_URL}/projects", timeout=5)
        return response.status_code == 200
    except:
        return False

def run_query(question: str, project: str = "adre_decisions_complete", **kwargs) -> Dict[str, Any]:
    """Run a query against the ADRE data."""
    query_data = {
        "question": question,
        "projects": [project],
        "enable_hierarchy": kwargs.get("hierarchy", True),
        "include_citations": kwargs.get("citations", True),
        "verbose": kwargs.get("verbose", False)
    }
    
    try:
        response = requests.post(f"{BASE_URL}/legal-query", json=query_data, timeout=60)
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"HTTP {response.status_code}: {response.text}"}
    except Exception as e:
        return {"error": f"Request failed: {str(e)}"}

def print_result(result: Dict[str, Any]):
    """Print query result in a readable format."""
    if "error" in result:
        print(f"❌ Error: {result['error']}")
        return
    
    print(f"📊 Query Type: {result.get('query_type', 'unknown')}")
    print(f"📚 Sources Used: {len(result.get('sources', []))}")
    
    if result.get('sources'):
        unique_docs = set(source['filename'] for source in result['sources'])
        print(f"📄 Unique Documents: {len(unique_docs)}")
    
    print(f"\n💡 Answer:")
    print("=" * 60)
    print(result.get('answer', 'No answer provided'))
    
    if result.get('citations'):
        print(f"\n📖 Citations ({len(result['citations'])}):")
        for citation, source in list(result['citations'].items())[:5]:
            print(f"  • {citation}: {source}")
    
    print("=" * 60)

def run_sample_queries():
    """Run a set of sample queries to demonstrate the system."""
    sample_queries = [
        {
            "question": "List all Administrative Law Judges who decided these ADRE cases.",
            "description": "Judge Information"
        },
        {
            "question": "What homeowners associations (HOAs) appear as respondents in these cases?",
            "description": "HOA Respondents"
        },
        {
            "question": "Find cases involving CC&R violations. What were the specific violations and outcomes?",
            "description": "CC&R Violations"
        },
        {
            "question": "List all attorneys with 'Esq.' titles and which cases they handled.",
            "description": "Attorneys with Esq. Titles"
        },
        {
            "question": "What Arizona Revised Statutes (A.R.S.) are most commonly cited in these cases?",
            "description": "Common A.R.S. Citations"
        },
        {
            "question": "Find cases where monetary fines were imposed. What were the amounts and reasons?",
            "description": "Monetary Penalties"
        },
        {
            "question": "What types of compliance orders were issued in these ADRE decisions?",
            "description": "Compliance Orders"
        }
    ]
    
    print("🔍 RUNNING SAMPLE QUERIES ON ADRE DATA")
    print("=" * 80)
    
    for i, query in enumerate(sample_queries, 1):
        print(f"\n{i}. {query['description']}")
        print("-" * 40)
        print(f"Query: {query['question']}")
        print()
        
        result = run_query(query['question'])
        print_result(result)
        
        if i < len(sample_queries):
            input("\nPress Enter to continue to next query...")

def interactive_mode():
    """Interactive query mode."""
    print("\n🤖 INTERACTIVE ADRE QUERY MODE")
    print("=" * 50)
    print("Type your questions about the ADRE cases.")
    print("Type 'quit' or 'exit' to stop.")
    print("Type 'help' for example queries.")
    print()
    
    while True:
        try:
            question = input("❓ Your question: ").strip()
            
            if question.lower() in ['quit', 'exit', 'q']:
                print("👋 Goodbye!")
                break
            
            if question.lower() in ['help', 'h']:
                print_help()
                continue
            
            if not question:
                continue
            
            print("\n🔍 Searching...")
            result = run_query(question)
            print_result(result)
            print()
            
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")

def print_help():
    """Print help with example queries."""
    examples = [
        "List all judges in these ADRE cases",
        "What attorneys represented homeowners associations?",
        "Find cases with architectural violations",
        "What are the most common penalties imposed?",
        "Show me cases from 2020 with specific case numbers",
        "Which HOAs had the most violations?",
        "Find cases involving trust account violations",
        "What Arizona statutes are cited most frequently?"
    ]
    
    print("\n💡 EXAMPLE QUERIES:")
    for i, example in enumerate(examples, 1):
        print(f"  {i}. {example}")
    print()

def main():
    """Main function."""
    print("🏛️ ADRE RAG SYSTEM QUERY TOOL")
    print("=" * 50)
    
    # Test connection
    if not test_connection():
        print("❌ Cannot connect to server at http://localhost:8000")
        print("Make sure the server is running with: python src/server.py")
        return 1
    
    print("✅ Connected to server successfully!")
    
    # Check if we have command line args
    if len(sys.argv) > 1:
        # Run single query from command line
        question = " ".join(sys.argv[1:])
        print(f"\n🔍 Running query: {question}")
        result = run_query(question)
        print_result(result)
        return 0
    
    # Show options
    print("\nChoose an option:")
    print("1. Run sample queries")
    print("2. Interactive query mode")
    print("3. Quit")
    
    while True:
        try:
            choice = input("\nEnter choice (1-3): ").strip()
            
            if choice == '1':
                run_sample_queries()
                break
            elif choice == '2':
                interactive_mode()
                break
            elif choice == '3':
                print("👋 Goodbye!")
                break
            else:
                print("Please enter 1, 2, or 3")
                
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
    
    return 0

if __name__ == "__main__":
    exit(main())
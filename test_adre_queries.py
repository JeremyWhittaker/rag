#!/usr/bin/env python3
"""Comprehensive test queries for ADRE decisions to verify ingestion."""

import requests
import json
import time

BASE_URL = "http://localhost:8000"

def test_query(query_data, description):
    """Execute a test query and display results."""
    print(f"\n{'='*80}")
    print(f"TEST: {description}")
    print(f"{'='*80}")
    
    response = requests.post(f"{BASE_URL}/legal-query", json=query_data)
    if response.status_code == 200:
        result = response.json()
        print(f"\nQuery Type: {result['query_type']}")
        print(f"Sources Found: {len(result['sources'])}")
        
        # Show unique sources
        unique_sources = set()
        for source in result['sources']:
            unique_sources.add(source['filename'])
        print(f"Unique Documents Used: {len(unique_sources)}")
        
        # Print answer excerpt
        answer = result['answer']
        if len(answer) > 500:
            print(f"\nAnswer Preview:\n{answer[:500]}...")
        else:
            print(f"\nAnswer:\n{answer}")
            
        # Show citations if any
        if result.get('citations'):
            print(f"\nCitations Found: {len(result['citations'])}")
            for citation, source in list(result['citations'].items())[:3]:
                print(f"  - {citation}: {source}")
                
        # Show metadata if verbose
        if result.get('metadata'):
            print(f"\nMetadata: {json.dumps(result['metadata'], indent=2)}")
    else:
        print(f"Error: {response.status_code} - {response.text}")
    
    time.sleep(1)  # Rate limiting

def run_all_tests():
    """Run comprehensive tests on ADRE decisions."""
    
    # Test 1: License Revocation Cases
    test_query({
        "question": "Find specific cases where real estate licenses were revoked. Include case numbers and reasons for revocation.",
        "projects": ["adre_decisions_complete"],
        "enable_hierarchy": True,
        "include_citations": True,
        "verbose": True
    }, "License Revocation Cases")
    
    # Test 2: Trust Account Violations
    test_query({
        "question": "What are the specific case numbers and penalties for trust account violations? List the respondent names.",
        "projects": ["adre_decisions_complete"],
        "enable_hierarchy": True,
        "include_citations": True,
        "verbose": False
    }, "Trust Account Violations with Case Numbers")
    
    # Test 3: Specific Case Number Query
    test_query({
        "question": "Tell me about case 18F-H1818052. What violations were found and what was the outcome?",
        "projects": ["adre_decisions_complete"],
        "enable_hierarchy": True,
        "include_citations": True,
        "verbose": False
    }, "Specific Case Number Analysis")
    
    # Test 4: Statutory Citations
    test_query({
        "question": "Which ADRE cases cite A.R.S. § 32-2153? What were these cases about?",
        "projects": ["adre_decisions_complete"],
        "enable_hierarchy": True,
        "include_citations": True,
        "verbose": False
    }, "Cases Citing Specific Statute")
    
    # Test 5: Commissioner Decisions
    test_query({
        "question": "List cases with Commissioner's Final Orders. What types of violations led to these orders?",
        "projects": ["adre_decisions_complete"],
        "enable_hierarchy": True,
        "include_citations": False,
        "verbose": False
    }, "Commissioner's Final Orders")
    
    # Test 6: Monetary Penalties
    test_query({
        "question": "Find cases where monetary fines were imposed. What were the amounts and reasons?",
        "projects": ["adre_decisions_complete"],
        "enable_hierarchy": True,
        "include_citations": False,
        "verbose": False
    }, "Monetary Fine Analysis")
    
    # Test 7: Misrepresentation Cases
    test_query({
        "question": "Analyze cases involving misrepresentation or false statements. Include respondent names and outcomes.",
        "projects": ["adre_decisions_complete"],
        "enable_hierarchy": True,
        "include_citations": True,
        "verbose": False
    }, "Misrepresentation Violations")
    
    # Test 8: Date Range Query
    test_query({
        "question": "What ADRE enforcement actions occurred in 2023? List case numbers and violation types.",
        "projects": ["adre_decisions_complete"],
        "enable_hierarchy": True,
        "include_citations": False,
        "verbose": False
    }, "2023 Enforcement Actions")
    
    # Test 9: Unlicensed Activity
    test_query({
        "question": "Find cases where individuals were cited for unlicensed real estate activity. What were the penalties?",
        "projects": ["adre_decisions_complete"],
        "enable_hierarchy": True,
        "include_citations": True,
        "verbose": False
    }, "Unlicensed Activity Cases")
    
    # Test 10: Pattern Analysis
    test_query({
        "question": "What are the most common violations that lead to license suspension versus revocation?",
        "projects": ["adre_decisions_complete"],
        "enable_hierarchy": True,
        "include_citations": False,
        "verbose": True
    }, "Suspension vs Revocation Pattern Analysis")

def test_metadata_search():
    """Test metadata search functionality."""
    print("\n" + "="*80)
    print("METADATA SEARCH TESTS")
    print("="*80)
    
    # Search by violation type
    response = requests.post(f"{BASE_URL}/metadata-search", json={
        "project": "adre_decisions_complete",
        "violation_type": "misrepresentation"
    })
    
    if response.status_code == 200:
        result = response.json()
        print(f"\nMisrepresentation Cases Found: {result['total_results']}")
        for doc in result['documents'][:5]:
            print(f"  - {doc['filename']} (Case: {doc.get('case_number', 'N/A')})")
    
    # Search by document type
    response = requests.post(f"{BASE_URL}/metadata-search", json={
        "project": "adre_decisions_complete",
        "document_type": "findings"
    })
    
    if response.status_code == 200:
        result = response.json()
        print(f"\nFindings Documents Found: {result['total_results']}")

def test_statistics():
    """Test project statistics."""
    print("\n" + "="*80)
    print("PROJECT STATISTICS")
    print("="*80)
    
    response = requests.get(f"{BASE_URL}/statistics/adre_decisions_complete")
    if response.status_code == 200:
        stats = response.json()
        print(f"\nTotal Documents: {stats['total_documents']}")
        print(f"\nDocument Types:")
        for doc_type, count in stats['document_types'].items():
            print(f"  - {doc_type}: {count}")
        print(f"\nViolation Types:")
        for violation, count in stats['violation_types'].items():
            print(f"  - {violation}: {count}")
        print(f"\nTotal Statutes Cited: {stats['total_statutes_cited']}")
        print(f"Total Cases Cited: {stats['total_cases_cited']}")

if __name__ == "__main__":
    print("Testing ADRE Decisions Ingestion...")
    
    # Run all query tests
    run_all_tests()
    
    # Run metadata search tests
    test_metadata_search()
    
    # Run statistics test
    test_statistics()
    
    print("\n\nAll tests completed!")
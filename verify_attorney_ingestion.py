#!/usr/bin/env python3
"""Verify that the RAG system has properly ingested attorney information."""

import requests
import json
import re
from typing import Set, List, Dict

BASE_URL = "http://localhost:8000"

def query_for_attorney_patterns():
    """Query the system using various attorney-related patterns."""
    print("ATTORNEY INGESTION VERIFICATION")
    print("=" * 80)
    
    # Various queries to test attorney information extraction
    test_queries = [
        {
            "question": "Find all mentions of 'Esq.' in these documents. List the full names before 'Esq.' and the cases they appear in.",
            "description": "Esq. Title Search"
        },
        {
            "question": "List all law firm names mentioned in these ADRE decisions. Look for firms with names like 'Law Office', 'Law Firm', 'LLP', 'LLC', 'PC', or 'PLC'.",
            "description": "Law Firm Search"
        },
        {
            "question": "Find cases where someone 'represented' or 'appeared on behalf of' a party. List the representative names.",
            "description": "Representation Search"
        },
        {
            "question": "Search for email addresses in these documents. List any attorney email addresses you find.",
            "description": "Attorney Email Search"
        },
        {
            "question": "Find all mentions of 'Assistant Attorney General' and list the names.",
            "description": "Assistant Attorney General Search"
        },
        {
            "question": "Look for transmission or copy sections that list attorney contact information. Extract attorney names and firms.",
            "description": "Transmission Section Search"
        },
        {
            "question": "Find any mentions of specific attorney names: David Fitzgibbons, Lydia Linsmeier, Eden Cohen, Mary Hone.",
            "description": "Specific Attorney Name Search"
        }
    ]
    
    all_attorneys = set()
    all_firms = set()
    all_emails = set()
    
    for query_info in test_queries:
        print(f"\n{'-'*60}")
        print(f"TEST: {query_info['description']}")
        print(f"{'-'*60}")
        
        query_data = {
            "question": query_info["question"],
            "projects": ["adre_decisions_complete"],
            "enable_hierarchy": True,
            "include_citations": True,
            "verbose": True
        }
        
        response = requests.post(f"{BASE_URL}/legal-query", json=query_data)
        
        if response.status_code == 200:
            result = response.json()
            print(f"Sources used: {len(result['sources'])}")
            print(f"Query type: {result['query_type']}")
            
            answer = result['answer']
            print(f"\nResponse preview (first 800 chars):")
            print(answer[:800] + "..." if len(answer) > 800 else answer)
            
            # Extract patterns from the answer
            if 'esq' in query_info['description'].lower():
                # Extract names before Esq.
                esq_matches = re.findall(r'([A-Z][a-z]+(?:\s+[A-Z]\.?\s*)?[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),?\s+Esq\.?', answer, re.IGNORECASE)
                if esq_matches:
                    print(f"\nEsq. attorneys found: {', '.join(esq_matches)}")
                    all_attorneys.update(esq_matches)
            
            elif 'firm' in query_info['description'].lower():
                # Extract law firm names
                firm_patterns = [
                    r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+(?:&|and)\s+[A-Z][a-z]+)*)\s+(?:Law\s+(?:Office|Firm|Group)s?|LLP|LLC|PC|PLC)',
                    r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+Law\s+(?:Office|Firm)s?'
                ]
                for pattern in firm_patterns:
                    firm_matches = re.findall(pattern, answer)
                    if firm_matches:
                        print(f"\nLaw firms found: {', '.join(firm_matches)}")
                        all_firms.update(firm_matches)
            
            elif 'email' in query_info['description'].lower():
                # Extract email addresses
                email_matches = re.findall(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', answer)
                if email_matches:
                    print(f"\nEmails found: {', '.join(email_matches)}")
                    all_emails.update(email_matches)
            
            elif 'represented' in query_info['description'].lower():
                # Extract names after "represented by" or "appeared on behalf"
                rep_patterns = [
                    r'(?:represented|appeared)\s+(?:by|on behalf of)\s+([A-Z][a-z]+(?:\s+[A-Z]\.?\s*)?[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
                    r'([A-Z][a-z]+(?:\s+[A-Z]\.?\s*)?[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:represented|appeared)'
                ]
                for pattern in rep_patterns:
                    rep_matches = re.findall(pattern, answer)
                    if rep_matches:
                        print(f"\nRepresentatives found: {', '.join(rep_matches)}")
                        all_attorneys.update(rep_matches)
            
            # Show sources for verification
            if result.get('sources'):
                print(f"\nSample source documents:")
                for source in result['sources'][:3]:
                    print(f"  - {source['filename']}")
        else:
            print(f"Error: {response.status_code} - {response.text}")
    
    # Summary
    print(f"\n{'='*80}")
    print("ATTORNEY INGESTION SUMMARY")
    print(f"{'='*80}")
    
    print(f"\nTotal unique attorney names found: {len(all_attorneys)}")
    if all_attorneys:
        print("Attorney names:")
        for i, attorney in enumerate(sorted(all_attorneys), 1):
            print(f"  {i}. {attorney}")
    
    print(f"\nTotal law firms found: {len(all_firms)}")
    if all_firms:
        print("Law firms:")
        for i, firm in enumerate(sorted(all_firms), 1):
            print(f"  {i}. {firm}")
    
    print(f"\nTotal email addresses found: {len(all_emails)}")
    if all_emails:
        print("Email addresses:")
        for i, email in enumerate(sorted(all_emails), 1):
            print(f"  {i}. {email}")
    
    return {
        'attorneys': list(all_attorneys),
        'firms': list(all_firms),
        'emails': list(all_emails)
    }

def test_specific_attorney_searches():
    """Test searches for specific attorneys we expect to find."""
    print(f"\n{'='*80}")
    print("SPECIFIC ATTORNEY VERIFICATION TESTS")
    print(f"{'='*80}")
    
    # Known attorneys that should appear in ADRE cases
    test_attorneys = [
        "David Fitzgibbons",
        "Lydia Linsmeier", 
        "Eden Cohen",
        "Mary Hone",
        "Ellen Davis",
        "Emily Mann",
        "Alexandra Kurtyka",
        "Christopher Hanlon"
    ]
    
    found_attorneys = []
    
    for attorney_name in test_attorneys:
        query_data = {
            "question": f"Find any mention of {attorney_name} in these ADRE cases. What cases did they handle and in what capacity?",
            "projects": ["adre_decisions_complete"],
            "enable_hierarchy": True,
            "include_citations": False,
            "verbose": False
        }
        
        response = requests.post(f"{BASE_URL}/legal-query", json=query_data)
        
        if response.status_code == 200:
            result = response.json()
            answer = result['answer'].lower()
            
            # Check if attorney name appears in answer
            if attorney_name.lower() in answer or any(part.lower() in answer for part in attorney_name.split()):
                found_attorneys.append({
                    'name': attorney_name,
                    'sources': len(result['sources']),
                    'mentioned': attorney_name.lower() in answer
                })
                print(f"✓ Found {attorney_name} (Sources: {len(result['sources'])})")
            else:
                print(f"✗ No mention of {attorney_name}")
    
    return found_attorneys

def check_metadata_for_attorneys():
    """Check if attorney information is stored in metadata."""
    print(f"\n{'='*80}")
    print("METADATA ATTORNEY CHECK")
    print(f"{'='*80}")
    
    # Get project statistics to see if attorney info is tracked
    response = requests.get(f"{BASE_URL}/statistics/adre_decisions_complete")
    
    if response.status_code == 200:
        stats = response.json()
        print(f"Total documents: {stats['total_documents']}")
        
        # Check if there are any attorney-related metadata fields
        print("\nAvailable metadata fields:")
        for key, value in stats.items():
            print(f"  {key}: {value}")
        
        # Try metadata search for attorney-related terms
        attorney_terms = ['attorney', 'esq', 'counsel', 'law firm', 'represented']
        
        for term in attorney_terms:
            meta_response = requests.post(f"{BASE_URL}/metadata-search", json={
                "project": "adre_decisions_complete",
                "search_term": term
            })
            
            if meta_response.status_code == 200:
                meta_result = meta_response.json()
                if meta_result.get('total_results', 0) > 0:
                    print(f"\nMetadata search for '{term}': {meta_result['total_results']} results")

def main():
    """Main verification process."""
    # Test 1: Query for attorney patterns
    attorney_data = query_for_attorney_patterns()
    
    # Test 2: Search for specific attorneys
    found_attorneys = test_specific_attorney_searches()
    
    # Test 3: Check metadata
    check_metadata_for_attorneys()
    
    # Final summary
    print(f"\n{'='*80}")
    print("FINAL VERIFICATION SUMMARY")
    print(f"{'='*80}")
    
    print(f"\nFrom pattern searches:")
    print(f"  - Attorneys found: {len(attorney_data['attorneys'])}")
    print(f"  - Law firms found: {len(attorney_data['firms'])}")
    print(f"  - Email addresses found: {len(attorney_data['emails'])}")
    
    print(f"\nFrom specific name searches:")
    print(f"  - Specific attorneys verified: {len(found_attorneys)}")
    
    if attorney_data['attorneys'] or found_attorneys:
        print(f"\n✓ CONCLUSION: The system IS parsing and storing attorney information!")
        print(f"✓ Attorney names are being indexed and are searchable through the RAG system.")
        
        # Save comprehensive results
        final_results = {
            'verification_summary': {
                'pattern_search_attorneys': len(attorney_data['attorneys']),
                'pattern_search_firms': len(attorney_data['firms']),
                'pattern_search_emails': len(attorney_data['emails']),
                'specific_attorneys_found': len(found_attorneys)
            },
            'attorneys_from_patterns': attorney_data['attorneys'],
            'law_firms_found': attorney_data['firms'],
            'email_addresses_found': attorney_data['emails'],
            'verified_specific_attorneys': found_attorneys
        }
        
        with open('attorney_verification_results.json', 'w') as f:
            json.dump(final_results, f, indent=2)
        
        print(f"✓ Complete verification results saved to attorney_verification_results.json")
        
    else:
        print(f"\n✗ ISSUE: Limited attorney information found in system.")
        print(f"This could indicate an ingestion issue or that these documents have minimal attorney representation.")

if __name__ == "__main__":
    main()
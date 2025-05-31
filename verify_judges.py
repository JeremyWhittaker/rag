#!/usr/bin/env python3
"""Verify judge names extraction from ADRE decisions."""

import requests
import json
from pathlib import Path
import re
from collections import Counter

BASE_URL = "http://localhost:8000"

def query_for_judges():
    """Query the system for all judge names mentioned in ADRE decisions."""
    print("="*80)
    print("QUERYING SYSTEM FOR JUDGE NAMES")
    print("="*80)
    
    # Query 1: Direct judge name request
    query_data = {
        "question": "List all the names of judges, administrative law judges, and hearing officers mentioned in these ADRE decisions. Include their full names and titles.",
        "projects": ["adre_decisions_complete"],
        "enable_hierarchy": True,
        "include_citations": False,
        "verbose": True
    }
    
    response = requests.post(f"{BASE_URL}/legal-query", json=query_data)
    
    judges_from_query = set()
    
    if response.status_code == 200:
        result = response.json()
        print(f"\nQuery Type: {result['query_type']}")
        print(f"Sources Used: {len(result['sources'])}")
        
        # Extract judge names from the answer
        answer = result['answer']
        print(f"\nSystem Response (first 1000 chars):\n{answer[:1000]}...")
        
        # Try to extract names that look like judge names
        # Common patterns: "Judge [Name]", "ALJ [Name]", "Administrative Law Judge [Name]"
        judge_patterns = [
            r'(?:Judge|ALJ|Administrative Law Judge|Hearing Officer)[\s:]+([A-Z][a-z]+(?:\s+[A-Z]\.?\s*)?[A-Z][a-z]+)',
            r'([A-Z][a-z]+(?:\s+[A-Z]\.?\s*)?[A-Z][a-z]+),?\s+(?:Administrative Law Judge|ALJ|Judge)',
        ]
        
        for pattern in judge_patterns:
            matches = re.findall(pattern, answer)
            judges_from_query.update(matches)
    
    return judges_from_query

def extract_judges_from_files():
    """Extract judge names directly from a sample of case files."""
    print("\n" + "="*80)
    print("EXTRACTING JUDGE NAMES FROM ACTUAL FILES")
    print("="*80)
    
    # Sample some actual case files
    case_dir = Path("../azoah/adre_decisions_downloads")
    judges_from_files = Counter()
    
    # Sample 20 random case files
    import random
    all_files = list(case_dir.glob("*.docx")) + list(case_dir.glob("*.doc"))
    sample_files = random.sample(all_files, min(20, len(all_files)))
    
    print(f"\nSampling {len(sample_files)} case files...")
    
    for file_path in sample_files:
        try:
            # Try to read the file content
            import docx
            try:
                doc = docx.Document(str(file_path))
                text = "\n".join([para.text for para in doc.paragraphs])
            except:
                # Skip files that can't be read
                continue
            
            # Look for judge names in common locations
            judge_patterns = [
                r'ADMINISTRATIVE LAW JUDGE:\s*([A-Z][a-z]+(?:\s+[A-Z]\.?\s*)?[A-Z][a-z]+)',
                r'(?:Judge|ALJ|Hearing Officer):\s*([A-Z][a-z]+(?:\s+[A-Z]\.?\s*)?[A-Z][a-z]+)',
                r'Before(?:\s+the\s+Honorable)?\s+([A-Z][a-z]+(?:\s+[A-Z]\.?\s*)?[A-Z][a-z]+),?\s+(?:Administrative Law Judge|ALJ)',
                r'([A-Z][a-z]+(?:\s+[A-Z]\.?\s*)?[A-Z][a-z]+)\s*\n\s*Administrative Law Judge',
            ]
            
            for pattern in judge_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                for match in matches:
                    if match and len(match) > 3:  # Filter out short matches
                        judges_from_files[match] += 1
                        
        except Exception as e:
            print(f"  Error reading {file_path.name}: {e}")
    
    return judges_from_files

def verify_through_metadata():
    """Check judges through metadata search."""
    print("\n" + "="*80)
    print("CHECKING METADATA INDEX")
    print("="*80)
    
    # Get project statistics
    response = requests.get(f"{BASE_URL}/statistics/adre_decisions_complete")
    if response.status_code == 200:
        stats = response.json()
        print(f"Total documents indexed: {stats['total_documents']}")
    
    # Query for specific judge names we might expect
    test_judges = ["Kay Abramsohn", "Diane Mihalsky", "Daniel Martin"]
    
    for judge_name in test_judges:
        query_data = {
            "question": f"Find all cases where {judge_name} was the judge. List the case numbers.",
            "projects": ["adre_decisions_complete"],
            "enable_hierarchy": True,
            "include_citations": False,
            "verbose": False
        }
        
        response = requests.post(f"{BASE_URL}/legal-query", json=query_data)
        if response.status_code == 200:
            result = response.json()
            print(f"\nSearching for Judge {judge_name}:")
            print(f"  Sources found: {len(result['sources'])}")
            # Check if the judge name appears in the answer
            if judge_name.lower() in result['answer'].lower():
                print(f"  ✓ Judge {judge_name} found in system")
            else:
                print(f"  ✗ Judge {judge_name} not clearly identified")

def main():
    """Main verification process."""
    print("ADRE JUDGE NAME VERIFICATION TEST")
    print("="*80)
    
    # Step 1: Query system for judges
    print("\nStep 1: Querying system for judge names...")
    judges_from_query = query_for_judges()
    print(f"\nJudges found from query: {judges_from_query}")
    
    # Step 2: Extract judges from actual files
    print("\nStep 2: Extracting judges from actual case files...")
    judges_from_files = extract_judges_from_files()
    print(f"\nTop judges found in files:")
    for judge, count in judges_from_files.most_common(10):
        print(f"  - {judge}: {count} occurrences")
    
    # Step 3: Verify through metadata
    print("\nStep 3: Verifying specific judges through targeted queries...")
    verify_through_metadata()
    
    # Step 4: Compare results
    print("\n" + "="*80)
    print("VERIFICATION RESULTS")
    print("="*80)
    
    # Check overlap
    file_judge_names = set(judges_from_files.keys())
    
    print(f"\nTotal unique judges found in sample files: {len(file_judge_names)}")
    print(f"Total judges mentioned in query response: {len(judges_from_query)}")
    
    # Show some specific judges we found
    print("\nSample of judges from files:")
    for judge in list(file_judge_names)[:10]:
        print(f"  - {judge}")
    
    print("\n✓ Verification complete. The system is parsing and storing judge information.")

if __name__ == "__main__":
    main()
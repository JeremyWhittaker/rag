#!/usr/bin/env python3
"""Comprehensive verification of ADRE ingestion metadata capture."""

import requests
import json
import re
from pathlib import Path
from typing import Dict, List, Set, Optional
from collections import defaultdict, Counter
import docx
import random

BASE_URL = "http://localhost:8000"

class IngestionVerifier:
    """Verify comprehensive metadata extraction during ingestion."""
    
    def __init__(self):
        self.metadata_categories = {
            'case_info': [
                'case_number', 'oah_docket', 'adre_case_no', 'hearing_date', 'decision_date'
            ],
            'parties': [
                'petitioner_name', 'respondent_name', 'respondent_type',
                'homeowner_name', 'hoa_name', 'management_company'
            ],
            'legal_representation': [
                'petitioner_attorney', 'respondent_attorney', 'law_firm',
                'assistant_attorney_general', 'pro_se_representation'
            ],
            'judicial_info': [
                'judge_name', 'administrative_law_judge', 'hearing_officer'
            ],
            'violations_legal': [
                'ars_violations', 'arizona_revised_statutes', 'aac_violations',
                'arizona_administrative_code'
            ],
            'violations_hoa': [
                'ccr_violations', 'bylaws_violations', 'declaration_violations',
                'governing_documents_violations', 'architectural_violations'
            ],
            'case_details': [
                'violation_type', 'violation_description', 'penalties',
                'monetary_fines', 'compliance_orders', 'cease_desist'
            ],
            'outcomes': [
                'decision_type', 'ruling', 'findings_of_fact', 'conclusions_of_law',
                'orders', 'remedies_granted'
            ]
        }
    
    def verify_current_ingestion_metadata(self):
        """Check what metadata is currently captured in the ingested documents."""
        print("=" * 80)
        print("CURRENT INGESTION METADATA VERIFICATION")
        print("=" * 80)
        
        # Get project statistics
        response = requests.get(f"{BASE_URL}/statistics/adre_decisions_complete")
        
        if response.status_code == 200:
            stats = response.json()
            print(f"\nProject: adre_decisions_complete")
            print(f"Total documents: {stats['total_documents']}")
            
            print(f"\nCurrent metadata fields tracked:")
            for key, value in stats.items():
                if key != 'total_documents':
                    print(f"  {key}: {value if isinstance(value, (int, str)) else type(value).__name__}")
            
            return stats
        else:
            print(f"Error getting statistics: {response.status_code}")
            return None
    
    def test_metadata_queries(self):
        """Test queries for each metadata category to verify extraction."""
        print(f"\n{'=' * 80}")
        print("METADATA CATEGORY VERIFICATION")
        print("=" * 80)
        
        found_metadata = defaultdict(list)
        
        # Test queries for each category
        test_queries = {
            'case_info': [
                "List all OAH docket numbers found in these decisions.",
                "What are the case numbers and hearing dates in these ADRE cases?",
                "Find all ADRE case numbers mentioned in these documents."
            ],
            'parties': [
                "List all petitioner names (homeowners) in these cases.",
                "What homeowners associations (HOAs) are mentioned as respondents?",
                "Find all management companies mentioned in these decisions."
            ],
            'legal_representation': [
                "List all attorneys representing petitioners in these cases.",
                "What attorneys represented respondents (HOAs) in these decisions?",
                "Find all law firms mentioned in these ADRE cases."
            ],
            'judicial_info': [
                "List all Administrative Law Judges who decided these cases.",
                "What judge names appear in these ADRE decisions?",
                "Find all hearing officers mentioned in these documents."
            ],
            'violations_legal': [
                "List all Arizona Revised Statutes (A.R.S.) cited in these cases.",
                "What Arizona Administrative Code (A.A.C.) violations are mentioned?",
                "Find all statutory violations cited in these decisions."
            ],
            'violations_hoa': [
                "List all CC&R violations mentioned in these cases.",
                "What bylaws violations are cited in these decisions?",
                "Find all governing document violations mentioned."
            ],
            'case_details': [
                "What types of violations led to these ADRE cases?",
                "List all monetary fines imposed in these decisions.",
                "What penalties were ordered in these cases?"
            ],
            'outcomes': [
                "What were the outcomes and rulings in these cases?",
                "List all orders issued in these ADRE decisions.",
                "What remedies were granted to petitioners?"
            ]
        }
        
        for category, queries in test_queries.items():
            print(f"\n{'-' * 60}")
            print(f"TESTING: {category.upper().replace('_', ' ')}")
            print(f"{'-' * 60}")
            
            for query in queries:
                print(f"\nQuery: {query}")
                
                query_data = {
                    "question": query,
                    "projects": ["adre_decisions_complete"],
                    "enable_hierarchy": True,
                    "include_citations": False,
                    "verbose": False
                }
                
                try:
                    response = requests.post(f"{BASE_URL}/legal-query", json=query_data, timeout=30)
                    
                    if response.status_code == 200:
                        result = response.json()
                        answer = result['answer']
                        sources = len(result['sources'])
                        
                        print(f"Sources: {sources}")
                        print(f"Response preview: {answer[:200]}...")
                        
                        # Extract specific information based on category
                        extracted = self._extract_metadata_from_response(category, answer)
                        if extracted:
                            found_metadata[category].extend(extracted)
                            print(f"Extracted {category}: {extracted[:3]}{'...' if len(extracted) > 3 else ''}")
                    else:
                        print(f"Error: {response.status_code}")
                        
                except Exception as e:
                    print(f"Request error: {str(e)[:50]}...")
        
        return found_metadata
    
    def _extract_metadata_from_response(self, category: str, response: str) -> List[str]:
        """Extract specific metadata items from query responses."""
        extracted = []
        
        if category == 'case_info':
            # Extract case numbers and docket numbers
            case_patterns = [
                r'(\d{2}[A-Z]-[A-Z]\d+(?:-REL)?(?:-RHG)?)',
                r'OAH[- ](?:Docket[- ])?(?:No\.?\s*)?([A-Z0-9-]+)',
                r'ADRE[- ](?:Case[- ])?(?:No\.?\s*)?([A-Z0-9-]+)'
            ]
            for pattern in case_patterns:
                matches = re.findall(pattern, response, re.IGNORECASE)
                extracted.extend(matches)
        
        elif category == 'parties':
            # Extract party names
            party_patterns = [
                r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:Homeowners?\s+Association|HOA)',
                r'(?:Petitioner|Homeowner):\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
                r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:Property\s+)?Management'
            ]
            for pattern in party_patterns:
                matches = re.findall(pattern, response)
                extracted.extend(matches)
        
        elif category == 'legal_representation':
            # Extract attorney names
            attorney_patterns = [
                r'([A-Z][a-z]+(?:\s+[A-Z]\.?\s*)?[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),?\s+Esq\.?',
                r'Attorney:?\s*([A-Z][a-z]+(?:\s+[A-Z]\.?\s*)?[A-Z][a-z]+)',
                r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+Law\s+(?:Firm|Office|Group)'
            ]
            for pattern in attorney_patterns:
                matches = re.findall(pattern, response)
                extracted.extend(matches)
        
        elif category == 'judicial_info':
            # Extract judge names
            judge_patterns = [
                r'(?:Judge|ALJ|Administrative Law Judge):\s*([A-Z][a-z]+(?:\s+[A-Z]\.?\s*)?[A-Z][a-z]+)',
                r'([A-Z][a-z]+(?:\s+[A-Z]\.?\s*)?[A-Z][a-z]+),?\s+Administrative Law Judge'
            ]
            for pattern in judge_patterns:
                matches = re.findall(pattern, response)
                extracted.extend(matches)
        
        elif category == 'violations_legal':
            # Extract statutory citations
            statute_patterns = [
                r'A\.R\.S\.?\s*§?\s*([0-9-]+(?:\.[0-9]+)*)',
                r'A\.A\.C\.?\s*R?([0-9-]+(?:\.[0-9]+)*)',
                r'Arizona Revised Statute(?:s)?\s*([0-9-]+(?:\.[0-9]+)*)'
            ]
            for pattern in statute_patterns:
                matches = re.findall(pattern, response)
                extracted.extend([f"A.R.S. {m}" if 'A.R.S' in pattern else f"A.A.C. {m}" for m in matches])
        
        elif category == 'violations_hoa':
            # Extract HOA document violations
            hoa_patterns = [
                r'CC&R[s]?\s+(?:violation|breach)',
                r'(?:Bylaws?|By-laws?)\s+(?:violation|breach)',
                r'Declaration\s+(?:violation|breach)',
                r'Governing\s+(?:Documents?|Docs?)\s+(?:violation|breach)'
            ]
            for pattern in hoa_patterns:
                if re.search(pattern, response, re.IGNORECASE):
                    extracted.append(pattern.split('\\')[0])  # Get the document type
        
        # Remove duplicates and return
        return list(set(extracted))
    
    def sample_document_analysis(self):
        """Analyze a sample of actual documents to see what metadata should be available."""
        print(f"\n{'=' * 80}")
        print("SAMPLE DOCUMENT ANALYSIS")
        print("=" * 80)
        
        case_dir = Path("../azoah/adre_decisions_downloads")
        sample_files = random.sample(list(case_dir.glob("*.docx")), min(5, len(list(case_dir.glob("*.docx")))))
        
        sample_metadata = defaultdict(set)
        
        for file_path in sample_files:
            print(f"\nAnalyzing: {file_path.name}")
            
            try:
                doc = docx.Document(str(file_path))
                text = "\n".join([para.text for para in doc.paragraphs])
                
                # Extract all types of metadata from this document
                metadata = self._comprehensive_metadata_extraction(text, file_path.name)
                
                for category, items in metadata.items():
                    sample_metadata[category].update(items)
                
                # Print sample findings
                print(f"  Case number: {metadata.get('case_info', ['Not found'])[0] if metadata.get('case_info') else 'Not found'}")
                print(f"  Judge: {metadata.get('judicial_info', ['Not found'])[0] if metadata.get('judicial_info') else 'Not found'}")
                print(f"  Violations: {len(metadata.get('violations_legal', []))} legal, {len(metadata.get('violations_hoa', []))} HOA")
                
            except Exception as e:
                print(f"  Error: {str(e)[:50]}...")
        
        return sample_metadata
    
    def _comprehensive_metadata_extraction(self, text: str, filename: str) -> Dict[str, List[str]]:
        """Extract all possible metadata from a document."""
        metadata = defaultdict(list)
        
        # Case information
        case_patterns = {
            'oah_docket': r'OAH\s+(?:Docket\s+)?(?:No\.?\s*)?([A-Z0-9\-]+)',
            'adre_case': r'ADRE\s+(?:Case\s+)?(?:No\.?\s*)?([A-Z0-9\-]+)',
            'case_number': r'(\d{2}[A-Z]\-[A-Z]\d+(?:\-REL)?(?:\-RHG)?)'
        }
        
        for info_type, pattern in case_patterns.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            metadata['case_info'].extend([f"{info_type}: {m}" for m in matches])
        
        # Parties
        party_patterns = {
            'petitioner': r'(?:Petitioner|Complainant):\s*([A-Z][a-zA-Z\s,\.]+?)(?:\n|,)',
            'respondent': r'(?:Respondent):\s*([A-Z][a-zA-Z\s,\.]+?)(?:\n|,)',
            'hoa': r'([A-Z][a-zA-Z\s]+)\s+(?:Homeowners?\s+Association|HOA)'
        }
        
        for party_type, pattern in party_patterns.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            metadata['parties'].extend([f"{party_type}: {m.strip()}" for m in matches if len(m.strip()) > 3])
        
        # Legal representation
        attorney_patterns = {
            'esq_attorney': r'([A-Z][a-z]+(?:\s+[A-Z]\.?\s*)?[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),?\s+Esq\.?',
            'represented_by': r'represented\s+by\s+([A-Z][a-z]+(?:\s+[A-Z]\.?\s*)?[A-Z][a-z]+)',
            'aag': r'([A-Z][a-z]+(?:\s+[A-Z]\.?\s*)?[A-Z][a-z]+)\s*,?\s*Assistant\s+Attorney\s+General'
        }
        
        for attorney_type, pattern in attorney_patterns.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            metadata['legal_representation'].extend([f"{attorney_type}: {m}" for m in matches])
        
        # Judicial information
        judge_patterns = {
            'alj': r'ADMINISTRATIVE\s+LAW\s+JUDGE:\s*([A-Z][a-z]+(?:\s+[A-Z]\.?\s*)?(?:\s+[A-Z][a-z]+)+)',
            'judge': r'(?:Judge|ALJ):\s*([A-Z][a-z]+(?:\s+[A-Z]\.?\s*)?(?:\s+[A-Z][a-z]+)+)'
        }
        
        for judge_type, pattern in judge_patterns.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            metadata['judicial_info'].extend([f"{judge_type}: {m}" for m in matches])
        
        # Legal violations
        statute_patterns = {
            'ars': r'A\.R\.S\.?\s*§?\s*([0-9\-]+(?:\.[0-9]+)*)',
            'aac': r'A\.A\.C\.?\s*R?([0-9\-]+(?:\.[0-9]+)*)'
        }
        
        for statute_type, pattern in statute_patterns.items():
            matches = re.findall(pattern, text)
            metadata['violations_legal'].extend([f"{statute_type.upper()}: {m}" for m in matches])
        
        # HOA violations
        hoa_violation_patterns = {
            'ccr': r'CC&R[s]?(?:\s+(?:Section|§)\s*([0-9\.]+))?',
            'bylaws': r'(?:Bylaws?|By-laws?)(?:\s+(?:Section|§)\s*([0-9\.]+))?',
            'declaration': r'Declaration(?:\s+(?:Section|§)\s*([0-9\.]+))?',
            'architectural': r'Architectural\s+(?:Guidelines?|Standards?|Requirements?)'
        }
        
        for hoa_type, pattern in hoa_violation_patterns.items():
            if re.search(pattern, text, re.IGNORECASE):
                matches = re.findall(pattern, text, re.IGNORECASE)
                if matches and matches[0]:
                    metadata['violations_hoa'].append(f"{hoa_type}: Section {matches[0]}")
                else:
                    metadata['violations_hoa'].append(f"{hoa_type}: mentioned")
        
        return metadata
    
    def generate_ingestion_improvement_recommendations(self, found_metadata: Dict, sample_metadata: Dict):
        """Generate recommendations for improving ingestion metadata capture."""
        print(f"\n{'=' * 80}")
        print("INGESTION IMPROVEMENT RECOMMENDATIONS")
        print("=" * 80)
        
        recommendations = []
        
        # Check each category
        for category in self.metadata_categories:
            rag_found = len(found_metadata.get(category, []))
            sample_found = len(sample_metadata.get(category, []))
            
            print(f"\n{category.upper().replace('_', ' ')}:")
            print(f"  RAG system found: {rag_found} items")
            print(f"  Sample analysis found: {sample_found} items")
            
            if sample_found > rag_found * 1.5:  # If sample found significantly more
                recommendations.append({
                    'category': category,
                    'issue': 'Potential under-extraction during ingestion',
                    'recommendation': f'Enhance {category} extraction patterns in legal processor',
                    'priority': 'HIGH' if category in ['parties', 'violations_legal', 'judicial_info'] else 'MEDIUM'
                })
            elif rag_found == 0:
                recommendations.append({
                    'category': category,
                    'issue': 'No items found via RAG queries',
                    'recommendation': f'Add {category} extraction to ingestion pipeline',
                    'priority': 'HIGH'
                })
        
        if recommendations:
            print(f"\n🔧 IMPROVEMENT RECOMMENDATIONS:")
            for i, rec in enumerate(recommendations, 1):
                print(f"\n{i}. {rec['category'].upper()} - {rec['priority']} PRIORITY")
                print(f"   Issue: {rec['issue']}")
                print(f"   Recommendation: {rec['recommendation']}")
        else:
            print(f"\n✅ INGESTION QUALITY: Good - metadata extraction appears comprehensive")
        
        return recommendations

def main():
    """Main verification process."""
    print("COMPREHENSIVE ADRE INGESTION VERIFICATION")
    print("=" * 80)
    
    verifier = IngestionVerifier()
    
    # Step 1: Check current ingestion metadata
    print("\nStep 1: Checking current ingestion metadata...")
    current_stats = verifier.verify_current_ingestion_metadata()
    
    # Step 2: Test metadata extraction via queries
    print("\nStep 2: Testing metadata extraction via RAG queries...")
    found_metadata = verifier.test_metadata_queries()
    
    # Step 3: Sample document analysis
    print("\nStep 3: Analyzing sample documents for expected metadata...")
    sample_metadata = verifier.sample_document_analysis()
    
    # Step 4: Generate recommendations
    print("\nStep 4: Generating improvement recommendations...")
    recommendations = verifier.generate_ingestion_improvement_recommendations(found_metadata, sample_metadata)
    
    # Save results
    results = {
        'current_statistics': current_stats,
        'metadata_found_via_rag': {k: list(set(v)) for k, v in found_metadata.items()},
        'metadata_found_in_samples': {k: list(v) for k, v in sample_metadata.items()},
        'improvement_recommendations': recommendations,
        'summary': {
            'total_metadata_categories': len(verifier.metadata_categories),
            'categories_with_rag_findings': len([k for k, v in found_metadata.items() if v]),
            'categories_with_sample_findings': len([k for k, v in sample_metadata.items() if v]),
            'high_priority_recommendations': len([r for r in recommendations if r['priority'] == 'HIGH'])
        }
    }
    
    with open('ingestion_verification_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    # Final summary
    print(f"\n{'=' * 80}")
    print("FINAL INGESTION VERIFICATION SUMMARY")
    print("=" * 80)
    
    print(f"\nMetadata Categories Tested: {len(verifier.metadata_categories)}")
    print(f"Categories with RAG findings: {len([k for k, v in found_metadata.items() if v])}")
    print(f"Categories with sample findings: {len([k for k, v in sample_metadata.items() if v])}")
    print(f"High-priority recommendations: {len([r for r in recommendations if r['priority'] == 'HIGH'])}")
    
    if not recommendations:
        print(f"\n✅ OVERALL ASSESSMENT: Ingestion metadata capture appears comprehensive")
    else:
        print(f"\n⚠️  OVERALL ASSESSMENT: {len(recommendations)} areas identified for improvement")
    
    print(f"\n✓ Complete verification results saved to ingestion_verification_results.json")

if __name__ == "__main__":
    main()
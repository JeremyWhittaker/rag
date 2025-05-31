#!/usr/bin/env python3
"""Extract and verify attorney information from ADRE decisions."""

import re
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from collections import Counter, defaultdict
import json
import requests
from dataclasses import dataclass, field
import docx
import random

@dataclass
class AttorneyInfo:
    """Information about an attorney."""
    name: str
    role: str  # 'petitioner', 'respondent', 'both'
    cases: Set[str] = field(default_factory=set)
    bar_number: Optional[str] = None
    firm: Optional[str] = None

class AttorneyExtractor:
    """Extract attorney information from ADRE/OAH documents."""
    
    def __init__(self):
        # Attorney patterns
        self.attorney_patterns = {
            'petitioner': [
                # Standard formats
                r'(?:for|representing)\s+(?:the\s+)?(?:Petitioner|State|Department|ADRE)(?:\s*:)?(?:\s*\n)?\s*([A-Z][a-z]+(?:\s+[A-Z]\.?)?(?:\s+[A-Z][a-z]+)+)',
                r'Petitioner[\'"]?s?\s+(?:Counsel|Attorney)(?:\s*:)?\s*([A-Z][a-z]+(?:\s+[A-Z]\.?)?(?:\s+[A-Z][a-z]+)+)',
                r'([A-Z][a-z]+(?:\s+[A-Z]\.?)?(?:\s+[A-Z][a-z]+)+)\s*(?:\n\s*)?(?:for|representing)\s+(?:the\s+)?(?:Petitioner|State)',
                # Assistant Attorney General patterns
                r'([A-Z][a-z]+(?:\s+[A-Z]\.?)?(?:\s+[A-Z][a-z]+)+)\s*\n\s*Assistant\s+Attorney\s+General',
                r'Assistant\s+Attorney\s+General\s*\n\s*([A-Z][a-z]+(?:\s+[A-Z]\.?)?(?:\s+[A-Z][a-z]+)+)',
                # By: patterns
                r'By:\s*([A-Z][a-z]+(?:\s+[A-Z]\.?)?(?:\s+[A-Z][a-z]+)+)\s*\n\s*(?:Assistant\s+)?Attorney\s+General',
            ],
            'respondent': [
                # Standard formats
                r'(?:for|representing)\s+(?:the\s+)?Respondent(?:\s*:)?(?:\s*\n)?\s*([A-Z][a-z]+(?:\s+[A-Z]\.?)?(?:\s+[A-Z][a-z]+)+)',
                r'Respondent[\'"]?s?\s+(?:Counsel|Attorney)(?:\s*:)?\s*([A-Z][a-z]+(?:\s+[A-Z]\.?)?(?:\s+[A-Z][a-z]+)+)',
                r'([A-Z][a-z]+(?:\s+[A-Z]\.?)?(?:\s+[A-Z][a-z]+)+)\s*(?:\n\s*)?(?:for|representing)\s+(?:the\s+)?Respondent',
                # Attorney for [Name], Respondent
                r'([A-Z][a-z]+(?:\s+[A-Z]\.?)?(?:\s+[A-Z][a-z]+)+)\s*\n\s*Attorney\s+for\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*,?\s+Respondent',
                # By: patterns for respondent
                r'Respondent\s+represented\s+by:\s*([A-Z][a-z]+(?:\s+[A-Z]\.?)?(?:\s+[A-Z][a-z]+)+)',
            ],
            'appearance': [
                # APPEARANCES section
                r'APPEARANCES?\s*:?\s*\n(?:.*\n)*?For\s+(?:the\s+)?Petitioner:\s*([A-Z][a-z]+(?:\s+[A-Z]\.?)?(?:\s+[A-Z][a-z]+)+)',
                r'APPEARANCES?\s*:?\s*\n(?:.*\n)*?For\s+(?:the\s+)?Respondent:\s*([A-Z][a-z]+(?:\s+[A-Z]\.?)?(?:\s+[A-Z][a-z]+)+)',
            ]
        }
        
        # Bar number patterns
        self.bar_patterns = [
            r'State\s+Bar\s+(?:No\.?|#)\s*(\d{6,})',
            r'Bar\s+(?:No\.?|#)\s*(\d{6,})',
            r'\((?:State\s+)?Bar\s+(?:No\.?|#)\s*(\d{6,})\)',
        ]
        
        # Law firm patterns
        self.firm_patterns = [
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+&\s+[A-Z][a-z]+)*\s+(?:LLP|LLC|PC|PLC|PLLC|Law\s+(?:Firm|Office|Group)))',
            r'(?:Law\s+(?:Office|Firm)s?\s+of\s+)([A-Z][a-z]+(?:\s+[A-Z]\.?)?(?:\s+[A-Z][a-z]+)+)',
        ]
        
        # Invalid attorney names to filter out
        self.invalid_names = {
            'Order', 'Decision', 'Copy', 'State', 'Arizona', 'Department', 
            'Real Estate', 'Commission', 'Commissioner', 'Administrative',
            'Law Judge', 'Hearing Officer', 'Notice', 'Findings', 'Fact',
            'Transmitted', 'Page', 'Case', 'Docket', 'Matter', 'License'
        }
    
    def extract_from_text(self, text: str, case_number: str) -> Dict[str, List[AttorneyInfo]]:
        """Extract attorney information from document text."""
        attorneys = {
            'petitioner': [],
            'respondent': []
        }
        
        # Clean text for better matching
        text_clean = re.sub(r'\s+', ' ', text)
        
        # Extract petitioner attorneys
        for pattern in self.attorney_patterns['petitioner']:
            matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                name = self._clean_attorney_name(match.group(1))
                if self._is_valid_attorney_name(name):
                    attorney = self._create_attorney_info(name, 'petitioner', case_number, text)
                    attorneys['petitioner'].append(attorney)
        
        # Extract respondent attorneys
        for pattern in self.attorney_patterns['respondent']:
            matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                name = self._clean_attorney_name(match.group(1))
                if self._is_valid_attorney_name(name):
                    attorney = self._create_attorney_info(name, 'respondent', case_number, text)
                    attorneys['respondent'].append(attorney)
        
        # Check APPEARANCES section
        appearances_match = re.search(r'APPEARANCES?\s*:?\s*\n((?:.*\n){1,20})', text, re.IGNORECASE)
        if appearances_match:
            appearance_text = appearances_match.group(1)
            
            # Extract from appearances
            pet_match = re.search(r'For\s+(?:the\s+)?(?:Petitioner|State|Department):\s*([A-Z][a-z]+(?:\s+[A-Z]\.?)?(?:\s+[A-Z][a-z]+)+)', 
                                appearance_text, re.IGNORECASE)
            if pet_match:
                name = self._clean_attorney_name(pet_match.group(1))
                if self._is_valid_attorney_name(name):
                    attorney = self._create_attorney_info(name, 'petitioner', case_number, text)
                    attorneys['petitioner'].append(attorney)
            
            resp_match = re.search(r'For\s+(?:the\s+)?Respondent:\s*([A-Z][a-z]+(?:\s+[A-Z]\.?)?(?:\s+[A-Z][a-z]+)+)', 
                                 appearance_text, re.IGNORECASE)
            if resp_match:
                name = self._clean_attorney_name(resp_match.group(1))
                if self._is_valid_attorney_name(name):
                    attorney = self._create_attorney_info(name, 'respondent', case_number, text)
                    attorneys['respondent'].append(attorney)
        
        # Deduplicate
        attorneys['petitioner'] = self._deduplicate_attorneys(attorneys['petitioner'])
        attorneys['respondent'] = self._deduplicate_attorneys(attorneys['respondent'])
        
        return attorneys
    
    def _create_attorney_info(self, name: str, role: str, case_number: str, text: str) -> AttorneyInfo:
        """Create AttorneyInfo object with additional details."""
        attorney = AttorneyInfo(name=name, role=role)
        attorney.cases.add(case_number)
        
        # Try to find bar number near attorney name
        name_index = text.find(name)
        if name_index != -1:
            context = text[max(0, name_index-100):name_index+200]
            for pattern in self.bar_patterns:
                match = re.search(pattern, context)
                if match:
                    attorney.bar_number = match.group(1)
                    break
            
            # Try to find firm name
            for pattern in self.firm_patterns:
                match = re.search(pattern, context)
                if match:
                    attorney.firm = match.group(1).strip()
                    break
        
        return attorney
    
    def _clean_attorney_name(self, name: str) -> str:
        """Clean and normalize attorney name."""
        # Remove extra whitespace
        name = ' '.join(name.split())
        # Remove trailing punctuation
        name = name.rstrip('.,;:')
        # Proper case
        return name.title()
    
    def _is_valid_attorney_name(self, name: str) -> bool:
        """Validate if extracted text is likely an attorney name."""
        if not name or len(name) < 5:
            return False
        
        # Must have at least first and last name
        parts = name.split()
        if len(parts) < 2:
            return False
        
        # Check against invalid terms
        for term in self.invalid_names:
            if term.lower() in name.lower():
                return False
        
        # Should start with capital letter
        if not name[0].isupper():
            return False
        
        # Should not be all caps (likely a header)
        if name.isupper() and len(name) > 10:
            return False
        
        return True
    
    def _deduplicate_attorneys(self, attorneys: List[AttorneyInfo]) -> List[AttorneyInfo]:
        """Remove duplicate attorneys, keeping the one with most info."""
        unique = {}
        for attorney in attorneys:
            if attorney.name not in unique:
                unique[attorney.name] = attorney
            else:
                # Merge information
                unique[attorney.name].cases.update(attorney.cases)
                if attorney.bar_number and not unique[attorney.name].bar_number:
                    unique[attorney.name].bar_number = attorney.bar_number
                if attorney.firm and not unique[attorney.name].firm:
                    unique[attorney.name].firm = attorney.firm
        
        return list(unique.values())

def extract_attorneys_from_files(sample_size: int = 50) -> Dict[str, List[AttorneyInfo]]:
    """Extract attorneys from a sample of ADRE decision files."""
    print("\n" + "="*80)
    print("EXTRACTING ATTORNEYS FROM ADRE DECISION FILES")
    print("="*80)
    
    extractor = AttorneyExtractor()
    case_dir = Path("../azoah/adre_decisions_downloads")
    
    all_attorneys = {
        'petitioner': defaultdict(lambda: AttorneyInfo("", "petitioner")),
        'respondent': defaultdict(lambda: AttorneyInfo("", "respondent"))
    }
    
    # Get all files
    all_files = list(case_dir.glob("*.docx")) + list(case_dir.glob("*.doc"))
    print(f"\nTotal files available: {len(all_files)}")
    
    # Sample files
    sample_files = random.sample(all_files, min(sample_size, len(all_files)))
    print(f"Sampling {len(sample_files)} files for attorney extraction...")
    
    files_processed = 0
    attorneys_found = 0
    
    for file_path in sample_files:
        try:
            # Extract case number from filename
            case_number = file_path.stem
            
            # Read document
            try:
                doc = docx.Document(str(file_path))
                text = "\n".join([para.text for para in doc.paragraphs])
            except:
                continue
            
            # Extract attorneys
            attorneys = extractor.extract_from_text(text, case_number)
            
            # Aggregate results
            for role in ['petitioner', 'respondent']:
                for attorney in attorneys[role]:
                    key = attorney.name
                    if key in all_attorneys[role]:
                        all_attorneys[role][key].cases.update(attorney.cases)
                        if attorney.bar_number:
                            all_attorneys[role][key].bar_number = attorney.bar_number
                        if attorney.firm:
                            all_attorneys[role][key].firm = attorney.firm
                    else:
                        all_attorneys[role][key] = attorney
                        attorneys_found += 1
            
            files_processed += 1
            
            # Progress indicator
            if files_processed % 10 == 0:
                print(f"  Processed {files_processed} files, found {attorneys_found} unique attorneys...")
                
        except Exception as e:
            print(f"  Error processing {file_path.name}: {e}")
    
    print(f"\nProcessed {files_processed} files successfully")
    
    # Convert defaultdict to regular dict with lists
    return {
        'petitioner': list(all_attorneys['petitioner'].values()),
        'respondent': list(all_attorneys['respondent'].values())
    }

def query_system_for_attorneys():
    """Query the RAG system for attorney information."""
    print("\n" + "="*80)
    print("QUERYING SYSTEM FOR ATTORNEY INFORMATION")
    print("="*80)
    
    BASE_URL = "http://localhost:8000"
    
    queries = [
        {
            "question": "List all attorneys who represented petitioners (the State/Department) in ADRE cases. Include their names and any bar numbers mentioned.",
            "description": "Petitioner Attorneys"
        },
        {
            "question": "List all attorneys who represented respondents in ADRE cases. Include their names, firms, and any bar numbers mentioned.",
            "description": "Respondent Attorneys"
        },
        {
            "question": "Find all mentions of Assistant Attorney General names in ADRE cases. List each attorney and the cases they handled.",
            "description": "Assistant Attorneys General"
        }
    ]
    
    system_attorneys = {
        'petitioner': set(),
        'respondent': set()
    }
    
    for query_info in queries:
        print(f"\nQuerying: {query_info['description']}")
        
        query_data = {
            "question": query_info["question"],
            "projects": ["adre_decisions_complete"],
            "enable_hierarchy": True,
            "include_citations": False,
            "verbose": True
        }
        
        response = requests.post(f"{BASE_URL}/legal-query", json=query_data)
        
        if response.status_code == 200:
            result = response.json()
            print(f"Sources used: {len(result['sources'])}")
            
            # Extract attorney names from response
            answer = result['answer']
            
            # Common attorney name patterns in responses
            name_patterns = [
                r'([A-Z][a-z]+(?:\s+[A-Z]\.?)?(?:\s+[A-Z][a-z]+)+)(?:\s*\(Bar\s*(?:No\.?|#)\s*\d+\))?',
            ]
            
            for pattern in name_patterns:
                matches = re.findall(pattern, answer)
                for match in matches:
                    name = match.strip()
                    if len(name) > 5 and name[0].isupper():
                        if 'petitioner' in query_info['description'].lower():
                            system_attorneys['petitioner'].add(name)
                        else:
                            system_attorneys['respondent'].add(name)
            
            print(f"Found {len(matches)} potential attorney names in response")
    
    return system_attorneys

def generate_comprehensive_report(file_attorneys: Dict[str, List[AttorneyInfo]], 
                               system_attorneys: Dict[str, set]):
    """Generate comprehensive attorney report."""
    print("\n" + "="*80)
    print("COMPREHENSIVE ATTORNEY REPORT")
    print("="*80)
    
    # Petitioner Attorneys (State/Department)
    print("\n### PETITIONER ATTORNEYS (Representing State/Department/ADRE) ###")
    print("-" * 60)
    
    pet_attorneys = sorted(file_attorneys['petitioner'], 
                          key=lambda x: len(x.cases), reverse=True)
    
    print(f"\nTotal unique petitioner attorneys found: {len(pet_attorneys)}")
    print("\nTop Petitioner Attorneys by Case Count:")
    
    for i, attorney in enumerate(pet_attorneys[:20], 1):
        print(f"\n{i}. {attorney.name}")
        print(f"   Cases handled: {len(attorney.cases)}")
        if attorney.bar_number:
            print(f"   Bar Number: {attorney.bar_number}")
        if attorney.firm:
            print(f"   Firm/Office: {attorney.firm}")
        print(f"   Sample cases: {', '.join(list(attorney.cases)[:3])}")
    
    # Respondent Attorneys
    print("\n\n### RESPONDENT ATTORNEYS ###")
    print("-" * 60)
    
    resp_attorneys = sorted(file_attorneys['respondent'], 
                           key=lambda x: len(x.cases), reverse=True)
    
    print(f"\nTotal unique respondent attorneys found: {len(resp_attorneys)}")
    print("\nTop Respondent Attorneys by Case Count:")
    
    for i, attorney in enumerate(resp_attorneys[:20], 1):
        print(f"\n{i}. {attorney.name}")
        print(f"   Cases handled: {len(attorney.cases)}")
        if attorney.bar_number:
            print(f"   Bar Number: {attorney.bar_number}")
        if attorney.firm:
            print(f"   Firm/Office: {attorney.firm}")
        print(f"   Sample cases: {', '.join(list(attorney.cases)[:3])}")
    
    # Summary Statistics
    print("\n\n### SUMMARY STATISTICS ###")
    print("-" * 60)
    
    total_pet_cases = sum(len(att.cases) for att in pet_attorneys)
    total_resp_cases = sum(len(att.cases) for att in resp_attorneys)
    
    print(f"\nPetitioner Attorneys:")
    print(f"  - Total unique attorneys: {len(pet_attorneys)}")
    print(f"  - Total case representations: {total_pet_cases}")
    print(f"  - Average cases per attorney: {total_pet_cases/len(pet_attorneys):.1f}")
    print(f"  - Attorneys with bar numbers: {sum(1 for a in pet_attorneys if a.bar_number)}")
    
    print(f"\nRespondent Attorneys:")
    print(f"  - Total unique attorneys: {len(resp_attorneys)}")
    print(f"  - Total case representations: {total_resp_cases}")
    print(f"  - Average cases per attorney: {total_resp_cases/len(resp_attorneys):.1f}")
    print(f"  - Attorneys with bar numbers: {sum(1 for a in resp_attorneys if a.bar_number)}")
    
    # Most active firms
    print("\n\n### MOST ACTIVE LAW FIRMS ###")
    print("-" * 60)
    
    firm_cases = defaultdict(int)
    firm_attorneys = defaultdict(set)
    
    for attorney in pet_attorneys + resp_attorneys:
        if attorney.firm:
            firm_cases[attorney.firm] += len(attorney.cases)
            firm_attorneys[attorney.firm].add(attorney.name)
    
    sorted_firms = sorted(firm_cases.items(), key=lambda x: x[1], reverse=True)
    
    print("\nTop Law Firms by Case Count:")
    for firm, case_count in sorted_firms[:10]:
        attorney_count = len(firm_attorneys[firm])
        print(f"\n{firm}")
        print(f"  - Total cases: {case_count}")
        print(f"  - Attorneys: {attorney_count}")
        print(f"  - Attorney names: {', '.join(list(firm_attorneys[firm])[:3])}")

def main():
    """Main execution function."""
    print("ADRE ATTORNEY EXTRACTION AND VERIFICATION")
    print("=" * 80)
    
    # Extract attorneys from files
    print("\nStep 1: Extracting attorneys from ADRE decision files...")
    file_attorneys = extract_attorneys_from_files(sample_size=100)
    
    # Query system for attorneys
    print("\nStep 2: Querying RAG system for attorney information...")
    system_attorneys = query_system_for_attorneys()
    
    # Generate comprehensive report
    print("\nStep 3: Generating comprehensive attorney report...")
    generate_comprehensive_report(file_attorneys, system_attorneys)
    
    # Save results to JSON
    print("\n\nSaving results to attorneys_extracted.json...")
    
    # Convert to serializable format
    output_data = {
        'petitioner_attorneys': [
            {
                'name': att.name,
                'cases': list(att.cases),
                'bar_number': att.bar_number,
                'firm': att.firm,
                'case_count': len(att.cases)
            }
            for att in file_attorneys['petitioner']
        ],
        'respondent_attorneys': [
            {
                'name': att.name,
                'cases': list(att.cases),
                'bar_number': att.bar_number,
                'firm': att.firm,
                'case_count': len(att.cases)
            }
            for att in file_attorneys['respondent']
        ]
    }
    
    with open('attorneys_extracted.json', 'w') as f:
        json.dump(output_data, f, indent=2)
    
    print("\n✓ Attorney extraction and verification complete!")
    print("Results saved to attorneys_extracted.json")

if __name__ == "__main__":
    main()
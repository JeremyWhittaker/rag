#!/usr/bin/env python3
"""Final optimized attorney extraction for OAH homeowner association decisions."""

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
    role: str  # 'petitioner', 'respondent'
    cases: Set[str] = field(default_factory=set)
    bar_number: Optional[str] = None
    firm: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    esq_title: bool = False

class OAHAttorneyExtractor:
    """Specialized extractor for OAH homeowner association decision documents."""
    
    def __init__(self):
        # Patterns specific to OAH format
        self.attorney_patterns = {
            'appearances_section': [
                # "represented by [Name]" in APPEARANCES
                r'(?:represented|appeared)\s+(?:by|on behalf of)\s+([A-Z][a-z]+(?:\s+[A-Z]\.?\s*)?[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
                # "[Name], Esq." patterns
                r'([A-Z][a-z]+(?:\s+[A-Z]\.?\s*)?[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),?\s+Esq\.?',
                # "[Name] and [Name], Esq." patterns
                r'([A-Z][a-z]+(?:\s+[A-Z]\.?\s*)?[A-Z][a-z]+)\s+and\s+([A-Z][a-z]+(?:\s+[A-Z]\.?\s*)?[A-Z][a-z]+),?\s+Esq\.?',
            ],
            'transmission_section': [
                # Full attorney blocks in transmission section
                r'([A-Z][a-z]+(?:\s+[A-Z]\.?\s*)?[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),?\s+Esq\.?,?\s*\n?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+(?:Law\s+)?(?:Office|Firm|Group|LLC|PLC|LLP))?[^,\n]*),?\s*\n?\s*([^,\n]+,\s*[A-Z]{2}\s+\d{5})',
                # Email patterns for attorneys
                r'([A-Z][a-z]+(?:\s+[A-Z]\.?\s*)?[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),?\s+Esq\.?[^@]*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
            ]
        }
        
        # Law firm patterns
        self.firm_patterns = [
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+(?:&|and)\s+[A-Z][a-z]+)*)\s+(?:Law\s+(?:Office|Firm|Group)s?|LLP|LLC|PC|PLC|PLLC)',
            r'(?:Law\s+(?:Office|Firm)s?\s+of\s+)([A-Z][a-z]+(?:\s+[A-Z]\.?\s*)?(?:\s+[A-Z][a-z]+)+)',
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:Law\s+(?:Office|Firm|Group)s?|LLP|LLC|PC|PLC|PLLC)',
        ]
        
        # Common law firms in ADRE cases
        self.known_firms = {
            'Carpenter Hazelwood Delgado',
            'Carpenter Hazlewood Delgado & Bolen',
            'Fitzgibbons Law Offices',
            'Mulcahy Law Firm',
            'Goodman Law Group',
        }
        
        # Invalid name parts
        self.invalid_terms = {
            'association', 'homeowners', 'respondent', 'petitioner', 'represented',
            'appeared', 'behalf', 'office', 'administrative', 'hearings', 'arizona',
            'department', 'real', 'estate', 'transmitted', 'decision', 'order',
            'findings', 'conclusions', 'matter', 'case', 'docket'
        }
    
    def extract_from_document(self, text: str, case_number: str) -> Dict[str, List[AttorneyInfo]]:
        """Extract attorney information from OAH document."""
        attorneys = {
            'petitioner': [],
            'respondent': []
        }
        
        # Extract from APPEARANCES section
        appearances = self._extract_appearances_section(text)
        if appearances:
            appearance_attorneys = self._extract_from_appearances(appearances, case_number)
            for role in ['petitioner', 'respondent']:
                attorneys[role].extend(appearance_attorneys.get(role, []))
        
        # Extract from transmission section
        transmission_attorneys = self._extract_from_transmission(text, case_number)
        for role in ['petitioner', 'respondent']:
            attorneys[role].extend(transmission_attorneys.get(role, []))
        
        # Deduplicate
        attorneys['petitioner'] = self._deduplicate_attorneys(attorneys['petitioner'])
        attorneys['respondent'] = self._deduplicate_attorneys(attorneys['respondent'])
        
        return attorneys
    
    def _extract_appearances_section(self, text: str) -> Optional[str]:
        """Extract APPEARANCES section."""
        pattern = r'APPEARANCES?\s*[:.]?\s*\n((?:.*\n){1,20}?)(?=\n\s*(?:FINDINGS|STATEMENT|BACKGROUND|I\.|1\.))'
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        return match.group(1) if match else None
    
    def _extract_from_appearances(self, appearances_text: str, case_number: str) -> Dict[str, List[AttorneyInfo]]:
        """Extract attorneys from APPEARANCES section."""
        attorneys = {
            'petitioner': [],
            'respondent': []
        }
        
        lines = appearances_text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Determine if this is about petitioner or respondent
            role = None
            if re.search(r'Petitioner.*(?:represented|appeared)', line, re.IGNORECASE):
                role = 'petitioner'
            elif re.search(r'Respondent.*(?:represented|appeared)', line, re.IGNORECASE):
                role = 'respondent'
            elif re.search(r'(?:represented|appeared).*Respondent', line, re.IGNORECASE):
                role = 'respondent'
            
            # Extract attorney names from this line
            for pattern in self.attorney_patterns['appearances_section']:
                matches = re.finditer(pattern, line, re.IGNORECASE)
                for match in matches:
                    name = match.group(1).strip()
                    if self._is_valid_attorney_name(name):
                        attorney = AttorneyInfo(name=name, role=role or 'respondent')  # Default to respondent
                        attorney.cases.add(case_number)
                        
                        # Check if has Esq. title
                        if 'Esq' in line:
                            attorney.esq_title = True
                        
                        # Try to find firm in same line
                        firm = self._extract_firm_from_line(line)
                        if firm:
                            attorney.firm = firm
                        
                        attorneys[attorney.role].append(attorney)
        
        return attorneys
    
    def _extract_from_transmission(self, text: str, case_number: str) -> Dict[str, List[AttorneyInfo]]:
        """Extract attorneys from transmission section at end of document."""
        attorneys = {
            'petitioner': [],
            'respondent': []
        }
        
        # Find transmission section (usually at the end)
        transmission_match = re.search(r'(?:TRANSMISSION|CC:|Copy to:|Served)[:\s]*\n((?:.*\n){0,30})$', 
                                     text, re.IGNORECASE | re.MULTILINE)
        
        if not transmission_match:
            # Also try to find attorney contact info anywhere in last part of document
            transmission_match = re.search(r'((?:.*\n){0,50})$', text, re.MULTILINE)
        
        if transmission_match:
            transmission_text = transmission_match.group(1)
            
            # Look for full attorney contact blocks
            contact_pattern = r'([A-Z][a-z]+(?:\s+[A-Z]\.?\s*)?[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),?\s+Esq\.?,?\s*\n?([^,\n]*(?:Law|LLC|PLC|LLP|Offices)[^,\n]*),?\s*\n?([^,\n]+,\s*[A-Z]{2}\s+\d{5})'
            
            for match in re.finditer(contact_pattern, transmission_text, re.IGNORECASE):
                name = match.group(1).strip()
                firm = match.group(2).strip() if match.group(2) else None
                address = match.group(3).strip() if match.group(3) else None
                
                if self._is_valid_attorney_name(name):
                    attorney = AttorneyInfo(name=name, role='respondent')  # Most are respondent attorneys
                    attorney.cases.add(case_number)
                    attorney.esq_title = True
                    attorney.firm = firm
                    attorney.address = address
                    
                    attorneys['respondent'].append(attorney)
            
            # Look for email patterns
            email_pattern = r'([A-Z][a-z]+(?:\s+[A-Z]\.?\s*)?[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),?\s+Esq\.?[^@]*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
            
            for match in re.finditer(email_pattern, transmission_text, re.IGNORECASE):
                name = match.group(1).strip()
                email = match.group(2).strip()
                
                if self._is_valid_attorney_name(name):
                    # See if we already have this attorney
                    found = False
                    for attorney in attorneys['respondent']:
                        if attorney.name == name:
                            attorney.email = email
                            found = True
                            break
                    
                    if not found:
                        attorney = AttorneyInfo(name=name, role='respondent')
                        attorney.cases.add(case_number)
                        attorney.esq_title = True
                        attorney.email = email
                        attorneys['respondent'].append(attorney)
        
        return attorneys
    
    def _extract_firm_from_line(self, line: str) -> Optional[str]:
        """Extract law firm name from a line."""
        for pattern in self.firm_patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        # Check known firms
        for firm in self.known_firms:
            if firm.lower() in line.lower():
                return firm
        
        return None
    
    def _is_valid_attorney_name(self, name: str) -> bool:
        """Validate attorney name."""
        if not name or len(name) < 5:
            return False
        
        parts = name.split()
        if len(parts) < 2:
            return False
        
        # Check against invalid terms
        name_lower = name.lower()
        for term in self.invalid_terms:
            if term in name_lower:
                return False
        
        # Should start with capital
        if not name[0].isupper():
            return False
        
        # Should not be all caps
        if name.isupper():
            return False
        
        # Should have reasonable length
        if len(name) > 50:
            return False
        
        return True
    
    def _deduplicate_attorneys(self, attorneys: List[AttorneyInfo]) -> List[AttorneyInfo]:
        """Remove duplicates and merge information."""
        unique = {}
        
        for attorney in attorneys:
            normalized_name = ' '.join(attorney.name.split())
            
            if normalized_name not in unique:
                unique[normalized_name] = attorney
            else:
                # Merge information
                unique[normalized_name].cases.update(attorney.cases)
                if attorney.email and not unique[normalized_name].email:
                    unique[normalized_name].email = attorney.email
                if attorney.firm and not unique[normalized_name].firm:
                    unique[normalized_name].firm = attorney.firm
                if attorney.address and not unique[normalized_name].address:
                    unique[normalized_name].address = attorney.address
                if attorney.esq_title:
                    unique[normalized_name].esq_title = True
        
        return list(unique.values())

def query_rag_system_for_verification():
    """Query the RAG system to verify attorney parsing."""
    print("\n" + "="*80)
    print("VERIFYING ATTORNEY EXTRACTION VIA RAG SYSTEM QUERIES")
    print("="*80)
    
    BASE_URL = "http://localhost:8000"
    
    queries = [
        "List all attorneys who represented homeowners associations in these ADRE cases. Include their names and law firms.",
        "Find mentions of 'Esq.' in these documents and list the attorney names.",
        "What law firms appear most frequently in these ADRE decisions?",
        "List all mentions of Carpenter Hazelwood or Fitzgibbons in these cases.",
    ]
    
    for query in queries:
        print(f"\nQuery: {query}")
        
        query_data = {
            "question": query,
            "projects": ["adre_decisions_complete"],
            "enable_hierarchy": True,
            "include_citations": False,
            "verbose": False
        }
        
        response = requests.post(f"{BASE_URL}/legal-query", json=query_data)
        
        if response.status_code == 200:
            result = response.json()
            print(f"Sources: {len(result['sources'])}")
            
            # Extract key attorney/firm mentions from answer
            answer = result['answer']
            
            # Look for Esq. patterns
            esq_matches = re.findall(r'([A-Z][a-z]+(?:\s+[A-Z]\.?\s*)?[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),?\s+Esq\.?', answer)
            if esq_matches:
                print(f"Attorneys with Esq.: {', '.join(esq_matches[:5])}")
            
            # Look for firm names
            firm_matches = re.findall(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+Law\s+(?:Office|Firm|Group)s?|LLP|LLC|PC|PLC))', answer)
            if firm_matches:
                print(f"Law firms mentioned: {', '.join(firm_matches[:3])}")
        
        print("-" * 40)

def main():
    """Main execution."""
    print("FINAL OAH ATTORNEY EXTRACTION")
    print("=" * 80)
    
    extractor = OAHAttorneyExtractor()
    case_dir = Path("../azoah/adre_decisions_downloads")
    
    all_attorneys = {
        'petitioner': defaultdict(lambda: AttorneyInfo("", "petitioner")),
        'respondent': defaultdict(lambda: AttorneyInfo("", "respondent"))
    }
    
    # Process all files
    all_files = list(case_dir.glob("*.docx")) + list(case_dir.glob("*.doc"))
    print(f"\nProcessing all {len(all_files)} files...")
    
    files_processed = 0
    unique_attorneys = set()
    
    for file_path in all_files:
        try:
            case_number = file_path.stem
            
            # Read document
            try:
                doc = docx.Document(str(file_path))
                text = "\n".join([para.text for para in doc.paragraphs])
            except:
                continue
            
            # Extract attorneys
            attorneys = extractor.extract_from_document(text, case_number)
            
            # Aggregate
            for role in ['petitioner', 'respondent']:
                for attorney in attorneys[role]:
                    key = attorney.name
                    unique_attorneys.add(key)
                    
                    if key in all_attorneys[role]:
                        all_attorneys[role][key].cases.update(attorney.cases)
                        if attorney.email:
                            all_attorneys[role][key].email = attorney.email
                        if attorney.firm:
                            all_attorneys[role][key].firm = attorney.firm
                        if attorney.address:
                            all_attorneys[role][key].address = attorney.address
                        if attorney.esq_title:
                            all_attorneys[role][key].esq_title = True
                    else:
                        all_attorneys[role][key] = attorney
            
            files_processed += 1
            
            if files_processed % 50 == 0:
                print(f"  Processed {files_processed} files, found {len(unique_attorneys)} unique attorneys...")
                
        except Exception as e:
            print(f"  Error processing {file_path.name}: {str(e)[:50]}...")
    
    # Convert and sort
    pet_attorneys = sorted(list(all_attorneys['petitioner'].values()), 
                          key=lambda x: len(x.cases), reverse=True)
    resp_attorneys = sorted(list(all_attorneys['respondent'].values()), 
                           key=lambda x: len(x.cases), reverse=True)
    
    # Generate final report
    print(f"\n" + "="*80)
    print("FINAL COMPREHENSIVE ATTORNEY REPORT")
    print("="*80)
    
    print(f"\nTotal files processed: {files_processed}")
    print(f"Total unique attorneys found: {len(unique_attorneys)}")
    print(f"Petitioner attorneys: {len(pet_attorneys)}")
    print(f"Respondent attorneys: {len(resp_attorneys)}")
    
    # Petitioner attorneys
    if pet_attorneys:
        print(f"\n### PETITIONER ATTORNEYS ###")
        for attorney in pet_attorneys:
            print(f"\n{attorney.name}")
            print(f"  Cases: {len(attorney.cases)}")
            if attorney.firm:
                print(f"  Firm: {attorney.firm}")
            if attorney.email:
                print(f"  Email: {attorney.email}")
    
    # Top respondent attorneys
    if resp_attorneys:
        print(f"\n### TOP RESPONDENT ATTORNEYS ###")
        for i, attorney in enumerate(resp_attorneys[:15], 1):
            print(f"\n{i}. {attorney.name}")
            print(f"   Cases: {len(attorney.cases)}")
            if attorney.firm:
                print(f"   Firm: {attorney.firm}")
            if attorney.email:
                print(f"   Email: {attorney.email}")
            if attorney.esq_title:
                print(f"   Title: Esq.")
            print(f"   Sample cases: {', '.join(list(attorney.cases)[:3])}")
    
    # Law firm analysis
    firm_stats = defaultdict(int)
    for attorney in resp_attorneys:
        if attorney.firm:
            firm_stats[attorney.firm] += len(attorney.cases)
    
    if firm_stats:
        print(f"\n### TOP LAW FIRMS BY CASE COUNT ###")
        sorted_firms = sorted(firm_stats.items(), key=lambda x: x[1], reverse=True)
        for firm, case_count in sorted_firms[:10]:
            print(f"{firm}: {case_count} cases")
    
    # Save results
    output_data = {
        'summary': {
            'files_processed': files_processed,
            'total_attorneys': len(unique_attorneys),
            'petitioner_count': len(pet_attorneys),
            'respondent_count': len(resp_attorneys)
        },
        'petitioner_attorneys': [
            {
                'name': att.name,
                'case_count': len(att.cases),
                'firm': att.firm,
                'email': att.email,
                'cases': list(att.cases)
            }
            for att in pet_attorneys
        ],
        'respondent_attorneys': [
            {
                'name': att.name,
                'case_count': len(att.cases),
                'firm': att.firm,
                'email': att.email,
                'esq_title': att.esq_title,
                'cases': list(att.cases)[:5]  # Limit for output size
            }
            for att in resp_attorneys
        ]
    }
    
    with open('attorneys_final_comprehensive.json', 'w') as f:
        json.dump(output_data, f, indent=2)
    
    # Query RAG system for verification
    query_rag_system_for_verification()
    
    print(f"\n✓ Final attorney extraction complete!")
    print("Results saved to attorneys_final_comprehensive.json")

if __name__ == "__main__":
    main()
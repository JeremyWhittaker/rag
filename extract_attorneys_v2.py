#!/usr/bin/env python3
"""Enhanced attorney extraction focusing on actual attorney names in ADRE decisions."""

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
    title: Optional[str] = None  # e.g., "Assistant Attorney General"

class EnhancedAttorneyExtractor:
    """Enhanced extraction of attorney information from ADRE/OAH documents."""
    
    def __init__(self):
        # More specific attorney patterns
        self.attorney_patterns = {
            'header_section': [
                # Look for attorney names in header sections
                r'(?:BEFORE THE )?OFFICE OF ADMINISTRATIVE HEARINGS.*?(?=APPEARANCES|In the Matter)',
                r'ARIZONA DEPARTMENT OF REAL ESTATE.*?(?=DECISION|ORDER|FINDINGS)',
            ],
            'appearances_section': [
                # APPEARANCES section is most reliable
                r'APPEARANCES?\s*[:.]?\s*\n((?:.*\n){0,15}?)(?=\n\s*(?:FINDINGS|ORDER|DECISION|BACKGROUND|THE MATTER))',
            ],
            'attorney_patterns': [
                # Specific patterns within sections
                r'For\s+(?:the\s+)?(?:Petitioner|State|Department|ADRE)\s*(?:of Arizona)?\s*[:.]?\s*\n?\s*([A-Z][a-z]+(?:\s+[A-Z]\.?)?(?:\s+[A-Z][a-z]+)+)(?:\s*,?\s*(?:Esq\.|Attorney|Assistant Attorney General))?',
                r'For\s+(?:the\s+)?Respondent\s*[:.]?\s*\n?\s*([A-Z][a-z]+(?:\s+[A-Z]\.?)?(?:\s+[A-Z][a-z]+)+)(?:\s*,?\s*(?:Esq\.|Attorney))?',
                # Assistant Attorney General patterns
                r'([A-Z][a-z]+(?:\s+[A-Z]\.?)?(?:\s+[A-Z][a-z]+)+)\s*,?\s*\n?\s*Assistant\s+Attorney\s+General',
                r'Assistant\s+Attorney\s+General\s*[:.]?\s*\n?\s*([A-Z][a-z]+(?:\s+[A-Z]\.?)?(?:\s+[A-Z][a-z]+)+)',
                # By: patterns (common in signature blocks)
                r'By\s*[:.]?\s*(?:/s/)?\s*([A-Z][a-z]+(?:\s+[A-Z]\.?)?(?:\s+[A-Z][a-z]+)+)\s*\n\s*(?:Assistant\s+)?Attorney(?:\s+General)?',
                # Attorney for [Party]
                r'([A-Z][a-z]+(?:\s+[A-Z]\.?)?(?:\s+[A-Z][a-z]+)+)\s*,?\s*(?:Esq\.|Attorney)\s*\n?\s*(?:for|representing)\s+(?:the\s+)?(?:Petitioner|Respondent)',
                # Law firm patterns with attorney names
                r'([A-Z][a-z]+(?:\s+[A-Z]\.?)?(?:\s+[A-Z][a-z]+)+)\s*\n\s*([A-Z][a-z]+(?:\s+(?:&|and)\s+[A-Z][a-z]+)*\s+(?:Law\s+(?:Firm|Office|Group)|LLP|LLC|PC|PLC|PLLC))',
            ],
            'signature_block': [
                # Signature blocks at end of documents
                r'Respectfully\s+submitted.*?\n\s*(?:/s/)?\s*([A-Z][a-z]+(?:\s+[A-Z]\.?)?(?:\s+[A-Z][a-z]+)+)',
                r'DATED\s+this.*?\n(?:.*\n){0,5}?(?:/s/)?\s*([A-Z][a-z]+(?:\s+[A-Z]\.?)?(?:\s+[A-Z][a-z]+)+)\s*\n\s*(?:Assistant\s+)?Attorney',
            ]
        }
        
        # State Bar patterns
        self.bar_patterns = [
            r'State\s+Bar\s+(?:No\.?|Number|#)\s*[:.]?\s*(\d{5,6})',
            r'Bar\s+(?:No\.?|Number|#)\s*[:.]?\s*(\d{5,6})',
            r'\(State\s+Bar\s+(?:No\.?|#)\s*(\d{5,6})\)',
            r'SBN\s*[:.]?\s*(\d{5,6})',
        ]
        
        # Known Assistant Attorneys General (common in ADRE cases)
        self.known_aags = {
            'Elizabeth A. Campbell',
            'Elizabeth Campbell',
            'Mary T. Hone',
            'Mary Hone',
            'Kimberly J. Cygan',
            'Kimberly Cygan',
        }
        
        # Invalid names to filter
        self.invalid_terms = {
            'order', 'decision', 'copy', 'state', 'arizona', 'department',
            'real estate', 'commission', 'commissioner', 'administrative',
            'law judge', 'hearing officer', 'notice', 'findings', 'fact',
            'transmitted', 'page', 'case', 'docket', 'matter', 'license',
            'petitioner', 'respondent', 'complainant', 'before', 'office',
            'the honorable', 'presiding', 'appearances', 'for the', 'by the',
            'dated', 'filed', 'hearing', 'decision and order', 'findings of fact'
        }
    
    def extract_from_document(self, text: str, case_number: str) -> Dict[str, List[AttorneyInfo]]:
        """Extract attorney information from document text."""
        attorneys = {
            'petitioner': [],
            'respondent': []
        }
        
        # First, try to find APPEARANCES section
        appearances_text = self._extract_appearances_section(text)
        if appearances_text:
            attorneys = self._extract_from_appearances(appearances_text, case_number)
        
        # Also check signature blocks
        signature_attorneys = self._extract_from_signatures(text, case_number)
        
        # Merge results
        for role in ['petitioner', 'respondent']:
            attorneys[role].extend(signature_attorneys.get(role, []))
        
        # Look for specific known AAGs
        for aag_name in self.known_aags:
            if aag_name in text:
                attorney = AttorneyInfo(
                    name=aag_name,
                    role='petitioner',
                    title='Assistant Attorney General'
                )
                attorney.cases.add(case_number)
                attorneys['petitioner'].append(attorney)
        
        # Deduplicate and clean
        attorneys['petitioner'] = self._deduplicate_attorneys(attorneys['petitioner'])
        attorneys['respondent'] = self._deduplicate_attorneys(attorneys['respondent'])
        
        return attorneys
    
    def _extract_appearances_section(self, text: str) -> Optional[str]:
        """Extract the APPEARANCES section from document."""
        # Try different patterns for APPEARANCES section
        patterns = [
            r'APPEARANCES?\s*[:.]?\s*\n((?:.*\n){1,15}?)(?=\n\s*(?:FINDINGS|ORDER|DECISION|BACKGROUND|STATEMENT|I\.|1\.))',
            r'(?:WHO\s+)?APPEARED\s*[:.]?\s*\n((?:.*\n){1,15}?)(?=\n\s*(?:FINDINGS|ORDER|DECISION|BACKGROUND))',
            r'PARTIES\s+PRESENT\s*[:.]?\s*\n((?:.*\n){1,15}?)(?=\n\s*(?:FINDINGS|ORDER|DECISION|BACKGROUND))',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                return match.group(1)
        
        return None
    
    def _extract_from_appearances(self, appearances_text: str, case_number: str) -> Dict[str, List[AttorneyInfo]]:
        """Extract attorneys from APPEARANCES section."""
        attorneys = {
            'petitioner': [],
            'respondent': []
        }
        
        # Split into lines for easier processing
        lines = appearances_text.split('\n')
        current_party = None
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Identify party
            if re.search(r'For\s+(?:the\s+)?(?:Petitioner|State|Department|ADRE)', line, re.IGNORECASE):
                current_party = 'petitioner'
            elif re.search(r'For\s+(?:the\s+)?Respondent', line, re.IGNORECASE):
                current_party = 'respondent'
            
            # Extract attorney name
            if current_party:
                # Check current line and next line for attorney name
                for check_line in [line, lines[i+1] if i+1 < len(lines) else '']:
                    # Look for name pattern
                    name_match = re.match(r'^([A-Z][a-z]+(?:\s+[A-Z]\.?)?(?:\s+[A-Z][a-z]+)+)', check_line.strip())
                    if name_match:
                        name = name_match.group(1)
                        if self._is_valid_attorney_name(name):
                            attorney = AttorneyInfo(name=name, role=current_party)
                            attorney.cases.add(case_number)
                            
                            # Check for title
                            if 'Assistant Attorney General' in check_line:
                                attorney.title = 'Assistant Attorney General'
                            
                            # Check for bar number
                            bar_match = re.search(r'Bar\s*(?:No\.?|#)\s*(\d{5,6})', check_line)
                            if bar_match:
                                attorney.bar_number = bar_match.group(1)
                            
                            attorneys[current_party].append(attorney)
                            current_party = None  # Reset after finding attorney
                            break
        
        return attorneys
    
    def _extract_from_signatures(self, text: str, case_number: str) -> Dict[str, List[AttorneyInfo]]:
        """Extract attorneys from signature blocks."""
        attorneys = {
            'petitioner': [],
            'respondent': []
        }
        
        # Look for signature blocks
        signature_patterns = [
            r'(?:Respectfully\s+submitted|DATED\s+this).*?(?:\n.*?){0,10}?/s/\s*([A-Z][a-z]+(?:\s+[A-Z]\.?)?(?:\s+[A-Z][a-z]+)+)',
            r'By\s*[:.]?\s*\n?\s*/s/\s*([A-Z][a-z]+(?:\s+[A-Z]\.?)?(?:\s+[A-Z][a-z]+)+)',
        ]
        
        for pattern in signature_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                name = match.group(1).strip()
                if self._is_valid_attorney_name(name):
                    # Determine role from context
                    context = text[max(0, match.start()-200):match.end()+200]
                    
                    attorney = AttorneyInfo(name=name, role='unknown')
                    attorney.cases.add(case_number)
                    
                    if 'Attorney General' in context:
                        attorney.role = 'petitioner'
                        attorney.title = 'Assistant Attorney General'
                    elif 'for Respondent' in context:
                        attorney.role = 'respondent'
                    elif 'for Petitioner' in context or 'for the State' in context:
                        attorney.role = 'petitioner'
                    
                    if attorney.role != 'unknown':
                        attorneys[attorney.role].append(attorney)
        
        return attorneys
    
    def _is_valid_attorney_name(self, name: str) -> bool:
        """Validate if extracted text is likely an attorney name."""
        if not name or len(name) < 5:
            return False
        
        # Must have at least first and last name
        parts = name.split()
        if len(parts) < 2:
            return False
        
        # Check against invalid terms
        name_lower = name.lower()
        for term in self.invalid_terms:
            if term in name_lower:
                return False
        
        # Should start with capital letter
        if not name[0].isupper():
            return False
        
        # Should not be all caps
        if name.isupper():
            return False
        
        # Should have reasonable length
        if len(name) > 50:
            return False
        
        # Check for common name patterns
        # At least one part should be 3+ characters (last name)
        has_valid_name_part = any(len(part) >= 3 for part in parts if not part.endswith('.'))
        if not has_valid_name_part:
            return False
        
        return True
    
    def _deduplicate_attorneys(self, attorneys: List[AttorneyInfo]) -> List[AttorneyInfo]:
        """Remove duplicate attorneys, merging their information."""
        unique = {}
        
        for attorney in attorneys:
            # Normalize name for comparison
            normalized_name = ' '.join(attorney.name.split())
            
            if normalized_name not in unique:
                unique[normalized_name] = attorney
            else:
                # Merge information
                unique[normalized_name].cases.update(attorney.cases)
                if attorney.bar_number and not unique[normalized_name].bar_number:
                    unique[normalized_name].bar_number = attorney.bar_number
                if attorney.firm and not unique[normalized_name].firm:
                    unique[normalized_name].firm = attorney.firm
                if attorney.title and not unique[normalized_name].title:
                    unique[normalized_name].title = attorney.title
        
        return list(unique.values())

def main():
    """Main execution function."""
    print("ENHANCED ADRE ATTORNEY EXTRACTION")
    print("=" * 80)
    
    extractor = EnhancedAttorneyExtractor()
    case_dir = Path("../azoah/adre_decisions_downloads")
    
    all_attorneys = {
        'petitioner': defaultdict(lambda: AttorneyInfo("", "petitioner")),
        'respondent': defaultdict(lambda: AttorneyInfo("", "respondent"))
    }
    
    # Get all files
    all_files = list(case_dir.glob("*.docx")) + list(case_dir.glob("*.doc"))
    print(f"\nTotal files available: {len(all_files)}")
    
    # Process all files
    print(f"Processing all {len(all_files)} files for comprehensive attorney list...")
    
    files_processed = 0
    unique_attorneys = set()
    
    for file_path in all_files:
        try:
            # Extract case number
            case_number = file_path.stem
            
            # Read document
            try:
                doc = docx.Document(str(file_path))
                text = "\n".join([para.text for para in doc.paragraphs])
            except:
                continue
            
            # Extract attorneys
            attorneys = extractor.extract_from_document(text, case_number)
            
            # Aggregate results
            for role in ['petitioner', 'respondent']:
                for attorney in attorneys[role]:
                    key = attorney.name
                    unique_attorneys.add(key)
                    
                    if key in all_attorneys[role]:
                        all_attorneys[role][key].cases.update(attorney.cases)
                        if attorney.bar_number:
                            all_attorneys[role][key].bar_number = attorney.bar_number
                        if attorney.firm:
                            all_attorneys[role][key].firm = attorney.firm
                        if attorney.title:
                            all_attorneys[role][key].title = attorney.title
                    else:
                        all_attorneys[role][key] = attorney
            
            files_processed += 1
            
            # Progress indicator
            if files_processed % 20 == 0:
                print(f"  Processed {files_processed} files, found {len(unique_attorneys)} unique attorneys...")
                
        except Exception as e:
            print(f"  Error processing {file_path.name}: {str(e)[:50]}...")
    
    print(f"\nProcessed {files_processed} files successfully")
    
    # Generate report
    print("\n" + "="*80)
    print("COMPREHENSIVE ATTORNEY REPORT")
    print("="*80)
    
    # Convert to lists and sort
    pet_attorneys = sorted(list(all_attorneys['petitioner'].values()), 
                          key=lambda x: len(x.cases), reverse=True)
    resp_attorneys = sorted(list(all_attorneys['respondent'].values()), 
                           key=lambda x: len(x.cases), reverse=True)
    
    # Petitioner Attorneys
    print("\n### PETITIONER ATTORNEYS (State/Department/ADRE) ###")
    print("-" * 60)
    print(f"\nTotal unique petitioner attorneys found: {len(pet_attorneys)}")
    
    if pet_attorneys:
        print("\nAll Petitioner Attorneys:")
        for attorney in pet_attorneys:
            print(f"\n{attorney.name}")
            if attorney.title:
                print(f"  Title: {attorney.title}")
            print(f"  Cases: {len(attorney.cases)}")
            if attorney.bar_number:
                print(f"  Bar #: {attorney.bar_number}")
            print(f"  Sample cases: {', '.join(list(attorney.cases)[:5])}")
    
    # Respondent Attorneys
    print("\n\n### RESPONDENT ATTORNEYS ###")
    print("-" * 60)
    print(f"\nTotal unique respondent attorneys found: {len(resp_attorneys)}")
    
    if resp_attorneys:
        print("\nTop 20 Respondent Attorneys by Case Count:")
        for i, attorney in enumerate(resp_attorneys[:20], 1):
            print(f"\n{i}. {attorney.name}")
            print(f"   Cases: {len(attorney.cases)}")
            if attorney.bar_number:
                print(f"   Bar #: {attorney.bar_number}")
            if attorney.firm:
                print(f"   Firm: {attorney.firm}")
            print(f"   Sample cases: {', '.join(list(attorney.cases)[:3])}")
    
    # Save results
    output_data = {
        'extraction_summary': {
            'total_files_processed': files_processed,
            'total_unique_attorneys': len(unique_attorneys),
            'petitioner_attorneys_count': len(pet_attorneys),
            'respondent_attorneys_count': len(resp_attorneys)
        },
        'petitioner_attorneys': [
            {
                'name': att.name,
                'title': att.title,
                'bar_number': att.bar_number,
                'case_count': len(att.cases),
                'cases': list(att.cases)
            }
            for att in pet_attorneys
        ],
        'respondent_attorneys': [
            {
                'name': att.name,
                'bar_number': att.bar_number,
                'firm': att.firm,
                'case_count': len(att.cases),
                'cases': list(att.cases)[:10]  # Limit cases in output
            }
            for att in resp_attorneys
        ]
    }
    
    with open('attorneys_comprehensive.json', 'w') as f:
        json.dump(output_data, f, indent=2)
    
    print(f"\n\nTotal unique attorneys found: {len(unique_attorneys)}")
    print("✓ Enhanced attorney extraction complete!")
    print("Results saved to attorneys_comprehensive.json")

if __name__ == "__main__":
    main()
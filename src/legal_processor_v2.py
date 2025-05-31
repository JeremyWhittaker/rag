"""Enhanced legal document processor with better ADRE/OAH case parsing."""

from __future__ import annotations
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

@dataclass
class ADRECaseInfo:
    """Structured information from ADRE/OAH cases."""
    case_number: str
    oah_docket: Optional[str] = None
    adre_case_no: Optional[str] = None
    respondent_name: Optional[str] = None
    respondent_license: Optional[str] = None
    complainant: Optional[str] = None
    judge_name: Optional[str] = None
    hearing_date: Optional[datetime] = None
    decision_date: Optional[datetime] = None
    document_type: str = "unknown"
    violations: List[str] = field(default_factory=list)
    statutes_violated: List[str] = field(default_factory=list)
    penalties: List[str] = field(default_factory=list)
    findings: List[str] = field(default_factory=list)
    order_text: Optional[str] = None


class EnhancedLegalProcessor:
    """Enhanced processor specifically for ADRE/OAH documents."""
    
    def __init__(self):
        # Enhanced patterns for ADRE cases
        self.case_patterns = {
            'oah_docket': [
                r'OAH\s+(?:Docket\s+)?(?:No\.?\s*)?([A-Z0-9\-]+)',
                r'Docket\s+(?:No\.?\s*)?([A-Z0-9\-]+)',
            ],
            'adre_case': [
                r'ADRE\s+(?:Case\s+)?(?:No\.?\s*)?([A-Z0-9\-]+)',
                r'Case\s+(?:No\.?\s*)?(\d{2}[A-Z]\-[A-Z]\d+(?:\-REL)?(?:\-RHG)?)',
            ],
            'judge': [
                r'ADMINISTRATIVE\s+LAW\s+JUDGE:\s*([A-Z][a-z]+(?:\s+[A-Z]\.?\s*)?(?:\s+[A-Z][a-z]+)+)',
                r'(?:Judge|ALJ|Hearing\s+Officer):\s*([A-Z][a-z]+(?:\s+[A-Z]\.?\s*)?(?:\s+[A-Z][a-z]+)+)',
                r'Before(?:\s+the\s+Honorable)?\s+([A-Z][a-z]+(?:\s+[A-Z]\.?\s*)?(?:\s+[A-Z][a-z]+)+),?\s+(?:Administrative\s+Law\s+Judge|ALJ)',
                r'([A-Z][a-z]+(?:\s+[A-Z]\.?\s*)?(?:\s+[A-Z][a-z]+)+)\s*\n\s*Administrative\s+Law\s+Judge',
            ],
            'respondent': [
                r'(?:In\s+the\s+[Mm]atter\s+of|Respondent):\s*([A-Z][A-Za-z\s,\.]+?)(?:\n|,\s*(?:Respondent|License))',
                r'([A-Z][A-Za-z\s,\.]+?),?\s+Respondent',
                r'RESPONDENT:\s*([A-Z][A-Za-z\s,\.]+?)(?:\n|$)',
            ],
            'license': [
                r'(?:License|Lic\.?)\s*(?:#|No\.?|Number)?\s*:?\s*([A-Z]{0,2}\d{6,})',
                r'(?:Real\s+Estate\s+)?(?:Salesperson|Broker)\s+License\s*(?:#|No\.?)?\s*([A-Z]{0,2}\d{6,})',
            ],
            'complainant': [
                r'(?:Complainant|Petitioner):\s*([A-Z][A-Za-z\s,\.]+?)(?:\n|,)',
                r'([A-Z][A-Za-z\s,\.]+?),?\s+(?:Complainant|Petitioner)',
            ]
        }
        
        # Document type indicators
        self.doc_type_indicators = {
            'findings_of_fact': ['FINDINGS OF FACT', 'FINDINGS AND CONCLUSIONS', 'FINDINGS'],
            'order': ['ORDER', 'FINAL ORDER', "COMMISSIONER'S FINAL ORDER", 'ADMINISTRATIVE ORDER'],
            'notice_of_hearing': ['NOTICE OF HEARING', 'HEARING NOTICE'],
            'motion': ['MOTION FOR', 'MOTION TO'],
            'complaint': ['COMPLAINT', 'PETITION'],
            'settlement': ['CONSENT ORDER', 'SETTLEMENT AGREEMENT'],
            'decision': ['DECISION AND ORDER', 'FINAL DECISION'],
        }
        
        # Violation patterns
        self.violation_patterns = {
            'trust_account': [
                r'trust\s+(?:account|funds?)',
                r'commingl(?:ing|ed?)',
                r'escrow\s+(?:account|funds?)',
            ],
            'misrepresentation': [
                r'misrepresent(?:ation|ed|ing)?',
                r'false\s+(?:statement|representation|information)',
                r'mislead(?:ing)?',
                r'deceptive\s+(?:practice|conduct)',
            ],
            'disclosure': [
                r'fail(?:ure|ed)?\s+to\s+disclose',
                r'non[\-\s]?disclosure',
                r'conceal(?:ment|ed|ing)?',
            ],
            'unlicensed': [
                r'unlicensed\s+(?:activity|practice)',
                r'practic(?:ing|ed?)\s+without\s+(?:a\s+)?license',
                r'license\s+required',
            ],
            'negligence': [
                r'negligen(?:ce|t)',
                r'breach\s+of\s+(?:fiduciary\s+)?duty',
                r'fail(?:ure|ed)?\s+to\s+exercise\s+reasonable\s+care',
            ],
            'advertising': [
                r'(?:false|misleading)\s+advertising',
                r'advertising\s+violation',
            ],
            'supervision': [
                r'fail(?:ure|ed)?\s+to\s+supervise',
                r'inadequate\s+supervision',
            ]
        }
        
        # Penalty patterns
        self.penalty_patterns = {
            'revocation': r'(?:license\s+)?(?:is\s+)?revok(?:ed?|ation)',
            'suspension': r'(?:license\s+)?(?:is\s+)?suspend(?:ed?|suspension)',
            'probation': r'probation(?:ary)?',
            'censure': r'censure[d]?',
            'fine': r'(?:civil\s+)?(?:penalty|fine)\s+of\s+\$?([\d,]+)',
            'education': r'(?:complete|take)\s+(?:\d+\s+hours?\s+of\s+)?(?:continuing\s+)?education',
            'cease_desist': r'cease\s+and\s+desist',
        }
    
    def extract_case_info(self, text: str, filename: str = "") -> ADRECaseInfo:
        """Extract comprehensive case information from ADRE/OAH document."""
        info = ADRECaseInfo(case_number=self._extract_case_number_from_filename(filename))
        
        # Clean text for better matching
        text_clean = re.sub(r'\s+', ' ', text)
        text_lines = text.split('\n')
        
        # Extract case numbers
        for pattern in self.case_patterns['oah_docket']:
            match = re.search(pattern, text_clean, re.IGNORECASE)
            if match:
                info.oah_docket = match.group(1)
                break
        
        for pattern in self.case_patterns['adre_case']:
            match = re.search(pattern, text_clean, re.IGNORECASE)
            if match:
                info.adre_case_no = match.group(1)
                break
        
        # Extract judge name (enhanced logic)
        info.judge_name = self._extract_judge_name(text, text_lines)
        
        # Extract respondent and license
        info.respondent_name = self._extract_respondent_name(text_clean)
        info.respondent_license = self._extract_license_number(text_clean)
        
        # Extract complainant
        for pattern in self.case_patterns['complainant']:
            match = re.search(pattern, text_clean)
            if match:
                info.complainant = self._clean_name(match.group(1))
                break
        
        # Determine document type
        info.document_type = self._classify_document_type(text)
        
        # Extract violations
        info.violations = self._extract_violations(text_clean)
        info.statutes_violated = self._extract_statute_violations(text_clean)
        
        # Extract penalties
        info.penalties = self._extract_penalties(text_clean)
        
        # Extract dates
        dates = self._extract_dates_with_context(text)
        info.hearing_date = dates.get('hearing')
        info.decision_date = dates.get('decision')
        
        # Extract key findings and orders
        info.findings = self._extract_findings(text)
        info.order_text = self._extract_order_text(text)
        
        return info
    
    def _extract_judge_name(self, text: str, text_lines: List[str]) -> Optional[str]:
        """Enhanced judge name extraction."""
        # Try each pattern
        for pattern in self.case_patterns['judge']:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                name = self._clean_name(match.group(1))
                # Validate it's a real name
                if self._is_valid_judge_name(name):
                    return name
        
        # Look for specific format in lines
        for i, line in enumerate(text_lines):
            if 'ADMINISTRATIVE LAW JUDGE' in line.upper():
                # Check same line after colon
                if ':' in line:
                    name = line.split(':', 1)[1].strip()
                    if self._is_valid_judge_name(name):
                        return self._clean_name(name)
                # Check next line
                elif i + 1 < len(text_lines):
                    name = text_lines[i + 1].strip()
                    if self._is_valid_judge_name(name):
                        return self._clean_name(name)
        
        return None
    
    def _is_valid_judge_name(self, name: str) -> bool:
        """Validate if extracted text is likely a judge name."""
        if not name or len(name) < 5:
            return False
        
        # Must have at least first and last name
        parts = name.split()
        if len(parts) < 2:
            return False
        
        # Filter out common false positives
        invalid_terms = ['Copy', 'Order', 'Decision', 'Arizona', 'Department', 
                        'Transmitted', 'Page', 'of', 'the', 'and']
        for term in invalid_terms:
            if term.lower() == name.lower():
                return False
        
        # Should start with capital letter
        if not name[0].isupper():
            return False
        
        return True
    
    def _extract_respondent_name(self, text: str) -> Optional[str]:
        """Extract respondent name with validation."""
        for pattern in self.case_patterns['respondent']:
            matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                name = self._clean_name(match.group(1))
                if self._is_valid_person_name(name):
                    return name
        return None
    
    def _is_valid_person_name(self, name: str) -> bool:
        """Validate if extracted text is likely a person/company name."""
        if not name or len(name) < 3:
            return False
        
        # Filter out common document terms
        invalid_terms = ['Respondent', 'Petitioner', 'Complainant', 'License', 
                        'Matter', 'Case', 'Docket', 'State', 'Arizona']
        
        for term in invalid_terms:
            if term.lower() in name.lower():
                return False
        
        return True
    
    def _extract_license_number(self, text: str) -> Optional[str]:
        """Extract license number with validation."""
        for pattern in self.case_patterns['license']:
            match = re.search(pattern, text)
            if match:
                license_no = match.group(1)
                # Validate format (should be alphanumeric, 6+ chars)
                if re.match(r'^[A-Z]{0,2}\d{6,}$', license_no):
                    return license_no
        return None
    
    def _classify_document_type(self, text: str) -> str:
        """Classify document type based on content."""
        text_upper = text.upper()
        
        for doc_type, indicators in self.doc_type_indicators.items():
            for indicator in indicators:
                if indicator in text_upper:
                    return doc_type
        
        # Additional heuristics
        if 'HEREBY ORDERED' in text_upper:
            return 'order'
        elif 'HEARING WILL BE HELD' in text_upper:
            return 'notice_of_hearing'
        elif 'COMPLAINT ALLEGES' in text_upper:
            return 'complaint'
        
        return 'unknown'
    
    def _extract_violations(self, text: str) -> List[str]:
        """Extract violation types from text."""
        violations = []
        text_lower = text.lower()
        
        for violation_type, patterns in self.violation_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    violations.append(violation_type)
                    break
        
        return list(set(violations))
    
    def _extract_statute_violations(self, text: str) -> List[str]:
        """Extract specific statute violations."""
        statutes = []
        
        # A.R.S. patterns
        ars_pattern = r'(?:violat(?:ed?|ion)\s+of\s+)?A\.R\.S\.?\s*§?\s*([\d\-\.]+)'
        for match in re.finditer(ars_pattern, text, re.IGNORECASE):
            statutes.append(f"A.R.S. § {match.group(1)}")
        
        # A.A.C. patterns
        aac_pattern = r'(?:violat(?:ed?|ion)\s+of\s+)?A\.A\.C\.?\s*R?([\d\-]+)'
        for match in re.finditer(aac_pattern, text, re.IGNORECASE):
            statutes.append(f"A.A.C. R{match.group(1)}")
        
        return list(set(statutes))
    
    def _extract_penalties(self, text: str) -> List[str]:
        """Extract penalties imposed."""
        penalties = []
        text_lower = text.lower()
        
        for penalty_type, pattern in self.penalty_patterns.items():
            matches = re.finditer(pattern, text_lower)
            for match in matches:
                if penalty_type == 'fine' and len(match.groups()) > 0:
                    amount = match.group(1)
                    penalties.append(f"Fine: ${amount}")
                else:
                    penalties.append(penalty_type.replace('_', ' ').title())
        
        return list(set(penalties))
    
    def _extract_dates_with_context(self, text: str) -> Dict[str, datetime]:
        """Extract dates with their context."""
        dates = {}
        
        # Date patterns
        date_patterns = [
            (r'(?:hearing|heard)\s+on\s+(\w+\s+\d{1,2},?\s+\d{4})', 'hearing'),
            (r'(?:dated?|issued?)\s+(?:this\s+)?(\w+\s+\d{1,2},?\s+\d{4})', 'decision'),
            (r'(\d{1,2}/\d{1,2}/\d{4})', 'general'),
        ]
        
        from dateutil import parser as date_parser
        
        for pattern, context in date_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                try:
                    date_str = match.group(1)
                    parsed_date = date_parser.parse(date_str)
                    if context == 'general':
                        # Try to determine context from surrounding text
                        surrounding = text[max(0, match.start()-50):match.end()+50].lower()
                        if 'hearing' in surrounding:
                            dates['hearing'] = parsed_date
                        elif 'decision' in surrounding or 'order' in surrounding:
                            dates['decision'] = parsed_date
                    else:
                        dates[context] = parsed_date
                except:
                    continue
        
        return dates
    
    def _extract_findings(self, text: str) -> List[str]:
        """Extract key findings from the document."""
        findings = []
        
        # Look for numbered findings
        finding_pattern = r'(?:FINDING|FACT)\s*(?:OF\s+FACT\s*)?#?\s*(\d+)[:\.]?\s*([^.\n]+(?:\.[^.\n]+)*\.)'
        for match in re.finditer(finding_pattern, text, re.IGNORECASE):
            finding_text = match.group(2).strip()
            if len(finding_text) > 20:  # Filter out very short findings
                findings.append(f"Finding {match.group(1)}: {finding_text[:200]}")
        
        # Look for conclusions
        conclusion_pattern = r'(?:THEREFORE|CONCLUDES?|FINDS?)\s+(?:THAT\s+)?([^.\n]+\.)'
        for match in re.finditer(conclusion_pattern, text, re.IGNORECASE):
            conclusion = match.group(1).strip()
            if len(conclusion) > 20 and conclusion not in findings:
                findings.append(f"Conclusion: {conclusion[:200]}")
        
        return findings[:10]  # Limit to 10 most important findings
    
    def _extract_order_text(self, text: str) -> Optional[str]:
        """Extract the main order text."""
        order_patterns = [
            r'IT\s+IS\s+(?:HEREBY\s+)?ORDERED\s+(?:THAT\s+)?([^.]+(?:\.[^.]+)*\.)',
            r'ORDERS?\s*:\s*\n([^.]+(?:\.[^.]+)*\.)',
            r'(?:HEREBY\s+)?ORDERS?\s+(?:AS\s+FOLLOWS\s*:?\s*)?([^.]+(?:\.[^.]+)*\.)',
        ]
        
        for pattern in order_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                order_text = match.group(1).strip()
                if len(order_text) > 30:  # Ensure it's substantial
                    return order_text[:500]  # Limit length
        
        return None
    
    def _extract_case_number_from_filename(self, filename: str) -> str:
        """Extract case number from filename."""
        # Pattern for ADRE case numbers in filenames
        match = re.search(r'(\d{2}[A-Z]\-[A-Z]\d+(?:\-REL)?(?:\-RHG)?)', filename)
        if match:
            return match.group(1)
        return filename
    
    def _clean_name(self, name: str) -> str:
        """Clean extracted name."""
        # Remove extra whitespace
        name = ' '.join(name.split())
        # Remove trailing punctuation
        name = name.rstrip('.,;:')
        # Title case
        return name.title()
    
    def create_enhanced_chunks(self, text: str, case_info: ADRECaseInfo) -> List[Dict]:
        """Create chunks with enhanced metadata."""
        chunks = []
        
        # Priority 1: Order text
        if case_info.order_text:
            chunks.append({
                'content': f"ORDER in case {case_info.case_number}: {case_info.order_text}",
                'metadata': {
                    'chunk_type': 'order',
                    'priority': 1,
                    'case_number': case_info.case_number,
                    'judge': case_info.judge_name,
                    'respondent': case_info.respondent_name,
                }
            })
        
        # Priority 2: Violations and penalties
        if case_info.violations or case_info.penalties:
            violation_text = f"Case {case_info.case_number} - Violations: {', '.join(case_info.violations)}. "
            violation_text += f"Statutes violated: {', '.join(case_info.statutes_violated)}. "
            violation_text += f"Penalties: {', '.join(case_info.penalties)}"
            
            chunks.append({
                'content': violation_text,
                'metadata': {
                    'chunk_type': 'violations_penalties',
                    'priority': 2,
                    'case_number': case_info.case_number,
                    'violations': case_info.violations,
                }
            })
        
        # Priority 3: Case header information
        header_text = f"ADRE Case {case_info.case_number}"
        if case_info.oah_docket:
            header_text += f", OAH Docket {case_info.oah_docket}"
        if case_info.respondent_name:
            header_text += f". Respondent: {case_info.respondent_name}"
        if case_info.respondent_license:
            header_text += f" (License: {case_info.respondent_license})"
        if case_info.judge_name:
            header_text += f". Judge: {case_info.judge_name}"
        
        chunks.append({
            'content': header_text,
            'metadata': {
                'chunk_type': 'case_header',
                'priority': 3,
                'case_number': case_info.case_number,
            }
        })
        
        # Priority 4: Key findings
        for i, finding in enumerate(case_info.findings[:5]):  # Top 5 findings
            chunks.append({
                'content': f"Case {case_info.case_number} - {finding}",
                'metadata': {
                    'chunk_type': 'finding',
                    'priority': 4,
                    'case_number': case_info.case_number,
                }
            })
        
        return chunks
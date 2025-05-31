"""Legal document processor with statute/case extraction and citation parsing."""

from __future__ import annotations
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime

import spacy
from dateutil import parser as date_parser

@dataclass
class LegalEntity:
    """Represents a legal entity (statute, case, regulation)."""
    entity_type: str  # 'statute', 'case', 'regulation'
    citation: str
    title: Optional[str] = None
    date: Optional[datetime] = None
    jurisdiction: Optional[str] = None
    summary: Optional[str] = None


class LegalDocumentProcessor:
    """Processes legal documents to extract structured information."""
    
    def __init__(self):
        # Arizona-specific patterns
        self.statute_patterns = [
            # A.R.S. § 12-341
            r'A\.R\.S\.?\s*§?\s*(\d+[-–]\d+(?:\.\d+)?)',
            # Arizona Revised Statutes § 12-341
            r'Arizona\s+Revised\s+Statutes?\s*§?\s*(\d+[-–]\d+(?:\.\d+)?)',
            # Title 12, Chapter 3, Article 4
            r'Title\s+(\d+),?\s*Chapter\s+(\d+),?\s*(?:Article\s+(\d+))?',
        ]
        
        self.case_patterns = [
            # Smith v. Jones, 123 Ariz. 456 (2021)
            r'([A-Z][a-zA-Z\s,\.]+?)\s+v\.\s+([A-Z][a-zA-Z\s,\.]+?),?\s*(\d+\s+Ariz\.\s+\d+)\s*(?:\((\d{4})\))?',
            # In re Smith, 123 Ariz. App. 456 (2021)
            r'In\s+re\s+([A-Z][a-zA-Z\s,\.]+?),?\s*(\d+\s+Ariz\.?\s*(?:App\.)?\s*\d+)\s*(?:\((\d{4})\))?',
            # Case No. CV-2021-12345
            r'Case\s+No\.?\s*([A-Z]{2}[-–]\d{4}[-–]\d+)',
        ]
        
        self.regulation_patterns = [
            # A.A.C. R4-28-301
            r'A\.A\.C\.?\s*R?(\d+[-–]\d+[-–]\d+)',
            # Arizona Administrative Code R4-28-301
            r'Arizona\s+Administrative\s+Code\s*R?(\d+[-–]\d+[-–]\d+)',
        ]
        
        # ADRE/OAH specific patterns
        self.adre_patterns = [
            r'ADRE\s+(?:Case\s+)?(?:No\.?\s*)?([A-Z0-9\-]+)',
            r'OAH\s+(?:Case\s+)?(?:No\.?\s*)?(\d+[A-Z]*\d*)',
            r'Commissioner\'s\s+(?:Final\s+)?Order\s+(?:No\.?\s*)?([A-Z0-9\-]+)',
        ]
    
    def extract_citations(self, text: str) -> Dict[str, List[LegalEntity]]:
        """Extract all legal citations from text."""
        entities = {
            'statutes': [],
            'cases': [],
            'regulations': [],
            'adre_oah': []
        }
        
        # Extract statutes
        for pattern in self.statute_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                citation = match.group(0)
                entities['statutes'].append(
                    LegalEntity(
                        entity_type='statute',
                        citation=citation,
                        jurisdiction='Arizona'
                    )
                )
        
        # Extract cases
        for pattern in self.case_patterns:
            for match in re.finditer(pattern, text):
                citation = match.group(0)
                year = match.group(4) if len(match.groups()) >= 4 else None
                date = datetime(int(year), 1, 1) if year else None
                entities['cases'].append(
                    LegalEntity(
                        entity_type='case',
                        citation=citation,
                        date=date,
                        jurisdiction='Arizona'
                    )
                )
        
        # Extract regulations
        for pattern in self.regulation_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                citation = match.group(0)
                entities['regulations'].append(
                    LegalEntity(
                        entity_type='regulation',
                        citation=citation,
                        jurisdiction='Arizona'
                    )
                )
        
        # Extract ADRE/OAH references
        for pattern in self.adre_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                citation = match.group(0)
                entities['adre_oah'].append(
                    LegalEntity(
                        entity_type='adre_oah',
                        citation=citation,
                        jurisdiction='Arizona ADRE/OAH'
                    )
                )
        
        return entities
    
    def extract_dates(self, text: str) -> List[Tuple[str, datetime]]:
        """Extract dates from legal documents."""
        date_patterns = [
            r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b',
            r'\b\d{1,2}/\d{1,2}/\d{2,4}\b',
            r'\b\d{4}-\d{2}-\d{2}\b',
        ]
        
        dates = []
        for pattern in date_patterns:
            for match in re.finditer(pattern, text):
                try:
                    date_str = match.group(0)
                    parsed_date = date_parser.parse(date_str)
                    dates.append((date_str, parsed_date))
                except:
                    continue
        
        return dates
    
    def extract_parties(self, text: str) -> Dict[str, List[str]]:
        """Extract party names from legal documents."""
        parties = {
            'plaintiffs': [],
            'defendants': [],
            'appellants': [],
            'appellees': [],
            'respondents': []
        }
        
        # Patterns for party extraction
        party_patterns = [
            (r'Plaintiff[s]?[,:\s]+([A-Z][A-Za-z\s,\.]+?)(?:\s+v\.|,)', 'plaintiffs'),
            (r'Defendant[s]?[,:\s]+([A-Z][A-Za-z\s,\.]+?)(?:\s+v\.|,)', 'defendants'),
            (r'Appellant[s]?[,:\s]+([A-Z][A-Za-z\s,\.]+?)(?:\s+v\.|,)', 'appellants'),
            (r'Appellee[s]?[,:\s]+([A-Z][A-Za-z\s,\.]+?)(?:\s+v\.|,)', 'appellees'),
            (r'Respondent[s]?[,:\s]+([A-Z][A-Za-z\s,\.]+?)(?:\s+v\.|,)', 'respondents'),
        ]
        
        for pattern, party_type in party_patterns:
            for match in re.finditer(pattern, text):
                party_name = match.group(1).strip()
                if party_name and party_name not in parties[party_type]:
                    parties[party_type].append(party_name)
        
        return parties
    
    def classify_document(self, text: str, filename: str = "") -> Dict[str, any]:
        """Classify legal document type and extract metadata."""
        doc_type = "unknown"
        metadata = {}
        
        # Check filename patterns
        filename_lower = filename.lower()
        if any(term in filename_lower for term in ['complaint', 'petition']):
            doc_type = "complaint"
        elif any(term in filename_lower for term in ['answer', 'response']):
            doc_type = "answer"
        elif any(term in filename_lower for term in ['motion']):
            doc_type = "motion"
        elif any(term in filename_lower for term in ['order', 'ruling']):
            doc_type = "order"
        elif any(term in filename_lower for term in ['brief']):
            doc_type = "brief"
        elif any(term in filename_lower for term in ['statute', 'ars', 'title']):
            doc_type = "statute"
        elif any(term in filename_lower for term in ['adre', 'oah']):
            doc_type = "adre_oah"
        
        # Extract document-specific metadata
        text_lower = text.lower()
        if "commissioner's final order" in text_lower:
            doc_type = "adre_order"
        elif "notice of hearing" in text_lower:
            doc_type = "hearing_notice"
        elif "findings of fact" in text_lower:
            doc_type = "findings"
        
        # Extract case number
        case_no_pattern = r'(?:Case\s+)?No\.?\s*([A-Z0-9\-]+)'
        case_match = re.search(case_no_pattern, text)
        if case_match:
            metadata['case_number'] = case_match.group(1)
        
        # Extract judge/commissioner
        judge_pattern = r'(?:Judge|Commissioner|Honorable)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)'
        judge_match = re.search(judge_pattern, text)
        if judge_match:
            metadata['judge'] = judge_match.group(1)
        
        return {
            'document_type': doc_type,
            'metadata': metadata,
            'citations': self.extract_citations(text),
            'dates': self.extract_dates(text),
            'parties': self.extract_parties(text)
        }
    
    def create_hierarchical_chunks(self, text: str, doc_info: Dict) -> List[Dict]:
        """Create chunks with hierarchical importance for legal documents."""
        chunks = []
        
        # Priority 1: Headings and holdings
        holding_patterns = [
            r'(?:WE\s+)?(?:THEREFORE\s+)?(?:HOLD|CONCLUDE|FIND|ORDER)(?:\s+THAT)?[:\s]+([^.]+\.)',
            r'IT\s+IS\s+(?:THEREFORE\s+)?ORDERED[:\s]+([^.]+\.)',
            r'CONCLUSION[:\s]+([^.]+\.)',
        ]
        
        for pattern in holding_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                chunks.append({
                    'content': match.group(0),
                    'priority': 1,
                    'type': 'holding',
                    'metadata': doc_info['metadata']
                })
        
        # Priority 2: Statute quotes
        statute_quote_pattern = r'(?:provides|states|reads)[:\s]+"([^"]+)"'
        for match in re.finditer(statute_quote_pattern, text, re.IGNORECASE):
            chunks.append({
                'content': match.group(0),
                'priority': 2,
                'type': 'statute_quote',
                'metadata': doc_info['metadata']
            })
        
        # Priority 3: Regular chunks (will be handled by existing splitter)
        
        return chunks
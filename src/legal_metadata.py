"""Metadata extraction and management for legal documents."""

from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass, field, asdict

@dataclass
class LegalDocumentMetadata:
    """Complete metadata for a legal document."""
    
    # Basic identification
    file_path: str
    file_name: str
    sha256: str
    
    # Document classification
    document_type: str  # statute, case, motion, order, etc.
    jurisdiction: str = "Arizona"
    court_level: Optional[str] = None  # supreme, appeals, superior, administrative
    
    # Entities and parties
    case_number: Optional[str] = None
    case_caption: Optional[str] = None
    parties: Dict[str, List[str]] = field(default_factory=dict)
    judge: Optional[str] = None
    
    # Dates
    date_filed: Optional[datetime] = None
    date_decided: Optional[datetime] = None
    date_effective: Optional[datetime] = None
    
    # Legal content
    statutes_cited: List[str] = field(default_factory=list)
    cases_cited: List[str] = field(default_factory=list)
    regulations_cited: List[str] = field(default_factory=list)
    
    # ADRE/OAH specific
    adre_case_no: Optional[str] = None
    license_number: Optional[str] = None
    violation_type: Optional[str] = None
    penalty: Optional[str] = None
    
    # Document hierarchy
    is_primary_authority: bool = False
    authority_weight: int = 1  # 1-10, higher is more authoritative
    
    # Processing metadata
    date_indexed: datetime = field(default_factory=datetime.now)
    processing_notes: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        data = asdict(self)
        # Convert datetime objects to strings
        for key in ['date_filed', 'date_decided', 'date_effective', 'date_indexed']:
            if data.get(key) and isinstance(data[key], datetime):
                data[key] = data[key].isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LegalDocumentMetadata':
        """Create from dictionary."""
        # Convert string dates back to datetime
        for key in ['date_filed', 'date_decided', 'date_effective', 'date_indexed']:
            if data.get(key) and isinstance(data[key], str):
                data[key] = datetime.fromisoformat(data[key])
        return cls(**data)


class MetadataExtractor:
    """Extracts comprehensive metadata from legal documents."""
    
    def __init__(self):
        self.violation_keywords = {
            'misrepresentation': ['misrepresent', 'false statement', 'misleading'],
            'trust_account': ['trust account', 'escrow', 'client funds'],
            'unlicensed_activity': ['unlicensed', 'without license', 'license required'],
            'failure_to_disclose': ['fail to disclose', 'non-disclosure', 'concealment'],
            'negligence': ['negligent', 'breach of duty', 'standard of care'],
            'fraud': ['fraud', 'deceptive', 'scheme', 'artifice'],
        }
        
        self.penalty_keywords = {
            'revocation': ['revoke', 'revocation'],
            'suspension': ['suspend', 'suspension'],
            'probation': ['probation', 'probationary'],
            'fine': ['fine', 'monetary penalty', 'civil penalty'],
            'censure': ['censure', 'reprimand'],
            'education': ['education', 'continuing education', 'CE hours'],
        }
    
    def extract_from_text(self, text: str, file_path: Path, sha256: str, 
                         doc_classification: Dict) -> LegalDocumentMetadata:
        """Extract comprehensive metadata from document text."""
        metadata = LegalDocumentMetadata(
            file_path=str(file_path),
            file_name=file_path.name,
            sha256=sha256,
            document_type=doc_classification.get('document_type', 'unknown'),
        )
        
        # Add basic classification metadata
        if doc_classification.get('metadata'):
            if 'case_number' in doc_classification['metadata']:
                metadata.case_number = doc_classification['metadata']['case_number']
            if 'judge' in doc_classification['metadata']:
                metadata.judge = doc_classification['metadata']['judge']
        
        # Extract citations
        if doc_classification.get('citations'):
            citations = doc_classification['citations']
            metadata.statutes_cited = [e.citation for e in citations.get('statutes', [])]
            metadata.cases_cited = [e.citation for e in citations.get('cases', [])]
            metadata.regulations_cited = [e.citation for e in citations.get('regulations', [])]
            
            # ADRE/OAH specific
            for entity in citations.get('adre_oah', []):
                if 'ADRE' in entity.citation:
                    metadata.adre_case_no = entity.citation
        
        # Extract parties
        if doc_classification.get('parties'):
            metadata.parties = doc_classification['parties']
        
        # Extract dates
        if doc_classification.get('dates'):
            dates = doc_classification['dates']
            if dates:
                # Simple heuristic: first date is filing, last is decision
                metadata.date_filed = dates[0][1]
                if len(dates) > 1:
                    metadata.date_decided = dates[-1][1]
        
        # Determine authority level
        metadata = self._determine_authority_level(metadata, text)
        
        # Extract ADRE-specific information
        metadata = self._extract_adre_info(metadata, text)
        
        return metadata
    
    def _determine_authority_level(self, metadata: LegalDocumentMetadata, 
                                 text: str) -> LegalDocumentMetadata:
        """Determine the authority level of the document."""
        text_lower = text.lower()
        
        # Primary authority detection
        if metadata.document_type == 'statute':
            metadata.is_primary_authority = True
            metadata.authority_weight = 10
        elif metadata.document_type == 'regulation':
            metadata.is_primary_authority = True
            metadata.authority_weight = 9
        elif 'supreme court' in text_lower:
            metadata.is_primary_authority = True
            metadata.authority_weight = 8
            metadata.court_level = 'supreme'
        elif 'court of appeals' in text_lower:
            metadata.is_primary_authority = True
            metadata.authority_weight = 7
            metadata.court_level = 'appeals'
        elif metadata.document_type == 'adre_order':
            metadata.is_primary_authority = True
            metadata.authority_weight = 6
            metadata.court_level = 'administrative'
        elif 'superior court' in text_lower:
            metadata.authority_weight = 5
            metadata.court_level = 'superior'
        
        return metadata
    
    def _extract_adre_info(self, metadata: LegalDocumentMetadata, 
                          text: str) -> LegalDocumentMetadata:
        """Extract ADRE-specific information."""
        text_lower = text.lower()
        
        # License number extraction
        import re
        license_pattern = r'(?:license|lic\.?)\s*(?:#|no\.?|number)?\s*([A-Z]{2}\d{6}|\d{6})'
        license_match = re.search(license_pattern, text, re.IGNORECASE)
        if license_match:
            metadata.license_number = license_match.group(1)
        
        # Violation type detection
        for violation_type, keywords in self.violation_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                metadata.violation_type = violation_type
                break
        
        # Penalty detection
        penalties = []
        for penalty_type, keywords in self.penalty_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                penalties.append(penalty_type)
        
        if penalties:
            metadata.penalty = ', '.join(penalties)
        
        # Extract fine amounts
        fine_pattern = r'\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)'
        fine_matches = re.findall(fine_pattern, text)
        if fine_matches and 'fine' in penalties:
            metadata.penalty = f"fine: ${max(fine_matches)}"
        
        return metadata


class MetadataIndex:
    """Manages metadata index for efficient querying."""
    
    def __init__(self, index_path: Path):
        self.index_path = index_path
        self.metadata_file = index_path / "metadata_index.json"
        self.index = self._load_index()
    
    def _load_index(self) -> Dict[str, LegalDocumentMetadata]:
        """Load existing metadata index."""
        if self.metadata_file.exists():
            with open(self.metadata_file, 'r') as f:
                data = json.load(f)
                return {
                    sha256: LegalDocumentMetadata.from_dict(meta)
                    for sha256, meta in data.items()
                }
        return {}
    
    def save_index(self):
        """Save metadata index to disk."""
        self.index_path.mkdir(parents=True, exist_ok=True)
        data = {
            sha256: meta.to_dict()
            for sha256, meta in self.index.items()
        }
        with open(self.metadata_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def add_document(self, metadata: LegalDocumentMetadata):
        """Add document metadata to index."""
        self.index[metadata.sha256] = metadata
    
    def get_by_sha256(self, sha256: str) -> Optional[LegalDocumentMetadata]:
        """Get metadata by document hash."""
        return self.index.get(sha256)
    
    def search(self, **criteria) -> List[LegalDocumentMetadata]:
        """Search metadata by criteria."""
        results = []
        
        for metadata in self.index.values():
            match = True
            
            for key, value in criteria.items():
                if hasattr(metadata, key):
                    attr_value = getattr(metadata, key)
                    if isinstance(value, list):
                        # Check if any value in list matches
                        if not any(v in str(attr_value) for v in value):
                            match = False
                            break
                    elif value not in str(attr_value):
                        match = False
                        break
                else:
                    match = False
                    break
            
            if match:
                results.append(metadata)
        
        # Sort by authority weight
        results.sort(key=lambda x: x.authority_weight, reverse=True)
        
        return results
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about the indexed documents."""
        stats = {
            'total_documents': len(self.index),
            'document_types': {},
            'jurisdictions': {},
            'violation_types': {},
            'total_statutes_cited': 0,
            'total_cases_cited': 0,
        }
        
        for metadata in self.index.values():
            # Document types
            doc_type = metadata.document_type
            stats['document_types'][doc_type] = stats['document_types'].get(doc_type, 0) + 1
            
            # Jurisdictions
            jurisdiction = metadata.jurisdiction
            stats['jurisdictions'][jurisdiction] = stats['jurisdictions'].get(jurisdiction, 0) + 1
            
            # Violations (ADRE specific)
            if metadata.violation_type:
                vtype = metadata.violation_type
                stats['violation_types'][vtype] = stats['violation_types'].get(vtype, 0) + 1
            
            # Citations
            stats['total_statutes_cited'] += len(metadata.statutes_cited)
            stats['total_cases_cited'] += len(metadata.cases_cited)
        
        return stats
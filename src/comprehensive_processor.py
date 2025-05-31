#!/usr/bin/env python3
"""Comprehensive ADRE/OAH document processor for complete metadata extraction."""

from __future__ import annotations
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

@dataclass
class ComprehensiveADRECase:
    """Complete metadata for ADRE/OAH cases."""
    # Case identification
    case_number: str
    oah_docket: Optional[str] = None
    adre_case_no: Optional[str] = None
    
    # Parties
    petitioner_name: Optional[str] = None
    petitioner_type: str = "homeowner"  # homeowner, resident, etc.
    respondent_name: Optional[str] = None
    respondent_type: str = "unknown"  # hoa, management_company, etc.
    hoa_name: Optional[str] = None
    management_company: Optional[str] = None
    
    # Legal representation
    petitioner_attorney: Optional[str] = None
    petitioner_attorney_firm: Optional[str] = None
    petitioner_attorney_email: Optional[str] = None
    petitioner_attorney_bar: Optional[str] = None
    respondent_attorney: Optional[str] = None
    respondent_attorney_firm: Optional[str] = None
    respondent_attorney_email: Optional[str] = None
    respondent_attorney_bar: Optional[str] = None
    assistant_attorney_general: Optional[str] = None
    pro_se_parties: List[str] = field(default_factory=list)
    
    # Judicial information
    judge_name: Optional[str] = None
    administrative_law_judge: Optional[str] = None
    hearing_officer: Optional[str] = None
    
    # Dates
    hearing_date: Optional[datetime] = None
    decision_date: Optional[datetime] = None
    filing_date: Optional[datetime] = None
    
    # Legal violations
    ars_violations: List[str] = field(default_factory=list)  # Arizona Revised Statutes
    aac_violations: List[str] = field(default_factory=list)  # Arizona Administrative Code
    statutes_violated: List[str] = field(default_factory=list)  # General statutory violations
    
    # HOA/Governing document violations
    ccr_violations: List[str] = field(default_factory=list)  # CC&R violations
    bylaws_violations: List[str] = field(default_factory=list)  # Bylaws violations
    declaration_violations: List[str] = field(default_factory=list)  # Declaration violations
    architectural_violations: List[str] = field(default_factory=list)  # Architectural violations
    governing_doc_violations: List[str] = field(default_factory=list)  # General governing docs
    
    # Case details
    violation_types: List[str] = field(default_factory=list)
    violation_descriptions: List[str] = field(default_factory=list)
    penalties: List[str] = field(default_factory=list)
    monetary_fines: List[str] = field(default_factory=list)
    compliance_orders: List[str] = field(default_factory=list)
    cease_desist_orders: List[str] = field(default_factory=list)
    
    # Outcomes
    decision_type: str = "unknown"  # final_order, dismissal, settlement, etc.
    ruling: Optional[str] = None  # favor_petitioner, favor_respondent, mixed
    findings_of_fact: List[str] = field(default_factory=list)
    conclusions_of_law: List[str] = field(default_factory=list)
    orders: List[str] = field(default_factory=list)
    remedies_granted: List[str] = field(default_factory=list)
    
    # Document metadata
    document_type: str = "unknown"
    document_subtype: Optional[str] = None
    authority_weight: float = 1.0
    is_primary_authority: bool = False


class ComprehensiveADREProcessor:
    """Enhanced processor for complete ADRE/OAH metadata extraction."""
    
    def __init__(self):
        # Case identification patterns
        self.case_patterns = {
            'oah_docket': [
                r'OAH\s+(?:Docket\s+)?(?:No\.?\s*)?([A-Z0-9\-]+)',
                r'Docket\s+(?:No\.?\s*)?([A-Z0-9\-]+)',
                r'(?:ALJ|Administrative\s+Law\s+Judge)\s+(?:Docket\s+)?(?:No\.?\s*)?([A-Z0-9\-]+)'
            ],
            'adre_case': [
                r'ADRE\s+(?:Case\s+)?(?:No\.?\s*)?([A-Z0-9\-]+)',
                r'Case\s+(?:No\.?\s*)?(\d{2}[A-Z]\-[A-Z]\d+(?:\-REL)?(?:\-RHG)?)',
                r'(?:In\s+)?(?:the\s+)?(?:Matter\s+of\s+)?(?:Case\s+)?(\d{2}[A-Z]\-[A-Z]\d+(?:\-REL)?(?:\-RHG)?)'
            ]
        }
        
        # Party identification patterns
        self.party_patterns = {
            'petitioner': [
                r'(?:Petitioner|Complainant):\s*([A-Z][a-zA-Z\s,\.\']+?)(?:\n|,\s*(?:Respondent|and))',
                r'(?:In\s+the\s+)?(?:Matter\s+of\s+)?([A-Z][a-zA-Z\s,\.\']+?),?\s*(?:Petitioner|Complainant)',
                r'([A-Z][a-zA-Z\s,\.\']+?)\s*(?:v\.?\s*|vs\.?\s*|against)'
            ],
            'respondent': [
                r'(?:Respondent|Defendant):\s*([A-Z][a-zA-Z\s,\.\']+?)(?:\n|$)',
                r'([A-Z][a-zA-Z\s,\.\']+?),?\s*(?:Respondent|Defendant)',
                r'(?:v\.?\s*|vs\.?\s*)([A-Z][a-zA-Z\s,\.\']+?)(?:\n|$)'
            ],
            'hoa': [
                r'([A-Z][a-zA-Z\s]+?)\s+(?:Homeowners?\s+Association|HOA)(?:\s*,?\s*Inc\.?)?',
                r'([A-Z][a-zA-Z\s]+?)\s+(?:Community\s+Association|Condominium\s+Association)',
                r'([A-Z][a-zA-Z\s]+?)\s+(?:Property\s+Owners?\s+Association|POA)'
            ],
            'management': [
                r'([A-Z][a-zA-Z\s]+?)\s+(?:Property\s+)?Management(?:\s+(?:Company|Corp?|LLC|Inc))?',
                r'([A-Z][a-zA-Z\s]+?)\s+(?:Management\s+Services|Mgmt)',
                r'([A-Z][a-zA-Z\s]+?)\s+(?:Community\s+)?Management'
            ]
        }
        
        # Legal representation patterns
        self.attorney_patterns = {
            'petitioner_attorney': [
                r'(?:For\s+(?:the\s+)?Petitioner|Petitioner\s+represented\s+by):\s*([A-Z][a-z]+(?:\s+[A-Z]\.?\s*)?[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
                r'([A-Z][a-z]+(?:\s+[A-Z]\.?\s*)?[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),?\s+(?:Esq\.?,?\s+)?(?:for|representing)\s+(?:the\s+)?Petitioner'
            ],
            'respondent_attorney': [
                r'(?:For\s+(?:the\s+)?Respondent|Respondent\s+represented\s+by):\s*([A-Z][a-z]+(?:\s+[A-Z]\.?\s*)?[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
                r'([A-Z][a-z]+(?:\s+[A-Z]\.?\s*)?[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),?\s+(?:Esq\.?,?\s+)?(?:for|representing)\s+(?:the\s+)?Respondent'
            ],
            'esq_titles': [
                r'([A-Z][a-z]+(?:\s+[A-Z]\.?\s*)?[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),?\s+Esq\.?'
            ],
            'aag': [
                r'([A-Z][a-z]+(?:\s+[A-Z]\.?\s*)?[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),?\s+Assistant\s+Attorney\s+General',
                r'Assistant\s+Attorney\s+General\s*[:.]?\s*([A-Z][a-z]+(?:\s+[A-Z]\.?\s*)?[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)'
            ]
        }
        
        # Judge patterns
        self.judge_patterns = {
            'alj': [
                r'ADMINISTRATIVE\s+LAW\s+JUDGE:\s*([A-Z][a-z]+(?:\s+[A-Z]\.?\s*)?(?:\s+[A-Z][a-z]+)+)',
                r'([A-Z][a-z]+(?:\s+[A-Z]\.?\s*)?(?:\s+[A-Z][a-z]+)+)\s*,?\s*Administrative\s+Law\s+Judge',
                r'Before\s+(?:the\s+Honorable\s+)?([A-Z][a-z]+(?:\s+[A-Z]\.?\s*)?(?:\s+[A-Z][a-z]+)+),?\s+Administrative\s+Law\s+Judge'
            ],
            'judge': [
                r'(?:Judge|Hearing\s+Officer):\s*([A-Z][a-z]+(?:\s+[A-Z]\.?\s*)?(?:\s+[A-Z][a-z]+)+)',
                r'([A-Z][a-z]+(?:\s+[A-Z]\.?\s*)?(?:\s+[A-Z][a-z]+)+),?\s+(?:Judge|Hearing\s+Officer)'
            ]
        }
        
        # Legal violation patterns
        self.violation_patterns = {
            'ars': [
                r'A\.R\.S\.?\s*§?\s*([0-9\-]+(?:\.[0-9A-Z\-]+)*)',
                r'Arizona\s+Revised\s+Statutes?\s*§?\s*([0-9\-]+(?:\.[0-9A-Z\-]+)*)',
                r'(?:Pursuant\s+to\s+|Under\s+|Violat(?:ing|ed?|ion)\s+(?:of\s+)?)?A\.R\.S\.?\s*§?\s*([0-9\-]+(?:\.[0-9A-Z\-]+)*)'
            ],
            'aac': [
                r'A\.A\.C\.?\s*R?([0-9\-]+(?:\.[0-9A-Z\-]+)*)',
                r'Arizona\s+Administrative\s+Code\s*R?([0-9\-]+(?:\.[0-9A-Z\-]+)*)',
                r'(?:Pursuant\s+to\s+|Under\s+|Violat(?:ing|ed?|ion)\s+(?:of\s+)?)?A\.A\.C\.?\s*R?([0-9\-]+(?:\.[0-9A-Z\-]+)*)'
            ]
        }
        
        # HOA document violation patterns
        self.hoa_violation_patterns = {
            'ccr': [
                r'CC&R[s]?\s*(?:Section\s*|§\s*)?([0-9\.]+)?',
                r'(?:Covenants?,?\s*)?Conditions?,?\s*(?:and\s+)?Restrictions?\s*(?:Section\s*|§\s*)?([0-9\.]+)?',
                r'Covenant[s]?\s*(?:Section\s*|§\s*)?([0-9\.]+)?'
            ],
            'bylaws': [
                r'(?:Bylaws?|By-laws?)\s*(?:Section\s*|§\s*)?([0-9\.]+)?',
                r'(?:Corporate\s+)?Bylaws?\s*(?:Section\s*|§\s*)?([0-9\.]+)?'
            ],
            'declaration': [
                r'Declaration\s*(?:Section\s*|§\s*)?([0-9\.]+)?',
                r'Declaration\s+of\s+(?:Covenants?|Restrictions?)\s*(?:Section\s*|§\s*)?([0-9\.]+)?'
            ],
            'architectural': [
                r'Architectural\s+(?:Guidelines?|Standards?|Requirements?|Rules?)\s*(?:Section\s*|§\s*)?([0-9\.]+)?',
                r'Design\s+(?:Guidelines?|Standards?|Requirements?)\s*(?:Section\s*|§\s*)?([0-9\.]+)?'
            ],
            'governing_doc': [
                r'Governing\s+Documents?\s*(?:Section\s*|§\s*)?([0-9\.]+)?',
                r'Community\s+Documents?\s*(?:Section\s*|§\s*)?([0-9\.]+)?'
            ]
        }
        
        # Penalty patterns
        self.penalty_patterns = {
            'monetary_fine': [
                r'(?:fine|penalty|assessment)\s+(?:of\s+)?\$([0-9,]+(?:\.[0-9]{2})?)',
                r'\$([0-9,]+(?:\.[0-9]{2})?)\s+(?:fine|penalty|assessment)',
                r'(?:civil\s+)?(?:money\s+)?penalty\s+(?:of\s+)?\$([0-9,]+(?:\.[0-9]{2})?)'
            ],
            'compliance_order': [
                r'(?:order(?:ed)?|direct(?:ed)?|require[ds]?)\s+(?:to\s+)?(?:comply|bring\s+into\s+compliance)',
                r'compliance\s+(?:order|directive)',
                r'(?:must|shall)\s+(?:comply|bring\s+into\s+compliance)'
            ],
            'cease_desist': [
                r'cease\s+and\s+desist',
                r'stop\s+(?:and\s+)?(?:cease|desist)',
                r'discontinue\s+(?:the\s+)?(?:practice|activity|conduct)'
            ]
        }
        
        # Document type indicators
        self.doc_type_indicators = {
            'final_order': ['FINAL ORDER', 'ORDER AND DECISION', 'DECISION AND ORDER'],
            'findings_of_fact': ['FINDINGS OF FACT', 'FINDINGS AND CONCLUSIONS'],
            'notice_of_hearing': ['NOTICE OF HEARING', 'HEARING NOTICE'],
            'motion': ['MOTION FOR', 'MOTION TO'],
            'complaint': ['COMPLAINT', 'PETITION'],
            'settlement': ['CONSENT ORDER', 'SETTLEMENT AGREEMENT'],
            'dismissal': ['ORDER OF DISMISSAL', 'DISMISSAL'],
            'summary_judgment': ['SUMMARY JUDGMENT', 'MOTION FOR SUMMARY JUDGMENT']
        }
    
    def extract_comprehensive_metadata(self, text: str, filename: str) -> ComprehensiveADRECase:
        """Extract all comprehensive metadata from ADRE/OAH document."""
        case = ComprehensiveADRECase(case_number=self._extract_case_number_from_filename(filename))
        
        # Clean text for processing
        text_clean = re.sub(r'\s+', ' ', text)
        text_lines = text.split('\n')
        
        # Extract case identification
        self._extract_case_info(case, text_clean)
        
        # Extract parties
        self._extract_parties(case, text_clean)
        
        # Extract legal representation
        self._extract_attorneys(case, text, text_clean)
        
        # Extract judicial information
        self._extract_judges(case, text, text_lines)
        
        # Extract legal violations
        self._extract_legal_violations(case, text_clean)
        
        # Extract HOA violations
        self._extract_hoa_violations(case, text_clean)
        
        # Extract penalties and orders
        self._extract_penalties_and_orders(case, text_clean)
        
        # Extract case outcomes
        self._extract_outcomes(case, text)
        
        # Extract dates
        self._extract_dates(case, text)
        
        # Classify document
        self._classify_document(case, text)
        
        return case
    
    def _extract_case_info(self, case: ComprehensiveADRECase, text: str):
        """Extract case identification information."""
        for pattern in self.case_patterns['oah_docket']:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                case.oah_docket = match.group(1)
                break
        
        for pattern in self.case_patterns['adre_case']:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                case.adre_case_no = match.group(1)
                if not case.case_number or case.case_number == case.adre_case_no:
                    case.case_number = match.group(1)
                break
    
    def _extract_parties(self, case: ComprehensiveADRECase, text: str):
        """Extract party information."""
        # Extract petitioner
        for pattern in self.party_patterns['petitioner']:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                name = self._clean_name(match.group(1))
                if self._is_valid_party_name(name):
                    case.petitioner_name = name
                    break
        
        # Extract respondent
        for pattern in self.party_patterns['respondent']:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                name = self._clean_name(match.group(1))
                if self._is_valid_party_name(name):
                    case.respondent_name = name
                    break
        
        # Extract HOA name
        for pattern in self.party_patterns['hoa']:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                hoa_name = self._clean_name(match.group(1))
                if len(hoa_name) > 3:
                    case.hoa_name = hoa_name
                    case.respondent_type = "hoa"
                    if not case.respondent_name:
                        case.respondent_name = f"{hoa_name} Homeowners Association"
                    break
        
        # Extract management company
        for pattern in self.party_patterns['management']:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                mgmt_name = self._clean_name(match.group(1))
                if len(mgmt_name) > 3:
                    case.management_company = mgmt_name
                    if "management" in case.respondent_name.lower() if case.respondent_name else False:
                        case.respondent_type = "management_company"
                    break
    
    def _extract_attorneys(self, case: ComprehensiveADRECase, text: str, text_clean: str):
        """Extract attorney information."""
        # Extract petitioner attorneys
        for pattern in self.attorney_patterns['petitioner_attorney']:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                name = self._clean_name(match.group(1))
                if self._is_valid_attorney_name(name):
                    case.petitioner_attorney = name
                    break
        
        # Extract respondent attorneys
        for pattern in self.attorney_patterns['respondent_attorney']:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                name = self._clean_name(match.group(1))
                if self._is_valid_attorney_name(name):
                    case.respondent_attorney = name
                    break
        
        # Extract all Esq. attorneys
        esq_attorneys = []
        for pattern in self.attorney_patterns['esq_titles']:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                name = self._clean_name(match.group(1))
                if self._is_valid_attorney_name(name):
                    esq_attorneys.append(name)
        
        # If we have Esq. attorneys but no specific role assignment, try to infer
        if esq_attorneys and not case.petitioner_attorney and not case.respondent_attorney:
            if len(esq_attorneys) == 1:
                # Single attorney - likely respondent attorney
                case.respondent_attorney = esq_attorneys[0]
            elif len(esq_attorneys) == 2:
                # Two attorneys - likely one for each side
                case.petitioner_attorney = esq_attorneys[0]
                case.respondent_attorney = esq_attorneys[1]
        
        # Extract Assistant Attorney General
        for pattern in self.attorney_patterns['aag']:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                name = self._clean_name(match.group(1))
                if self._is_valid_attorney_name(name):
                    case.assistant_attorney_general = name
                    if not case.petitioner_attorney:
                        case.petitioner_attorney = name
                    break
        
        # Check for pro se representation
        if re.search(r'(?:appearing\s+)?pro\s+se|self[\-\s]represented', text, re.IGNORECASE):
            if not case.petitioner_attorney:
                case.pro_se_parties.append("petitioner")
            if not case.respondent_attorney:
                case.pro_se_parties.append("respondent")
    
    def _extract_judges(self, case: ComprehensiveADRECase, text: str, text_lines: List[str]):
        """Extract judge information."""
        # Extract Administrative Law Judge
        for pattern in self.judge_patterns['alj']:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                name = self._clean_name(match.group(1))
                if self._is_valid_judge_name(name):
                    case.administrative_law_judge = name
                    case.judge_name = name
                    break
        
        # Extract other judges/hearing officers
        if not case.judge_name:
            for pattern in self.judge_patterns['judge']:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    name = self._clean_name(match.group(1))
                    if self._is_valid_judge_name(name):
                        case.judge_name = name
                        if 'hearing officer' in pattern.lower():
                            case.hearing_officer = name
                        break
    
    def _extract_legal_violations(self, case: ComprehensiveADRECase, text: str):
        """Extract statutory and regulatory violations."""
        # Extract A.R.S. violations
        for pattern in self.violation_patterns['ars']:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                statute = f"A.R.S. § {match.group(1)}"
                if statute not in case.ars_violations:
                    case.ars_violations.append(statute)
                    case.statutes_violated.append(statute)
        
        # Extract A.A.C. violations
        for pattern in self.violation_patterns['aac']:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                regulation = f"A.A.C. R{match.group(1)}"
                if regulation not in case.aac_violations:
                    case.aac_violations.append(regulation)
                    case.statutes_violated.append(regulation)
    
    def _extract_hoa_violations(self, case: ComprehensiveADRECase, text: str):
        """Extract HOA governing document violations."""
        for doc_type, patterns in self.hoa_violation_patterns.items():
            for pattern in patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    section = match.group(1) if match.groups() and match.group(1) else "general"
                    violation = f"{doc_type.upper()} Section {section}" if section != "general" else doc_type.upper()
                    
                    target_list = getattr(case, f"{doc_type}_violations")
                    if violation not in target_list:
                        target_list.append(violation)
                        case.governing_doc_violations.append(violation)
    
    def _extract_penalties_and_orders(self, case: ComprehensiveADRECase, text: str):
        """Extract penalties and compliance orders."""
        # Extract monetary fines
        for pattern in self.penalty_patterns['monetary_fine']:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                amount = match.group(1)
                fine = f"${amount}"
                if fine not in case.monetary_fines:
                    case.monetary_fines.append(fine)
                    case.penalties.append(f"Monetary fine: {fine}")
        
        # Extract compliance orders
        for pattern in self.penalty_patterns['compliance_order']:
            if re.search(pattern, text, re.IGNORECASE):
                compliance = "Compliance order issued"
                if compliance not in case.compliance_orders:
                    case.compliance_orders.append(compliance)
                    case.penalties.append(compliance)
        
        # Extract cease and desist orders
        for pattern in self.penalty_patterns['cease_desist']:
            if re.search(pattern, text, re.IGNORECASE):
                cease_desist = "Cease and desist order"
                if cease_desist not in case.cease_desist_orders:
                    case.cease_desist_orders.append(cease_desist)
                    case.penalties.append(cease_desist)
    
    def _extract_outcomes(self, case: ComprehensiveADRECase, text: str):
        """Extract case outcomes and decisions."""
        # Extract findings of fact
        findings_pattern = r'(?:FINDING|FACT)\s*(?:OF\s+FACT\s*)?#?\s*(\d+)[:\.]?\s*([^.\n]+(?:\.[^.\n]+)*\.)'
        for match in re.finditer(findings_pattern, text, re.IGNORECASE):
            finding = f"Finding {match.group(1)}: {match.group(2).strip()[:200]}"
            case.findings_of_fact.append(finding)
        
        # Extract conclusions of law
        conclusions_pattern = r'(?:CONCLUSION|LAW)\s*(?:OF\s+LAW\s*)?#?\s*(\d+)[:\.]?\s*([^.\n]+(?:\.[^.\n]+)*\.)'
        for match in re.finditer(conclusions_pattern, text, re.IGNORECASE):
            conclusion = f"Conclusion {match.group(1)}: {match.group(2).strip()[:200]}"
            case.conclusions_of_law.append(conclusion)
        
        # Extract orders
        order_patterns = [
            r'IT\s+IS\s+(?:HEREBY\s+)?ORDERED\s+(?:THAT\s+)?([^.]+(?:\.[^.]+)*\.)',
            r'ORDERS?\s*:\s*\n([^.]+(?:\.[^.]+)*\.)',
            r'(?:HEREBY\s+)?ORDERS?\s+(?:AS\s+FOLLOWS\s*:?\s*)?([^.]+(?:\.[^.]+)*\.)'
        ]
        
        for pattern in order_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                order_text = match.group(1).strip()[:300]
                case.orders.append(order_text)
        
        # Determine ruling based on orders and outcomes
        if case.orders or case.penalties:
            if any("dismiss" in order.lower() for order in case.orders):
                case.ruling = "favor_respondent"
            elif case.monetary_fines or case.compliance_orders:
                case.ruling = "favor_petitioner"
            else:
                case.ruling = "mixed"
    
    def _extract_dates(self, case: ComprehensiveADRECase, text: str):
        """Extract relevant dates."""
        from dateutil import parser as date_parser
        
        date_patterns = [
            (r'(?:hearing|heard)\s+on\s+(\w+\s+\d{1,2},?\s+\d{4})', 'hearing'),
            (r'(?:dated?|issued?)\s+(?:this\s+)?(\w+\s+\d{1,2},?\s+\d{4})', 'decision'),
            (r'(?:filed?\s+on\s+|filing\s+date:?\s*)(\w+\s+\d{1,2},?\s+\d{4})', 'filing'),
            (r'(\d{1,2}/\d{1,2}/\d{4})', 'general')
        ]
        
        for pattern, date_type in date_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                try:
                    date_str = match.group(1)
                    parsed_date = date_parser.parse(date_str)
                    
                    if date_type == 'hearing':
                        case.hearing_date = parsed_date
                    elif date_type == 'decision':
                        case.decision_date = parsed_date
                    elif date_type == 'filing':
                        case.filing_date = parsed_date
                    elif date_type == 'general':
                        # Try to determine context
                        context = text[max(0, match.start()-50):match.end()+50].lower()
                        if 'hearing' in context and not case.hearing_date:
                            case.hearing_date = parsed_date
                        elif ('decision' in context or 'order' in context) and not case.decision_date:
                            case.decision_date = parsed_date
                except:
                    continue
    
    def _classify_document(self, case: ComprehensiveADRECase, text: str):
        """Classify document type and set authority weight."""
        text_upper = text.upper()
        
        for doc_type, indicators in self.doc_type_indicators.items():
            for indicator in indicators:
                if indicator in text_upper:
                    case.document_type = doc_type
                    case.decision_type = doc_type
                    break
        
        # Set authority weight based on document type
        if case.document_type in ['final_order', 'decision_and_order']:
            case.authority_weight = 3.0
            case.is_primary_authority = True
        elif case.document_type in ['findings_of_fact', 'conclusions_of_law']:
            case.authority_weight = 2.5
            case.is_primary_authority = True
        elif case.document_type in ['settlement', 'consent_order']:
            case.authority_weight = 2.0
        else:
            case.authority_weight = 1.0
    
    def _extract_case_number_from_filename(self, filename: str) -> str:
        """Extract case number from filename."""
        match = re.search(r'(\d{2}[A-Z]\-[A-Z]\d+(?:\-REL)?(?:\-RHG)?)', filename)
        return match.group(1) if match else filename.replace('.docx', '').replace('.doc', '')
    
    def _clean_name(self, name: str) -> str:
        """Clean and normalize name."""
        name = ' '.join(name.split())
        name = name.rstrip('.,;:')
        return name.title()
    
    def _is_valid_party_name(self, name: str) -> bool:
        """Validate party name."""
        if not name or len(name) < 3:
            return False
        
        invalid_terms = ['respondent', 'petitioner', 'complainant', 'matter', 'case', 'docket']
        return not any(term in name.lower() for term in invalid_terms)
    
    def _is_valid_attorney_name(self, name: str) -> bool:
        """Validate attorney name."""
        if not name or len(name) < 5:
            return False
        
        parts = name.split()
        if len(parts) < 2:
            return False
        
        invalid_terms = ['copy', 'order', 'decision', 'arizona', 'department', 'transmitted']
        return not any(term.lower() in name.lower() for term in invalid_terms)
    
    def _is_valid_judge_name(self, name: str) -> bool:
        """Validate judge name."""
        if not name or len(name) < 5:
            return False
        
        parts = name.split()
        if len(parts) < 2:
            return False
        
        invalid_terms = ['copy', 'order', 'decision', 'arizona', 'department', 'transmitted', 'page']
        return not any(term.lower() in name.lower() for term in invalid_terms)
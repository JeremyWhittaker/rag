"""Enhanced query system with legal-specific understanding and citation resolution."""

from __future__ import annotations
import re
from typing import List, Dict, Optional, Tuple
from datetime import datetime

from langchain.schema import Document
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate
from langchain.callbacks.base import BaseCallbackHandler

from .legal_processor import LegalDocumentProcessor, LegalEntity


class LegalQueryEnhancer:
    """Enhances queries with legal context and understanding."""
    
    def __init__(self):
        self.processor = LegalDocumentProcessor()
        self.legal_abbreviations = {
            'ars': 'Arizona Revised Statutes',
            'aac': 'Arizona Administrative Code',
            'adre': 'Arizona Department of Real Estate',
            'oah': 'Office of Administrative Hearings',
            'cv': 'Civil',
            'frcp': 'Federal Rules of Civil Procedure',
            'azrcp': 'Arizona Rules of Civil Procedure',
        }
        
        # Common legal query patterns
        self.query_patterns = {
            'statute_lookup': [
                r'what\s+(?:does|is)\s+(?:ars|statute|section)\s*§?\s*(\d+[-–]\d+)',
                r'explain\s+(?:ars|statute|section)\s*§?\s*(\d+[-–]\d+)',
                r'(?:ars|statute|section)\s*§?\s*(\d+[-–]\d+)\s+(?:says?|provides?|states?)',
            ],
            'case_lookup': [
                r'what\s+(?:did|was|happened)\s+in\s+([A-Za-z\s]+v\.\s+[A-Za-z\s]+)',
                r'([A-Za-z\s]+v\.\s+[A-Za-z\s]+)\s+(?:held|decided|ruling)',
            ],
            'compliance': [
                r'(?:do|does|did)\s+(?:i|we|they)\s+(?:comply|violate|breach)',
                r'(?:is|was)\s+(?:this|that|it)\s+(?:legal|allowed|permitted|compliant)',
            ],
            'precedent': [
                r'(?:cases?|precedents?|rulings?)\s+(?:about|regarding|on)\s+(.+)',
                r'(?:similar|related)\s+(?:cases?|rulings?)',
            ],
            'deadline': [
                r'(?:when|deadline|time\s+limit|statute\s+of\s+limitations?)\s+(?:for|to)\s+(.+)',
                r'how\s+(?:long|many\s+days?)\s+(?:do|does)\s+(?:i|we)\s+have',
            ]
        }
    
    def enhance_query(self, query: str) -> Dict[str, any]:
        """Enhance query with legal understanding."""
        enhanced = {
            'original_query': query,
            'query_type': self._classify_query(query),
            'extracted_citations': self.processor.extract_citations(query),
            'expanded_terms': self._expand_legal_terms(query),
            'temporal_context': self._extract_temporal_context(query),
        }
        
        # Add specific enhancements based on query type
        if enhanced['query_type'] == 'statute_lookup':
            enhanced['focus'] = 'statutory_interpretation'
        elif enhanced['query_type'] == 'case_lookup':
            enhanced['focus'] = 'case_law_analysis'
        elif enhanced['query_type'] == 'compliance':
            enhanced['focus'] = 'compliance_assessment'
        elif enhanced['query_type'] == 'precedent':
            enhanced['focus'] = 'precedent_search'
        elif enhanced['query_type'] == 'deadline':
            enhanced['focus'] = 'temporal_requirements'
        
        return enhanced
    
    def _classify_query(self, query: str) -> str:
        """Classify the type of legal query."""
        query_lower = query.lower()
        
        for query_type, patterns in self.query_patterns.items():
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    return query_type
        
        # Additional classification based on keywords
        if any(term in query_lower for term in ['statute', 'ars', '§', 'section']):
            return 'statute_lookup'
        elif any(term in query_lower for term in [' v. ', ' v ', 'case', 'ruling']):
            return 'case_lookup'
        elif any(term in query_lower for term in ['comply', 'violation', 'breach', 'legal']):
            return 'compliance'
        elif any(term in query_lower for term in ['similar', 'precedent', 'cases about']):
            return 'precedent'
        elif any(term in query_lower for term in ['deadline', 'time limit', 'how long']):
            return 'deadline'
        
        return 'general'
    
    def _expand_legal_terms(self, query: str) -> List[str]:
        """Expand legal abbreviations and add related terms."""
        expanded_terms = []
        query_lower = query.lower()
        
        # Expand abbreviations
        for abbr, full in self.legal_abbreviations.items():
            if abbr in query_lower:
                expanded_terms.append(full)
        
        # Add related legal concepts
        concept_relations = {
            'breach': ['violation', 'non-compliance', 'failure to comply'],
            'negligence': ['duty of care', 'reasonable care', 'breach of duty'],
            'damages': ['compensation', 'remedies', 'relief'],
            'motion': ['request', 'petition', 'application'],
            'discovery': ['disclosure', 'interrogatories', 'depositions'],
            'summary judgment': ['rule 56', 'no genuine issue', 'material fact'],
        }
        
        for concept, related in concept_relations.items():
            if concept in query_lower:
                expanded_terms.extend(related)
        
        return list(set(expanded_terms))
    
    def _extract_temporal_context(self, query: str) -> Optional[Dict]:
        """Extract temporal context from query."""
        temporal_keywords = {
            'current': 'present',
            'latest': 'most_recent',
            'historical': 'past',
            'before': 'prior_to',
            'after': 'subsequent_to',
            'between': 'date_range',
        }
        
        for keyword, context_type in temporal_keywords.items():
            if keyword in query.lower():
                return {'type': context_type, 'keyword': keyword}
        
        # Check for specific dates
        dates = self.processor.extract_dates(query)
        if dates:
            return {'type': 'specific_dates', 'dates': dates}
        
        return None


class LegalSystemPrompt:
    """Manages system prompts for legal queries."""
    
    @staticmethod
    def get_system_prompt(query_type: str, jurisdiction: str = "Arizona") -> str:
        """Get appropriate system prompt based on query type."""
        base_prompt = f"""You are an expert legal assistant specializing in {jurisdiction} law, 
particularly real estate law, ADRE regulations, and OAH proceedings. You provide accurate, 
well-reasoned legal analysis while being accessible to non-lawyers.

Important guidelines:
1. Always cite specific statutes, cases, or regulations when applicable
2. Explain legal concepts in plain language when needed
3. Distinguish between binding authority and persuasive authority
4. Note any important deadlines or time limits
5. Identify when professional legal counsel should be sought

When analyzing {jurisdiction} law:
- Statutes (A.R.S.) are primary authority
- Arizona Administrative Code (A.A.C.) provides regulatory details
- Case law interprets and applies statutes
- ADRE has specific authority over real estate professionals
- OAH handles administrative hearings

"""
        
        specific_prompts = {
            'statute_lookup': """When explaining statutes:
- Quote the relevant text exactly
- Explain the plain meaning
- Note any defined terms
- Identify related statutes or regulations
- Mention relevant case law interpretations""",
            
            'case_lookup': """When analyzing cases:
- State the holding clearly
- Explain the facts that led to the decision
- Identify the legal principles applied
- Note if it's binding precedent
- Mention any dissenting opinions if significant""",
            
            'compliance': """When assessing compliance:
- Identify all applicable laws and regulations
- Analyze each requirement separately
- Note any exceptions or defenses
- Suggest remedial actions if non-compliant
- Identify potential penalties or consequences""",
            
            'precedent': """When searching for precedent:
- Focus on factually similar cases
- Prioritize binding authority
- Note distinguishing factors
- Explain the legal principles that transfer
- Mention trends in recent decisions""",
            
            'deadline': """When discussing deadlines:
- State the specific time limit clearly
- Identify what triggers the deadline
- Note any exceptions or extensions
- Explain consequences of missing the deadline
- Mention any notice requirements""",
            
            'general': """Provide comprehensive legal analysis:
- Identify the legal issues
- Research applicable law
- Apply law to facts
- Reach reasoned conclusions
- Suggest next steps""",
        }
        
        return base_prompt + "\n\n" + specific_prompts.get(query_type, specific_prompts['general'])


class LegalCallbackHandler(BaseCallbackHandler):
    """Callback handler for legal query processing."""
    
    def __init__(self):
        self.citations_found = []
        self.legal_terms = []
    
    def on_llm_start(self, serialized: Dict[str, any], prompts: List[str], **kwargs):
        """Log when LLM starts processing."""
        print("🔍 Analyzing legal query...")
    
    def on_llm_end(self, response, **kwargs):
        """Process LLM response for citations."""
        text = str(response)
        processor = LegalDocumentProcessor()
        citations = processor.extract_citations(text)
        
        for citation_type, citation_list in citations.items():
            if citation_list:
                self.citations_found.extend(citation_list)
        
        if self.citations_found:
            print(f"📚 Found {len(self.citations_found)} legal citations")


def create_legal_prompt_template(query_type: str) -> ChatPromptTemplate:
    """Create a prompt template for legal queries."""
    system_prompt = LegalSystemPrompt.get_system_prompt(query_type)
    
    messages = [
        SystemMessagePromptTemplate.from_template(system_prompt),
        ("human", """Context from relevant documents:
{context}

Legal Question: {input}

Additional Instructions:
- {focus}
- Consider any expanded terms: {expanded_terms}
- Query type: {query_type}

Please provide a thorough legal analysis.""")
    ]
    
    return ChatPromptTemplate.from_messages(messages)
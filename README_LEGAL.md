# Legal RAG Assistant - Enhanced Features

This document describes the legal-specific enhancements added to the RAG system for ADRE/OAH case analysis.

## 🎯 Key Features

### 1. **Legal Document Processing**
- **Automatic Classification**: Identifies document types (statute, case, motion, order, etc.)
- **Citation Extraction**: Extracts Arizona statutes (A.R.S.), cases, regulations (A.A.C.), and ADRE/OAH references
- **Party Identification**: Extracts plaintiff, defendant, appellant names
- **Date Extraction**: Identifies filing dates, decision dates, deadlines
- **Hierarchical Chunking**: Prioritizes legal holdings and statute quotes

### 2. **Legal Query Understanding**
- **Query Classification**: Identifies query types (statute lookup, case analysis, compliance check, etc.)
- **Term Expansion**: Expands legal abbreviations and adds related concepts
- **Temporal Context**: Understands time-based queries (current law, historical cases)
- **Authority Hierarchy**: Weights statutes > regulations > cases > other documents

### 3. **Citation Resolution**
- **Cross-Reference**: Resolves citations to actual documents in your index
- **Citation Graph**: Builds relationships between documents
- **Reverse Lookup**: Find all documents citing a specific statute or case

### 4. **Metadata Management**
- **Comprehensive Tracking**: Stores document type, jurisdiction, court level, parties, dates
- **ADRE-Specific**: Tracks license numbers, violation types, penalties
- **Search by Metadata**: Find documents by case number, date range, violation type

## 📁 New Files Created

1. **`src/legal_processor.py`**: Core legal document processing and citation extraction
2. **`src/legal_query.py`**: Query enhancement and legal-specific prompts
3. **`src/legal_metadata.py`**: Metadata extraction and indexing
4. **`src/citation_resolver.py`**: Citation resolution and cross-referencing
5. **`src/legal_server.py`**: Enhanced API with legal endpoints

## 🚀 Usage Examples

### Ingesting Legal Documents

```bash
# Ingest statutes with legal processing
python -m src.ingest --pdf-dir ~/legal/arizona_statutes --project statutes

# Ingest ADRE cases
python -m src.ingest --pdf-dir ~/legal/adre_cases --project adre_cases

# Ingest OAH decisions
python -m src.ingest --pdf-dir ~/legal/oah_decisions --project oah_decisions

# Disable legal processing if needed
python -m src.ingest --pdf-dir ~/general_docs --project general --disable-legal
```

### Querying with Legal Enhancements

```bash
# Query with legal understanding
python -m src.query "What does A.R.S. § 32-2153 say about disclosure requirements?" \
    --projects statutes adre_cases

# Query with verbose output showing analysis
python -m src.query "Has anyone successfully appealed an ADRE license revocation?" \
    --projects adre_cases oah_decisions --verbose

# Query without authority hierarchy
python -m src.query "Find all mentions of trust account violations" \
    --projects adre_cases --no-hierarchy
```

### Using the Enhanced API

Start the legal server:
```bash
uvicorn src.legal_server:app --host 0.0.0.0 --port 8000
```

#### API Endpoints:

1. **Legal Query** (POST `/legal-query`):
```json
{
  "question": "What are the penalties for misrepresentation under Arizona real estate law?",
  "projects": ["statutes", "adre_cases"],
  "enable_hierarchy": true,
  "include_citations": true,
  "verbose": true
}
```

2. **Citation Lookup** (POST `/citation-lookup`):
```json
{
  "citation": "A.R.S. § 32-2153",
  "projects": ["statutes", "adre_cases"],
  "include_citing_docs": true
}
```

3. **Metadata Search** (POST `/metadata-search`):
```json
{
  "project": "adre_cases",
  "document_type": "adre_order",
  "violation_type": "misrepresentation",
  "date_from": "2020-01-01"
}
```

4. **Project Statistics** (GET `/statistics/{project}`):
```
GET /statistics/adre_cases
```

## 🏛️ Legal Authority Hierarchy

The system automatically weights documents by authority level:

1. **Statutes (A.R.S.)** - Weight: 10 (highest)
2. **Regulations (A.A.C.)** - Weight: 9
3. **Supreme Court** - Weight: 8
4. **Appeals Court** - Weight: 7
5. **ADRE Orders** - Weight: 6
6. **Superior Court** - Weight: 5
7. **Other Documents** - Weight: 1-4

## 📊 Query Types and Handling

### Statute Lookup
- Extracts exact statute text
- Explains plain meaning
- Links to interpreting cases

### Case Analysis
- Identifies holdings
- Extracts key facts
- Notes precedential value

### Compliance Assessment
- Lists applicable laws
- Analyzes requirements
- Suggests remedial actions

### Precedent Search
- Finds factually similar cases
- Prioritizes binding authority
- Identifies trends

### Deadline Queries
- States specific time limits
- Identifies triggers
- Notes exceptions

## 🔍 Advanced Features

### Smart Citation Enhancement
When citations are found in responses, the system:
- Adds reference markers [1], [2], etc.
- Resolves to source documents
- Provides relevant excerpts

### Legal Prompt Engineering
System prompts are tailored for:
- Arizona jurisdiction expertise
- Plain language explanations
- Professional legal analysis
- Appropriate disclaimers

### Metadata-Driven Search
Search documents by:
- Case numbers
- Filing dates
- Violation types
- Penalties imposed
- Judge/Commissioner

## 💡 Tips for Best Results

1. **Project Organization**: Keep statutes, regulations, and cases in separate projects
2. **Naming Convention**: Use descriptive project names (e.g., "ars_title_32", "adre_2023_cases")
3. **Query Specificity**: Include statute numbers, case names, or specific legal terms
4. **Authority Hierarchy**: Let the system prioritize statutes over cases for legal requirements
5. **Regular Updates**: Re-ingest when new cases or statute amendments are available

## 🚧 Future Enhancements

Consider adding:
- Shepardizing (tracking case treatment)
- Timeline visualization
- Conflict detection between sources
- Legal brief generation
- Deadline calculator
- Form filling assistance
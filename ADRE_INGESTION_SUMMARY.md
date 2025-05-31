# ADRE Decisions Ingestion Summary

## What's Happening
- Successfully ingesting 250 ADRE decision documents from `/home/shared/projects/azoah/adre_decisions_downloads`
- Created 19,935 text chunks (800 tokens each with 120 token overlap)
- Currently embedding these chunks using OpenAI's text-embedding-3-large model
- Progress is logged to `adre_ingest.log`

## Issues Fixed
1. **iso639 Language Detection**: The unstructured library had issues with language detection. We worked around this by:
   - Using python-docx as a fallback for DOCX parsing
   - The documents are still being processed successfully

2. **Chroma Persistence**: Updated code to use the new langchain-chroma API (removed deprecated persist() calls)

## What's Been Created

### 1. Legal Document Processing System
- **Citation Extraction**: Automatically extracts A.R.S. statutes, case references, A.A.C. regulations, and ADRE/OAH case numbers
- **Metadata Extraction**: Captures case numbers, parties, judges, dates, violation types, and penalties
- **Document Classification**: Identifies document types (order, motion, brief, etc.)
- **Authority Hierarchy**: Weights statutes > regulations > cases for legal accuracy

### 2. Enhanced Query System  
- **Legal Query Understanding**: Classifies queries (statute lookup, case analysis, compliance check, etc.)
- **Smart Prompting**: Uses Arizona-specific legal knowledge in responses
- **Citation Resolution**: Can find and cross-reference cited documents
- **Source Attribution**: Shows which documents were used for each answer

### 3. New API Endpoints (via legal_server.py)
- `/legal-query`: Advanced legal queries with citation resolution
- `/citation-lookup`: Look up specific statutes or cases
- `/metadata-search`: Search by case number, date, violation type
- `/statistics/{project}`: Get index statistics

## Estimated Completion Time
Based on the embedding rate (~1-2 seconds per 100 chunks), the full ingestion should complete in approximately 5-10 minutes.

## Next Steps

1. **Monitor Progress**:
   ```bash
   tail -f adre_ingest.log
   ```

2. **Once Complete, Test Queries**:
   ```bash
   # Basic query
   python -m src.query "What are common trust account violations?" --projects adre_decisions

   # Detailed query with metadata
   python -m src.query "Show me cases where licenses were revoked for fraud" --projects adre_decisions --verbose
   ```

3. **Use the Legal API**:
   ```bash
   # Start server
   python -m src.legal_server

   # Query via API
   curl -X POST http://localhost:8000/legal-query \
     -H "Content-Type: application/json" \
     -d '{
       "question": "What penalties has ADRE imposed for unlicensed activity?",
       "projects": ["adre_decisions"],
       "include_citations": true
     }'
   ```

4. **Search by Metadata**:
   ```bash
   curl -X POST http://localhost:8000/metadata-search \
     -H "Content-Type: application/json" \
     -d '{
       "project": "adre_decisions",
       "violation_type": "misrepresentation",
       "date_from": "2020-01-01"
     }'
   ```

## Legal Query Examples

1. **Statute Analysis**: "What does A.R.S. § 32-2153 require for trust account management?"
2. **Case Precedent**: "Find cases where ADRE revoked licenses for commingling funds"
3. **Compliance Check**: "Does keeping earnest money in a business account violate ADRE rules?"
4. **Penalty Research**: "What are typical penalties for first-time disclosure violations?"
5. **Timeline Questions**: "What is the deadline to respond to an ADRE complaint?"

## Tips for Best Results

1. **Be Specific**: Include case numbers, statute references, or specific violation types
2. **Use Legal Terms**: The system understands terms like "commingling", "fiduciary duty", "disclosure"
3. **Ask About Patterns**: "What factors lead to license revocation vs suspension?"
4. **Request Analysis**: "Compare penalties for trust account vs advertising violations"

## Troubleshooting

If queries aren't returning good results:
1. Check if ingestion completed: `ls -la index/adre_decisions/`
2. Verify document count: `sqlite3 index/adre_decisions/chroma.sqlite3 "SELECT COUNT(*) FROM embeddings;"`
3. Check metadata index: `cat index/adre_decisions/metadata_index.json | jq . | head`

The system is now building a comprehensive legal knowledge base from your ADRE decisions!
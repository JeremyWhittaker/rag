#!/usr/bin/env python3
"""Enhanced ingestion with comprehensive metadata extraction."""

import argparse
import hashlib
import json
import logging
import shutil
from pathlib import Path
from typing import List, Optional, Dict, Any

import chromadb
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings

from src.config import CHROMA_DB_PATH, OPENAI_API_KEY, PROJECT_ROOT
from src.logger import setup_logger
from src.legal_processor import LegalDocumentProcessor
from src.legal_metadata import LegalMetadataExtractor, MetadataIndex
from src.comprehensive_processor import ComprehensiveADREProcessor

# Setup logging
LOGGER = setup_logger(__name__)

def load_pdf(path: Path) -> List[str]:
    """Load PDF and return text chunks."""
    try:
        from unstructured.partition.pdf import partition_pdf
        elements = partition_pdf(filename=str(path))
        return [el.text for el in elements if el.text and not el.text.isspace()]
    except Exception as e:
        LOGGER.error(f"Error loading PDF {path}: {e}")
        return []

def ingest_document_comprehensive(
    path: Path,
    chroma_client: chromadb.Client,
    collection_name: str,
    embeddings: OpenAIEmbeddings,
    legal_processor: LegalDocumentProcessor,
    metadata_extractor: LegalMetadataExtractor,
    metadata_index: MetadataIndex,
    comprehensive_processor: ComprehensiveADREProcessor,
    enable_legal_processing: bool = True,
    enable_comprehensive_processing: bool = True
) -> bool:
    """Ingest a single document with comprehensive metadata extraction."""
    
    try:
        LOGGER.info(f"Processing {path.name}...")
        
        # Calculate file hash
        with open(path, 'rb') as f:
            digest = hashlib.sha256(f.read()).hexdigest()
        
        # Check if already processed
        collection = chroma_client.get_collection(collection_name)
        existing = collection.get(where={"sha256": digest})
        if existing['ids']:
            LOGGER.info(f"Skipping {path.name} (already processed)")
            return True
        
        # Load document text
        if path.suffix.lower() == ".pdf":
            texts = load_pdf(path)
        else:  # .docx / .doc
            try:
                from unstructured.partition.docx import partition_docx
                elements = partition_docx(
                    filename=str(path),
                    metadata_filename=None,
                    include_metadata=False
                )
                texts = [el.text for el in elements if el.text and not el.text.isspace()]
            except Exception as e:
                LOGGER.warning(f"Error loading {path} with unstructured: {e}")
                try:
                    import docx
                    doc = docx.Document(str(path))
                    texts = [para.text for para in doc.paragraphs if para.text and not para.text.isspace()]
                except Exception as e2:
                    LOGGER.error(f"Failed to load {path} with both methods: {e2}")
                    return False
        
        if not texts:
            LOGGER.warning(f"No text extracted from {path}")
            return False
        
        # Combine all text
        full_text = "\n".join(texts)
        
        # Base metadata
        base_metadata = {"source": path.name, "sha256": digest}
        
        # Comprehensive ADRE processing
        comprehensive_case = None
        if enable_comprehensive_processing:
            try:
                comprehensive_case = comprehensive_processor.extract_comprehensive_metadata(full_text, path.name)
                LOGGER.info(f"Comprehensive extraction completed for {path.name}")
                
                # Add comprehensive metadata to base metadata
                base_metadata.update({
                    "case_number": comprehensive_case.case_number,
                    "oah_docket": comprehensive_case.oah_docket,
                    "adre_case_no": comprehensive_case.adre_case_no,
                    "petitioner_name": comprehensive_case.petitioner_name,
                    "respondent_name": comprehensive_case.respondent_name,
                    "hoa_name": comprehensive_case.hoa_name,
                    "management_company": comprehensive_case.management_company,
                    "petitioner_attorney": comprehensive_case.petitioner_attorney,
                    "respondent_attorney": comprehensive_case.respondent_attorney,
                    "judge_name": comprehensive_case.judge_name,
                    "administrative_law_judge": comprehensive_case.administrative_law_judge,
                    "document_type": comprehensive_case.document_type,
                    "decision_type": comprehensive_case.decision_type,
                    "ruling": comprehensive_case.ruling,
                    "authority_weight": comprehensive_case.authority_weight,
                    "is_primary_authority": comprehensive_case.is_primary_authority,
                    "ars_violations": comprehensive_case.ars_violations,
                    "aac_violations": comprehensive_case.aac_violations,
                    "ccr_violations": comprehensive_case.ccr_violations,
                    "bylaws_violations": comprehensive_case.bylaws_violations,
                    "penalties": comprehensive_case.penalties,
                    "monetary_fines": comprehensive_case.monetary_fines,
                    "pro_se_parties": comprehensive_case.pro_se_parties,
                    "violation_types": comprehensive_case.violation_types
                })
                
                # Add date fields if available
                if comprehensive_case.hearing_date:
                    base_metadata["hearing_date"] = comprehensive_case.hearing_date.isoformat()
                if comprehensive_case.decision_date:
                    base_metadata["decision_date"] = comprehensive_case.decision_date.isoformat()
                
            except Exception as e:
                LOGGER.error(f"Comprehensive processing failed for {path.name}: {e}")
                comprehensive_case = None
        
        # Legacy legal processing (for compatibility)
        if enable_legal_processing and full_text:
            try:
                doc_info = legal_processor.classify_document(full_text, path.name)
                legal_metadata = metadata_extractor.extract_from_text(
                    full_text, path, digest, doc_info
                )
                metadata_index.add_document(legal_metadata)
                
                # Add legacy metadata if not already present
                if "document_type" not in base_metadata:
                    base_metadata.update({
                        "document_type": legal_metadata.document_type,
                        "authority_weight": legal_metadata.authority_weight,
                        "is_primary_authority": legal_metadata.is_primary_authority,
                        "case_number": legal_metadata.case_number,
                        "jurisdiction": legal_metadata.jurisdiction,
                    })
                    
            except Exception as e:
                LOGGER.error(f"Legacy legal processing failed for {path.name}: {e}")
        
        # Create chunks with enhanced metadata
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
            separators=["\n\n", "\n", ". ", "! ", "? ", " ", ""]
        )
        
        chunks = text_splitter.split_text(full_text)
        
        # Create documents with comprehensive metadata
        documents = []
        metadatas = []
        ids = []
        
        for i, chunk in enumerate(chunks):
            chunk_id = f"{path.stem}_{i}"
            chunk_metadata = base_metadata.copy()
            chunk_metadata.update({
                "chunk_index": i,
                "total_chunks": len(chunks)
            })
            
            # Add priority chunks for important information
            if comprehensive_case:
                chunk_lower = chunk.lower()
                
                # Boost chunks with key information
                if any(term in chunk_lower for term in ['order', 'finding', 'conclusion', 'violation']):
                    chunk_metadata["chunk_priority"] = "high"
                elif any(term in chunk_lower for term in ['attorney', 'esq', 'judge', 'hearing']):
                    chunk_metadata["chunk_priority"] = "medium"
                else:
                    chunk_metadata["chunk_priority"] = "normal"
            
            documents.append(chunk)
            metadatas.append(chunk_metadata)
            ids.append(chunk_id)
        
        # Add to collection
        collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        
        LOGGER.info(f"Successfully ingested {path.name} with {len(chunks)} chunks")
        
        # Log comprehensive extraction summary
        if comprehensive_case:
            summary = {
                "case_number": comprehensive_case.case_number,
                "parties": f"{comprehensive_case.petitioner_name} v. {comprehensive_case.respondent_name}",
                "judge": comprehensive_case.judge_name,
                "attorneys": {
                    "petitioner": comprehensive_case.petitioner_attorney,
                    "respondent": comprehensive_case.respondent_attorney
                },
                "violations": {
                    "ars": len(comprehensive_case.ars_violations),
                    "aac": len(comprehensive_case.aac_violations),
                    "ccr": len(comprehensive_case.ccr_violations),
                    "bylaws": len(comprehensive_case.bylaws_violations)
                },
                "penalties": len(comprehensive_case.penalties)
            }
            LOGGER.info(f"Comprehensive metadata for {path.name}: {json.dumps(summary, indent=2)}")
        
        return True
        
    except Exception as e:
        LOGGER.error(f"Error processing {path}: {e}")
        return False

def ingest_directory_comprehensive(
    directory: Path,
    project_name: str,
    enable_legal_processing: bool = True,
    enable_comprehensive_processing: bool = True,
    reset_collection: bool = False
) -> None:
    """Ingest all documents in directory with comprehensive processing."""
    
    if not directory.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")
    
    # Initialize components
    embeddings = OpenAIEmbeddings(
        model="text-embedding-3-large",
        openai_api_key=OPENAI_API_KEY
    )
    
    chroma_client = chromadb.PersistentClient(path=str(CHROMA_DB_PATH))
    
    # Handle collection reset
    if reset_collection:
        try:
            chroma_client.delete_collection(project_name)
            LOGGER.info(f"Deleted existing collection: {project_name}")
        except Exception:
            pass
    
    # Create or get collection
    try:
        collection = chroma_client.create_collection(
            name=project_name,
            embedding_function=chromadb.utils.embedding_functions.OpenAIEmbeddingFunction(
                api_key=OPENAI_API_KEY,
                model_name="text-embedding-3-large"
            )
        )
        LOGGER.info(f"Created new collection: {project_name}")
    except Exception:
        collection = chroma_client.get_collection(project_name)
        LOGGER.info(f"Using existing collection: {project_name}")
    
    # Initialize processors
    legal_processor = LegalDocumentProcessor()
    metadata_extractor = LegalMetadataExtractor()
    metadata_index = MetadataIndex(PROJECT_ROOT / "metadata" / f"{project_name}_metadata.json")
    comprehensive_processor = ComprehensiveADREProcessor()
    
    # Find all documents
    doc_files = []
    for pattern in ["*.pdf", "*.docx", "*.doc"]:
        doc_files.extend(directory.glob(pattern))
    
    LOGGER.info(f"Found {len(doc_files)} documents to process")
    
    # Process documents
    success_count = 0
    error_count = 0
    
    for doc_file in doc_files:
        try:
            success = ingest_document_comprehensive(
                doc_file,
                chroma_client,
                project_name,
                embeddings,
                legal_processor,
                metadata_extractor,
                metadata_index,
                comprehensive_processor,
                enable_legal_processing,
                enable_comprehensive_processing
            )
            
            if success:
                success_count += 1
            else:
                error_count += 1
                
        except Exception as e:
            LOGGER.error(f"Failed to process {doc_file}: {e}")
            error_count += 1
    
    # Save metadata index
    metadata_index.save()
    
    # Final summary
    LOGGER.info(f"Ingestion complete:")
    LOGGER.info(f"  Successfully processed: {success_count}")
    LOGGER.info(f"  Errors: {error_count}")
    LOGGER.info(f"  Collection: {project_name}")
    
    # Generate ingestion report
    report = {
        "project_name": project_name,
        "directory": str(directory),
        "total_files": len(doc_files),
        "successful": success_count,
        "errors": error_count,
        "comprehensive_processing": enable_comprehensive_processing,
        "legal_processing": enable_legal_processing
    }
    
    report_file = PROJECT_ROOT / f"ingestion_report_{project_name}.json"
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)
    
    LOGGER.info(f"Ingestion report saved to: {report_file}")

def main():
    """Main ingestion function."""
    parser = argparse.ArgumentParser(description="Enhanced document ingestion with comprehensive metadata")
    parser.add_argument("directory", type=Path, help="Directory containing documents to ingest")
    parser.add_argument("project_name", help="Name for the project/collection")
    parser.add_argument("--reset", action="store_true", help="Reset the collection before ingesting")
    parser.add_argument("--no-legal", action="store_true", help="Disable legacy legal processing")
    parser.add_argument("--no-comprehensive", action="store_true", help="Disable comprehensive processing")
    
    args = parser.parse_args()
    
    # Validate directory
    if not args.directory.exists():
        LOGGER.error(f"Directory does not exist: {args.directory}")
        return 1
    
    # Run ingestion
    try:
        ingest_directory_comprehensive(
            directory=args.directory,
            project_name=args.project_name,
            enable_legal_processing=not args.no_legal,
            enable_comprehensive_processing=not args.no_comprehensive,
            reset_collection=args.reset
        )
        LOGGER.info("Enhanced ingestion completed successfully!")
        return 0
        
    except Exception as e:
        LOGGER.error(f"Ingestion failed: {e}")
        return 1

if __name__ == "__main__":
    exit(main())
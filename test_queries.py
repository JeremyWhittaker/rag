#!/usr/bin/env python3
"""Test queries for ADRE decisions database."""

from src.query import main
import sys
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from src.config import EMBED_MODEL, INDEX_DIR
from src.legal_metadata import MetadataIndex
import json

def test_judge_names():
    """Query to find all OAH judges mentioned in the decisions."""
    print("\n=== TEST 1: Finding OAH Judge Names ===")
    
    # Check metadata index for judges
    try:
        metadata_index = MetadataIndex(INDEX_DIR / "adre_decisions_complete")
        all_judges = set()
        
        for sha256, metadata in metadata_index.index.items():
            if metadata.judge:
                all_judges.add(metadata.judge)
        
        if all_judges:
            print(f"\nJudges found in metadata index:")
            for judge in sorted(all_judges):
                print(f"  - {judge}")
        else:
            print("\nNo judges found in metadata index.")
    except Exception as e:
        print(f"Could not read metadata index: {e}")
    
    # Run query
    print("\nRunning query for OAH judges...")
    old_argv = sys.argv
    sys.argv = ["query", "List all the names of OAH judges mentioned in these decisions", 
                "--projects", "adre_decisions_complete", "--verbose"]
    try:
        main()
    except Exception as e:
        print(f"Query error: {e}")
    finally:
        sys.argv = old_argv

def test_homeowner_wins():
    """Query to analyze homeowner vs HOA outcomes."""
    print("\n\n=== TEST 2: Homeowner vs HOA Win Analysis ===")
    
    # Run query
    print("\nRunning query for homeowner vs HOA outcomes...")
    old_argv = sys.argv
    sys.argv = ["query", 
                "Analyze the cases: How many times did the homeowner win versus the HOA? Provide specific case numbers and outcomes.",
                "--projects", "adre_decisions_complete", "--verbose"]
    try:
        main()
    except Exception as e:
        print(f"Query error: {e}")
    finally:
        sys.argv = old_argv

def check_index_status():
    """Check the status of the ADRE decisions index."""
    print("\n=== INDEX STATUS CHECK ===")
    
    try:
        db = Chroma(
            persist_directory=str(INDEX_DIR / "adre_decisions_complete"),
            collection_name="adre_decisions_complete",
            embedding_function=OpenAIEmbeddings(model=EMBED_MODEL),
        )
        count = db._collection.count()
        print(f"Total documents in index: {count}")
        
        # Sample a few documents
        sample = db.get(limit=3)
        if sample and sample["documents"]:
            print("\nSample documents:")
            for i, (doc, meta) in enumerate(zip(sample["documents"], sample["metadatas"])):
                print(f"\n{i+1}. Source: {meta.get('source', 'Unknown')}")
                print(f"   Type: {meta.get('document_type', 'Unknown')}")
                print(f"   Case: {meta.get('case_number', 'N/A')}")
                print(f"   Content preview: {doc[:200]}...")
    except Exception as e:
        print(f"Could not check index: {e}")

if __name__ == "__main__":
    import time
    
    # First check if index exists
    check_index_status()
    
    # If index exists, run tests
    db_path = INDEX_DIR / "adre_decisions_complete" / "chroma.sqlite3"
    if db_path.exists():
        time.sleep(1)
        test_judge_names()
        time.sleep(1)
        test_homeowner_wins()
    else:
        print("\nIndex not yet created. Waiting for ingestion to complete...")
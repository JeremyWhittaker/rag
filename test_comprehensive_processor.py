#!/usr/bin/env python3
"""Test the comprehensive processor on sample documents."""

import json
from pathlib import Path
import docx
from src.comprehensive_processor import ComprehensiveADREProcessor

def test_comprehensive_extraction():
    """Test comprehensive metadata extraction on sample documents."""
    print("TESTING COMPREHENSIVE ADRE PROCESSOR")
    print("=" * 60)
    
    processor = ComprehensiveADREProcessor()
    case_dir = Path("../azoah/adre_decisions_downloads")
    
    # Test on 3 sample documents
    sample_files = list(case_dir.glob("*.docx"))[:3]
    
    for file_path in sample_files:
        print(f"\nProcessing: {file_path.name}")
        print("-" * 40)
        
        try:
            # Read document
            doc = docx.Document(str(file_path))
            text = "\n".join([para.text for para in doc.paragraphs])
            
            # Extract comprehensive metadata
            case = processor.extract_comprehensive_metadata(text, file_path.name)
            
            # Display results
            print(f"Case Number: {case.case_number}")
            print(f"OAH Docket: {case.oah_docket}")
            print(f"ADRE Case: {case.adre_case_no}")
            print(f"Document Type: {case.document_type}")
            
            print(f"\nParties:")
            print(f"  Petitioner: {case.petitioner_name}")
            print(f"  Respondent: {case.respondent_name}")
            print(f"  HOA: {case.hoa_name}")
            print(f"  Management: {case.management_company}")
            
            print(f"\nLegal Representation:")
            print(f"  Petitioner Attorney: {case.petitioner_attorney}")
            print(f"  Respondent Attorney: {case.respondent_attorney}")
            print(f"  Assistant AG: {case.assistant_attorney_general}")
            print(f"  Pro Se: {case.pro_se_parties}")
            
            print(f"\nJudicial:")
            print(f"  Judge: {case.judge_name}")
            print(f"  ALJ: {case.administrative_law_judge}")
            
            print(f"\nViolations:")
            print(f"  A.R.S.: {len(case.ars_violations)} ({case.ars_violations[:2]})")
            print(f"  A.A.C.: {len(case.aac_violations)} ({case.aac_violations[:2]})")
            print(f"  CC&Rs: {len(case.ccr_violations)} ({case.ccr_violations[:2]})")
            print(f"  Bylaws: {len(case.bylaws_violations)} ({case.bylaws_violations[:2]})")
            
            print(f"\nPenalties/Orders:")
            print(f"  Penalties: {len(case.penalties)}")
            print(f"  Fines: {case.monetary_fines}")
            print(f"  Compliance Orders: {len(case.compliance_orders)}")
            
            print(f"\nOutcome:")
            print(f"  Ruling: {case.ruling}")
            print(f"  Authority Weight: {case.authority_weight}")
            
            print(f"\nDates:")
            print(f"  Hearing: {case.hearing_date}")
            print(f"  Decision: {case.decision_date}")
            
        except Exception as e:
            print(f"Error processing {file_path.name}: {e}")
    
    print(f"\n✓ Comprehensive processor test complete!")

if __name__ == "__main__":
    test_comprehensive_extraction()
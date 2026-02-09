"""Test script to demonstrate state-level credential filtering."""

import pandas as pd
from app.services.credential_service import CredentialService
from app.services.classification_service import ClassificationService
from app.services.data_extraction_service import DataExtractionService


def test_state_filtering():
    """Test the state-level credential filtering functionality."""
    
    print("="*80)
    print("STATE-LEVEL CREDENTIAL FILTERING TEST")
    print("="*80)
    
    # Test configuration
    csv_path = "app/tables/Extract_syneos_GSK_20260131000000.csv"
    mapping_file = "PossibleNames_to_Credential_Mapping.xlsx"
    
    # Sample expense ID from the concur file
    expense_id = "gWin$pt80e0DhaqIUyNyIgqtmbOu8$pYY3jtg"  # From Pennsylvania data
    
    print(f"\n1. Loading data for expense: {expense_id}")
    print("-" * 80)
    
    # Initialize services
    data_service = DataExtractionService(csv_path)
    
    # NOTE: In actual workflow, company_id is extracted from OCR results:
    #   ocr_results = gemini_client.process_ocr(prompt, processed_image)
    #   company_id = data_service.extract_company_id_from_ocr(ocr_results)
    # The LLM identifies company from signin sheet header (GSK=1, AstraZeneca=2, Lilly=3)
    # For this test, we'll use the default company_id
    company_id = 1  # Simulating GSK
    
    print(f"\n2. Using company_id: {company_id} (normally extracted from OCR)")
    print("-" * 80)
    
    # Step 2: Get venue state for the expense
    print("\n3. Extracting venue state...")
    print("-" * 80)
    venue_state = data_service.get_venue_state(expense_id)
    
    if not venue_state:
        print("[ERROR] Could not extract venue state. Exiting.")
        return
    
    print(f"✓ Venue State: {venue_state}")
    
    # Step 3: Get state-specific credential IDs from database
    print("\n4. Querying database for state-specific credentials...")
    print("-" * 80)
    
    with CredentialService() as credential_service:
        valid_credential_ids = credential_service.get_state_specific_credential_ids(
            venue_state=venue_state,
            company_id=company_id
        )
    
    if not valid_credential_ids:
        print(f"[WARN] No credentials found for state '{venue_state}' and company_id={company_id}")
        print("Classification will proceed without state filtering.")
    else:
        print(f"✓ Found {len(valid_credential_ids)} valid credential IDs")
        print(f"  Sample IDs: {valid_credential_ids[:5]}")
    
    # Step 4: Initialize classification service with company filter
    print("\n5. Initializing classification service...")
    print("-" * 80)
    
    classifier = ClassificationService(
        mapping_file=mapping_file,
        company_id=company_id,
        fuzzy_threshold=80
    )
    
    print(f"✓ Initial mappings loaded: {len(classifier.mapping_df)} records")
    
    # Step 5: Apply state-level filtering
    if valid_credential_ids:
        print("\n6. Applying state-level filtering...")
        print("-" * 80)
        
        classifier.filter_by_state_credentials(
            valid_credential_ids=valid_credential_ids,
            company_id=company_id
        )
        
        print(f"\n✓ After state filtering: {len(classifier.mapping_df)} records remain")
        
        # Show sample of remaining credentials
        if not classifier.mapping_df.empty:
            print("\nSample of state-valid credentials:")
            unique_creds = classifier.mapping_df['Credential'].unique()[:10]
            for cred in unique_creds:
                print(f"  - {cred}")
    
    # Step 6: Test classification with a sample credential
    print("\n7. Testing classification with state-filtered credentials...")
    print("-" * 80)
    
    test_credentials = ["MD", "RN", "NP", "PA", "Doctor of Medicine"]
    
    for test_cred in test_credentials:
        classification, standardized, score, method = classifier.classify_credential(test_cred)
        print(f"\nInput: '{test_cred}'")
        print(f"  → Classification: {classification}")
        print(f"  → Standardized: {standardized}")
        print(f"  → Score: {score:.1f}%")
        print(f"  → Method: {method}")
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"✓ Venue State: {venue_state}")
    print(f"✓ Company ID: {company_id}")
    print(f"✓ Valid Credentials for State: {len(valid_credential_ids) if valid_credential_ids else 0}")
    print(f"✓ Mappings After Filtering: {len(classifier.mapping_df)}")
    print("\nState-level filtering ensures only state-compliant credentials are classified as HCP.")
    print("="*80)


def test_multiple_states():
    """Test state filtering for multiple states."""
    
    print("\n\n" + "="*80)
    print("TESTING MULTIPLE STATES")
    print("="*80)
    
    states_to_test = ["Pennsylvania", "Maryland", "Texas", "Indiana"]
    company_id = 1
    
    with CredentialService() as credential_service:
        for state in states_to_test:
            print(f"\n{state}:")
            print("-" * 40)
            credential_ids = credential_service.get_state_specific_credential_ids(
                venue_state=state,
                company_id=company_id
            )
            print(f"  Valid credentials: {len(credential_ids) if credential_ids else 0}")


if __name__ == "__main__":
    try:
        test_state_filtering()
        test_multiple_states()
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()

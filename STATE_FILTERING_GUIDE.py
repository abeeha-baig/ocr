"""
STATE-LEVEL CREDENTIAL FILTERING - INTEGRATION GUIDE
====================================================

This guide explains how to integrate state-level credential filtering into your OCR processing workflow.

OVERVIEW
--------
The system now supports state-level credential filtering, which ensures that only credentials 
valid for a specific state are used during classification. This is important for compliance 
purposes, as different states have different credential requirements.

HOW IT WORKS
------------
1. Extract the venue state from the concur file (ExpenseV3_LocationSubdivision column)
2. Query the database for credentials valid in that state (federal + state-specific)
3. Filter the credential mapping to only include those valid credentials
4. Classify OCR results using only the filtered credentials

NEW METHODS ADDED
-----------------

### CredentialService.get_state_specific_credential_ids(venue_state, company_id=1)
```python
# Query database for credentials valid in a specific state
valid_credential_ids = credential_service.get_state_specific_credential_ids(
    venue_state="Pennsylvania",
    company_id=1
)
# Returns: List of credential IDs valid for the state
```

### DataExtractionService.get_venue_state(expense_id)
```python
# Get the venue state for an expense
venue_state = data_service.get_venue_state(expense_id)
# Returns: State string (e.g., "Pennsylvania") or None
```

### ClassificationService.filter_by_state_credentials(valid_credential_ids, company_id=None)
```python
# Filter classification mappings to only include state-valid credentials
classifier.filter_by_state_credentials(
    valid_credential_ids=[1, 2, 3, 5, 8],
    company_id=1
)
```

INTEGRATION EXAMPLE
-------------------

Here's how to integrate this into your sis_concour.py workflow:

```python
def main():
    # Initialize services
    data_service = DataExtractionService(CSV_PATH)
    gemini_client = GeminiClient()
    classification_service = ClassificationService(
        CREDENTIAL_MAPPING_FILE, 
        fuzzy_threshold=FUZZY_MATCH_THRESHOLD
    )
    
    # Extract expense ID
    expense_id = data_service.extract_expense_id_from_filename(SIGNIN_IMAGE_PATH)
    
    # Get HCP names for OCR prompt
    hcp_names = data_service.get_hcp_names(expense_id)
    
    # Process image with OCR
    processed_image = image_service.deskew_image(SIGNIN_IMAGE_PATH)
    prompt = OCR_SIGNIN_PROMPT.format(HCPs=hcp_names)
    ocr_results = gemini_client.process_ocr(prompt, processed_image)
    
    # STEP 1: Extract company_id from OCR results (LLM identifies it from signin sheet header)
    company_id = data_service.extract_company_id_from_ocr(ocr_results)
    print(f"✓ Company ID from OCR: {company_id}")
    
    # STEP 2: Reload classification service with the correct company_id
    classification_service.reload_with_company_id(company_id)
    
    # STEP 3: Get venue state for state-level filtering
    venue_state = data_service.get_venue_state(expense_id)
    
    if venue_state:
        print(f"✓ Venue State: {venue_state}")
        
        # STEP 4: Get valid credentials for this state
        with CredentialService() as credential_service:
            valid_credential_ids = credential_service.get_state_specific_credential_ids(
                venue_state=venue_state,
                company_id=company_id
            )
        
        # STEP 5: Apply state-level filtering
        if valid_credential_ids:
            classification_service.filter_by_state_credentials(
                valid_credential_ids=valid_credential_ids,
                company_id=company_id
            )
            print(f"✓ State filtering applied: {len(valid_credential_ids)} valid credentials")
        else:
            print("⚠️  No state-specific credentials found. Using all credentials for company.")
    else:
        print("⚠️  Could not determine venue state. Skipping state filtering.")
    
    # STEP 6: Classify credentials (now using company+state filtered mappings)
    classified_results = classification_service.classify_ocr_results(ocr_results)
    
    # Save results
    classification_service.save_results(classified_results)
```

PROCESSING MULTIPLE EXPENSES
-----------------------------

When processing multiple expense entries from the same report, you'll need to 
apply state filtering for each unique expense:

```python
# Process batch of expenses
for expense_id in expense_ids:
    # Get state for this expense
    venue_state = data_service.get_venue_state(expense_id)
    
    # Get valid credentials for this state
    with CredentialService() as cred_service:
        valid_creds = cred_service.get_state_specific_credential_ids(
            venue_state=venue_state,
            company_id=company_id
        )
    
    # Create a new classifier instance for this expense
    # (or reload the existing one with new filters)
    classifier = ClassificationService(
        mapping_file=CREDENTIAL_MAPPING_FILE,
        company_id=company_id
    )
    
    # Apply state filtering
    classifier.filter_by_state_credentials(valid_creds, company_id)
    
    # Process OCR and classify
    # ... your OCR processing code ...
    classified_results = classifier.classify_ocr_results(ocr_results)
```

DATABASE QUERY DETAILS
-----------------------

The state-specific credentials query:
```sql
SELECT DISTINCT a.credentialid, a.credential, a.company_id
FROM tbl_CredentialClassification a 
INNER JOIN tbl_State_HCPCredential as b 
    ON a.id = b.Credentialid 
WHERE LOWER(b.state) IN ('federal', '{venue_state}')
    AND a.classification = 'hcp'
    AND a.company_id = {company_id}
```

This returns credentials that are:
- Valid federally (work in all states), OR
- Valid in the specific state
- Classified as HCP
- Belonging to the specified company

TESTING
-------

Run the test script to verify functionality:
```bash
python test_state_filtering.py
```

This will:
1. Load a sample expense from the concur file
2. Extract the venue state
3. Query database for state-valid credentials
4. Apply filtering
5. Test classification with sample credentials

FALLBACK BEHAVIOR
------------------

If state information is not available or no state-specific credentials are found:
- The system will log a warning
- Classification will proceed using ALL credentials for the company
- No error will be thrown

This ensures the system remains functional even when state data is incomplete.

IMPORTANT NOTES
---------------

1. **Company ID Source**: The company_id is extracted from the OCR results (LLM identifies 
   GSK=1, AstraZeneca=2, Lilly=3 from the signin sheet header), NOT from the CSV file.
   - The LLM outputs "COMPANY_ID: <number>" in the OCR results
   - Use `data_service.extract_company_id_from_ocr(ocr_results)` to get it
   - Defaults to 1 (GSK) if not found in OCR results

2. **CredentialID Column**: The CredentialID column MUST be present in the 
   PossibleNames_to_Credential_Mapping.xlsx file (added in previous update)

3. **Filtering Order**: State filtering is applied AFTER company_id filtering
   - First filter: company_id (from OCR)
   - Second filter: state-specific credentials (from database)

4. **State Name Matching**: The state name from the concur file (ExpenseV3_LocationSubdivision) 
   should match the state names in the tbl_State_HCPCredential table

5. **HCP Only**: State filtering only affects HCP credentials. Non-HCP classifications are unaffected.

BENEFITS
--------

✓ Compliance: Only credentials valid in the event's state are considered
✓ Accuracy: Reduces false positives from credentials valid in other states
✓ Flexibility: Falls back gracefully when state data is unavailable
✓ Performance: Filtering happens once per expense, not per credential
✓ Transparency: Clear logging shows what filtering is applied

"""

if __name__ == "__main__":
    print(__doc__)

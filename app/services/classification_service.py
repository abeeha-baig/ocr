"""Classification service for credential classification using rule-based and fuzzy matching."""

import re
import pandas as pd
from rapidfuzz import fuzz, process


class ClassificationService:
    """Service for classifying OCR results against credential mappings."""
    
    def __init__(self, mapping_file="PossibleNames_to_Credential_Mapping.xlsx", fuzzy_threshold=80, company_id=None):
        """
        Initialize classification service.
        
        Args:
            mapping_file: Path to Excel file with credential mappings
            fuzzy_threshold: Minimum similarity score for fuzzy matching (0-100, default: 80)
            company_id: Company ID to filter mappings (None = no filter, use for initial load)
        """
        self.mapping_file = mapping_file
        self.fuzzy_threshold = fuzzy_threshold
        self.company_id = company_id
        self.mapping_df = None
        self.credential_list = []
        self._full_mapping_df = None  # Cache the full Excel file
        self._company_cache = {}  # Cache filtered mappings per company_id
        self._load_mapping()
    
    def _load_mapping(self, company_id=None):
        """Load and normalize mapping data from Excel file.
        
        Args:
            company_id: Optional company ID to filter by. If provided, overrides self.company_id
        """
        if company_id is None:
            company_id = self.company_id
        
        # Load full Excel file only once
        if self._full_mapping_df is None:
            self._full_mapping_df = pd.read_excel(self.mapping_file)
            print(f"✓ Loaded {len(self._full_mapping_df)} total credential mappings from Excel")
        
        # Check cache first
        if company_id is not None and company_id in self._company_cache:
            cached_data = self._company_cache[company_id]
            self.mapping_df = cached_data['mapping_df']
            self.credential_list = cached_data['credential_list']
            print(f"✓ Using cached mappings for company_id={company_id}: {len(self.mapping_df)} records")
            return
            
        # Filter by company_id if provided - THIS IS CRITICAL FOR CORRECT MATCHING
        if company_id is not None:
            # Only include credentials that belong to this specific company
            self.mapping_df = self._full_mapping_df[self._full_mapping_df['company_id'] == company_id].copy()
            print(f"✓ Filtered mappings by company_id={company_id}: {len(self.mapping_df)} records")
            if self.mapping_df.empty:
                print(f"⚠️  WARNING: No credentials found for company_id={company_id}!")
        else:
            self.mapping_df = self._full_mapping_df.copy()
            print(f"⚠️  WARNING: No company_id filter applied - using ALL credentials from all companies!")
        
        # Normalize mapping data for case-insensitive matching
        self.mapping_df['PossibleNames_Upper'] = (
            self.mapping_df['PossibleNames'].str.upper().str.strip()
        )
        self.mapping_df['Credential_Upper'] = (
            self.mapping_df['Credential'].str.upper().str.strip()
        )
        
        # Create list of unique credentials for fuzzy matching
        self.credential_list = self.mapping_df['Credential_Upper'].unique().tolist()
        
        # Cache the filtered result
        if company_id is not None:
            self._company_cache[company_id] = {
                'mapping_df': self.mapping_df,
                'credential_list': self.credential_list
            }
        
        if company_id is None:
            print(f"✓ Processed {len(self.mapping_df)} credential mappings")
        print(f"✓ Fuzzy matching enabled with threshold: {self.fuzzy_threshold}%")
    
    def reload_with_company_id(self, company_id):
        """Reload mappings with a specific company_id filter.
        This ensures that credential matching ONLY happens within the specified company.
        
        Args:
            company_id: Company ID to filter by
        """
        print(f"\n🔄 Reloading credential mappings for company_id={company_id}")
        self.company_id = company_id
        self._load_mapping(company_id)
        print(f"✓ Credential matching will now ONLY use company_id={company_id} credentials")
        print(f"✓ Available credentials for matching: {len(self.mapping_df)} records\n")
    
    def parse_ocr_results(self, ocr_text):
        """
        Parse markdown-formatted OCR results.
        
        Args:
            ocr_text: OCR output in markdown format (- Name, Credential)
            
        Returns:
            List of dictionaries with Name and Credential_OCR keys
        """
        lines = ocr_text.split('\n')
        extracted_data = []
        
        for line in lines:
            # Match markdown format: "- Name, Credential"
            match = re.match(r'-\s*(.+?),\s*(.+)$', line.strip())
            if match:
                name = match.group(1).strip()
                credential_ocr = match.group(2).strip()
                extracted_data.append({
                    'Name': name,
                    'Credential_OCR': credential_ocr
                })
        
        return extracted_data
    
    def classify_credential(self, credential_ocr):
        """
        Classify a single credential using exact and fuzzy matching.
        IMPORTANT: Only matches against credentials filtered by company_id.
        
        Matching strategy:
        1. Exact match in PossibleNames column (filtered by company_id)
        2. Exact match in Credential column (filtered by company_id)
        3. Fuzzy match against Credential column (filtered by company_id)
        4. Default to Non-HCP
        
        Args:
            credential_ocr: OCR-extracted credential string
            
        Returns:
            Tuple of (classification, standardized_credential, match_score, match_method)
        """
        credential_upper = credential_ocr.upper().strip()
        
        # Ensure we're working with company-filtered data
        if self.mapping_df.empty:
            return 'Non-HCP', credential_ocr, 0.0, 'no_mapping_data'
        
        # Rule 1: Try exact match in PossibleNames column (already filtered by company_id)
        match = self.mapping_df[
            self.mapping_df['PossibleNames_Upper'] == credential_upper
        ]
        
        if not match.empty:
            classification = match.iloc[0]['Classification']
            standardized = match.iloc[0]['Credential']
            company = match.iloc[0].get('company_id', 'N/A')
            return classification, standardized, 100.0, f'exact_possiblenames(company:{company})'
        
        # Rule 2: Try exact match in Credential column (already filtered by company_id)
        match = self.mapping_df[
            self.mapping_df['Credential_Upper'] == credential_upper
        ]
        
        if not match.empty:
            classification = match.iloc[0]['Classification']
            standardized = match.iloc[0]['Credential']
            company = match.iloc[0].get('company_id', 'N/A')
            return classification, standardized, 100.0, f'exact_credential(company:{company})'
        
        # Rule 3: Try fuzzy match against PossibleNames column (already filtered by company_id)
        fuzzy_match = self._fuzzy_match_credential(credential_upper)
        if fuzzy_match:
            classification, standardized, score, company = fuzzy_match
            return classification, standardized, score, f'fuzzy_possiblenames(company:{company})'
        
        # No match found - classify as Non-HCP
        return 'Non-HCP', credential_ocr, 0.0, 'no_match'
    
    def _fuzzy_match_credential(self, credential_upper):
        """
        Perform fuzzy matching against PossibleNames column.
        IMPORTANT: Only searches within company-filtered mapping_df.
        
        Args:
            credential_upper: Uppercased OCR credential string
            
        Returns:
            Tuple of (classification, standardized_credential, score, company_id) or None
        """
        if self.mapping_df.empty:
            return None
        
        # Get list of all PossibleNames (uppercased) - already filtered by company_id
        possible_names_list = self.mapping_df['PossibleNames_Upper'].tolist()
        
        # Find best match using token_sort_ratio (handles word order and punctuation)
        result = process.extractOne(
            credential_upper,
            possible_names_list,
            scorer=fuzz.token_sort_ratio
        )
        
        if result:
            best_match, score, _ = result
            
            # Check if score meets threshold
            if score >= self.fuzzy_threshold:
                # Get the corresponding credential details (from company-filtered data)
                matched_row = self.mapping_df[
                    self.mapping_df['PossibleNames_Upper'] == best_match
                ].iloc[0]
                
                classification = matched_row['Classification']
                standardized = matched_row['Credential']
                company = matched_row.get('company_id', 'N/A')
                
                return classification, standardized, score, company
        
        return None
    
    def classify_ocr_results(self, ocr_text):
        """
        Parse OCR results and classify all credentials.
        Classification is purely based on lookup in the mapping file - no AI involved.
        
        Args:
            ocr_text: OCR output in markdown format
            
        Returns:
            pandas DataFrame with classifications
        """
        # Parse OCR results
        extracted_data = self.parse_ocr_results(ocr_text)
        
        if not extracted_data:
            print("⚠️ No data extracted from OCR results")
            return pd.DataFrame()
        
        # Create DataFrame
        results_df = pd.DataFrame(extracted_data)
        
        # Classification with exact and fuzzy matching
        classifications = []
        matched_credentials = []
        match_scores = []
        match_methods = []
        
        for _, row in results_df.iterrows():
            classification, standardized, score, method = self.classify_credential(
                row['Credential_OCR']
            )
            classifications.append(classification)
            matched_credentials.append(standardized)
            match_scores.append(score)
            match_methods.append(method)
        
        results_df['Credential_Standardized'] = matched_credentials
        results_df['Classification'] = classifications
        results_df['Match_Score'] = match_scores
        results_df['Match_Method'] = match_methods
        
        # Post-processing: Remove duplicate names
        results_df = self.remove_duplicate_names(results_df)
        
        return results_df
    
    def remove_duplicate_names(self, results_df):
        """Keep first occurrence of each name, remove subsequent duplicates (case-insensitive)."""
        if results_df.empty:
            return results_df
        
        results_df['Name_Upper'] = results_df['Name'].str.upper()
        results_df = results_df.drop_duplicates(subset=['Name_Upper'], keep='first')
        results_df = results_df.drop(columns=['Name_Upper'])
        return results_df
    
    def save_results(self, results_df, expense_id=None, output_file=None):
        """
        Save classification results to Excel file.
        
        Args:
            results_df: DataFrame with classification results
            expense_id: Optional expense ID to include in filename
            output_file: Optional output Excel file path (overrides expense_id naming)
        """
        import os
        from app.constants.config import OUTPUT_DIR
        
        if output_file is None:
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            if expense_id:
                output_file = os.path.join(OUTPUT_DIR, f"OCR_Results_Classified_{expense_id}.xlsx")
            else:
                output_file = os.path.join(OUTPUT_DIR, "OCR_Results_Classified.xlsx")
        
        results_df.to_excel(output_file, index=False)
        print(f"\n✅ Classified results saved to: {output_file}")
        
        # Print summary
        print(f"\nSummary:")
        print(f"  Total entries: {len(results_df)}")
        print(f"  HCP: {sum(results_df['Classification'] == 'HCP')}")
        print(f"  Field Employee: {sum(results_df['Classification'] == 'Field Employee')}")
        print(f"  Non-HCP: {sum(results_df['Classification'] == 'Non-HCP')}")
        
        return output_file

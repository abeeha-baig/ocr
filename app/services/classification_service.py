"""Classification service for credential classification using rule-based matching."""

import re
import pandas as pd


class ClassificationService:
    """Service for classifying OCR results against credential mappings."""
    
    def __init__(self, mapping_file="PossibleNames_to_Credential_Mapping.xlsx"):
        """
        Initialize classification service.
        
        Args:
            mapping_file: Path to Excel file with credential mappings
        """
        self.mapping_file = mapping_file
        self.mapping_df = None
        self._load_mapping()
    
    def _load_mapping(self):
        """Load and normalize mapping data from Excel file."""
        self.mapping_df = pd.read_excel(self.mapping_file)
        
        # Normalize mapping data for case-insensitive matching
        self.mapping_df['PossibleNames_Upper'] = (
            self.mapping_df['PossibleNames'].str.upper().str.strip()
        )
        self.mapping_df['Credential_Upper'] = (
            self.mapping_df['Credential'].str.upper().str.strip()
        )
        
        print(f"✓ Loaded {len(self.mapping_df)} credential mappings")
    
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
        Classify a single credential using rule-based exact matching.
        
        Args:
            credential_ocr: OCR-extracted credential string
            
        Returns:
            Tuple of (classification, standardized_credential)
        """
        credential_upper = credential_ocr.upper().strip()
        
        # Rule 1: Try exact match in PossibleNames column
        match = self.mapping_df[
            self.mapping_df['PossibleNames_Upper'] == credential_upper
        ]
        
        # Rule 2: If not found, try exact match in Credential column
        if match.empty:
            match = self.mapping_df[
                self.mapping_df['Credential_Upper'] == credential_upper
            ]
        
        # Apply classification based on match
        if not match.empty:
            # Use first match (exact lookup from mapping file)
            classification = match.iloc[0]['Classification']
            standardized = match.iloc[0]['Credential']
            return classification, standardized
        else:
            # No match found in mapping file
            return 'Unknown', credential_ocr
    
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
        
        # Rule-based classification: exact lookup in mapping file
        classifications = []
        matched_credentials = []
        
        for _, row in results_df.iterrows():
            classification, standardized = self.classify_credential(
                row['Credential_OCR']
            )
            classifications.append(classification)
            matched_credentials.append(standardized)
        
        results_df['Credential_Standardized'] = matched_credentials
        results_df['Classification'] = classifications
        
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
        if output_file is None:
            if expense_id:
                output_file = f"OCR_Results_Classified_{expense_id}.xlsx"
            else:
                output_file = "OCR_Results_Classified.xlsx"
        
        results_df.to_excel(output_file, index=False)
        print(f"\n✅ Classified results saved to: {output_file}")
        
        # Print summary
        print(f"\nSummary:")
        print(f"  Total entries: {len(results_df)}")
        print(f"  HCP: {sum(results_df['Classification'] == 'HCP')}")
        print(f"  Field Employee: {sum(results_df['Classification'] == 'Field Employee')}")
        print(f"  Unknown: {sum(results_df['Classification'] == 'Unknown')}")
        
        return output_file

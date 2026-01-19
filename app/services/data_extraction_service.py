"""Data extraction service for loading and processing CSV data."""

import re
import pandas as pd


class DataExtractionService:
    """Service for extracting and processing data from CSV files."""
    
    def __init__(self, csv_path):
        """
        Initialize data extraction service.
        
        Args:
            csv_path: Path to the CSV file
        """
        self.csv_path = csv_path
        self.df = None
        self._load_csv()
    
    def _load_csv(self):
        """Load CSV file into DataFrame."""
        self.df = pd.read_csv(self.csv_path, sep="|", dtype=str)
        self.df["ExpenseV3_ID"] = self.df["ExpenseV3_ID"].str.strip()
        print(f"✓ Loaded CSV with {len(self.df)} records")
    
    def extract_expense_id_from_filename(self, filename):
        """
        Extract expense ID from image filename.
        
        Args:
            filename: Image filename or path
            
        Returns:
            Expense ID string or None if not found
        """
        match = re.search(r"HCP Spend_(gWin\$[^_]+)", filename)
        if match:
            return match.group(1)
        return None
    
    def get_attendees_for_expense(self, expense_id):
        """
        Get attendees for a specific expense ID.
        
        Args:
            expense_id: Expense ID to filter by
            
        Returns:
            pandas DataFrame with attendee information
        """
        result = self.df.loc[
            self.df["ExpenseV3_ID"] == expense_id,
            ["AttendeeV3_FirstName", "AttendeeV3_LastName", "ExpenseV3_ID"]
        ]
        return result
    
    def get_hcp_names(self, expense_id):
        """
        Get list of HCP full names for a specific expense ID.
        
        Args:
            expense_id: Expense ID to filter by
            
        Returns:
            List of full names (first + last)
        """
        result = self.get_attendees_for_expense(expense_id)
        
        if result.empty:
            return []
        
        # Combine first and last names
        result["FullName"] = (
            result["AttendeeV3_FirstName"] + " " + result["AttendeeV3_LastName"]
        )
        
        # Prepare HCPs list, removing NaNs
        hcp_names = [
            str(name).strip() 
            for name in result["FullName"].tolist() 
            if pd.notna(name)
        ]
        
        return hcp_names
    
    def load_hcp_credentials(self, excel_file, company_id=1):
        """
        Load HCP credentials from Excel file.
        
        Args:
            excel_file: Path to Excel file with credential mappings
            company_id: Company ID to filter by (default: 1)
            
        Returns:
            Tuple of (DataFrame, credential_mapping_dict)
        """
        hcp_credentials_df = pd.read_excel(excel_file)
        
        # Filter for HCP classification and company_id
        hcp_credentials_df = hcp_credentials_df[
            (hcp_credentials_df['Classification'] == 'HCP') & 
            (hcp_credentials_df['company_id'] == company_id)
        ]
        
        # Create credential mapping dictionary
        hcp_credential_mapping = dict(zip(
            hcp_credentials_df['PossibleNames'], 
            hcp_credentials_df['Credential']
        ))
        
        print(f"✓ Loaded {len(hcp_credential_mapping)} HCP credential mappings for company_id={company_id}")
        
        return hcp_credentials_df, hcp_credential_mapping
    
    def extract_company_id_from_ocr(self, ocr_text):
        """
        Extract company_id from OCR results.
        
        Args:
            ocr_text: OCR text output from Gemini
            
        Returns:
            int: Company ID (default: 1 if not found)
        """
        # Look for "COMPANY_ID: <number>" pattern
        match = re.search(r'COMPANY_ID:\s*(\d+)', ocr_text, re.IGNORECASE)
        if match:
            company_id = int(match.group(1))
            print(f"✓ Extracted company_id: {company_id}")
            return company_id
        
        print("⚠️ No company_id found in OCR results, using default: 1")
        return 1

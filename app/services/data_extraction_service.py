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
        print(f"[OK] Loaded CSV with {len(self.df)} records")
    
    def extract_expense_id_from_filename(self, filename):
        """
        Extract expense ID from image filename.
        
        The expense ID is always after the second underscore (3rd part when split by '_').
        Format: [ID]_[Event Type]_[Expense ID]_[Project/Other Info]_[Timestamp]
        
        Examples:
        - "94420BB5DB3B4AE48A4E_HCP Business Lunch_gWgglnG97TnM69nd6xfgKyDBrNYl$pup11oA_ProjectID_2026-01-27T195657.647"
          Returns: "gWgglnG97TnM69nd6xfgKyDBrNYl$pup11oA"
        - "01C778FD04414D31BA0C_HCP Spend_gWin$pt81oo0IomGWW2zysP6gRxyAgjFIfg_7025 - ST-US - GSK - Vacancy Management (0325)_2026-01-30T185735.71"
          Returns: "gWin$pt81oo0IomGWW2zysP6gRxyAgjFIfg"
        
        Args:
            filename: Image filename or path
            
        Returns:
            Expense ID string or None if not found
        """
        try:
            # Split by underscore and get the third part (index 2)
            parts = filename.split('_')
            if len(parts) >= 3:
                expense_id = parts[2]
                return expense_id
            else:
                print(f"[WARN] Filename doesn't have expected format: {filename}")
                return None
        except Exception as e:
            print(f"[WARN] Error extracting expense ID from {filename}: {e}")
            return None
    
    def get_attendees_for_expense(self, expense_id):
        """
        Get attendees for a specific expense ID.
        
        Args:
            expense_id: Expense ID to filter by
            
        Returns:
            pandas DataFrame with attendee information
        """
        # Include AttendeeV3_Custom13 for credential hints
        columns = ["AttendeeV3_FirstName", "AttendeeV3_LastName", "ExpenseV3_ID"]
        if "AttendeeV3_Custom13" in self.df.columns:
            columns.append("AttendeeV3_Custom13")
        
        result = self.df.loc[
            self.df["ExpenseV3_ID"] == expense_id,
            columns
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
    
    def get_venue_state(self, expense_id):
        """
        Get the venue state (ExpenseV3_Custom21) for a specific expense ID.
        
        Args:
            expense_id: Expense ID to filter by
            
        Returns:
            State string (e.g., 'Pennsylvania', 'Texas') or None if not found
        """
        if "ExpenseV3_Custom21" not in self.df.columns:
            print("[WARN] Column 'ExpenseV3_Custom21' not found in CSV")
            return None
        
        result = self.df.loc[
            self.df["ExpenseV3_ID"] == expense_id,
            "ExpenseV3_Custom21"
        ]
        
        if result.empty:
            print(f"[WARN] No state found for expense_id: {expense_id}")
            return None
        
        # Get the first non-null value
        venue_state = result.iloc[0]
        
        if pd.isna(venue_state):
            print(f"[WARN] State is null for expense_id: {expense_id}")
            return None
        
        venue_state = str(venue_state).strip()
        print(f"[OK] Venue state for expense {expense_id}: {venue_state}")
        return venue_state
    
    def get_company_id(self, expense_id):
        """
        Get the company_id for a specific expense ID from the concur file.
        
        NOTE: In standard workflow, use extract_company_id_from_ocr() instead.
        The LLM identifies company from signin sheet header (GSK=1, AstraZeneca=2, Lilly=3).
        This method can be used as a fallback or validation.
        
        Args:
            expense_id: Expense ID to filter by
            
        Returns:
            int: Company ID, defaults to 1 if not found or invalid
        """
        if "User_companyId" not in self.df.columns:
            print("[WARN] Column 'User_companyId' not found in CSV, using default company_id=1")
            return 1
        
        result = self.df.loc[
            self.df["ExpenseV3_ID"] == expense_id,
            "User_companyId"
        ]
        
        if result.empty:
            print(f"[WARN] No company_id found for expense_id: {expense_id}, using default company_id=1")
            return 1
        
        # Get the first non-null value
        company_id = result.iloc[0]
        
        if pd.isna(company_id):
            print(f"[WARN] company_id is null for expense_id: {expense_id}, using default company_id=1")
            return 1
        
        try:
            # Convert to int (handles both string and UUID formats)
            if isinstance(company_id, str):
                # If it's a UUID string, we might need different handling
                # For now, try to extract numeric part or default to 1
                if '-' in company_id:  # Looks like a UUID
                    print(f"[WARN] UUID format company_id found: {company_id}, using default company_id=1")
                    return 1
                company_id = int(company_id)
            else:
                company_id = int(company_id)
            
            print(f"[OK] Company ID for expense {expense_id}: {company_id}")
            return company_id
        except (ValueError, TypeError) as e:
            print(f"[WARN] Could not convert company_id to int: {company_id}, using default company_id=1")
            return 1
    
    def get_credential_hints(self, expense_id):
        """
        Get credential hints from Concur file for a specific expense ID.
        This provides the LLM with expected credentials as a reading guide.
        
        Args:
            expense_id: Expense ID to filter by
            
        Returns:
            Dictionary mapping full names to their credentials from AttendeeV3_Custom13
        """
        result = self.get_attendees_for_expense(expense_id)
        
        if result.empty or "AttendeeV3_Custom13" not in result.columns:
            return {}
        
        # Combine first and last names
        result["FullName"] = (
            result["AttendeeV3_FirstName"] + " " + result["AttendeeV3_LastName"]
        )
        
        # Create name-to-credential mapping, excluding NaN/empty credentials
        credential_hints = {}
        for _, row in result.iterrows():
            full_name = str(row["FullName"]).strip()
            credential = row.get("AttendeeV3_Custom13", "")
            
            # Only add if credential exists and is not NaN/empty
            if pd.notna(credential) and str(credential).strip():
                credential_hints[full_name] = str(credential).strip()
        
        return credential_hints
    
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
        
        print(f"[OK] Loaded {len(hcp_credential_mapping)} HCP credential mappings for company_id={company_id}")
        
        return hcp_credentials_df, hcp_credential_mapping
    
    def extract_company_id_from_ocr(self, ocr_text):
        """
        Extract company_id from OCR results.
        The LLM identifies company from the signin sheet header (GSK=1, AstraZeneca=2, Lilly=3).
        
        Args:
            ocr_text: OCR text output from Gemini
            
        Returns:
            int: Company ID (default: 1 if not found)
        """
        # Look for "COMPANY_ID: <number>" pattern that LLM outputs
        match = re.search(r'COMPANY_ID:\s*(\d+)', ocr_text, re.IGNORECASE)
        if match:
            company_id = int(match.group(1))
            print(f"[OK] Extracted company_id from OCR: {company_id}")
            return company_id
        
        print("[WARN] No company_id found in OCR results, defaulting to company_id=1")
        return 1

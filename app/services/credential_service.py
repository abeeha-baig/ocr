"""Service for managing credential-related database queries."""

import pandas as pd
from app.services.database import SQLServerConnection


class CredentialService:
    """Service to fetch credential data from database tables."""
    
    def __init__(self):
        self.db = SQLServerConnection()
    
    def get_credential_mapping(self):
        """Fetch all records from tbl_SIS_CredentialMapping."""
        query = "SELECT * FROM tbl_SIS_CredentialMapping"
        df = self.db.fetch_to_dataframe(query)
        return df
    
    def get_credential_classification(self):
        """Fetch all records from tbl_CredentialClassification."""
        query = "SELECT * FROM tbl_CredentialClassification"
        df = self.db.fetch_to_dataframe(query)
        return df
    
    def get_credential_possible_names(self):
        """Fetch all records from tbl_Credential_PossibleNames."""
        query = "SELECT * FROM tbl_Credential_PossibleNames"
        df = self.db.fetch_to_dataframe(query)
        return df
    
    def get_all_credentials_list(self):
        """Get a simple list of all credential abbreviations."""
        df = self.get_credential_classification()
        # Assuming there's a column like 'credential' or 'abbreviation'
        # Adjust column name as needed based on actual table structure
        return df.iloc[:, 0].tolist() if not df.empty else []
    
    def get_possible_names_list(self):
        """Get a simple list of all possible names."""
        df = self.get_credential_possible_names()
        # Adjust column name as needed based on actual table structure
        return df.iloc[:, 0].tolist() if not df.empty else []
    
    def get_possible_names_to_credential_mapping(self):
        """
        Get mapping between PossibleNames and Credentials.
        Joins tbl_Credential_PossibleNames with tbl_CredentialClassification.
        Returns: DataFrame with PossibleNames and their corresponding Credentials
        """
        query = """
        SELECT 
            pn.PossibleNames,
            cc.Credential,
            cc.Classification,
            cc.company_id,
            cc.precedence_in_classification
        FROM tbl_Credential_PossibleNames pn
        INNER JOIN tbl_CredentialClassification cc 
            ON pn.CredentialID = cc.ID
        ORDER BY cc.Credential, pn.PossibleNames
        """
        df = self.db.fetch_to_dataframe(query)
        return df
    
    def get_credential_mapping_dict(self):
        """
        Get a dictionary mapping PossibleNames to Credentials.
        Returns: dict {PossibleName: Credential}
        """
        df = self.get_possible_names_to_credential_mapping()
        return dict(zip(df['PossibleNames'], df['Credential']))
    
    def get_hcp_credentials_for_company(self, company_id=1):
        """
        Get HCP credentials only for a specific company.
        Returns: DataFrame with PossibleNames and Credentials where Classification='HCP' and company_id matches
        """
        query = f"""
        SELECT 
            pn.PossibleNames,
            cc.Credential,
            cc.Classification,
            cc.company_id,
            cc.precedence_in_classification
        FROM tbl_Credential_PossibleNames pn
        INNER JOIN tbl_CredentialClassification cc 
            ON pn.CredentialID = cc.ID
        WHERE cc.Classification = 'HCP' 
            AND cc.company_id = {company_id}
        ORDER BY cc.Credential, pn.PossibleNames
        """
        df = self.db.fetch_to_dataframe(query)
        return df
    
    def get_hcp_credentials_dict(self, company_id=1):
        """
        Get a dictionary of HCP credentials for prompt.
        Returns: dict {PossibleName: Credential} for HCPs only
        """
        df = self.get_hcp_credentials_for_company(company_id)
        return dict(zip(df['PossibleNames'], df['Credential']))
    
    def close(self):
        """Close database connection."""
        self.db.disconnect()
    
    def __enter__(self):
        """Context manager entry."""
        self.db.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# Convenience functions for quick access
def fetch_credential_mapping():
    """Quick function to fetch credential mapping."""
    with CredentialService() as service:
        return service.get_credential_mapping()


def fetch_credential_classification():
    """Quick function to fetch credential classification."""
    with CredentialService() as service:
        return service.get_credential_classification()


def fetch_credential_possible_names():
    """Quick function to fetch possible names."""
    with CredentialService() as service:
        return service.get_credential_possible_names()


# Example usage
if __name__ == "__main__":
    # Option 1: Using context manager
    with CredentialService() as service:
        mapping = service.get_credential_mapping()
        classification = service.get_credential_classification()
        possible_names = service.get_credential_possible_names()
        
        print("Credential Mapping:")
        print(mapping.head())
        print(f"\nTotal records: {len(mapping)}\n")
        
        print("Credential Classification:")
        print(classification.head())
        print(f"\nTotal records: {len(classification)}\n")
        
        print("Credential Possible Names:")
        print(possible_names.head())
        print(f"\nTotal records: {len(possible_names)}\n")
    
    # Option 2: Using convenience functions
    # df = fetch_credential_mapping()

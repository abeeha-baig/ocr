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
        Uses LEFT JOIN to include all PossibleNames, even if CredentialID doesn't exist.
        Returns: DataFrame with PossibleNames and their corresponding Credentials
        """
        query = """
        SELECT 
            pn.PossibleNames,
            pn.CredentialID,
            ISNULL(cc.Credential, 'UNKNOWN') AS Credential,
            ISNULL(cc.Classification, 'Non-HCP') AS Classification,
            cc.company_id,
            cc.precedence_in_classification
        FROM tbl_Credential_PossibleNames pn
        LEFT JOIN tbl_CredentialClassification cc 
            ON pn.CredentialID = cc.ID
        ORDER BY cc.Credential, pn.PossibleNames
        """
        df = self.db.fetch_to_dataframe(query)
        return df
    
    def get_credential_ocr_mapping(self):
        """
        Get CredentialOCR mapping from tbl_SIS_CredentialMapping.
        Traces CredentialMapping value through the lookup chain:
        1. Check if CredentialMapping exists in tbl_Credential_PossibleNames -> get CredentialID -> get Credential
        2. If not, check if CredentialMapping exists directly in tbl_CredentialClassification.Credential
        3. If not found, defaults to 'Non-HCP'
        Returns: DataFrame with CredentialOCR as PossibleNames and final Credential
        """
        query = """
        SELECT 
            scm.CredentialOCR AS PossibleNames,
            scm.CredentialMapping
        FROM tbl_SIS_CredentialMapping scm
        WHERE scm.CredentialOCR IS NOT NULL 
            AND scm.CredentialOCR != ''
            AND scm.CredentialMapping IS NOT NULL
            AND scm.CredentialMapping != ''
        ORDER BY scm.CredentialMapping, scm.CredentialOCR
        """
        df = self.db.fetch_to_dataframe(query)
        
        if df.empty:
            return df
        
        # For each CredentialMapping, trace it through the lookup chain
        results = []
        unique_mappings = df['CredentialMapping'].unique()
        
        print(f"  Tracing {len(unique_mappings)} unique CredentialMapping values through lookup chain...")
        
        for mapping_value in unique_mappings:
            # Step 1: Check if CredentialMapping exists in tbl_Credential_PossibleNames
            lookup_query1 = """
            SELECT pn.CredentialID, cc.Credential, cc.Classification, cc.company_id, cc.precedence_in_classification
            FROM tbl_Credential_PossibleNames pn
            INNER JOIN tbl_CredentialClassification cc ON pn.CredentialID = cc.ID
            WHERE pn.PossibleNames = %s
            """
            result1 = self.db.fetch_to_dataframe(lookup_query1, params=(mapping_value,))
            
            if not result1.empty:
                # Found in PossibleNames -> follow the CredentialID chain
                results.append({
                    'mapping_value': mapping_value,
                    'credential': result1.iloc[0]['Credential'],
                    'classification': result1.iloc[0]['Classification'],
                    'company_id': result1.iloc[0]['company_id'],
                    'precedence': result1.iloc[0]['precedence_in_classification'],
                    'method': 'via_possiblenames'
                })
                continue
            
            # Step 2: Check if CredentialMapping exists directly in tbl_CredentialClassification.Credential
            lookup_query2 = """
            SELECT Credential, Classification, company_id, precedence_in_classification
            FROM tbl_CredentialClassification
            WHERE Credential = %s
            """
            result2 = self.db.fetch_to_dataframe(lookup_query2, params=(mapping_value,))
            
            if not result2.empty:
                # Found directly in Credential
                results.append({
                    'mapping_value': mapping_value,
                    'credential': result2.iloc[0]['Credential'],
                    'classification': result2.iloc[0]['Classification'],
                    'company_id': result2.iloc[0]['company_id'],
                    'precedence': result2.iloc[0]['precedence_in_classification'],
                    'method': 'direct_credential'
                })
                continue
            
            # Step 3: Not found anywhere - default to Non-HCP
            results.append({
                'mapping_value': mapping_value,
                'credential': mapping_value,  # Keep original value
                'classification': 'Non-HCP',
                'company_id': None,
                'precedence': None,
                'method': 'not_found'
            })
        
        # Create lookup dictionary
        lookup_dict = {r['mapping_value']: r for r in results}
        
        # Apply to all rows
        df['Credential'] = df['CredentialMapping'].map(lambda x: lookup_dict[x]['credential'])
        df['Classification'] = df['CredentialMapping'].map(lambda x: lookup_dict[x]['classification'])
        df['company_id'] = df['CredentialMapping'].map(lambda x: lookup_dict[x]['company_id'])
        df['precedence_in_classification'] = df['CredentialMapping'].map(lambda x: lookup_dict[x]['precedence'])
        
        # Drop the CredentialMapping column as it's no longer needed
        df = df.drop(columns=['CredentialMapping'])
        
        # Count by method
        method_counts = {}
        for r in results:
            method_counts[r['method']] = method_counts.get(r['method'], 0) + 1
        
        print(f"  ✓ Traced through PossibleNames: {method_counts.get('via_possiblenames', 0)}")
        print(f"  ✓ Found directly in Credential: {method_counts.get('direct_credential', 0)}")
        print(f"  ✓ Defaulted to Non-HCP: {method_counts.get('not_found', 0)}")
        
        return df
    
    def get_combined_credential_mapping(self):
        """
        Get combined mapping with both PossibleNames and CredentialOCR.
        Combines data from tbl_Credential_PossibleNames and tbl_SIS_CredentialMapping.
        Returns: DataFrame with all possible credential variations
        """
        import pandas as pd
        
        # Get PossibleNames mappings
        possible_names_df = self.get_possible_names_to_credential_mapping()
        print(f"  From tbl_Credential_PossibleNames: {len(possible_names_df)} rows")
        
        # Get CredentialOCR mappings
        ocr_mapping_df = self.get_credential_ocr_mapping()
        print(f"  From tbl_SIS_CredentialMapping: {len(ocr_mapping_df)} rows")
        
        # Combine both DataFrames
        combined_df = pd.concat([possible_names_df, ocr_mapping_df], ignore_index=True)
        print(f"  Combined total: {len(combined_df)} rows")
        
        # Remove duplicates (same PossibleName + Credential combination)
        # This is intentional - if the same variation appears in both tables, we only need it once
        # combined_df = combined_df.drop_duplicates(subset=['PossibleNames', 'Credential'], keep='first')
        # print(f"  After removing duplicates: {len(combined_df)} rows")
        # print(f"  ✓ Removed {len(possible_names_df) + len(ocr_mapping_df) - len(combined_df)} duplicate PossibleName+Credential pairs")
        
        # Sort by Credential and PossibleNames
        combined_df = combined_df.sort_values(['Credential', 'PossibleNames']).reset_index(drop=True)
        
        return combined_df
    
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
    
    def get_state_specific_credential_ids(self, venue_state, company_id=1):
        """
        Get valid credential IDs for a specific state.
        Queries the database for credentials valid in 'federal' or the specific state.
        
        Args:
            venue_state: State abbreviation or name (e.g., 'Pennsylvania', 'TX')
            company_id: Company ID to filter by (default: 1)
            
        Returns:
            List of valid credential IDs for the state
        """
        query = f"""
        SELECT DISTINCT a.id as credentialid, a.credential, a.company_id
        FROM tbl_CredentialClassification a 
        INNER JOIN tbl_State_HCPCredential as b 
            ON a.id = b.Credentialid 
        WHERE LOWER(b.state) IN ('federal', '{venue_state.lower()}')
            AND a.classification = 'hcp'
            AND a.company_id = {company_id}
        """
        df = self.db.fetch_to_dataframe(query)
        
        if df.empty:
            print(f"[WARN] No state-specific credentials found for state='{venue_state}', company_id={company_id}")
            return []
        
        # Return list of credential IDs
        credential_ids = df['credentialid'].tolist()
        print(f"[OK] Found {len(credential_ids)} valid credential IDs for state='{venue_state}', company_id={company_id}")
        return credential_ids
    
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

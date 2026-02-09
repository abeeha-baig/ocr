"""Test script to export PossibleNames to Credential Mapping to Excel."""

import pandas as pd
from app.services.credential_service import CredentialService


def export_possible_names_mapping():
    """Export the possible names to credential mapping to an Excel file."""
    print("Fetching possible names to credential mapping from database...")
    
    service = CredentialService()
    mapping_df = service.get_possible_names_to_credential_mapping()
    
    print(f"Retrieved {len(mapping_df)} records")
    print("\nFirst few rows:")
    print(mapping_df.head())
    
    # Export to Excel
    output_file = "PossibleNames_to_Credential_Mapping.xlsx"
    mapping_df.to_excel(output_file, index=False)
    
    print(f"\n✓ Successfully exported to {output_file}")
    print(f"\nColumns in the export:")
    for col in mapping_df.columns:
        print(f"  - {col}")


if __name__ == "__main__":
    export_possible_names_mapping()

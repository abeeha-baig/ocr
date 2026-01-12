from app.services.database import SQLServerConnection
from app.services.credential_service import CredentialService
import os
from dotenv import load_dotenv

def test_connection():
    try:
        # Load and display env vars
        load_dotenv()
        print("Environment variables:")
        print(f"  DB_SERVER: {os.getenv('DB_SERVER')}")
        print(f"  DB_NAME: {os.getenv('DB_NAME')}")
        print(f"  DB_USER: {os.getenv('DB_USER')}")
        print(f"  DB_PASSWORD: {'***' if os.getenv('DB_PASSWORD') else None}")
        print(f"  DB_PORT: {os.getenv('DB_PORT')}")
        print()
        
        print("Testing SQL Server connection...")
        
        with SQLServerConnection() as db:
            print("✓ Connected successfully!")
            
            # Simple query to verify connection
            query = "SELECT @@VERSION as Version"
            results = db.execute_query(query)
            
            print(f"\n✓ Database connection verified!")
            print(f"  Server version: {results[0][0][:50]}...")
        
        print("\n" + "="*60)
        print("Testing Credential Service...")
        print("="*60)
        
        with CredentialService() as service:
            print("\n1. Credential Mapping:")
            mapping = service.get_credential_mapping()
            print(f"   Columns: {list(mapping.columns)}")
            print(f"   Total records: {len(mapping)}")
            print(mapping.head())
            
            print("\n2. Credential Classification:")
            classification = service.get_credential_classification()
            print(f"   Columns: {list(classification.columns)}")
            print(f"   Total records: {len(classification)}")
            print(classification.head())
            
            print("\n3. Credential Possible Names:")
            possible_names = service.get_credential_possible_names()
            print(f"   Columns: {list(possible_names.columns)}")
            print(f"   Total records: {len(possible_names)}")
            print(possible_names.head())
            
            print("\n4. PossibleNames to Credential Mapping:")
            mapping = service.get_possible_names_to_credential_mapping()
            print(f"   Columns: {list(mapping.columns)}")
            print(f"   Total records: {len(mapping)}")
            print(mapping.head(10))
            
            # Save to Excel
            output_file = "PossibleNames_to_Credential_Mapping.xlsx"
            mapping.to_excel(output_file, index=False)
            print(f"\n✓ Saved mapping to: {output_file}")
            
            print("\n5. Credential Mapping Dictionary (sample):")
            cred_dict = service.get_credential_mapping_dict()
            print(f"   Total mappings: {len(cred_dict)}")
            print("   Sample mappings:")
            for i, (key, value) in enumerate(list(cred_dict.items())[:10]):
                print(f"     '{key}' → '{value}'")
                
                
    except Exception as e:
        import traceback
        print(f"✗ Connection failed: {str(e)}")
        print("\nFull traceback:")
        traceback.print_exc()

if __name__ == "__main__":
    test_connection()

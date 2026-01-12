"""Test persistent database connection."""

from app.services.database import db_manager, get_persistent_connection, close_persistent_connection
import time

def test_persistent_connection():
    """Test the persistent database connection."""
    
    print("="*60)
    print("Testing Persistent Database Connection")
    print("="*60)
    
    # Initialize persistent connection
    print("\n1. Initializing persistent connection...")
    conn = get_persistent_connection()
    print(f"   Connection status: {'Connected' if db_manager.is_connected() else 'Not connected'}")
    
    # Use connection multiple times without reconnecting
    print("\n2. Running multiple queries with same connection...")
    cursor = conn.cursor()
    
    # Query 1
    cursor.execute("SELECT @@VERSION")
    version = cursor.fetchone()
    print(f"   Query 1 - Server Version: {version[0][:50]}...")
    
    # Query 2
    cursor.execute("SELECT COUNT(*) FROM tbl_CredentialClassification")
    count = cursor.fetchone()
    print(f"   Query 2 - Credential Classification count: {count[0]}")
    
    # Query 3
    cursor.execute("SELECT COUNT(*) FROM tbl_Credential_PossibleNames")
    count = cursor.fetchone()
    print(f"   Query 3 - Possible Names count: {count[0]}")
    
    cursor.close()
    
    print(f"\n3. Connection still active: {db_manager.is_connected()}")
    
    # Simulate doing other work
    print("\n4. Connection remains open for other operations...")
    time.sleep(1)
    print(f"   Connection status: {'Active' if db_manager.is_connected() else 'Closed'}")
    
    # Close when done
    print("\n5. Closing persistent connection...")
    close_persistent_connection()
    print(f"   Connection status: {'Active' if db_manager.is_connected() else 'Closed'}")
    
    print("\n" + "="*60)
    print("Persistent connection test completed!")
    print("="*60)


if __name__ == "__main__":
    test_persistent_connection()

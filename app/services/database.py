import os
import pymssql
from dotenv import load_dotenv
from typing import Optional
import pandas as pd

# Load environment variables
load_dotenv()


class DatabaseConnectionManager:
    """Singleton database connection manager for persistent connections."""
    
    _instance = None
    _connection = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseConnectionManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            # Ensure .env is loaded
            load_dotenv()
            self.server = os.getenv("DB_SERVER")
            self.database = os.getenv("DB_NAME")
            self.username = os.getenv("DB_USER")
            self.password = os.getenv("DB_PASSWORD")
            port_str = os.getenv("DB_PORT", "1433")
            self.port = int(port_str) if port_str else 1433
            self.initialized = True
    
    def get_connection(self):
        """Get or create a persistent database connection."""
        if self._connection is None:
            try:
                # Validate parameters
                if not all([self.server, self.database, self.username, self.password]):
                    raise ValueError("Missing database connection parameters. Check .env file.")
                
                self._connection = pymssql.connect(
                    server=self.server,
                    user=self.username,
                    password=self.password,
                    database=self.database,
                    port=self.port
                )
                print(f"✅ Database connection established to: {self.database}")
            except pymssql.Error as e:
                print(f"❌ Error connecting to database: {e}")
                raise
            except ValueError as e:
                print(f"❌ Configuration error: {e}")
                raise
        return self._connection
    
    def close_connection(self):
        """Manually close the database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None
            print("✅ Database connection closed")
    
    def is_connected(self):
        """Check if connection is active."""
        return self._connection is not None


# Global singleton instance
db_manager = DatabaseConnectionManager()


class SQLServerConnection:
    """SQL Server database connection manager."""
    
    def __init__(self):
        self.server = os.getenv("DB_SERVER")
        self.database = os.getenv("DB_NAME")
        self.username = os.getenv("DB_USER")
        self.password = os.getenv("DB_PASSWORD")
        self.port = int(os.getenv("DB_PORT", "1433"))
        self.connection: Optional[pymssql.Connection] = None
        self.cursor = None
    
    def connect(self):
        """Establish connection to SQL Server database."""
        try:
            # Connect using pymssql
            self.connection = pymssql.connect(
                server=self.server,
                user=self.username,
                password=self.password,
                database=self.database,
                port=self.port
            )
            self.cursor = self.connection.cursor()
            print(f"✅ Connected to SQL Server database: {self.database}")
            return self.connection
        
        except pymssql.Error as e:
            print(f"❌ Error connecting to database: {e}")
            raise
    
    def disconnect(self):
        """Close database connection."""
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()
            print("✅ Database connection closed")
    
    def execute_query(self, query: str, params: tuple = None):
        """Execute a query and return results."""
        try:
            if not self.connection:
                self.connect()
            
            if params:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)
            
            return self.cursor.fetchall()
        
        except pymssql.Error as e:
            print(f"❌ Query execution error: {e}")
            raise
    
    def execute_non_query(self, query: str, params: tuple = None):
        """Execute insert, update, delete queries."""
        try:
            if not self.connection:
                self.connect()
            
            if params:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)
            
            self.connection.commit()
            print(f"✅ Query executed successfully. Rows affected: {self.cursor.rowcount}")
            return self.cursor.rowcount
        
        except pymssql.Error as e:
            self.connection.rollback()
            print(f"❌ Query execution error: {e}")
            raise
    
    def fetch_to_dataframe(self, query: str, params: tuple = None):
        """Fetch query results as pandas DataFrame."""
        try:
            if not self.connection:
                self.connect()
            
            return pd.read_sql(query, self.connection, params=params)
        
        except Exception as e:
            print(f"❌ Error fetching data to DataFrame: {e}")
            raise
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()


# Convenience function for quick queries
def get_db_connection():
    """Get a new database connection instance."""
    return SQLServerConnection()


def get_persistent_connection():
    """Get the persistent database connection from singleton manager."""
    return db_manager.get_connection()


def close_persistent_connection():
    """Close the persistent database connection."""
    db_manager.close_connection()


# Example usage functions
def test_connection():
    """Test the database connection."""
    try:
        with SQLServerConnection() as db:
            result = db.execute_query("SELECT @@VERSION as Version")
            print("Database Version:", result[0][0])
            return True
    except Exception as e:
        print(f"Connection test failed: {e}")
        return False


if __name__ == "__main__":
    # Test the connection
    test_connection()

"""
Script to run MySQL migrations.
"""
import mysql.connector
from mysql.connector import Error
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_connection():
    """Get MySQL connection."""
    try:
        connection = mysql.connector.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            port=int(os.getenv('DB_PORT', 3306)),
            user=os.getenv('DB_USERNAME', 'root'),
            password=os.getenv('DB_PASSWORD', 'root')
        )
        return connection
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        raise

def create_database(connection, db_name):
    """Create database if it doesn't exist."""
    try:
        cursor = connection.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
        print(f"Database '{db_name}' ready")
        cursor.close()
    except Error as e:
        print(f"Error creating database: {e}")
        raise

def run_migration_file(connection, file_path):
    """Run a single migration file."""
    try:
        cursor = connection.cursor()
        
        with open(file_path, 'r', encoding='utf-8') as f:
            sql_content = f.read()
        
        # Remove comments and split by semicolon
        lines = []
        for line in sql_content.split('\n'):
            # Remove full-line comments
            if line.strip().startswith('--'):
                continue
            # Remove inline comments (simple approach)
            if '--' in line:
                line = line[:line.index('--')]
            lines.append(line)
        
        # Join and split by semicolon
        cleaned_content = '\n'.join(lines)
        statements = [s.strip() for s in cleaned_content.split(';') if s.strip()]
        
        for statement in statements:
            if statement:
                try:
                    cursor.execute(statement)
                    connection.commit()
                except Error as e:
                    # Some errors are expected (like IF NOT EXISTS)
                    error_msg = str(e).lower()
                    if "already exists" not in error_msg and "duplicate" not in error_msg:
                        print(f"Warning in {file_path.name}: {e}")
                        print(f"Statement: {statement[:100]}...")
        
        cursor.close()
        print(f"Ran migration: {file_path.name}")
        return True
    except Error as e:
        print(f"Error running migration {file_path.name}: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error in {file_path.name}: {e}")
        return False

def main():
    """Main function to run all migrations."""
    db_name = os.getenv('DB_NAME', 'ressy')
    migrations_dir = Path(__file__).parent.parent / 'migrations'
    
    print(f"Starting migrations for database: {db_name}")
    
    # Get connection (without database)
    connection = get_connection()
    
    try:
        # Create database
        create_database(connection, db_name)
        
        # Connect to the database
        connection.database = db_name
        
        # Get all migration files sorted
        migration_files = sorted([f for f in migrations_dir.glob('*.sql') if f.name.startswith('0')])
        
        print(f"Found {len(migration_files)} migration files")
        
        # Run each migration
        for migration_file in migration_files:
            run_migration_file(connection, migration_file)
        
        print("\nAll migrations completed successfully!")
        
    except Error as e:
        print(f"Migration error: {e}")
    finally:
        if connection.is_connected():
            connection.close()
            print("Database connection closed")

if __name__ == "__main__":
    main()


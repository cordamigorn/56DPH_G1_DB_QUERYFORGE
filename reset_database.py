
"""
Reset Database - Factory Reset
Completely wipes the database (DROPS ALL TABLES including user tables) 
and re-initializes the system schema.
"""
import sqlite3
import os
import sys

# Import schema initialization logic from app
try:
    # Add project root to python path to allow importing app modules
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from app.core.database import init_database
except ImportError:
    print("❌ Could not import app modules. Make sure you run this from the project root.")
    sys.exit(1)

def factory_reset():
    """Wipe everything and start fresh"""
    db_path = "queryforge.db"
    
    if not os.path.exists(db_path):
        print(f"⚠️ Database not found at {db_path}. Initializing fresh one...")
        try:
            init_database()
            print("✅ Fresh database created.")
            return
        except Exception as e:
            print(f"❌ Error creating database: {e}")
            return
            
    print("🔥 INITIATING FACTORY RESET...")
    print("   This will DROP ALL TABLES (System + User Data).")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 1. Get list of all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        table_names = [t[0] for t in tables if t[0] != 'sqlite_sequence']
        
        if not table_names:
            print("   Database is already empty.")
        else:
            print(f"   Found {len(table_names)} tables: {', '.join(table_names)}")
            
            # 2. Drop all tables
            print("💥 Dropping tables...")
            # Disable foreign keys to allow dropping in any order
            cursor.execute("PRAGMA foreign_keys = OFF")
            
            for table in table_names:
                print(f"     - Dropping {table}...")
                cursor.execute(f"DROP TABLE IF EXISTS {table}")
                
            cursor.execute("PRAGMA foreign_keys = ON")
            conn.commit()
            print("✨ All tables dropped.")

        # 3. Re-initialize System Schema
        print("🏗️  Re-initializing system schema...")
        conn.close() # Close connection to allow init_database to open its own
        
        init_database()
        
        print("\n✅ FACTORY RESET COMPLETE!")
        print("   The database is now returned to its initial installation state.")
        
    except Exception as e:
        print(f"\n❌ Error during reset: {e}")
        if conn:
            conn.close()

if __name__ == "__main__":
    print("⚠️  WARNING: FACTORY RESET MODE")
    print("    This will delete ALL DATA including:")
    print("    - All Pipelines & History")
    print("    - All User Tables (Sales, Customers, Products, etc.)")
    print("    - All System Logs")
    print("    - EVERYTHING.")
    
    response = input("\nAre you ABSOLUTELY sure? (yes/no): ")
    
    if response.lower() == 'yes':
        factory_reset()
    else:
        print("❌ Reset cancelled.")

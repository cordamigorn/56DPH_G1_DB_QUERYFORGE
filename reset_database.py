"""
Reset Database - Clean All Data
Deletes all pipelines and resets Sales table
"""
import sqlite3
import os

def reset_database():
    """Reset database to clean state"""
    db_path = "queryforge.db"
    
    if not os.path.exists(db_path):
        print(f"❌ Database not found: {db_path}")
        return
    
    print("🧹 Resetting database...")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 1. Delete all pipeline-related data
        print("  - Deleting Execution_Logs...")
        cursor.execute("DELETE FROM Execution_Logs")
        
        print("  - Deleting Repair_Logs...")
        cursor.execute("DELETE FROM Repair_Logs")
        
        print("  - Deleting Filesystem_Changes...")
        cursor.execute("DELETE FROM Filesystem_Changes")
        
        print("  - Deleting Schema_Snapshots...")
        cursor.execute("DELETE FROM Schema_Snapshots")
        
        print("  - Deleting Pipeline_Steps...")
        cursor.execute("DELETE FROM Pipeline_Steps")
        
        print("  - Deleting Pipelines...")
        cursor.execute("DELETE FROM Pipelines")
        
        # 2. Clear Sales table
        print("  - Clearing Sales table...")
        cursor.execute("DELETE FROM Sales")
        
        # 3. Reset auto-increment counters
        print("  - Resetting auto-increment counters...")
        cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('Pipelines', 'Pipeline_Steps', 'Execution_Logs', 'Repair_Logs', 'Schema_Snapshots', 'Filesystem_Changes')")
        
        # Commit changes
        conn.commit()
        
        # Verify
        cursor.execute("SELECT COUNT(*) FROM Pipelines")
        pipeline_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM Sales")
        sales_count = cursor.fetchone()[0]
        
        print(f"\n✅ Database reset complete!")
        print(f"   - Pipelines: {pipeline_count}")
        print(f"   - Sales records: {sales_count}")
        print(f"\n💡 Database is now clean and ready for fresh start!")
        
    except Exception as e:
        print(f"\n❌ Error resetting database: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    # Ask for confirmation
    print("⚠️  This will DELETE ALL pipelines and Sales data!")
    response = input("Are you sure? (yes/no): ")
    
    if response.lower() == 'yes':
        reset_database()
    else:
        print("❌ Reset cancelled.")

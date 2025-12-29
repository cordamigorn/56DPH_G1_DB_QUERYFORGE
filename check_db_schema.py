import sqlite3
import os

def check_database_schema():
    """Check all tables and their compatibility with data files"""
    
    db_path = "queryforge.db"
    data_dir = "data"
    
    print("=" * 80)
    print("DATABASE SCHEMA VERIFICATION")
    print("=" * 80)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all user tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    tables = [row[0] for row in cursor.fetchall()]
    
    print(f"\n📊 Found {len(tables)} tables in database:\n")
    
    for table_name in sorted(tables):
        print(f"\n{'='*80}")
        print(f"TABLE: {table_name}")
        print('='*80)
        
        # Get column info
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        
        print("\nColumns:")
        for col in columns:
            col_id, name, col_type, notnull, default, pk = col
            pk_str = " [PRIMARY KEY]" if pk else ""
            null_str = " NOT NULL" if notnull else ""
            default_str = f" DEFAULT {default}" if default else ""
            print(f"  - {name} ({col_type}){pk_str}{null_str}{default_str}")
        
        # Get row count
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        print(f"\n📈 Total rows: {count}")
        
        # Show sample data
        if count > 0:
            cursor.execute(f"SELECT * FROM {table_name} LIMIT 3")
            rows = cursor.fetchall()
            col_names = [desc[0] for desc in cursor.description]
            
            print("\n🔍 Sample data (first 3 rows):")
            for i, row in enumerate(rows, 1):
                print(f"\n  Row {i}:")
                for col_name, value in zip(col_names, row):
                    # Truncate long values
                    if isinstance(value, str) and len(value) > 50:
                        value = value[:50] + "..."
                    print(f"    {col_name}: {value}")
    
    conn.close()
    
    # Check data files
    print(f"\n\n{'='*80}")
    print("DATA FILES IN data/ DIRECTORY")
    print('='*80)
    
    if os.path.exists(data_dir):
        files = os.listdir(data_dir)
        print(f"\n📁 Found {len(files)} files:\n")
        for filename in sorted(files):
            filepath = os.path.join(data_dir, filename)
            size = os.path.getsize(filepath)
            print(f"  - {filename} ({size} bytes)")
            
            # Show first few lines for CSV
            if filename.endswith('.csv'):
                with open(filepath, 'r', encoding='utf-8') as f:
                    lines = [f.readline().strip() for _ in range(3)]
                print(f"    Header: {lines[0]}")
                if len(lines) > 1:
                    print(f"    First row: {lines[1]}")
            
            # Show structure for JSON
            elif filename.endswith('.json'):
                import json
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, list):
                    print(f"    JSON array with {len(data)} items")
                    if data and isinstance(data[0], dict):
                        print(f"    Fields: {', '.join(data[0].keys())}")
                elif isinstance(data, dict):
                    print(f"    JSON object with keys: {', '.join(data.keys())}")
    
    # Summary
    print(f"\n\n{'='*80}")
    print("COMPATIBILITY CHECK")
    print('='*80)
    
    # Check sales.csv vs Sales table
    print("\n✓ sales.csv → Sales table:")
    print("  Expected: order_id, customer, amount, date, region")
    if 'Sales' in tables or 'sales' in tables:
        print("  ✅ Sales table exists")
    else:
        print("  ❌ Sales table NOT FOUND!")
    
    # Check customers.csv vs customers table
    print("\n✓ customers.csv → customers table:")
    print("  Expected: customer_id, name, email, phone, country")
    # customers table might not exist yet
    
    # Check inventory.json vs products table
    print("\n✓ inventory.json → products table:")
    print("  JSON fields: product_id, stock_level, warehouse_location")
    print("  Table columns: product_id, product_name, category, price, stock_quantity")
    if 'products' in tables:
        print("  ✅ products table exists")
        print("  ⚠️  NOTE: Field mismatch!")
        print("      - stock_level (JSON) → stock_quantity (table)")
        print("      - warehouse_location (JSON) → NOT in table")
        print("      - product_name, category, price (table) → NOT in JSON")
    else:
        print("  ❌ products table NOT FOUND!")
    
    print("\n" + "="*80)
    print("VERIFICATION COMPLETE")
    print("="*80)

if __name__ == "__main__":
    check_database_schema()

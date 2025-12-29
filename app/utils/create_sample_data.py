"""
Sample test data creation script
Creates database tables and sample files for testing
"""
import sqlite3
import json
import csv
from datetime import datetime
from app.core.config import settings
from app.core.database import get_db_path

def create_sample_tables():
    """Create sample database tables with test data"""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create Sales table (for sales.csv imports)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Sales (
            order_id INTEGER PRIMARY KEY,
            customer TEXT NOT NULL,
            amount DECIMAL(10, 2) NOT NULL,
            date DATE NOT NULL,
            region TEXT NOT NULL
        )
    """)
    
    # Create orders table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT NOT NULL,
            amount DECIMAL(10, 2) NOT NULL,
            order_date DATE NOT NULL,
            status TEXT DEFAULT 'pending'
        )
    """)
    
    # Insert sample order data
    sample_orders = [
        ('John Doe', 150.50, '2025-01-15', 'completed'),
        ('Jane Smith', 320.00, '2025-01-16', 'completed'),
        ('Bob Johnson', 89.99, '2025-01-17', 'pending'),
        ('Alice Brown', 220.75, '2025-01-18', 'completed'),
        ('Charlie Davis', 445.20, '2025-01-19', 'shipped'),
        ('Eve Wilson', 178.30, '2025-01-20', 'pending'),
        ('Frank Miller', 560.00, '2025-01-21', 'completed'),
        ('Grace Lee', 95.50, '2025-01-22', 'cancelled'),
        ('Henry Taylor', 310.25, '2025-01-23', 'completed'),
        ('Ivy Anderson', 198.80, '2025-01-24', 'shipped'),
    ]
    
    cursor.executemany(
        "INSERT INTO orders (customer_name, amount, order_date, status) VALUES (?, ?, ?, ?)",
        sample_orders
    )
    
    # Create products table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            product_id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_name TEXT NOT NULL,
            category TEXT NOT NULL,
            price DECIMAL(10, 2) NOT NULL,
            stock_quantity INTEGER DEFAULT 0
        )
    """)
    
    # Insert sample product data
    sample_products = [
        ('Laptop Pro 15', 'Electronics', 1299.99, 45),
        ('Wireless Mouse', 'Electronics', 29.99, 150),
        ('USB-C Cable', 'Accessories', 12.99, 300),
        ('Desk Chair', 'Furniture', 199.99, 25),
        ('Monitor 27"', 'Electronics', 399.99, 35),
        ('Keyboard Mechanical', 'Electronics', 89.99, 80),
        ('Webcam HD', 'Electronics', 79.99, 60),
        ('Headphones Noise-Canceling', 'Electronics', 249.99, 50),
        ('Desk Lamp LED', 'Furniture', 34.99, 100),
        ('Mouse Pad', 'Accessories', 14.99, 200),
        ('External SSD 1TB', 'Storage', 149.99, 70),
        ('Phone Stand', 'Accessories', 19.99, 180),
        ('Cable Organizer', 'Accessories', 9.99, 250),
        ('Laptop Bag', 'Accessories', 49.99, 95),
        ('Power Bank 20000mAh', 'Electronics', 39.99, 120),
    ]
    
    cursor.executemany(
        "INSERT INTO products (product_name, category, price, stock_quantity) VALUES (?, ?, ?, ?)",
        sample_products
    )
    
    conn.commit()
    conn.close()
    
    print("✓ Sample database tables created successfully")
    print(f"  - Created 'Sales' table (empty, for CSV imports)")
    print(f"  - Created 'orders' table with {len(sample_orders)} records")
    print(f"  - Created 'products' table with {len(sample_products)} records")


def create_sample_csv_files():
    """Create sample CSV files in data directory"""
    import os
    os.makedirs(settings.DATA_DIRECTORY, exist_ok=True)
    
    # Create sales.csv
    sales_file = os.path.join(settings.DATA_DIRECTORY, "sales.csv")
    with open(sales_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['order_id', 'customer', 'amount', 'date', 'region'])
        
        sales_data = [
            [1001, 'John Doe', 150.50, '2025-01-15', 'North'],
            [1002, 'Jane Smith', 320.00, '2025-01-16', 'South'],
            [1003, 'Bob Johnson', 89.99, '2025-01-17', 'East'],
            [1004, 'Alice Brown', 220.75, '2025-01-18', 'West'],
            [1005, 'Charlie Davis', 445.20, '2025-01-19', 'North'],
            [1006, 'Eve Wilson', 178.30, '2025-01-20', 'South'],
            [1007, 'Frank Miller', 560.00, '2025-01-21', 'East'],
            [1008, 'Grace Lee', 95.50, '2025-01-22', 'West'],
            [1009, 'Henry Taylor', 310.25, '2025-01-23', 'North'],
            [1010, 'Ivy Anderson', 198.80, '2025-01-24', 'South'],
            [1011, 'Jack Brown', 425.00, '2025-01-25', 'East'],
            [1012, 'Kelly White', 189.50, '2025-01-26', 'West'],
            [1013, 'Leo Martin', 275.30, '2025-01-27', 'North'],
            [1014, 'Mia Garcia', 340.00, '2025-01-28', 'South'],
            [1015, 'Noah Martinez', 198.75, '2025-01-29', 'East'],
            [1016, 'Olivia Lopez', 456.20, '2025-01-30', 'West'],
            [1017, 'Peter Gonzalez', 312.50, '2025-01-31', 'North'],
            [1018, 'Quinn Rodriguez', 178.90, '2025-02-01', 'South'],
            [1019, 'Ruby Hernandez', 289.60, '2025-02-02', 'East'],
            [1020, 'Sam Wilson', 401.25, '2025-02-03', 'West'],
        ]
        
        writer.writerows(sales_data)
    
    print(f"✓ Created {sales_file} with {len(sales_data)} records")
    
    # Create inventory.json
    inventory_file = os.path.join(settings.DATA_DIRECTORY, "inventory.json")
    inventory_data = [
        {"product_id": 1, "stock_level": 45, "warehouse_location": "A1"},
        {"product_id": 2, "stock_level": 150, "warehouse_location": "A2"},
        {"product_id": 3, "stock_level": 300, "warehouse_location": "A3"},
        {"product_id": 4, "stock_level": 25, "warehouse_location": "B1"},
        {"product_id": 5, "stock_level": 35, "warehouse_location": "B2"},
        {"product_id": 6, "stock_level": 80, "warehouse_location": "B3"},
        {"product_id": 7, "stock_level": 60, "warehouse_location": "C1"},
        {"product_id": 8, "stock_level": 50, "warehouse_location": "C2"},
        {"product_id": 9, "stock_level": 100, "warehouse_location": "C3"},
        {"product_id": 10, "stock_level": 200, "warehouse_location": "D1"},
        {"product_id": 11, "stock_level": 70, "warehouse_location": "D2"},
        {"product_id": 12, "stock_level": 180, "warehouse_location": "D3"},
        {"product_id": 13, "stock_level": 250, "warehouse_location": "E1"},
        {"product_id": 14, "stock_level": 95, "warehouse_location": "E2"},
        {"product_id": 15, "stock_level": 120, "warehouse_location": "E3"},
    ]
    
    with open(inventory_file, 'w', encoding='utf-8') as f:
        json.dump(inventory_data, f, indent=2)
    
    print(f"✓ Created {inventory_file} with {len(inventory_data)} records")
    
    # Create customers.csv
    customers_file = os.path.join(settings.DATA_DIRECTORY, "customers.csv")
    with open(customers_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['customer_id', 'name', 'email', 'phone', 'country'])
        
        customers_data = [
            [1, 'John Doe', 'john.doe@email.com', '555-0101', 'USA'],
            [2, 'Jane Smith', 'jane.smith@email.com', '555-0102', 'Canada'],
            [3, 'Bob Johnson', 'bob.johnson@email.com', '555-0103', 'UK'],
            [4, 'Alice Brown', 'alice.brown@email.com', '555-0104', 'Australia'],
            [5, 'Charlie Davis', 'charlie.davis@email.com', '555-0105', 'USA'],
            [6, 'Eve Wilson', 'eve.wilson@email.com', '555-0106', 'Canada'],
            [7, 'Frank Miller', 'frank.miller@email.com', '555-0107', 'UK'],
            [8, 'Grace Lee', 'grace.lee@email.com', '555-0108', 'Australia'],
            [9, 'Henry Taylor', 'henry.taylor@email.com', '555-0109', 'USA'],
            [10, 'Ivy Anderson', 'ivy.anderson@email.com', '555-0110', 'Canada'],
        ]
        
        writer.writerows(customers_data)
    
    print(f"✓ Created {customers_file} with {len(customers_data)} records")


def main():
    """Main function to create all sample data"""
    print("Creating sample test data for QueryForge...\n")
    
    try:
        # Create sample database tables
        create_sample_tables()
        print()
        
        # Create sample CSV and JSON files
        create_sample_csv_files()
        print()
        
        print("✅ Sample test data created successfully!")
        print(f"\nDatabase location: {get_db_path()}")
        print(f"Data files location: {settings.DATA_DIRECTORY}")
        
    except Exception as e:
        print(f"\n❌ Error creating sample data: {e}")
        raise


if __name__ == "__main__":
    main()

from app.services.mcp import get_filesystem_metadata
import json

context = get_filesystem_metadata('data')
files = context.get('files', [])

print("=== Files in data/ directory ===")
for f in files:
    path = f.get('path')
    ftype = f.get('type')
    row_count = f.get('row_count_estimate', 0)
    preview_rows = f.get('preview_rows', 0)
    
    if ftype == 'csv':
        print(f"{path}: {ftype} - {row_count} total rows, {preview_rows} in preview")
    elif ftype == 'json':
        structure = f.get('structure', {})
        total_items = f.get('total_items', 0)
        preview_count = f.get('preview_count', 0)
        print(f"{path}: {ftype} - {total_items} total items, {preview_count} in preview")

print("\n=== inventory.json Preview ===")
inventory = [f for f in files if 'inventory.json' in f.get('path', '').lower()]
if inventory:
    inv_file = inventory[0]
    preview = inv_file.get('preview', [])
    total = inv_file.get('total_items', 0)
    print(f"Total items: {total}")
    print(f"Preview contains {len(preview)} items")
    print("\nFirst 3 items:")
    for i, item in enumerate(preview[:3], 1):
        print(f"  Item {i}: {item}")
    
    if len(preview) > 3:
        print(f"\n  ... and {len(preview) - 3} more items")
else:
    print("inventory.json not found!")

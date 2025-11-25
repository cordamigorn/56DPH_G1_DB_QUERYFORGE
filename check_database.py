"""
Veritabanında ne değişti?
"""
import sqlite3
import json

conn = sqlite3.connect('queryforge.db')
cursor = conn.cursor()

print("\n" + "="*80)
print("VERİTABANINDA NELER DEĞİŞTİ?")
print("="*80)

# 1. Pipelines tablosu
print("\n1️⃣  PIPELINES TABLOSU (Oluşturulan Pipeline'lar)")
print("-" * 80)
cursor.execute('SELECT id, user_id, prompt_text, status, created_at FROM Pipelines ORDER BY id DESC LIMIT 5')
rows = cursor.fetchall()

if rows:
    print(f"Toplam {len(rows)} pipeline bulundu:\n")
    for row in rows:
        print(f"Pipeline ID: {row[0]}")
        print(f"  User ID: {row[1]}")
        print(f"  İstek: {row[2]}")
        print(f"  Durum: {row[3]}")
        print(f"  Oluşturulma: {row[4]}")
        print()
else:
    print("Henüz pipeline oluşturulmamış.")

# 2. Pipeline Steps
print("\n2️⃣  PIPELINE_STEPS TABLOSU (Pipeline Adımları)")
print("-" * 80)
cursor.execute('''
    SELECT ps.id, ps.pipeline_id, ps.step_number, ps.code_type, 
           substr(ps.script_content, 1, 60) as content_preview
    FROM Pipeline_Steps ps
    ORDER BY ps.pipeline_id DESC, ps.step_number
    LIMIT 10
''')
rows = cursor.fetchall()

if rows:
    print(f"Toplam {len(rows)} adım bulundu:\n")
    for row in rows:
        print(f"Step ID: {row[0]} (Pipeline {row[1]} - Step {row[2]})")
        print(f"  Tip: {row[3].upper()}")
        print(f"  İçerik: {row[4]}...")
        print()
else:
    print("Henüz adım oluşturulmamış.")

# 3. Schema Snapshots
print("\n3️⃣  SCHEMA_SNAPSHOTS TABLOSU (Context Snapshots)")
print("-" * 80)
cursor.execute('SELECT id, pipeline_id, snapshot_time FROM Schema_Snapshots ORDER BY id DESC LIMIT 3')
rows = cursor.fetchall()

if rows:
    print(f"Toplam {len(rows)} snapshot bulundu:\n")
    for row in rows:
        print(f"Snapshot ID: {row[0]} (Pipeline {row[1]})")
        print(f"  Zaman: {row[2]}")
        
        # İlk snapshot'ın detaylarını göster
        if row == rows[0]:
            cursor.execute('SELECT db_structure, file_list FROM Schema_Snapshots WHERE id = ?', (row[0],))
            snap = cursor.fetchone()
            
            db_struct = json.loads(snap[0])
            file_list = json.loads(snap[1])
            
            print(f"  Tablolar: {len(db_struct.get('tables', []))} tablo")
            print(f"  Dosyalar: {file_list.get('total_files', 0)} dosya")
        print()
else:
    print("Henüz snapshot oluşturulmamış.")

# 4. Özet
print("\n" + "="*80)
print("ÖZET")
print("="*80)

cursor.execute('SELECT COUNT(*) FROM Pipelines')
pipeline_count = cursor.fetchone()[0]

cursor.execute('SELECT COUNT(*) FROM Pipeline_Steps')
step_count = cursor.fetchone()[0]

cursor.execute('SELECT COUNT(*) FROM Schema_Snapshots')
snapshot_count = cursor.fetchone()[0]

print(f"Toplam Pipeline: {pipeline_count}")
print(f"Toplam Adım: {step_count}")
print(f"Toplam Snapshot: {snapshot_count}")

print("\nBu kayıtlar VERİTABANINA kalıcı olarak kaydedildi.")
print("="*80)

conn.close()

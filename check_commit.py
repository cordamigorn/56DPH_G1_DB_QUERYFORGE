"""Quick script to check commit results"""
import sqlite3
import sys

# Fix Windows encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('queryforge.db')
cursor = conn.cursor()

print("=" * 60)
print("PIPELINE #5 COMMIT KONTROLU")
print("=" * 60)

# 1. Pipeline commit status
cursor.execute("SELECT id, commit_status, commit_time FROM Pipelines WHERE id=5")
pipeline = cursor.fetchone()
if pipeline:
    print(f"\n[OK] Pipeline #5 Durumu:")
    print(f"   Commit Status: {pipeline[1]}")
    print(f"   Commit Time: {pipeline[2]}")
else:
    print("\n[ERROR] Pipeline #5 bulunamadi")

# 2. Sales tablosu kontrolu
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Sales'")
if cursor.fetchone():
    print(f"\n[OK] Sales tablosu olusturulmus!")
    
    cursor.execute("SELECT COUNT(*) FROM Sales")
    count = cursor.fetchone()[0]
    print(f"   Toplam satir sayisi: {count}")
    
    cursor.execute("SELECT * FROM Sales LIMIT 10")
    rows = cursor.fetchall()
    print(f"\n   Ilk {len(rows)} satir:")
    for row in rows:
        print(f"   - {row}")
else:
    print("\n[ERROR] Sales tablosu bulunamadi!")

# 3. Snapshot kontrolu
cursor.execute("SELECT id, snapshot_time FROM Schema_Snapshots WHERE pipeline_id=5 ORDER BY id DESC LIMIT 1")
snapshot = cursor.fetchone()
if snapshot:
    print(f"\n[OK] Snapshot olusturulmus:")
    print(f"   Snapshot ID: {snapshot[0]}")
    print(f"   Snapshot Time: {snapshot[1]}")

# 4. Execution logs kontrolu
cursor.execute("SELECT COUNT(*) FROM Execution_Logs WHERE pipeline_id=5")
exec_count = cursor.fetchone()[0]
print(f"\n[OK] Execution Logs: {exec_count} kayit")

conn.close()
print("\n" + "=" * 60)


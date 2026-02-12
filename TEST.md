# 🧪 Test Scenarios & Usage Guide

## ✅ Verified Prompts
These prompts have been tested and confirmed to work:

1. **Import CSV to Table**
   > "Import sales.csv file into Sales table"

2. **Update Data from JSON**
   > "Update stock levels in products table's stock_quantity column from inventory.json"

3. **Create Table from CSV**
   > "Create customers table from customers.csv and import data"

4. **Insert JSON Data**
   > "Insert inventory.json file into products table (stock_quantity)"

5. **Join Operations**
   > "Create a new table named sales_with_customers by joining existing Sales and customers tables on Sales.customer = customers.name. Do not create or import customers/sales from files."

## 🚀 Execution Steps
1. **Create Pipeline**: Submit a prompt.
2. **Run in Sandbox**: Execute the generated steps.
3. **Commit**: Save changes.
4. **Verify**: Check results in **DB Browser for SQLite**.

## ⚙️ Setup & Running

### First Time Installation & Setup
Before running the app, you need to install the dependencies.

1. **Verify Python**: Ensure Python 3.10+ is installed.
   ```bash
   python --version
   ```

2. **Create Virtual Environment (Optional but Recommended)**:
   ```bash
   python -m venv venv
   ```

3. **Activate Virtual Environment**:
   - **Windows (PowerShell)**:
     ```bash
      .\venv\Scripts\Activate.ps1
     ```
   - **Mac/Linux**:
     ```bash
     source venv/bin/activate
     ```

4. **Install Requirements**:
   ```bash
   pip install -r requirements.txt
   ```
   *Note: This will install FastAPI, Uvicorn, Google GenAI, and other tools.*

### Start the Server
```bash
python -m uvicorn app.main:app --reload
```

### Access Web Interface
Link: [http://127.0.0.1:8000/web/](http://127.0.0.1:8000/web/)


# 🧹 TEMİZLİK VE SIFIRLAMA

## Recent Pipelines (Geçmiş İşlemleri) Temizleme ve Database Resetleme

Eğer geçmiş pipeline'ları silmek ve veritabanını sıfırlamak (en baştan kurulum gibi) istiyorsan şu kodu terminalde çalıştır:

```bash
python reset_database.py
```

Bu komut:
1. Tüm geçmiş pipeline kayıtlarını siler (Recent Pipelines temizlenir).
2. Sales ve diğer tablolardaki verileri temizler.
3. Sistemi ilk kurulduğu "temiz" haline döndürür.

Eğer veritabanı dosyasını tamamen silip uygulamanın yeniden oluşturmasını istersen:
1. `queryforge.db` dosyasını sil (Silmeden önce uygulamayı durdur).
2. Uygulamayı tekrar başlat (`python -m uvicorn app.main:app --reload`), dosya otomatik olarak sıfırdan oluşturulacaktır.

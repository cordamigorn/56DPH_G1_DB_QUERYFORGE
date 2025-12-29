# QueryForge Web UI Test Senaryoları

Bu dosya QueryForge web arayüzü üzerinden test etmek için hazırlanmış senaryoları içerir. Tüm testler tarayıcı üzerinden yapılabilir.

## 📋 İçindekiler

1. [Hızlı Başlangıç](#hızlı-başlangıç)
2. [Temel Test Senaryoları](#temel-test-senaryoları)
3. [Orta Seviye Test Senaryoları](#orta-seviye-test-senaryoları)
4. [İleri Seviye Test Senaryoları](#ileri-seviye-test-senaryoları)
5. [Hata Senaryoları](#hata-senaryoları)
6. [Tam İş Akışı Örnekleri](#tam-iş-akışı-örnekleri)

---

## Hızlı Başlangıç

### Sunucuyu Başlatma

```bash
# Terminal'de sunucuyu başlat
uvicorn app.main:app --reload

# Sunucu http://127.0.0.1:8000 adresinde çalışacak
```

### Web Arayüzüne Erişim

1. Tarayıcınızı açın
2. Şu adrese gidin: **http://127.0.0.1:8000/web/**
3. Ana sayfa açılmalı - "QueryForge - Automated Data Pipeline Generation System" başlığını görmelisiniz

### Temel Kontroller

- ✅ Ana sayfa açılıyor mu?
- ✅ "Recent Pipelines" tablosu görünüyor mu?
- ✅ Form alanları (User ID, Prompt) görünüyor mu?
- ✅ "Create Pipeline" butonu çalışıyor mu?

---

## Temel Test Senaryoları

### Senaryo 1: Basit CSV İçe Aktarma

**Amaç:** `sales.csv` dosyasını veritabanına aktarmak

**Adımlar:**

1. **Web arayüzüne git:** http://127.0.0.1:8000/web/
2. **Formu doldur:**
   - User ID: `1` (varsayılan değer)
   - Prompt: `sales.csv dosyasını veritabanına aktar`
3. **"Create Pipeline" butonuna tıkla**
4. **Bekle:** Pipeline oluşturulurken "Creating..." mesajı görünecek (birkaç saniye sürebilir)

**Beklenen Sonuç:**

✅ **Başarılı durumda:**
- Yeşil bir kutu görünecek: "✓ Pipeline created successfully!"
- Pipeline ID gösterilecek (örn: Pipeline ID: 1)
- Status: "pending"
- Steps sayısı gösterilecek (örn: Steps: 2-4)
- "View Pipeline Details" butonu görünecek
- Form temizlenecek
- "Recent Pipelines" tablosunda yeni pipeline görünecek

❌ **Hata durumunda:**
- Kırmızı bir kutu görünecek: "✗ Error: ..."
- Hata mesajı gösterilecek

**Kontrol Listesi:**
- [ ] Pipeline başarıyla oluşturuldu mu?
- [ ] Pipeline ID görünüyor mu?
- [ ] "Recent Pipelines" tablosunda yeni pipeline var mı?
- [ ] Status "pending" olarak görünüyor mu?

---

### Senaryo 2: JSON Dosyası İşleme

**Amaç:** `inventory.json` dosyasını işlemek

**Adımlar:**

1. **Web arayüzüne git:** http://127.0.0.1:8000/web/
2. **Formu doldur:**
   - User ID: `1`
   - Prompt: `inventory.json dosyasındaki stock seviyelerini products tablosundaki stock_quantity kolonuna güncelle`
3. **"Create Pipeline" butonuna tıkla**

**Beklenen Sonuç:**

✅ Pipeline başarıyla oluşturulmalı
✅ "Recent Pipelines" tablosunda görünmeli

---

### Senaryo 3: Pipeline Çalıştırma

**Önkoşul:** Senaryo 1 veya 2'yi tamamlamış olmalısınız

**Adımlar:**

1. **Ana sayfada "Recent Pipelines" tablosunda bir pipeline bulun**
2. **"View" butonuna tıklayın** → Pipeline detay sayfasına yönlendirileceksiniz
3. **"► Run in Sandbox" butonuna tıklayın**
4. **Onay penceresinde "OK" deyin**
5. **Bekleyin:** Pipeline çalıştırılırken sayfa yenilenecek

**Beklenen Sonuç (Başarılı):**

✅ Sayfa yenilendiğinde:
- Status badge'i **yeşil** olmalı: "success" veya "sandbox_success"
- Execution Logs sayısı artmış olmalı (örn: 2, 3, 4...)
- Pipeline Steps bölümünde tüm step'ler görünmeli
- Hata mesajı görünmemeli

**Beklenen Sonuç (Hatalı):**

❌ Sayfa yenilendiğinde:
- Status badge'i **kırmızı** olmalı: "failed" veya "sandbox_failed"
- Mavi bir pop-up penceresi görünebilir: "✗ Execution failed: ..."
- Hata mesajı gösterilecek (örn: "no such table", "file not found")

**Kontrol Listesi:**
- [ ] Pipeline çalıştırıldı mı?
- [ ] Status değişti mi? (pending → success/failed)
- [ ] Execution Logs sayısı arttı mı?
- [ ] Hata varsa, hata mesajı anlaşılır mı?

---

## Orta Seviye Test Senaryoları

### Senaryo 4: Veri Temizleme ve Dönüştürme

**Adımlar:**

1. **Ana sayfada formu doldur:**
   - User ID: `1`
   - Prompt: `sales.csv dosyasındaki boş amount değerlerine sahip satırları sil ve temizlenmiş veriyi orders tablosuna aktar`
2. **"Create Pipeline" butonuna tıkla**

**Beklenen Sonuç:**

✅ Pipeline oluşturulmalı
✅ En az 2-3 step içermeli
✅ İlk step'ler CSV temizleme (bash) içermeli
✅ Sonraki step'ler SQL tablo oluşturma içermeli

---

### Senaryo 5: Çoklu Dosya İşleme

**Adımlar:**

1. **Ana sayfada formu doldur:**
   - User ID: `1`
   - Prompt: `customers.csv ve sales.csv dosyalarını birleştir ve müşteri satış raporu oluştur`
2. **"Create Pipeline" butonuna tıkla**

**Beklenen Sonuç:**

✅ Pipeline oluşturulmalı
✅ Her iki dosyayı da işleyen step'ler olmalı
✅ JOIN veya birleştirme işlemi içeren SQL step'leri olmalı

---

### Senaryo 6: Pipeline Loglarını Görüntüleme

**Adımlar:**

1. **Ana sayfada "Recent Pipelines" tablosunda bir pipeline bulun**
2. **"View" butonuna tıklayın** → Pipeline detay sayfasına gidin
3. **"📋 View Full Logs" butonuna tıklayın** → Yeni sekmede JSON logları açılacak

**Beklenen Sonuç:**

✅ Yeni sekmede JSON formatında loglar görünmeli:
- `success: true`
- `pipeline_id`: Pipeline ID'si
- `original_prompt`: Orijinal prompt metni
- `execution_logs`: Array of execution log objects
- `repair_logs`: Array of repair log objects (varsa)
- `final_pipeline`: Final pipeline steps
- `overall_status`: "success", "failed", vb.

---

## İleri Seviye Test Senaryoları

### Senaryo 7: Otomatik Onarım (Repair)

**Önkoşul:** Başarısız bir pipeline oluşturun

**Adım 1: Hatalı Pipeline Oluştur**

1. **Ana sayfada formu doldur:**
   - User ID: `1`
   - Prompt: `sales.csv dosyasını yanlis_tablo_adi tablosuna aktar` (bilerek yanlış tablo adı)
2. **"Create Pipeline" butonuna tıkla**
3. **Pipeline oluşturulduktan sonra "View Pipeline Details" butonuna tıkla**

**Adım 2: Pipeline'ı Çalıştır (Başarısız olacak)**

1. **Pipeline detay sayfasında "► Run in Sandbox" butonuna tıkla**
2. **Onay penceresinde "OK" deyin**
3. **Bekle:** Pipeline başarısız olacak
4. **Sonuç:** Status "failed" olarak görünecek, hata mesajı pop-up'ta görünecek

**Adım 3: Onarımı Tetikle**

1. **"✔ Repair" butonuna tıkla**
2. **Onay penceresinde "OK" deyin**
3. **Bekle:** AI hatayı analiz edip düzeltecek (birkaç saniye sürebilir)
4. **Sonuç:** Pop-up penceresi görünecek: "✓ Repair completed! Status: ..."

**Beklenen Sonuç:**

✅ Repair başarılı olursa:
- Pop-up: "✓ Repair completed! Status: repaired_success"
- Sayfa yenilenecek
- Status badge'i yeşil olabilir
- Repair Attempts sayısı artmış olmalı (örn: 1)

❌ Repair başarısız olursa:
- Pop-up: "✗ Repair failed: ..."
- Status hala "failed" olabilir

---

### Senaryo 8: Pipeline Commit (Production'a Aktarma)

**Önkoşul:** Başarılı bir pipeline oluşturup çalıştırmış olmalısınız

**Adımlar:**

1. **Başarılı bir pipeline'ın detay sayfasına gidin** (Status: "success" olan)
2. **"✓ Commit to Production" butonuna tıkla**
3. **Onay penceresinde dikkatli okuyun:** "Commit this pipeline to production? This will apply all changes to the real database and filesystem."
4. **"OK" deyin** (sadece test için, gerçek production'da dikkatli olun!)
5. **Bekle:** Commit işlemi tamamlanacak

**Beklenen Sonuç:**

✅ Commit başarılı olursa:
- Pop-up: "✓ Pipeline committed successfully! Snapshot ID: ..."
- Sayfa yenilenecek
- Status badge'i mavi olabilir: "committed"
- Commit time gösterilebilir

**⚠️ DİKKAT:** Commit işlemi geri alınamaz (rollback özelliği varsa kullanılabilir). Test ortamında dikkatli kullanın!

---

## Hata Senaryoları

### Senaryo 9: Geçersiz Prompt

**Adımlar:**

1. **Ana sayfada formu doldur:**
   - User ID: `1`
   - Prompt: `` (boş bırakın)
2. **"Create Pipeline" butonuna tıkla**

**Beklenen Sonuç:**

❌ Tarayıcı form validasyonu:
- Prompt alanı kırmızı olabilir
- "Please provide a detailed prompt (at least 10 characters)" mesajı görünebilir
- Pipeline oluşturulmayacak

---

### Senaryo 10: Çok Kısa Prompt

**Adımlar:**

1. **Ana sayfada formu doldur:**
   - User ID: `1`
   - Prompt: `test` (çok kısa, 10 karakterden az)
2. **"Create Pipeline" butonuna tıkla**

**Beklenen Sonuç:**

❌ Kırmızı hata kutusu:
- "✗ Error: Please provide a detailed prompt (at least 10 characters)"
- Pipeline oluşturulmayacak

---

### Senaryo 11: Olmayan Pipeline'a Erişim

**Adımlar:**

1. **Tarayıcı adres çubuğuna yazın:** `http://127.0.0.1:8000/web/pipeline/99999/view`
2. **Enter'a basın**

**Beklenen Sonuç:**

❌ Hata sayfası veya boş sayfa görünebilir
❌ Veya "Pipeline not found" mesajı görünebilir

---

## Tam İş Akışı Örnekleri

### Örnek 1: Basit Veri İçe Aktarma İş Akışı

**Tam Adımlar:**

1. **Ana sayfaya git:** http://127.0.0.1:8000/web/
2. **Pipeline oluştur:**
   - User ID: `1`
   - Prompt: `sales.csv dosyasını veritabanına aktar`
   - "Create Pipeline" butonuna tıkla
   - Pipeline ID'yi not edin (örn: Pipeline ID: 3)
3. **Pipeline detay sayfasına git:**
   - "View Pipeline Details" butonuna tıkla
   - Veya "Recent Pipelines" tablosunda "View" butonuna tıkla
4. **Pipeline'ı çalıştır:**
   - "► Run in Sandbox" butonuna tıkla
   - Onay penceresinde "OK" deyin
   - Bekle: Status "success" veya "failed" olacak
5. **Sonuçları kontrol et:**
   - Status badge'ini kontrol edin
   - Execution Logs sayısını kontrol edin
   - "📋 View Full Logs" butonuna tıklayarak detaylı logları görün

**Kontrol Listesi:**
- [ ] Pipeline oluşturuldu mu?
- [ ] Pipeline çalıştırıldı mı?
- [ ] Status "success" mi?
- [ ] Execution Logs var mı?

---

### Örnek 2: Hata Onarımı İş Akışı

**Tam Adımlar:**

1. **Hatalı pipeline oluştur:**
   - Ana sayfada Prompt: `sales.csv dosyasını yanlis_tablo tablosuna aktar`
   - "Create Pipeline" butonuna tıkla
   - Pipeline ID'yi not edin
2. **Pipeline detay sayfasına git:**
   - "View Pipeline Details" veya "View" butonuna tıkla
3. **Pipeline'ı çalıştır (başarısız olacak):**
   - "► Run in Sandbox" butonuna tıkla
   - Bekle: Status "failed" olacak, hata mesajı görünecek
4. **Onarımı tetikle:**
   - "✔ Repair" butonuna tıkla
   - Onay penceresinde "OK" deyin
   - Bekle: AI hatayı analiz edip düzeltecek (10-30 saniye sürebilir)
5. **Sonucu kontrol et:**
   - Pop-up mesajını okuyun
   - Sayfa yenilendiğinde status'u kontrol edin
   - Repair Attempts sayısını kontrol edin

**Kontrol Listesi:**
- [ ] Pipeline başarısız oldu mu?
- [ ] Repair butonu çalıştı mı?
- [ ] Repair başarılı oldu mu?
- [ ] Status "repaired_success" veya "success" mi?

---

## Test Kontrol Listesi

Her test sonrası kontrol edin:

- [ ] `success: true` döndü mü?
- [ ] Pipeline ID geçerli bir sayı mı?
- [ ] `draft_pipeline` array'i boş değil mi?
- [ ] Her step'te `step_number`, `type`, `content` var mı?
- [ ] Step numaraları sıralı mı (1, 2, 3...)?
- [ ] `type` değerleri "bash" veya "sql" mi?
- [ ] Çalıştırma sonrası `overall_status` doğru mu?
- [ ] Hata durumunda `error` mesajı var mı?

---

## Web Arayüzü Özellikleri

### Ana Sayfa Özellikleri

- **Pipeline Oluşturma Formu:**
  - User ID girişi (varsayılan: 1)
  - Prompt textarea (doğal dil girişi)
  - "Create Pipeline" butonu

- **Recent Pipelines Tablosu:**
  - ID: Pipeline ID'si
  - Prompt: Prompt metninin ilk 60 karakteri
  - Status: Pipeline durumu (pending, success, failed, vb.)
  - Created: Oluşturulma tarihi
  - Actions: "View" butonu

### Pipeline Detay Sayfası Özellikleri

- **Pipeline Bilgileri:**
  - Prompt: Orijinal prompt metni
  - Status: Durum badge'i (renkli)
  - Execution Logs: Çalıştırma log sayısı
  - Repair Attempts: Onarım denemesi sayısı

- **Aksiyon Butonları:**
  - **► Run in Sandbox:** Pipeline'ı sandbox'ta çalıştır
  - **✔ Repair:** Başarısız pipeline'ı otomatik onar
  - **✓ Commit to Production:** Production'a aktar (dikkatli kullan!)
  - **📋 View Full Logs:** Detaylı logları JSON formatında görüntüle

- **Pipeline Steps:**
  - Her step için:
    - Step numarası ve tipi (bash/sql)
    - Step içeriği (kod)
    - Renkli kutular içinde gösterilir

### Status Badge Renkleri

- **Gri (pending):** Henüz çalıştırılmamış
- **Yeşil (success/sandbox_success):** Başarıyla tamamlandı
- **Kırmızı (failed/sandbox_failed):** Başarısız oldu
- **Mavi (committed):** Production'a aktarıldı

---

## Sorun Giderme

### Problem: Sayfa açılmıyor / Boş sayfa görünüyor
**Çözüm:**
- Sunucunun çalıştığından emin olun: `uvicorn app.main:app --reload`
- Doğru adresi kullandığınızdan emin olun: `http://127.0.0.1:8000/web/`
- Tarayıcı cache'ini temizleyin (Ctrl+Shift+Delete)
- Hard refresh yapın (Ctrl+F5)

### Problem: "Pipeline created successfully" mesajı görünmüyor
**Çözüm:**
- Gemini API key'inin geçerli olduğunu kontrol edin (`.env` dosyasında)
- Sunucu terminalinde hata mesajları var mı kontrol edin
- Prompt'un yeterince açıklayıcı olduğundan emin olun (en az 10 karakter)
- Birkaç saniye bekleyin, LLM işlemi zaman alabilir

### Problem: "Run in Sandbox" butonu çalışmıyor
**Çözüm:**
- Pipeline'ın oluşturulduğundan emin olun
- Sayfayı yenileyin (F5)
- Tarayıcı konsolunda (F12) JavaScript hataları var mı kontrol edin
- Sunucu loglarını kontrol edin

### Problem: Pipeline başarısız oluyor
**Çözüm:**
- Hata mesajını okuyun (pop-up penceresinde)
- "View Full Logs" butonuna tıklayarak detaylı logları görün
- "Repair" butonunu deneyin - otomatik onarım yapabilir
- Prompt'u daha açıklayıcı hale getirin

### Problem: Repair butonu çalışmıyor
**Çözüm:**
- Pipeline'ın başarısız olduğundan emin olun (Status: "failed")
- Gemini API key'inin geçerli olduğunu kontrol edin
- Birkaç saniye bekleyin, repair işlemi zaman alabilir (10-30 saniye)
- Sunucu loglarını kontrol edin

---

## Notlar ve İpuçları

### Genel Notlar

- ✅ Tüm testler `sandbox` modunda çalışır (production'a dokunmaz)
- ✅ Pipeline'lar veritabanında saklanır (`queryforge.db`)
- ✅ Her pipeline için execution logları tutulur
- ✅ Başarısız pipeline'lar otomatik onarılabilir (Repair butonu ile)
- ⚠️ Commit işlemi production'a dokunur - dikkatli kullanın!

### Kullanım İpuçları

1. **Prompt Yazarken:**
   - Açık ve net olun: "sales.csv dosyasını veritabanına aktar"
   - Dosya adlarını doğru yazın: `sales.csv`, `inventory.json`, `customers.csv`
   - Tablo adlarını belirtin: "products tablosuna ekle"
   - İşlemleri sıralayın: "önce temizle, sonra aktar"

2. **Pipeline Çalıştırırken:**
   - İlk çalıştırmada başarısız olabilir - normal!
   - "Repair" butonunu kullanın - çoğu hata otomatik düzeltilir
   - "View Full Logs" ile detaylı bilgi alın

3. **Hata Ayıklama:**
   - Tarayıcı konsolunu açın (F12) - JavaScript hatalarını görebilirsiniz
   - Sunucu terminalini izleyin - backend hatalarını görebilirsiniz
   - "View Full Logs" ile execution detaylarını görün

### Test Senaryoları Sırası

1. ✅ Senaryo 1: Basit CSV içe aktarma (başlangıç için ideal)
2. ✅ Senaryo 3: Pipeline çalıştırma (Senaryo 1'den sonra)
3. ✅ Senaryo 2: JSON işleme (farklı dosya tipi)
4. ✅ Senaryo 7: Repair testi (hata yönetimi)
5. ✅ Senaryo 4-5: Orta seviye senaryolar (karmaşık işlemler)

---

**Son Güncelleme:** 2025-12-29  
**Versiyon:** 2.0 (Web UI için güncellendi)


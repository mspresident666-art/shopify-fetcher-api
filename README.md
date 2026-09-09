# 🛍️ SYF — Shopify Product Fetcher API

Server API pribadi untuk fetch produk dari toko Shopify mana saja secara massal, lengkap dengan filter harga, stok, diskon, dan direct checkout URL.

---

## 🚀 Cara Menjalankan

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Jalankan server (lokal)
```bash
python main.py
```
Server berjalan di: `http://localhost:8000`

Buka dokumentasi interaktif: `http://localhost:8000/docs`

---

## 📡 Endpoints

| Method | Endpoint | Fungsi |
|--------|----------|--------|
| GET | `/api/v1/health` | Status server |
| GET | `/api/v1/discover` | Cari toko Shopify |
| GET/POST | `/api/v1/fetch` | Fetch produk 1 toko |
| GET/POST | `/api/v1/bulk` | Fetch produk banyak toko |

---

## 🔧 Contoh Penggunaan

### Health Check
```bash
curl http://localhost:8000/api/v1/health
```

### Discover Toko Fashion
```bash
curl "http://localhost:8000/api/v1/discover?category=fashion"
```

### Fetch Produk (di bawah $50, ada stok)
```bash
curl "http://localhost:8000/api/v1/fetch?url=allbirds.com&max_price=50&available=true&sort=price-asc"
```

### Fetch Produk Diskon
```bash
curl "http://localhost:8000/api/v1/fetch?url=gymshark.com&on_sale=true&limit=20"
```

### Bulk Fetch Banyak Toko
```bash
curl -X POST http://localhost:8000/api/v1/bulk \
  -H "Content-Type: application/json" \
  -d '{
    "stores": ["allbirds.com", "gymshark.com"],
    "filters": {
      "max_price": 50,
      "available_only": true,
      "sort": "price-asc"
    },
    "global_limit": 100,
    "parallel": true
  }'
```

### Fetch Semua Toko Fashion (via GET)
```bash
curl "http://localhost:8000/api/v1/bulk?category=fashion&max_price=30&available=true"
```

---

## 🐍 Python Client Example

```python
import requests

BASE = "http://localhost:8000"

# Fetch produk murah dari satu toko
r = requests.get(f"{BASE}/api/v1/fetch", params={
    "url": "allbirds.com",
    "max_price": 100,
    "available": "true",
    "sort": "price-asc"
})
data = r.json()
for p in data["products"]:
    c = p["_checkout"]
    print(f"📦 {p['title']} | {c['cheapest_checkout_price']} | {c['cheapest_checkout_url']}")
```

---

## 📦 Struktur Proyek

```
shopify-fetcher-api/
├── main.py              ← Entry point
├── requirements.txt
├── routers/
│   ├── health.py        ← GET /health
│   ├── discover.py      ← GET /discover
│   ├── fetch.py         ← GET+POST /fetch
│   └── bulk.py          ← GET+POST /bulk
├── core/
│   ├── fetcher.py       ← Fetch products.json dari Shopify
│   ├── filters.py       ← Filter & sort produk
│   └── formatter.py     ← Format _checkout field
└── data/
    └── stores.json      ← Database toko (bisa ditambah sendiri)
```

---

## ⚡ Rate Limits

- 60 requests per menit
- Max 20 toko per bulk request
- Max 6.250 produk per toko
- CORS enabled (bisa dipakai dari browser/frontend)

---

## 🌐 Deploy Online (Gratis)

### Railway
```bash
npm install -g @railway/cli
railway login
railway init
railway up
```

### Render
1. Push ke GitHub
2. Buka render.com → New Web Service
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`

---

## ➕ Menambah Toko ke Database

Edit file `data/stores.json` dan tambahkan entry baru:
```json
{
  "name": "Nama Toko",
  "url": "toko.myshopify.com",
  "domain": "toko.myshopify.com",
  "category": "fashion"
}
```

Kategori yang tersedia: `fashion`, `beauty`, `food`, `accessories`, `electronics`

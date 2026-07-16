# Nexus Terminal - Complete Setup Guide

## 📋 ما حالا داریم:

1. **Backend Server** - روی port 5000
2. **Frontend Server** - روی port 8000 (HTML server)

---

## 🚀 راه اندازی (Step by Step)

### **Terminal 1: Backend Server**

```bash
# اگر قبلاً بند کردی
cd D:\SRH\Courses\Agile\nexus-backend

# فعال کردن Virtual Environment
venv\Scripts\activate

# شروع Backend
python app.py
```

**باید ببینی:**
```
Running on: http://localhost:5000
```

---

### **Terminal 2: Frontend Server**

**نکس ترمینال جدید باز کن** (CTRL+SHIFT+T یا نیا window)

```bash
# به فولدری برو جایی serve_html.py هست
cd D:\SRH\Courses\Agile\nexus-backend

# یا جایی که فایل‌ها کپی کردی

# شروع Frontend
python serve_html.py
```

**باید ببینی:**
```
Running on: http://localhost:8000
```

---

### **Step 3: Browser**

دو ورقه باز کن:

1. **Backend Test:**
   ```
   http://localhost:5000/
   ```
   ✅ JSON جواب دهد

2. **Frontend:**
   ```
   http://localhost:8000/
   ```
   ✅ Nexus Terminal باز شود

---

## ⚠️ مهم:

**هر دو server باید اجرا شود:**
- Backend (5000) = API server
- Frontend (8000) = HTML server

اگر یکی بند باشد، کار نمی‌کنه!

---

## ✅ تست:

1. Browser میں http://localhost:8000 باز کن
2. HTML ماژول کلیک کن
3. Terminal میں Backend بخش چک کن - request باید آمد!

مثلاً:
```
127.0.0.1 - - [14/Jul/2026 13:34:05] "GET /api/crypto/price/bitcoin HTTP/1.1" 200
```

---

## 🛠️ Troubleshooting

| مشکل | حل |
|------|-----|
| "Port 5000 already in use" | صفحه دیگری 5000 استفاده می‌کند - بند کن یا بگیر |
| "Port 8000 already in use" | صفحه دیگری 8000 استفاده می‌کند - بند کن یا بگیر |
| "Cannot connect to backend" | Backend باید روی 5000 اجرا شود |
| "HTML نمی‌آید" | Frontend server (8000) باید اجرا شود |

---

**حالا شروع کن!** 🚀

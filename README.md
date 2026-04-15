# 🏭 Master Bot

## ⚙️ Setup (مرة وحدة فقط)

### 1. تثبيت المتطلبات
pip install -r requirements.txt

### 2. إعداد .env
copy .env.example .env
notepad .env

### 3. ⚠️ مهم — تسجيل جلسة Telethon أولاً
python setup_session.py
(يطلب كود التحقق — مرة وحدة فقط)

### 4. تشغيل الماستر بوت
python run.py

---

## 📋 الأوامر
- /start → القائمة الرئيسية
- /broadcast <msg> → إرسال لجميع مستخدمي كل البوتات

## 🔘 أزرار القائمة
- ➕ Add New Bot   → Token ← عدد المالكين ← IDs ← Credits ← تشغيل
- 📋 List Bots    → عرض كل البوتات وحالتها
- 🗑️ Remove Bot   → إيقاف وحذف بوت
- 📢 Broadcast    → إرسال جماعي

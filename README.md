# ClickUp Telegram Bot 🔔

نوتیفیکیشن کامنت‌های ClickUp به تلگرام - **فقط با GitHub Actions**

## 🚀 راه‌اندازی

### مرحله 1: Fork کنید
این repository را Fork کنید.

### مرحله 2: تنظیم Secrets
به Settings → Secrets and variables → Actions بروید و این‌ها را اضافه کنید:

| Secret | مقدار |
|--------|-------|
| `TELEGRAM_BOT_TOKEN` | توکن بات تلگرام |
| `TELEGRAM_CHAT_ID` | آیدی چت تلگرام |
| `CLICKUP_API_TOKEN` | توکن API کلیک‌آپ |
| `CLICKUP_TEAM_ID` | آیدی تیم کلیک‌آپ |

### مرحله 3: فعال کردن Actions
به تب Actions بروید و workflow را فعال کنید.

## ⚙️ نحوه کار

- هر **5 دقیقه** کامنت‌های جدید چک می‌شوند
- اگر کامنت جدیدی باشد، به تلگرام ارسال می‌شود
- تاریخ **شمسی** نمایش داده می‌شود

## 📱 نمونه پیام

```
📋 در تسک «نام تسک»

👤 کاربر نوشته:

💬 متن کامنت

🕐 ۸ آذر ۱۴۰۳ - ساعت ۱۲:۳۰
```

## 📝 License

MIT

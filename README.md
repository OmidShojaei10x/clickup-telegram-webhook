# ClickUp Telegram Webhook

🔔 سرور webhook برای ارسال نوتیفیکیشن‌های ClickUp به تلگرام

## 🚀 Deploy به Render.com

### مرحله 1: ساخت Repository در GitHub

1. به [github.com/new](https://github.com/new) بروید
2. نام: `clickup-telegram-webhook`
3. Public یا Private انتخاب کنید
4. Create repository بزنید

### مرحله 2: Push کردن کد

```bash
cd clickup-webhook
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/clickup-telegram-webhook.git
git push -u origin main
```

### مرحله 3: Deploy به Render

1. به [render.com](https://render.com) بروید و با GitHub لاگین کنید
2. روی **New** → **Web Service** کلیک کنید
3. Repository خود را انتخاب کنید
4. تنظیمات:
   - **Name**: `clickup-telegram-webhook`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`

### مرحله 4: تنظیم Environment Variables

در Render Dashboard، به **Environment** بروید و این متغیرها را اضافه کنید:

| Key | Value |
|-----|-------|
| `TELEGRAM_BOT_TOKEN` | `8490026779:AAEa-nrNKoJVs2-lqYwjaYSa2YoAWVw7HcI` |
| `TELEGRAM_CHAT_ID` | `918656204` |
| `CLICKUP_API_TOKEN` | `pk_32675396_J1WBBWGEDNYO4E0ERZVYRCJM26IO782E` |

### مرحله 5: تنظیم ClickUp Automation

بعد از deploy، URL شما این شکلی خواهد بود:
```
https://clickup-telegram-webhook.onrender.com/webhook
```

این URL را در ClickUp Automation وارد کنید.

## 📌 Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | اطلاعات سرور |
| `/webhook` | POST | دریافت webhook از ClickUp |
| `/health` | GET | بررسی سلامت سرور |
| `/test` | GET | تست ارسال پیام |

## 🔧 Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | ✅ | توکن بات تلگرام |
| `TELEGRAM_CHAT_ID` | ✅ | آیدی چت تلگرام |
| `CLICKUP_API_TOKEN` | ❌ | توکن API کلیک‌آپ (برای دریافت متن کامنت) |

## 📝 License

MIT


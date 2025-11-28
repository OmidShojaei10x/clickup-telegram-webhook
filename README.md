# ClickUp Telegram Webhook 🔔

سرور webhook برای ارسال نوتیفیکیشن‌های ClickUp به تلگرام

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/clickup-webhook?referralCode=omid)

## 🚀 Deploy با یک کلیک

روی دکمه بالا کلیک کنید و این Environment Variables را وارد کنید:

| Variable | Value |
|----------|-------|
| `TELEGRAM_BOT_TOKEN` | توکن بات تلگرام |
| `TELEGRAM_CHAT_ID` | آیدی چت تلگرام |
| `CLICKUP_API_TOKEN` | توکن API کلیک‌آپ |

## 📌 Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | اطلاعات سرور |
| `/webhook` | POST | دریافت webhook از ClickUp |
| `/health` | GET | بررسی سلامت سرور |
| `/test` | GET | تست ارسال پیام |

## 🔧 تنظیم ClickUp

بعد از deploy، URL را در ClickUp Automation وارد کنید:
```
https://YOUR-APP.up.railway.app/webhook
```

## 📝 License

MIT

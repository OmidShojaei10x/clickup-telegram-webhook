"""
ClickUp Webhook Server - Production Version
سرور webhook برای دریافت نوتیفیکیشن از ClickUp و ارسال به تلگرام
"""

import logging
import os
from datetime import datetime

import httpx
from flask import Flask, request, jsonify
from flask_cors import CORS

# ─────────────────────────────────────────────────────────────────
#  تنظیمات
# ─────────────────────────────────────────────────────────────────

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "918656204")
CLICKUP_API_TOKEN = os.getenv("CLICKUP_API_TOKEN")

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("webhook")

app = Flask(__name__)
CORS(app)

# ─────────────────────────────────────────────────────────────────
#  تبدیل تاریخ شمسی
# ─────────────────────────────────────────────────────────────────

def gregorian_to_jalali(gy: int, gm: int, gd: int) -> tuple:
    """تبدیل تاریخ میلادی به شمسی"""
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    
    if gy > 1600:
        jy = 979
        gy -= 1600
    else:
        jy = 0
        gy -= 621
    
    gy2 = gy + 1 if gm > 2 else gy
    days = (365 * gy) + (gy2 + 3) // 4 - (gy2 + 99) // 100 + (gy2 + 399) // 400 - 80 + gd + g_d_m[gm - 1]
    
    jy += 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    
    if days < 186:
        jm = 1 + days // 31
        jd = 1 + days % 31
    else:
        jm = 7 + (days - 186) // 30
        jd = 1 + (days - 186) % 30
    
    return jy, jm, jd


def format_jalali_datetime(timestamp) -> str:
    """تبدیل timestamp به تاریخ و ساعت شمسی"""
    if not timestamp:
        return get_jalali_now()
    try:
        ts = int(timestamp)
        if ts > 10000000000:
            ts = ts / 1000
        dt = datetime.fromtimestamp(ts)
        
        jy, jm, jd = gregorian_to_jalali(dt.year, dt.month, dt.day)
        
        months = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
                  "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]
        
        time_str = dt.strftime("%H:%M")
        date_str = f"{jd} {months[jm-1]} {jy}"
        
        return f"{date_str} - ساعت {time_str}"
    except:
        return get_jalali_now()


def get_jalali_now() -> str:
    """دریافت تاریخ و ساعت شمسی الان"""
    now = datetime.now()
    jy, jm, jd = gregorian_to_jalali(now.year, now.month, now.day)
    
    months = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
              "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]
    
    time_str = now.strftime("%H:%M")
    date_str = f"{jd} {months[jm-1]} {jy}"
    
    return f"{date_str} - ساعت {time_str}"


# ─────────────────────────────────────────────────────────────────
#  ClickUp API
# ─────────────────────────────────────────────────────────────────

def get_latest_comment(task_id: str) -> dict:
    """دریافت آخرین کامنت یک تسک"""
    if not CLICKUP_API_TOKEN:
        return None
    
    url = f"https://api.clickup.com/api/v2/task/{task_id}/comment"
    headers = {"Authorization": CLICKUP_API_TOKEN}
    
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                comments = data.get("comments", [])
                if comments:
                    return comments[0]
    except Exception as e:
        logger.error(f"ClickUp API error: {e}")
    
    return None


# ─────────────────────────────────────────────────────────────────
#  ارسال به تلگرام
# ─────────────────────────────────────────────────────────────────

def send_telegram_message(text: str) -> bool:
    """ارسال پیام به تلگرام"""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set")
        return False
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(url, data={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": text,
                "parse_mode": "Markdown"
            })
        
        if response.status_code == 200:
            logger.info("✅ Message sent to Telegram")
            return True
        else:
            logger.error(f"❌ Telegram error: {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return False


# ─────────────────────────────────────────────────────────────────
#  Routes
# ─────────────────────────────────────────────────────────────────

@app.route("/", methods=["GET"])
def home():
    """صفحه اصلی"""
    return jsonify({
        "status": "running",
        "service": "ClickUp Webhook Server",
        "version": "1.0.0",
        "endpoints": {
            "/webhook": "POST - Receive ClickUp webhooks",
            "/health": "GET - Health check"
        }
    })


@app.route("/webhook", methods=["POST"])
def webhook():
    """دریافت webhook از ClickUp"""
    try:
        data = request.json
        logger.info(f"📥 Webhook received")
        
        if "payload" in data:
            payload = data.get("payload", {})
            task_name = payload.get("name", "نامشخص")
            task_id = payload.get("id", "")
            
            logger.info(f"📌 Task: {task_name}")
            
            # دریافت آخرین کامنت
            comment_text = ""
            username = ""
            comment_date = ""
            
            if task_id and CLICKUP_API_TOKEN:
                comment = get_latest_comment(task_id)
                if comment:
                    comment_text = comment.get("comment_text", "")
                    user = comment.get("user", {})
                    username = user.get("username") or user.get("email", "")
                    comment_date = comment.get("date", "")
            
            # ساخت پیام
            if comment_text and username:
                date_str = format_jalali_datetime(comment_date)
                message = f"""📋 **در تسک «{task_name}»**

👤 **{username}** نوشته:

💬 {comment_text}

🕐 {date_str}"""
            else:
                message = f"""🔔 **فعالیت جدید در ClickUp**

📋 **تسک:** {task_name}

🕐 {get_jalali_now()}"""
            
            send_telegram_message(message)
        
        elif "body" in data:
            message = f"""🧪 **تست Webhook**

✅ سرور فعال است!

🕐 {get_jalali_now()}"""
            send_telegram_message(message)
        
        return jsonify({"status": "ok"}), 200
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/health", methods=["GET"])
def health():
    """Health check for uptime monitoring"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat()
    })


@app.route("/test", methods=["GET"])
def test():
    """تست ارسال پیام"""
    message = f"""🧪 **تست سرور**

✅ سرور ابری فعال است!
🕐 {get_jalali_now()}"""
    
    success = send_telegram_message(message)
    return jsonify({"status": "ok" if success else "error"})


# ─────────────────────────────────────────────────────────────────
#  اجرا
# ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    logger.info(f"Starting server on port {port}")
    app.run(host="0.0.0.0", port=port)


"""
ClickUp Webhook - Vercel Serverless Function
"""

import os
import json
from datetime import datetime
from http.client import HTTPSConnection
from urllib.parse import urlencode

# ─────────────────────────────────────────────────────────────────
#  تنظیمات
# ─────────────────────────────────────────────────────────────────

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "918656204")
CLICKUP_API_TOKEN = os.getenv("CLICKUP_API_TOKEN")


# ─────────────────────────────────────────────────────────────────
#  تبدیل تاریخ شمسی
# ─────────────────────────────────────────────────────────────────

def gregorian_to_jalali(gy, gm, gd):
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


def get_jalali_now():
    now = datetime.now()
    jy, jm, jd = gregorian_to_jalali(now.year, now.month, now.day)
    months = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
              "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]
    return f"{jd} {months[jm-1]} {jy} - ساعت {now.strftime('%H:%M')}"


def format_jalali_datetime(timestamp):
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
        return f"{jd} {months[jm-1]} {jy} - ساعت {dt.strftime('%H:%M')}"
    except:
        return get_jalali_now()


# ─────────────────────────────────────────────────────────────────
#  API Functions
# ─────────────────────────────────────────────────────────────────

def get_latest_comment(task_id):
    if not CLICKUP_API_TOKEN:
        return None
    try:
        conn = HTTPSConnection("api.clickup.com")
        conn.request("GET", f"/api/v2/task/{task_id}/comment", 
                     headers={"Authorization": CLICKUP_API_TOKEN})
        response = conn.getresponse()
        if response.status == 200:
            data = json.loads(response.read())
            comments = data.get("comments", [])
            if comments:
                return comments[0]
    except:
        pass
    return None


def send_telegram_message(text):
    if not TELEGRAM_BOT_TOKEN:
        return False
    try:
        conn = HTTPSConnection("api.telegram.org")
        params = urlencode({
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "Markdown"
        })
        conn.request("POST", f"/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                     body=params,
                     headers={"Content-Type": "application/x-www-form-urlencoded"})
        response = conn.getresponse()
        return response.status == 200
    except:
        return False


# ─────────────────────────────────────────────────────────────────
#  Vercel Handler
# ─────────────────────────────────────────────────────────────────

def handler(request):
    """Vercel serverless function handler"""
    
    # Health check
    if request.method == "GET":
        return {
            "statusCode": 200,
            "body": json.dumps({
                "status": "running",
                "service": "ClickUp Webhook",
                "time": get_jalali_now()
            })
        }
    
    # Webhook POST
    if request.method == "POST":
        try:
            body = request.body
            if isinstance(body, bytes):
                body = body.decode('utf-8')
            data = json.loads(body) if body else {}
            
            if "payload" in data:
                payload = data.get("payload", {})
                task_name = payload.get("name", "نامشخص")
                task_id = payload.get("id", "")
                
                # دریافت کامنت
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
            
            return {"statusCode": 200, "body": json.dumps({"status": "ok"})}
            
        except Exception as e:
            return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
    
    return {"statusCode": 405, "body": "Method not allowed"}





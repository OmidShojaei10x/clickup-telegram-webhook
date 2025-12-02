"""
ClickUp & Telegram Webhook - Vercel Serverless Function
"""

import os
import json
import sys
from datetime import datetime, timedelta, timezone
from http.client import HTTPSConnection
from urllib.parse import urlencode

# ─────────────────────────────────────────────────────────────────
#  تنظیمات (کپی شده برای اطمینان از دسترسی در Vercel)
# ─────────────────────────────────────────────────────────────────

# تیم‌ها را اینجا تعریف کنید
TEAMS = {
    "facility": {
        "chat_id": "-1002914241474",
        "name": "Facility & Partnership",
        "emoji": "🏢",
        "enabled": True,
    }
}

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
# اگر CHAT_ID در env نبود، از پیش‌فرض استفاده کن
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "918656204")
CLICKUP_API_TOKEN = os.getenv("CLICKUP_API_TOKEN")

# تایم‌زون ایران
IRAN_TZ = timezone(timedelta(hours=3, minutes=30))


# ─────────────────────────────────────────────────────────────────
#  توابع کمکی (تاریخ و ...)
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
    now = datetime.now(IRAN_TZ)
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
        dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(IRAN_TZ)
        jy, jm, jd = gregorian_to_jalali(dt.year, dt.month, dt.day)
        months = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
                  "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]
        return f"{jd} {months[jm-1]} {jy} - ساعت {dt.strftime('%H:%M')}"
    except:
        return get_jalali_now()


# ─────────────────────────────────────────────────────────────────
#  Telegram Helper Functions
# ─────────────────────────────────────────────────────────────────

def telegram_request(method, params):
    if not TELEGRAM_BOT_TOKEN:
        return None
    try:
        conn = HTTPSConnection("api.telegram.org")
        headers = {"Content-Type": "application/json"}
        conn.request("POST", f"/bot{TELEGRAM_BOT_TOKEN}/{method}", 
                     body=json.dumps(params), headers=headers)
        response = conn.getresponse()
        if response.status == 200:
            return json.loads(response.read())
    except Exception as e:
        print(f"Telegram Error: {e}")
    return None

def send_message(text, chat_id=None, reply_markup=None):
    chat_id = chat_id or TELEGRAM_CHAT_ID
    params = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    if reply_markup:
        params["reply_markup"] = reply_markup
    return telegram_request("sendMessage", params)

def send_photo(photo_file_id_or_url, caption, chat_id=None, reply_markup=None):
    chat_id = chat_id or TELEGRAM_CHAT_ID
    params = {
        "chat_id": chat_id,
        "photo": photo_file_id_or_url,
        "caption": caption,
        "parse_mode": "Markdown"
    }
    if reply_markup:
        params["reply_markup"] = reply_markup
    return telegram_request("sendPhoto", params)

def answer_callback(callback_query_id, text=None):
    params = {"callback_query_id": callback_query_id}
    if text:
        params["text"] = text
    return telegram_request("answerCallbackQuery", params)

def edit_message_reply_markup(chat_id, message_id, reply_markup=None):
    params = {"chat_id": chat_id, "message_id": message_id}
    if reply_markup:
        params["reply_markup"] = reply_markup
    return telegram_request("editMessageReplyMarkup", params)


# ─────────────────────────────────────────────────────────────────
#  ClickUp Helper Functions
# ─────────────────────────────────────────────────────────────────

def get_clickup_data(path):
    if not CLICKUP_API_TOKEN: return None
    try:
        conn = HTTPSConnection("api.clickup.com")
        conn.request("GET", path, headers={"Authorization": CLICKUP_API_TOKEN})
        response = conn.getresponse()
        if response.status == 200:
            return json.loads(response.read())
    except:
        pass
    return None

def get_latest_comment(task_id):
    data = get_clickup_data(f"/api/v2/task/{task_id}/comment")
    if data and "comments" in data:
        return data["comments"][0] if data["comments"] else None
    return None

def get_task_details(task_id):
    return get_clickup_data(f"/api/v2/task/{task_id}")

def parse_comment(comment):
    text_parts = []
    images = []
    
    if not comment: return "", []
    
    comment_content = comment.get("comment", [])
    if isinstance(comment_content, list):
        for part in comment_content:
            if part.get("type") == "image":
                img = part.get("image", {})
                url = img.get("thumbnail_large") or img.get("url")
                if url: images.append(url)
            elif part.get("text"):
                text_parts.append(part.get("text"))
                
    text = "".join(text_parts).strip() or comment.get("comment_text", "")
    return text, images

def get_team_from_task(task_data):
    """تشخیص تیم از فیلد Requestor"""
    if not task_data: return None, None
    
    custom_fields = task_data.get('custom_fields', [])
    for field in custom_fields:
        if "requestor" in field.get('name', '').lower():
            value = field.get('value')
            options = field.get('type_config', {}).get('options', [])
            if value is not None and options:
                for opt in options:
                    if opt.get('orderindex') == value:
                        team_name = opt.get('name', '').lower()
                        for key, conf in TEAMS.items():
                            if key in team_name or team_name in key:
                                return key, conf
    return None, None


# ─────────────────────────────────────────────────────────────────
#  Vercel Handler
# ─────────────────────────────────────────────────────────────────

def handler(request):
    """Main entry point for Vercel"""
    
    if request.method == "GET":
        return {
            "statusCode": 200,
            "body": json.dumps({"status": "running", "time": get_jalali_now()})
        }
    
    if request.method == "POST":
        try:
            body = request.body
            if isinstance(body, bytes):
                body = body.decode('utf-8')
            data = json.loads(body) if body else {}
            
            # ───────────────────────────────────────────────
            # 1. Telegram Updates (Callback / Message)
            # ───────────────────────────────────────────────
            if "update_id" in data:
                
                # الف) دکمه‌ها (Callback Query)
                if "callback_query" in data:
                    cb = data["callback_query"]
                    cb_id = cb["id"]
                    cb_data = cb.get("data", "")
                    msg = cb.get("message", {})
                    chat_id = msg.get("chat", {}).get("id")
                    msg_id = msg.get("message_id")
                    
                    if ":" in cb_data:
                        action, team_key = cb_data.split(":", 1)
                        team = TEAMS.get(team_key)
                        
                        if not team:
                            answer_callback(cb_id, "❌ تیم یافت نشد")
                            return {"statusCode": 200}

                        if action == "send":
                            # ارسال مستقیم
                            text = msg.get("text") or msg.get("caption")
                            photo = msg.get("photo")
                            
                            sent = False
                            if photo:
                                # آخرین سایز عکس (بزرگترین)
                                file_id = photo[-1]["file_id"]
                                sent = send_photo(file_id, text, team["chat_id"])
                            else:
                                sent = send_message(text, team["chat_id"])
                                
                            if sent:
                                answer_callback(cb_id, "✅ ارسال شد")
                                edit_message_reply_markup(chat_id, msg_id, reply_markup=None)
                            else:
                                answer_callback(cb_id, "❌ خطا در ارسال")

                        elif action == "edit":
                            # درخواست متن جدید
                            team_name = team.get("name")
                            force_reply = {
                                "force_reply": True,
                                "input_field_placeholder": f"متن برای {team_name}..."
                            }
                            prompt = f"✍️ متن ویرایش شده برای تیم **{team_name}** را در پاسخ به این پیام بنویسید.\n\n(ID: {team_key})"
                            send_message(prompt, chat_id, reply_markup=force_reply)
                            answer_callback(cb_id, "📝 منتظر متن جدید...")

                # ب) پیام ریپلای شده (برای ادیت)
                elif "message" in data:
                    m = data["message"]
                    reply = m.get("reply_to_message")
                    if reply and "text" in reply:
                        rt = reply["text"]
                        # چک کردن الگوی ID
                        if "(ID: " in rt:
                            try:
                                team_key = rt.split("(ID: ")[1].split(")")[0]
                                team = TEAMS.get(team_key)
                                new_text = m.get("text")
                                if team and new_text:
                                    send_message(new_text, team["chat_id"])
                                    send_message("✅ پیام ویرایش شده ارسال شد.", m["chat"]["id"])
                            except:
                                pass
                
                return {"statusCode": 200, "body": "ok"}

            # ───────────────────────────────────────────────
            # 2. ClickUp Webhook
            # ───────────────────────────────────────────────
            if "payload" in data or "event" in data:
                # ساپورت فرمت‌های مختلف وب‌هوک
                payload = data.get("payload", {}) if "payload" in data else data
                
                task_id = payload.get("id")
                task_name = payload.get("name", "تسک")
                
                # دریافت اطلاعات تکمیلی
                task_data = get_task_details(task_id) if task_id else None
                comment_data = get_latest_comment(task_id) if task_id else None
                
                team_key, team_conf = get_team_from_task(task_data)
                
                if comment_data:
                    # کامنت جدید
                    user = comment_data.get("user", {})
                    username = user.get("username") or user.get("email", "کاربر")
                    date_ts = comment_data.get("date")
                    date_str = format_jalali_datetime(date_ts)
                    
                    comment_text, images = parse_comment(comment_data)
                    if not comment_text and images:
                        comment_text = "📷 تصویر جدید"

                    # ساخت پیام
                    msg = f"💬 **کامنت جدید**\n\n"
                    msg += f"📋 **تسک:** {task_name}\n\n"
                    msg += f"💬 **کامنت:** {comment_text}\n\n"
                    msg += f"👤 **نوشته:** {username}\n\n"
                    msg += f"🕐 **تاریخ:** {date_str}\n\n"
                    msg += f"🔗 [مشاهده تسک](https://app.clickup.com/t/{task_id})"

                    # دکمه‌ها
                    reply_markup = None
                    if team_key and team_conf:
                        reply_markup = {
                            "inline_keyboard": [[
                                {"text": "ارسال به تیم 📤", "callback_data": f"send:{team_key}"},
                                {"text": "ادیت و ارسال ✏️", "callback_data": f"edit:{team_key}"}
                            ]]
                        }
                    
                    # ارسال به ادمین
                    if images:
                        for img in images:
                            send_photo(img, msg, reply_markup=reply_markup)
                    else:
                        send_message(msg, reply_markup=reply_markup)
                
                else:
                    # تغییر وضعیت یا فعالیت دیگر
                    msg = f"🔔 **فعالیت جدید**\n\n📋 **تسک:** {task_name}\n\n🕐 {get_jalali_now()}\n\n🔗 [مشاهده تسک](https://app.clickup.com/t/{task_id})"
                    send_message(msg)

                return {"statusCode": 200, "body": "ok"}

        except Exception as e:
            print(f"Error: {str(e)}")
            return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
            
    return {"statusCode": 405, "body": "Method not allowed"}

from flask import Flask, request, jsonify
from flask_cors import CORS
import os, json, urllib.request, urllib.parse, hashlib, hmac
from datetime import datetime, timedelta, timezone

# ─────────────────────────────────────────────────────────────────────────────────
#  📋 تنظیمات از فایل config.py
# ─────────────────────────────────────────────────────────────────────────────────
try:
    from config import TEAMS, NOTIFICATIONS, GENERAL
except ImportError:
    # تنظیمات پیش‌فرض اگر فایل config نبود
    TEAMS = {
        "facility": {
            "chat_id": "-1002914241474",
            "name": "Facility & Partnership",
            "emoji": "🏢",
            "enabled": True,
        }
    }
    NOTIFICATIONS = {
        "comment_added": True,
        "status_changed": True,
        "task_completed": True,
        "task_created": True,
    }
    GENERAL = {
        "default_chat_id": "918656204",
        "also_send_to_default": True,
        "show_task_link": True,
        "team_field_name": "requestor",
    }

# تایم‌زون ایران (UTC+3:30)
IRAN_TZ = timezone(timedelta(hours=3, minutes=30))

app = Flask(__name__)
CORS(app, origins=["https://app.clickup.com", "https://api.clickup.com"])

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID") or GENERAL.get("default_chat_id")
CLICKUP_API_TOKEN = os.getenv("CLICKUP_API_TOKEN")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")


# ═══════════════════════════════════════════════════════════════════════════════
#  🛠️ توابع کمکی
# ═══════════════════════════════════════════════════════════════════════════════

def jalali(gy,gm,gd):
    g=[0,31,59,90,120,151,181,212,243,273,304,334]
    jy=979 if gy>1600 else 0
    gy-=1600 if gy>1600 else 621
    gy2=gy+1 if gm>2 else gy
    d=(365*gy)+(gy2+3)//4-(gy2+99)//100+(gy2+399)//400-80+gd+g[gm-1]
    jy+=33*(d//12053);d%=12053
    jy+=4*(d//1461);d%=1461
    if d>365:jy+=(d-1)//365;d=(d-1)%365
    return (jy,1+d//31,1+d%31) if d<186 else (jy,7+(d-186)//30,1+(d-186)%30)

def fmt(ts):
    try:
        ts=int(ts)
        if ts>1e10:ts/=1000
        dt=datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(IRAN_TZ)
        jy,jm,jd=jalali(dt.year,dt.month,dt.day)
        m=["فروردین","اردیبهشت","خرداد","تیر","مرداد","شهریور","مهر","آبان","آذر","دی","بهمن","اسفند"]
        return f"{jd} {m[jm-1]} {jy} - ساعت {dt.strftime('%H:%M')}"
    except:
        now=datetime.now(IRAN_TZ)
        jy,jm,jd=jalali(now.year,now.month,now.day)
        m=["فروردین","اردیبهشت","خرداد","تیر","مرداد","شهریور","مهر","آبان","آذر","دی","بهمن","اسفند"]
        return f"{jd} {m[jm-1]} {jy} - ساعت {now.strftime('%H:%M')}"

def get_task_link(task_id):
    return f"https://app.clickup.com/t/{task_id}"


# ═══════════════════════════════════════════════════════════════════════════════
#  📤 توابع ارسال پیام
# ═══════════════════════════════════════════════════════════════════════════════

def make_request(method, params):
    if not TELEGRAM_BOT_TOKEN: return None
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}"
    headers = {'Content-Type': 'application/json'}
    try:
        req = urllib.request.Request(url, data=json.dumps(params).encode(), headers=headers)
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read())
    except Exception as e:
        print(f"Telegram Error: {e}")
        return None

def send_telegram(text, chat_id=None, reply_markup=None):
    target_chat = chat_id or TELEGRAM_CHAT_ID
    if not target_chat: return False
    params = {
        'chat_id': target_chat,
        'text': text,
        'parse_mode': 'Markdown'
    }
    if reply_markup:
        params['reply_markup'] = reply_markup
    return make_request("sendMessage", params) is not None

def send_photo(photo_url, caption, chat_id=None, reply_markup=None):
    target_chat = chat_id or TELEGRAM_CHAT_ID
    if not target_chat: return False
    params = {
        'chat_id': target_chat,
        'photo': photo_url,
        'caption': caption,
        'parse_mode': 'Markdown'
    }
    if reply_markup:
        params['reply_markup'] = reply_markup
    return make_request("sendPhoto", params) is not None

def edit_message_reply_markup(chat_id, message_id, reply_markup=None):
    params = {
        'chat_id': chat_id,
        'message_id': message_id
    }
    if reply_markup:
        params['reply_markup'] = reply_markup
    return make_request("editMessageReplyMarkup", params)

def answer_callback_query(callback_query_id, text=None):
    params = {'callback_query_id': callback_query_id}
    if text: params['text'] = text
    return make_request("answerCallbackQuery", params)

def send_to_team(team_key, text, photo_url=None):
    """ارسال پیام به گروه تیم"""
    team = TEAMS.get(team_key)
    if not team or not team.get("enabled") or not team.get("chat_id"):
        return False
    
    if photo_url:
        return send_photo(photo_url, text, team["chat_id"])
    else:
        return send_telegram(text, team["chat_id"])


# ═══════════════════════════════════════════════════════════════════════════════
#  🔍 توابع ClickUp API
# ═══════════════════════════════════════════════════════════════════════════════

def get_comment(task_id):
    if not CLICKUP_API_TOKEN:return None
    try:
        r=urllib.request.Request(f"https://api.clickup.com/api/v2/task/{task_id}/comment",headers={'Authorization':CLICKUP_API_TOKEN})
        return json.loads(urllib.request.urlopen(r,timeout=10).read()).get('comments',[])[0]
    except:return None

def get_task(task_id):
    if not CLICKUP_API_TOKEN:return None
    try:
        r=urllib.request.Request(f"https://api.clickup.com/api/v2/task/{task_id}",headers={'Authorization':CLICKUP_API_TOKEN})
        return json.loads(urllib.request.urlopen(r,timeout=10).read())
    except:return None

def get_images_from_comment(comment):
    images = []
    comment_parts = comment.get('comment', [])
    if isinstance(comment_parts, list):
        for part in comment_parts:
            if part.get('type') == 'image':
                img = part.get('image', {})
                url = img.get('thumbnail_large') or img.get('url')
                if url:
                    images.append(url)
    return images

def get_text_from_comment(comment):
    text_parts = []
    comment_parts = comment.get('comment', [])
    if isinstance(comment_parts, list):
        for part in comment_parts:
            if part.get('type') != 'image':
                txt = part.get('text', '').strip()
                if txt and not txt.endswith('.png') and not txt.endswith('.jpg'):
                    text_parts.append(txt)
    return ' '.join(text_parts).strip() or comment.get('comment_text', '')


# ═══════════════════════════════════════════════════════════════════════════════
#  🏢 تشخیص تیم
# ═══════════════════════════════════════════════════════════════════════════════

def get_team_from_task(task_data):
    """تشخیص تیم از فیلد Requestor"""
    if not task_data:
        return None, None
    
    team_field_name = GENERAL.get("team_field_name", "requestor").lower()
    custom_fields = task_data.get('custom_fields', [])
    
    for field in custom_fields:
        field_name = field.get('name', '').lower()
        if team_field_name in field_name:
            value = field.get('value')
            options = field.get('type_config', {}).get('options', [])
            
            if value is not None and options:
                for opt in options:
                    if opt.get('orderindex') == value:
                        team_name = opt.get('name', '').lower()
                        # پیدا کردن تیم در config
                        for team_key, team_config in TEAMS.items():
                            if team_key in team_name or team_name in team_key:
                                return team_key, team_config
    
    return None, None


# ═══════════════════════════════════════════════════════════════════════════════
#  📝 ساخت پیام
# ═══════════════════════════════════════════════════════════════════════════════

def build_comment_message(task_name, task_id, comment_text, username, date, team_config=None):
    """ساخت پیام کامنت جدید"""
    # ❌ حذف خط تیم طبق درخواست کاربر
    
    task_link = get_task_link(task_id)
    
    # ✅ بلد کردن عنوان‌ها
    msg = f"💬 **کامنت جدید**\n\n"
    # msg += team_line  <-- Removed
    msg += f"📋 **تسک:** {task_name}\n\n"
    msg += f"💬 **کامنت:** {comment_text}\n\n"
    msg += f"👤 **نوشته:** {username}\n\n"
    msg += f"🕐 **تاریخ:** {fmt(date)}\n\n"
    
    if GENERAL.get("show_task_link", True):
        msg += f"🔗 [مشاهده تسک]({task_link})"
    
    return msg

def build_activity_message(task_name, task_id, team_config=None):
    """ساخت پیام فعالیت جدید"""
    # ❌ حذف خط تیم طبق درخواست کاربر
    
    task_link = get_task_link(task_id)
    
    msg = f"🔔 **فعالیت جدید**\n\n"
    msg += f"📋 **تسک:** {task_name}\n\n"
    msg += f"🕐 **تاریخ:** {fmt(None)}\n\n"
    
    if GENERAL.get("show_task_link", True):
        msg += f"🔗 [مشاهده تسک]({task_link})"
    
    return msg


# ═══════════════════════════════════════════════════════════════════════════════
#  🌐 Routes
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/")
def home():
    return jsonify({
        "status": "running",
        "service": "ClickUp Team Updater Bot",
        "teams": list(TEAMS.keys())
    })

@app.route("/health")
def health():
    return jsonify({"status": "healthy"})

@app.route("/config")
def show_config():
    """نمایش تنظیمات فعلی"""
    secret = request.args.get('key')
    if secret != os.getenv("TEST_KEY", "clickup2025"):
        return jsonify({"error": "Forbidden"}), 403
    
    return jsonify({
        "teams": {k: {"name": v["name"], "enabled": v["enabled"]} for k, v in TEAMS.items()},
        "notifications": NOTIFICATIONS,
        "general": GENERAL
    })

def verify_webhook(req):
    if not WEBHOOK_SECRET:
        return True
    signature = req.headers.get('X-Signature')
    if not signature:
        return False
    body = req.get_data()
    expected = hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)


@app.route("/webhook", methods=["POST"])
def webhook():
    if not verify_webhook(request):
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.json or {}
    
    if "payload" in data:
        p = data["payload"]
        task_name = p.get("name", "?")
        task_id = p.get("id", "")
        
        # گرفتن اطلاعات تسک و کامنت
        task_data = get_task(task_id) if task_id else None
        comment = get_comment(task_id) if task_id else None
        
        # تشخیص تیم
        team_key, team_config = get_team_from_task(task_data)
        
        if comment and NOTIFICATIONS.get("comment_added", True):
            # کامنت جدید
            user = comment.get("user", {})
            username = user.get('username') or user.get('email', '?')
            images = get_images_from_comment(comment)
            comment_text = get_text_from_comment(comment)
            
            if not comment_text and images:
                comment_text = "📷 تصویر"
            
            msg = build_comment_message(
                task_name, task_id, comment_text, username,
                comment.get('date'), team_config
            )
            
            # دکمه‌های ارسال
            reply_markup = None
            if team_key and team_config and team_config.get("enabled"):
                 reply_markup = {
                    "inline_keyboard": [
                        [
                            {"text": "ارسال به تیم 📤", "callback_data": f"send:{team_key}"},
                            {"text": "ادیت و ارسال ✏️", "callback_data": f"edit:{team_key}"}
                        ]
                    ]
                }
            
            # ارسال به ادمین (همیشه)
            if images:
                for img_url in images:
                    send_photo(img_url, msg, reply_markup=reply_markup)
            else:
                send_telegram(msg, reply_markup=reply_markup)
            
            # ❌ ارسال خودکار به تیم حذف شد (طبق فلو جدید)
        
        else:
            # فعالیت جدید (بدون کامنت)
            msg = build_activity_message(task_name, task_id, team_config)
            send_telegram(msg) # فقط به ادمین
    
    elif "body" in data:
        send_telegram(f"🧪 **تست Webhook**\n\n✅ سرور فعال است!\n\n🕐 {fmt(None)}")
    
    return jsonify({"status": "ok"})


@app.route("/telegram", methods=["POST"])
def telegram_webhook():
    """هندلر وب‌هوک تلگرام برای دریافت دکمه‌ها و پیام‌ها"""
    update = request.json
    if not update:
        return jsonify({"status": "no data"})

    # 1. هندل کردن دکمه‌ها (Callback Query)
    if "callback_query" in update:
        cb = update["callback_query"]
        cb_id = cb["id"]
        data = cb.get("data", "")
        message = cb.get("message", {})
        chat_id = message.get("chat", {}).get("id")
        message_id = message.get("message_id")
        
        # تشخیص اکشن و تیم
        if ":" in data:
            action, team_key = data.split(":", 1)
            team = TEAMS.get(team_key)
            
            if not team:
                answer_callback_query(cb_id, "❌ تیم یافت نشد")
                return jsonify({"status": "team not found"})

            if action == "send":
                # ارسال مستقیم متن موجود به تیم
                text_to_send = message.get("text") or message.get("caption")
                # اگر عکس بود
                photo = message.get("photo")
                photo_url = None
                if photo:
                     # گرفتن بزرگترین سایز عکس
                     photo_id = photo[-1]["file_id"]
                     photo_url = photo_id # تلگرام file_id را در sendPhoto قبول می‌کند

                # ارسال به تیم
                if photo_url:
                    success = send_photo(photo_url, text_to_send, team["chat_id"])
                else:
                    success = send_telegram(text_to_send, team["chat_id"])
                
                if success:
                    answer_callback_query(cb_id, "✅ ارسال شد")
                    # حذف دکمه‌ها و اضافه کردن تیک
                    edit_message_reply_markup(chat_id, message_id, reply_markup=None)
                    # آپدیت متن پیام ادمین برای نشان دادن وضعیت (اختیاری، ساده‌ترین کار حذف دکمه است)
                else:
                    answer_callback_query(cb_id, "❌ خطا در ارسال")

            elif action == "edit":
                # درخواست متن جدید از ادمین (ForceReply)
                team_name = team.get("name")
                prompt_msg = f"✍️ لطفا متن جدید برای ارسال به تیم **{team_name}** را ریپلای کنید:"
                
                # ارسال پیام ForceReply
                force_reply = {
                    "force_reply": True,
                    "input_field_placeholder": f"متن برای {team_name}..."
                }
                
                # ما team_key را در متن پیام مخفی می‌کنیم یا در دیتابیس نگه می‌داریم.
                # چون دیتابیس نداریم، از یک ترفند استفاده می‌کنیم:
                # نام تیم را در متن پیام می‌آوریم و در هندلر پیام آن را پیدا می‌کنیم.
                # بهتر: team_key را به صورت مخفی (invisible char) یا فقط با مچ کردن نام تیم پیدا کنیم.
                # راه ساده: در متن پیام بگذاریم: "متن جدید برای ارسال به تیم {team_name} (کد: {team_key})"
                
                prompt_msg = f"✍️ متن ویرایش شده برای تیم **{team_name}** را در پاسخ به این پیام بنویسید.\n\n(ID: {team_key})"
                
                make_request("sendMessage", {
                    "chat_id": chat_id,
                    "text": prompt_msg,
                    "reply_markup": force_reply
                })
                answer_callback_query(cb_id, "📝 منتظر متن جدید...")

    # 2. هندل کردن پیام‌های ریپلای شده (Message)
    elif "message" in update:
        msg = update["message"]
        reply = msg.get("reply_to_message")
        
        if reply and "text" in reply:
            reply_text = reply["text"]
            # چک کردن الگوی پیام ما
            if "متن ویرایش شده برای تیم" in reply_text and "ID:" in reply_text:
                # استخراج team_key
                try:
                    # فرمت: ... (ID: team_key)
                    team_key = reply_text.split("(ID: ")[1].split(")")[0]
                    new_text = msg.get("text")
                    
                    team = TEAMS.get(team_key)
                    if team and new_text:
                        if send_telegram(new_text, team["chat_id"]):
                            send_telegram("✅ پیام ویرایش شده با موفقیت ارسال شد.", msg["chat"]["id"])
                        else:
                            send_telegram("❌ خطا در ارسال به تیم.", msg["chat"]["id"])
                except:
                    pass

    return jsonify({"status": "ok"})


@app.route("/test")
def test():
    secret = request.args.get('key')
    if secret != os.getenv("TEST_KEY", "clickup2025"):
        return jsonify({"error": "Forbidden"}), 403
    
    # لیست تیم‌های فعال
    active_teams = [f"{v['emoji']} {v['name']}" for k, v in TEAMS.items() if v.get('enabled')]
    teams_list = "\n".join(active_teams) if active_teams else "هیچ تیمی فعال نیست"
    
    msg = f"🧪 **تست سرور**\n\n"
    msg += f"✅ سرور ابری فعال است!\n\n"
    msg += f"📋 **تیم‌های فعال:**\n{teams_list}\n\n"
    msg += f"🕐 {fmt(None)}"
    
    send_telegram(msg)
    return jsonify({"status": "ok", "active_teams": len(active_teams)})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))

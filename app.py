from flask import Flask, request, jsonify
from flask_cors import CORS
import os, json, urllib.request, urllib.parse
from datetime import datetime

app = Flask(__name__)
CORS(app)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "918656204")
TELEGRAM_GROUP_FACILITY = os.getenv("TELEGRAM_GROUP_FACILITY", "-1002914241474")  # گروه Facility & Partnership
CLICKUP_API_TOKEN = os.getenv("CLICKUP_API_TOKEN")

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
        dt=datetime.fromtimestamp(ts)
        jy,jm,jd=jalali(dt.year,dt.month,dt.day)
        m=["فروردین","اردیبهشت","خرداد","تیر","مرداد","شهریور","مهر","آبان","آذر","دی","بهمن","اسفند"]
        return f"{jd} {m[jm-1]} {jy} - ساعت {dt.strftime('%H:%M')}"
    except:
        now=datetime.now()
        jy,jm,jd=jalali(now.year,now.month,now.day)
        m=["فروردین","اردیبهشت","خرداد","تیر","مرداد","شهریور","مهر","آبان","آذر","دی","بهمن","اسفند"]
        return f"{jd} {m[jm-1]} {jy} - ساعت {now.strftime('%H:%M')}"

def send_telegram(text, chat_id=None):
    if not TELEGRAM_BOT_TOKEN:return
    target_chat = chat_id or TELEGRAM_CHAT_ID
    d=urllib.parse.urlencode({'chat_id':target_chat,'text':text,'parse_mode':'Markdown'}).encode()
    try:urllib.request.urlopen(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",d,timeout=10)
    except:pass

def get_comment(task_id):
    if not CLICKUP_API_TOKEN:return None
    try:
        r=urllib.request.Request(f"https://api.clickup.com/api/v2/task/{task_id}/comment",headers={'Authorization':CLICKUP_API_TOKEN})
        return json.loads(urllib.request.urlopen(r,timeout=10).read()).get('comments',[])[0]
    except:return None

def get_task(task_id):
    """گرفتن اطلاعات کامل تسک شامل فیلدهای سفارشی"""
    if not CLICKUP_API_TOKEN:return None
    try:
        r=urllib.request.Request(f"https://api.clickup.com/api/v2/task/{task_id}",headers={'Authorization':CLICKUP_API_TOKEN})
        return json.loads(urllib.request.urlopen(r,timeout=10).read())
    except:return None

def is_facility_task(task_data):
    """چک کردن اینکه آیا requestor این تسک Facility است"""
    if not task_data:return False
    custom_fields = task_data.get('custom_fields', [])
    for field in custom_fields:
        field_name = field.get('name', '').lower()
        if 'requestor' in field_name:
            value = field.get('value')
            options = field.get('type_config', {}).get('options', [])
            
            # dropdown با مقدار عددی (orderindex)
            if value is not None and options:
                for opt in options:
                    if opt.get('orderindex') == value:
                        opt_name = opt.get('name', '').lower()
                        # Facility با orderindex=1
                        if opt_name == 'facility':
                            return True
    return False

@app.route("/")
def home():
    return jsonify({"status":"running","service":"ClickUp Webhook"})

@app.route("/health")
def health():
    return jsonify({"status":"healthy"})

@app.route("/webhook",methods=["POST"])
def webhook():
    data=request.json or {}
    if "payload" in data:
        p=data["payload"]
        name,tid=p.get("name","?"),p.get("id","")
        
        # گرفتن اطلاعات تسک و کامنت
        task_data = get_task(tid) if tid else None
        c=get_comment(tid) if tid else None
        
        if c:
            u=c.get("user",{})
            msg=f"🟢 **تسک:** {name}\n\n💬 **کامنت:** {c.get('comment_text','')}\n\n👤 **نوشته:** {u.get('username') or u.get('email','?')}\n\n🕐 **تاریخ:** {fmt(c.get('date'))}"
        else:
            msg=f"🔔 **فعالیت جدید**\n\n📋 **تسک:** {name}\n\n🕐 {fmt(None)}"
        
        # همیشه به چت اصلی ارسال کن
        send_telegram(msg)
        
        # اگر requestor تیم facility است، به گروه هم ارسال کن
        if is_facility_task(task_data):
            send_telegram(msg, TELEGRAM_GROUP_FACILITY)
            
    elif "body" in data:
        send_telegram(f"🧪 **تست Webhook**\n\n✅ سرور فعال است!\n\n🕐 {fmt(None)}")
    return jsonify({"status":"ok"})

@app.route("/test")
def test():
    send_telegram(f"🧪 **تست سرور**\n\n✅ سرور ابری فعال است!\n\n🕐 {fmt(None)}")
    return jsonify({"status":"ok"})

if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.getenv("PORT",5000)))

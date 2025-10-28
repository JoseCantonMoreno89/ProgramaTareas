# twilio_client.py
import os
from twilio.rest import Client
from dotenv import load_dotenv
from db import list_pending_tasks
from datetime import datetime, timedelta

load_dotenv()

TWILIO_ACCOUNT_SID = os.getenv("USc3e4b5521b41528bbc68a7b7cec07fb5")
TWILIO_AUTH_TOKEN  = os.getenv("571fdfac5b0bf840737cf7c204dda132")
TWILIO_WHATSAPP_FROM = os.getenv("+14155238886")  # ej: 'whatsapp:+1415xxxxxxx'
TARGET_NUMBER = os.getenv("+34628094958")         # tu número: 'whatsapp:+34xxxxxx'

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

def send_whatsapp_message(body: str):
    message = client.messages.create(
        from_=TWILIO_WHATSAPP_FROM,
        body=body,
        to=TARGET_NUMBER
    )
    return message.sid

def _parse_due(due_value):
    if not due_value:
        return None
    try:
        return datetime.fromisoformat(due_value)
    except Exception:
        try:
            from datetime import datetime as _dt
            return _dt.strptime(due_value, "%Y-%m-%d %H:%M:%S")
        except Exception:
            return None

def send_reminders_via_whatsapp():
    tasks = list_pending_tasks()
    now = datetime.now()
    soon = now + timedelta(hours=48)
    lines = []
    for t in tasks:
        due = _parse_due(t.get('due'))
        if due and now <= due <= soon:
            lines.append(f"{t['title']} — entrega: {due.strftime('%Y-%m-%d %H:%M')}")
    if not lines:
        body = "No hay tareas próximas en las próximas 48 horas."
    else:
        body = "Recordatorio de tareas próximas:\n" + "\n".join(lines)
    sid = send_whatsapp_message(body)
    return sid

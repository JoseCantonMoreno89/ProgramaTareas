# send_reminders.py
from twilio_client import send_reminders_via_whatsapp
from db import init_db

if __name__ == "__main__":
    # Aseguramos que la BD y tablas existen
    init_db()
    sid = send_reminders_via_whatsapp()
    print("Mensaje enviado, sid:", sid)

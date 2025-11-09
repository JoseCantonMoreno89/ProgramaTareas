# telegram_client.py
import os
import re
from datetime import datetime, timedelta
import telegram
from db import list_pending_tasks, mark_as_principal_by_title

# --- Configuración (se carga desde variables de entorno) ---
BOT_TOKEN = os.getenv("8109216707:AAFTCT8gXb_tqHBWoFcrwYTfcfVUwCmp6ms")
# Tu ID de chat numérico personal (para que el bot TE envíe recordatorios)
CHAT_ID = os.getenv("730910001") 
# La URL pública de tu servidor (para que Telegram te envíe mensajes)
SERVER_URL = os.getenv("http://93.189.95.135:5000")  

if not all([BOT_TOKEN, CHAT_ID, SERVER_URL]):
    print("¡ADVERTENCIA! Faltan variables de entorno de Telegram (BOT_TOKEN, CHAT_ID, SERVER_URL)")
    # (El bot no funcionará sin esto)

bot = None
if BOT_TOKEN:
    bot = telegram.Bot(token=BOT_TOKEN)
else:
    print("No se encontró BOT_TOKEN, el bot de Telegram está desactivado.")

def setup_telegram_webhook():
    """Le dice a Telegram dónde enviar las actualizaciones (mensajes)."""
    if not bot:
        return False
        
    webhook_url = f"{SERVER_URL}/telegram-webhook"
    try:
        if bot.set_webhook(url=webhook_url):
            print(f"Webhook de Telegram configurado en: {webhook_url}")
            return True
        else:
            print("Error al configurar el webhook de Telegram.")
            return False
    except Exception as e:
        print(f"Error al configurar webhook: {e}")
        return False

def _parse_due(due_value: str):
    """Convierte el campo 'due' (almacenado como ISO string) a datetime o None."""
    if not due_value:
        return None
    try:
        return datetime.fromisoformat(due_value)
    except (ValueError, TypeError):
        return None # Ignorar fechas mal formadas

def check_and_send_reminders():
    """Función llamada por el scheduler (cada 5 horas)"""
    if not bot:
        print("Scheduler: Bot de Telegram no configurado, saltando envío.")
        return

    print(f"[{datetime.now()}] Ejecutando envío de recordatorios Telegram...")
    
    tasks = list_pending_tasks()
    now = datetime.now()
    # Tareas que venzan entre ahora y las próximas 48 horas
    soon = now + timedelta(hours=48) 
    
    lines = []
    for t in tasks:
        due = _parse_due(t.get('due'))
        status_icon = "🟡" if t.get('status') == 'principal' else "🔴"
        
        # Solo notificar si la tarea tiene fecha y está en el rango
        if due and (now <= due <= soon):
            lines.append(f"{status_icon} *{t['title']}* — Entrega: {due.strftime('%Y-%m-%d %H:%M')}")
    
    if not lines:
        body = "¡Buen trabajo! No tienes tareas próximas en las siguientes 48 horas."
    else:
        body = "🔔 *Recordatorio de Tareas Próximas:*\n\n" + "\n".join(lines)
    
    try:
        bot.send_message(
            chat_id=CHAT_ID,
            text=body,
            parse_mode=telegram.ParseMode.MARKDOWN
        )
        print("Mensaje de recordatorio enviado a Telegram.")
    except Exception as e:
        print(f"Error al enviar mensaje a Telegram: {e}")

def handle_telegram_update(update_json):
    """Procesa un mensaje recibido desde Telegram."""
    if not bot:
        return
        
    update = telegram.Update.de_json(update_json, bot)
    if not update.message or not update.message.text:
        return

    msg = update.message
    body = msg.text.strip()

    # Buscamos patrón "lo voy a hacer <nombre tarea>"
    m = re.match(r"^\s*lo voy a hacer\s+(.+)$", body, flags=re.IGNORECASE)
    
    if m:
        title = m.group(1).strip()
        task_id = mark_as_principal_by_title(title)
        if task_id:
            reply_text = f"✅ ¡Entendido! Tarea '{title}' marcada como principal."
        else:
            reply_text = f"😕 No encontré la tarea pendiente: '{title}'."
    else:
        reply_text = ("Mensaje recibido. Para marcar una tarea como principal, "
                      "envía: \n`lo voy a hacer <nombre exacto de la tarea>`")

    # Responder al usuario
    bot.send_message(chat_id=msg.chat_id, text=reply_text, parse_mode=telegram.ParseMode.MARKDOWN)

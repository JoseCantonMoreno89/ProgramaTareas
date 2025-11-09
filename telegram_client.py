# telegram_client.py
import os
import re
from datetime import datetime, timedelta
import telegram
import pytz # <-- ¡Importante para la corrección de zona horaria!
from db import list_pending_tasks, mark_as_principal_by_title

# --- Configuración (se carga desde variables de entorno) ---
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID") 

if not all([BOT_TOKEN, CHAT_ID]):
    print("¡ADVERTENCIA! Faltan variables de entorno de Telegram (BOT_TOKEN, CHAT_ID)")

bot = None
if BOT_TOKEN:
    bot = telegram.Bot(token=BOT_TOKEN)
else:
    print("No se encontró BOT_TOKEN, el bot de Telegram está desactivado.")

LAST_UPDATE_ID = None
SERVER_TIMEZONE = pytz.timezone("Europe/Madrid") # Zona horaria definida

def _parse_due(due_value: str):
    """Convierte el campo 'due' (almacenado como ISO string) a datetime o None."""
    if not due_value:
        return None
    try:
        return datetime.fromisoformat(due_value)
    except (ValueError, TypeError):
        return None 

def check_and_send_reminders():
    """Función llamada por el scheduler (cada 5 horas)"""
    if not bot:
        print("Scheduler: Bot de Telegram no configurado, saltando envío de recordatorios.")
        return

    print(f"[{datetime.now()}] Ejecutando envío de recordatorios Telegram...")
    
    tasks = list_pending_tasks()
    
    # --- ¡CORRECCIÓN DE DEPURACIÓN! ---
    # Obtenemos la hora actual CON la zona horaria correcta
    now = datetime.now(SERVER_TIMEZONE)
    soon = now + timedelta(hours=48) 
    
    lines = []
    for t in tasks:
        due_naive = _parse_due(t.get('due'))
        status_icon = "🟡" if t.get('status') == 'principal' else "🔴"
        
        if due_naive:
            # Convertimos la hora "naive" de la BD a la zona horaria del servidor
            due_aware = SERVER_TIMEZONE.localize(due_naive.replace(tzinfo=None))
            
            # Comparamos ambas horas "aware" (conscientes de la zona horaria)
            if (now <= due_aware <= soon):
                lines.append(f"{status_icon} *{t['title']}* — Entrega: {due_aware.strftime('%Y-%m-%d %H:%M')}")
    
    if not lines:
        body = "¡Buen trabajo! No tienes tareas próximas en las siguientes 48 horas."
    else:
        body = "🔔 *Recordatorio de Tareas Próximas:*\n\n" + "\n".join(lines)
    
    try:
        bot.send_message(chat_id=CHAT_ID, text=body, parse_mode=telegram.ParseMode.MARKDOWN)
        print("Mensaje de recordatorio enviado a Telegram.")
    except Exception as e:
        print(f"Error al enviar mensaje a Telegram: {e}")


def _handle_start_command(msg):
    """Gestiona el comando /start."""
    print("Recibido comando /start")
    
    # --- ¡CAMBIO SOLICITADO! ---
    # El usuario solo quiere un mensaje de éxito
    reply_text = "¡Hola! El bot funciona exitosamente. ✅"
    
    bot.send_message(chat_id=msg.chat_id, text=reply_text)

def _handle_lo_voy_a_hacer_command(msg, match):
    """Gestiona el comando 'lo voy a hacer...'"""
    print("Recibido comando 'lo voy a hacer...'")
    title = match.group(1).strip()
    task_id = mark_as_principal_by_title(title)
    if task_id:
        reply_text = f"✅ ¡Entendido! Tarea '{title}' marcada como principal."
    else:
        reply_text = f"😕 No encontré la tarea pendiente: '{title}'."
    
    bot.send_message(chat_id=msg.chat_id, text=reply_text, parse_mode=telegram.ParseMode.MARKDOWN)

def _process_message(msg):
    """Procesa un solo mensaje recibido del bot y lo enruta."""
    if not msg or not msg.text:
        return

    body = msg.text.strip()
    
    if body == "/start":
        _handle_start_command(msg)
        return

    m = re.match(r"^\s*lo voy a hacer\s+(.+)$", body, flags=re.IGNORECASE)
    if m:
        _handle_lo_voy_a_hacer_command(msg, m)
        return

    reply_text = ("Mensaje recibido. Para marcar una tarea como principal, "
                  "envía: \n`lo voy a hacer <nombre de la tarea>`\n\n"
                  "O envía `/start` para ver tu estado.")
    bot.send_message(chat_id=msg.chat_id, text=reply_text, parse_mode=telegram.ParseMode.MARKDOWN)


def check_for_messages():
    """Función llamada por el scheduler (cada 30 seg) para buscar comandos."""
    global LAST_UPDATE_ID
    if not bot:
        return

    try:
        updates = bot.get_updates(offset=LAST_UPDATE_ID, timeout=10)
        
        for update in updates:
            _process_message(update.message)
            LAST_UPDATE_ID = update.update_id + 1 
            
    except Exception as e:
        print(f"Error durante el polling de Telegram: {e}")

# telegram_client.py
import os
import re
from datetime import datetime, timedelta
import telegram
from db import list_pending_tasks, mark_as_principal_by_title

# --- Configuración (se carga desde variables de entorno) ---
BOT_TOKEN = os.getenv("8109216707:AAFTCT8gXb_tqHBWoFcrwYTfcfVUwCmp6ms")
CHAT_ID = os.getenv("730910001") 

if not all([BOT_TOKEN, CHAT_ID]):
    print("¡ADVERTENCIA! Faltan variables de entorno de Telegram (BOT_TOKEN, CHAT_ID)")

bot = None
if BOT_TOKEN:
    bot = telegram.Bot(token=BOT_TOKEN)
else:
    print("No se encontró BOT_TOKEN, el bot de Telegram está desactivado.")

# Esta variable global rastrea el último mensaje procesado
LAST_UPDATE_ID = None

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
    now = datetime.now() 
    soon = now + timedelta(hours=48) 
    
    lines = []
    for t in tasks:
        due = _parse_due(t.get('due'))
        status_icon = "🟡" if t.get('status') == 'principal' else "🔴"
        
        if due and (now <= due.replace(tzinfo=None) <= soon):
            lines.append(f"{status_icon} *{t['title']}* — Entrega: {due.strftime('%Y-%m-%d %H:%M')}")
    
    if not lines:
        body = "¡Buen trabajo! No tienes tareas próximas en las siguientes 48 horas."
    else:
        body = "🔔 *Recordatorio de Tareas Próximas:*\n\n" + "\n".join(lines)
    
    try:
        bot.send_message(chat_id=CHAT_ID, text=body, parse_mode=telegram.ParseMode.MARKDOWN)
        print("Mensaje de recordatorio enviado a Telegram.")
    except Exception as e:
        print(f"Error al enviar mensaje a Telegram: {e}")

def _process_message(msg):
    """Procesa un solo mensaje recibido del bot."""
    if not msg or not msg.text:
        return

    body = msg.text.strip()
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

    bot.send_message(chat_id=msg.chat_id, text=reply_text, parse_mode=telegram.ParseMode.MARKDOWN)

# --- ¡ESTA ES LA FUNCIÓN QUE FALTABA! ---
def check_for_messages():
    """Función llamada por el scheduler (cada 30 seg) para buscar comandos."""
    global LAST_UPDATE_ID
    if not bot:
        # No imprimimos error aquí para no llenar el log cada 30s
        return

    try:
        # Buscamos actualizaciones (mensajes) nuevas
        updates = bot.get_updates(offset=LAST_UPDATE_ID, timeout=10)
        
        for update in updates:
            _process_message(update.message)
            LAST_UPDATE_ID = update.update_id + 1 # Marcamos este mensaje como procesado
            
    except Exception as e:
        # Ignorar errores de red temporales, pero registrarlos
        print(f"Error durante el polling de Telegram: {e}")

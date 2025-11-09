# telegram_client.py
import os
import re
from datetime import datetime, timedelta
import telegram
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
import pytz 
# Importamos las 3 funciones de DB
from db import list_pending_tasks, mark_as_principal_by_title, mark_done_by_title, mark_pending_by_title

# --- Configuración (sin cambios) ---
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID") 
if not all([BOT_TOKEN, CHAT_ID]): print("¡ADVERTENCIA! Faltan variables de entorno de Telegram")
bot = None
if BOT_TOKEN: bot = telegram.Bot(token=BOT_TOKEN)
else: print("No se encontró BOT_TOKEN, el bot de Telegram está desactivado.")
LAST_UPDATE_ID = None
try: SERVER_TIMEZONE = pytz.timezone("Europe/Madrid")
except Exception: SERVER_TIMEZONE = pytz.utc

def _parse_due(due_value: str):
    if not due_value: return None
    try: return datetime.fromisoformat(due_value)
    except (ValueError, TypeError): return None 

def check_and_send_reminders():
    if not bot: return
    print(f"[{datetime.now()}] Ejecutando envío de recordatorios Telegram...")
    tasks = list_pending_tasks()
    now = datetime.now(SERVER_TIMEZONE)
    soon = now + timedelta(hours=48) 
    lines = []
    for t in tasks:
        due_naive = _parse_due(t.get('due'))
        status_icon = "🟡" if t.get('status') == 'principal' else "🔴"
        if due_naive:
            due_aware = SERVER_TIMEZONE.localize(due_naive.replace(tzinfo=None))
            if (now <= due_aware <= soon):
                lines.append(f"{status_icon} *{t['title']}* — Entrega: {due_aware.strftime('%Y-%m-%d %H:%M')}")
    if not lines: body = "¡Buen trabajo! No tienes tareas próximas en las siguientes 48 horas."
    else: body = "🔔 *Recordatorio de Tareas Próximas:*\n\n" + "\n".join(lines)
    try:
        bot.send_message(chat_id=CHAT_ID, text=body, parse_mode=telegram.ParseMode.MARKDOWN)
        print("Mensaje de recordatorio enviado a Telegram.")
    except Exception as e: print(f"Error al enviar mensaje a Telegram: {e}")

# --- Lógica del Menú ---

def _handle_start_command(msg=None, query=None):
    """Muestra el menú principal."""
    keyboard = [[InlineKeyboardButton("Ver Lista de Tareas", callback_data="list_tasks")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "¡Hola! Soy tu bot de tareas. ¿Qué quieres hacer?"
    if query: query.edit_message_text(text=text, reply_markup=reply_markup)
    else: bot.send_message(chat_id=msg.chat_id, text=text, reply_markup=reply_markup)

def _handle_list_tasks(query):
    """Muestra las tareas pendientes como botones."""
    tasks = list_pending_tasks()
    keyboard = []
    if not tasks: text = "No hay tareas pendientes en el servidor."
    else:
        text = "Selecciona una tarea de la lista:"
        for t in tasks:
            status_icon = "🟡" if t.get('status') == 'principal' else "🔴"
            keyboard.append([
                InlineKeyboardButton(
                    f"{status_icon} {t['title']}", 
                    callback_data=f"view_task:{t['title']}"
                )
            ])
    keyboard.append([InlineKeyboardButton("« Volver al Menú", callback_data="main_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.edit_message_text(text=text, reply_markup=reply_markup)

def _handle_task_selected(query):
    """Muestra las 3 opciones: Hecha, En progreso, Pendiente."""
    try:
        task_title = query.data.split("view_task:", 1)[1]
    except IndexError:
        query.answer("Error al leer la tarea")
        return

    # --- ¡CAMBIO AQUÍ! 3 Botones ---
    keyboard = [
        [InlineKeyboardButton("🟢 Hecha", callback_data=f"set_status:done:{task_title}")],
        [InlineKeyboardButton("🟡 En progreso", callback_data=f"set_status:principal:{task_title}")],
        [InlineKeyboardButton("🔴 Pendiente", callback_data=f"set_status:pending:{task_title}")],
        [InlineKeyboardButton("« Volver a la Lista", callback_data="list_tasks")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.edit_message_text(text=f"Tarea seleccionada:\n*'{task_title}'*\n\n¿En qué estado la pones?", reply_markup=reply_markup, parse_mode=telegram.ParseMode.MARKDOWN)

def _handle_set_status(query):
    """Procesa los 3 botones de estado."""
    try:
        # callback_data = "set_status:principal:Mi Tarea"
        parts = query.data.split(":", 2)
        new_status = parts[1]
        title = parts[2]
    except IndexError:
        query.answer("Error al leer la tarea")
        return

    task_id = None
    if new_status == "done":
        task_id = mark_done_by_title(title)
        query.answer(text=f"❌ Tarea '{title}' marcada como Hecha.")
    elif new_status == "principal":
        task_id = mark_as_principal_by_title(title)
        query.answer(text=f"🟡 Tarea '{title}' marcada como En progreso.")
    elif new_status == "pending":
        task_id = mark_pending_by_title(title)
        query.answer(text=f"🔴 Tarea '{title}' marcada como Pendiente.")
    else:
        query.answer(text="Estado no reconocido.")
    
    if not task_id:
        query.answer(text=f"😕 No encontré la tarea '{title}'.")
    
    _handle_list_tasks(query) # Volver a la lista de tareas


# --- RUTEO DE MENSAJES Y BOTONES ---

def _process_message(msg):
    """Procesa solo mensajes de TEXTO (comandos escritos)."""
    if not msg or not msg.text: return
    body = msg.text.strip()
    
    if body == "/start":
        _handle_start_command(msg=msg)
        return
    
    # Mantenemos el comando "lo voy a hacer"
    m = re.match(r"^\s*lo voy a hacer\s+(.+)$", body, flags=re.IGNORECASE)
    if m:
        title = m.group(1).strip()
        task_id = mark_as_principal_by_title(title)
        if task_id: reply_text = f"✅ ¡Entendido! Tarea '{title}' marcada como En progreso."
        else: reply_text = f"😕 No encontré la tarea pendiente: '{title}'."
        bot.send_message(chat_id=msg.chat_id, text=reply_text)
        return
    
    bot.send_message(chat_id=msg.chat_id, text="No entendí eso. Envía /start para usar los botones.")

def _process_callback_query(query):
    """Procesa solo clics en BOTONES INLINE."""
    query.answer() # Responde al clic
    data = query.data

    if data == "main_menu":
        _handle_start_command(query=query)
    elif data == "list_tasks":
        _handle_list_tasks(query)
    elif data.startswith("view_task:"):
        _handle_task_selected(query)
    # --- ¡CAMBIO AQUÍ! ---
    elif data.startswith("set_status:"):
        _handle_set_status(query)

def check_for_messages():
    """Función llamada por el scheduler (cada 5 seg) para buscar comandos."""
    global LAST_UPDATE_ID
    if not bot: return
    try:
        updates = bot.get_updates(offset=LAST_UPDATE_ID, timeout=10)
        for update in updates:
            if update.callback_query:
                _process_callback_query(update.callback_query)
            elif update.message:
                _process_message(update.message)
            LAST_UPDATE_ID = update.update_id + 1 
    except Exception as e:
        if "Timed out" not in str(e): print(f"Error durante el polling de Telegram: {e}")

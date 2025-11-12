# telegram_client.py
import os
import re
from datetime import datetime, timedelta
import telegram
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
import pytz 
from db import (list_all_tasks, mark_as_principal_by_title, mark_done_by_title, 
                mark_pending_by_title, get_task_by_title, add_task_from_bot, 
                delete_task_by_title) # <-- Nuevas importaciones

# --- Configuración ---
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
    """(Req 5) Comprueba TODAS las tareas y filtra las pendientes"""
    if not bot: return
    print(f"[{datetime.now()}] Ejecutando envío de recordatorios Telegram...")
    
    all_tasks = list_all_tasks() # Obtenemos TODAS
    
    # Filtramos solo las pendientes/en progreso
    tasks_to_check = [t for t in all_tasks if t.get('status') != 'done']

    now = datetime.now(SERVER_TIMEZONE)
    soon = now + timedelta(hours=2) # (Req 4) Avisar con 2 horas
    
    lines = []
    for t in tasks_to_check: # Usamos la lista filtrada
        due_naive = _parse_due(t.get('due'))
        status_icon = "🟡" if t.get('status') == 'principal' else "🔴"
        if due_naive:
            due_aware = SERVER_TIMEZONE.localize(due_naive.replace(tzinfo=None))
            if (now <= due_aware <= soon):
                lines.append(f"{status_icon} *{t['title']}* — Entrega: {due_aware.strftime('%Y-%m-%d %H:%M')}")
                
    if not lines: body = "¡Buen trabajo! No tienes tareas próximas en las siguientes 2 horas."
    else: body = "🔔 *Recordatorio de Tareas Próximas:*\n\n" + "\n".join(lines)
    
    try:
        bot.send_message(chat_id=CHAT_ID, text=body, parse_mode=telegram.ParseMode.MARKDOWN)
        print("Mensaje de recordatorio enviado a Telegram.")
    except Exception as e: print(f"Error al enviar mensaje a Telegram: {e}")

# --- Lógica del Menú (Req 3, 4) ---

def _handle_start_command(msg=None, query=None):
    """Muestra el menú principal con las nuevas opciones."""
    keyboard = [
        [InlineKeyboardButton("🗒️ Ver Tareas", callback_data="list_tasks")],
        [InlineKeyboardButton("➕ Crear Tarea", callback_data="create_task")],
        [InlineKeyboardButton("❌ Eliminar Tarea", callback_data="list_delete_tasks")],
        [InlineKeyboardButton("❓ Ayuda", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "¡Hola! Soy tu bot de tareas. ¿Qué quieres hacer?"
    try:
        if query: query.edit_message_text(text=text, reply_markup=reply_markup)
        else: bot.send_message(chat_id=msg.chat_id, text=text, reply_markup=reply_markup)
    except telegram.error.BadRequest as e:
        if "Message is not modified" in str(e): pass # Ignorar si el menú ya está visible
        else: print(f"Error en start_command: {e}")


def _handle_help_command(query):
    """(Req 4) Muestra el mensaje de ayuda."""
    text = (
        "🤖 *Ayuda del Bot de Tareas*\n\n"
        "Este bot te permite gestionar las tareas de tu aplicación de escritorio:\n\n"
        "1.  *Ver Tareas*: Te muestra una lista de *todas* las tareas. Al pulsar una, puedes ver su descripción y cambiar su estado.\n"
        "2.  *Crear Tarea*: Te da instrucciones para crear una tarea nueva.\n"
        "3.  *Eliminar Tarea*: Te permite seleccionar una tarea para borrarla permanentemente.\n\n"
        "*Sintaxis de Creación:*\n"
        "`/crear Título de la Tarea`\n"
        "`/crear Título | Con descripción`"
    )
    keyboard = [[InlineKeyboardButton("« Volver al Menú", callback_data="main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode=telegram.ParseMode.MARKDOWN)

def _handle_create_command(query):
    """(Req 6) Instruye al usuario sobre cómo crear una tarea."""
    text = (
        "Escribe un mensaje con uno de estos formatos:\n\n"
        "1. Solo Título:\n"
        "`/crear El título de tu nueva tarea`\n\n"
        "2. Título y Descripción (separados por `|`):\n"
        "`/crear Título de la tarea | Esta es la descripción`"
    )
    keyboard = [[InlineKeyboardButton("« Volver al Menú", callback_data="main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode=telegram.ParseMode.MARKDOWN)

def _handle_list_tasks(query, action: str = "view"):
    """(Req 7) Muestra TODAS las tareas (incluidas las hechas)"""
    tasks = list_all_tasks() # ¡Obtenemos TODAS!
    keyboard = []
    
    if not tasks:
        text = "No hay ninguna tarea en el servidor."
    else:
        if action == "view":
            text = "Selecciona una tarea para ver sus detalles:"
            callback_prefix = "view_task:"
        else: # action == "delete"
            text = "Selecciona la tarea que quieres ELIMINAR:"
            callback_prefix = "delete_task:"
            
        for t in tasks:
            # --- ¡CAMBIO (Req 7)! ---
            if t['status'] == 'done': status_icon = "🟢"
            elif t['status'] == 'principal': status_icon = "🟡"
            else: status_icon = "🔴"
            
            keyboard.append([
                InlineKeyboardButton(
                    f"{status_icon} {t['title']}", 
                    callback_data=f"{callback_prefix}{t['title']}"
                )
            ])
            
    keyboard.append([InlineKeyboardButton("« Volver al Menú", callback_data="main_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.edit_message_text(text=text, reply_markup=reply_markup)

def _handle_task_selected(query):
    """(Req 5) Muestra la descripción y las 3 opciones."""
    try:
        task_title = query.data.split("view_task:", 1)[1]
    except IndexError:
        query.answer("Error al leer la tarea")
        return

    task = get_task_by_title(task_title)
    if not task:
        query.answer(f"No se encontró la tarea '{task_title}'.")
        _handle_list_tasks(query, action="view")
        return

    # --- ¡NUEVO! Mostrar descripción (Req 5) ---
    description = task.get('description')
    if not description:
        description = "_(Sin descripción)_"
    
    tags = task.get('tags')
    if tags:
        description += f"\n\n*Etiquetas:* `{tags}`"
        
    text = (
        f"Tarea: *{task['title']}*\n\n"
        f"{description}\n\n"
        "¿En qué estado la pones?"
    )
    
    keyboard = [
        [InlineKeyboardButton("🟢 Hecha", callback_data=f"set_status:done:{task_title}")],
        [InlineKeyboardButton("🟡 En progreso", callback_data=f"set_status:principal:{task_title}")],
        [InlineKeyboardButton("🔴 Pendiente", callback_data=f"set_status:pending:{task_title}")],
        [InlineKeyboardButton("« Volver a la Lista", callback_data="list_tasks")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode=telegram.ParseMode.MARKDOWN)

def _handle_set_status(query):
    try:
        _, new_status, title = query.data.split(":", 2)
    except IndexError:
        query.answer("Error al procesar")
        return

    task_id = None
    if new_status == "done":
        task_id = mark_done_by_title(title)
        query.answer(f"🟢 Tarea '{title}' marcada como Hecha.")
    elif new_status == "principal":
        task_id = mark_as_principal_by_title(title)
        query.answer(f"🟡 Tarea '{title}' marcada como En progreso.")
    elif new_status == "pending":
        task_id = mark_pending_by_title(title)
        query.answer(f"🔴 Tarea '{title}' marcada como Pendiente.")
    if not task_id:
        query.answer(f"😕 No encontré la tarea '{title}'.")
    
    _handle_list_tasks(query, action="view") # Volver a la lista

def _handle_delete_task(query):
    """(Req 3) Procesa la eliminación de una tarea."""
    try:
        title = query.data.split("delete_task:", 1)[1]
    except IndexError:
        query.answer("Error al leer la tarea")
        return
    task_id = delete_task_by_title(title)
    if task_id:
        query.answer(text=f"✅ Tarea '{title}' eliminada.")
    else:
        query.answer(text=f"😕 No encontré la tarea '{title}'.")
    _handle_list_tasks(query, action="delete")


# --- RUTEO DE MENSAJES Y BOTONES ---

def _process_message(msg):
    """Procesa solo mensajes de TEXTO (comandos escritos)."""
    if not msg or not msg.text: return
    body = msg.text.strip()
    
    if body == "/start":
        _handle_start_command(msg=msg)
        return
    
    # --- ¡CAMBIO! (Req 6) Comando /crear con descripción ---
    m_crear = re.match(r"^\s*/crear\s+([^|]+)(?:\s*\|\s*(.+))?$", body, flags=re.IGNORECASE)
    if m_crear:
        title = m_crear.group(1).strip()
        description = m_crear.group(2).strip() if m_crear.group(2) else ""
        add_task_from_bot(title, description)
        bot.send_message(chat_id=msg.chat_id, text=f"✅ Tarea '{title}' creada.")
        return
        
    m_hacer = re.match(r"^\s*lo voy a hacer\s+(.+)$", body, flags=re.IGNORECASE)
    if m_hacer:
        title = m_hacer.group(1).strip()
        task_id = mark_as_principal_by_title(title)
        if task_id: reply_text = f"✅ ¡Entendido! Tarea '{title}' marcada como En progreso."
        else: reply_text = f"😕 No encontré la tarea pendiente: '{title}'."
        bot.send_message(chat_id=msg.chat_id, text=reply_text)
        return
    
    bot.send_message(chat_id=msg.chat_id, text="No entendí eso. Envía /start para usar los botones.")

def _process_callback_query(query):
    """Procesa solo clics en BOTONES INLINE."""
    query.answer()
    data = query.data

    if data == "main_menu":
        _handle_start_command(query=query)
    elif data == "help":
        _handle_help_command(query)
    elif data == "create_task":
        _handle_create_command(query)
    elif data == "list_tasks":
        _handle_list_tasks(query, action="view")
    elif data == "list_delete_tasks":
        _handle_list_tasks(query, action="delete")
    elif data.startswith("view_task:"):
        _handle_task_selected(query)
    elif data.startswith("set_status:"):
        _handle_set_status(query)
    elif data.startswith("delete_task:"):
        _handle_delete_task(query)

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

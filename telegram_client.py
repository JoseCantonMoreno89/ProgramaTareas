# telegram_client.py
import os
import re
from datetime import datetime, timedelta
import telegram
# ¡Importaciones clave para los botones Inline!
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
import pytz 
from db import list_pending_tasks, mark_as_principal_by_title, mark_done_by_title

# --- Configuración (sin cambios) ---
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
try:
    SERVER_TIMEZONE = pytz.timezone("Europe/Madrid")
except Exception:
    SERVER_TIMEZONE = pytz.utc

def _parse_due(due_value: str):
    if not due_value:
        return None
    try:
        return datetime.fromisoformat(due_value)
    except (ValueError, TypeError):
        return None 

def check_and_send_reminders():
    """Función llamada por el scheduler (cada 5 horas)"""
    if not bot:
        return
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
    
    if not lines:
        body = "¡Buen trabajo! No tienes tareas próximas en las siguientes 48 horas."
    else:
        body = "🔔 *Recordatorio de Tareas Próximas:*\n\n" + "\n".join(lines)
    
    try:
        bot.send_message(chat_id=CHAT_ID, text=body, parse_mode=telegram.ParseMode.MARKDOWN)
        print("Mensaje de recordatorio enviado a Telegram.")
    except Exception as e:
        print(f"Error al enviar mensaje a Telegram: {e}")


# --- Lógica del Menú (Reescrita para Botones Inline) ---

def _handle_start_command(msg=None, query=None):
    """Muestra el menú principal."""
    keyboard = [[InlineKeyboardButton("Ver Lista de Tareas", callback_data="list_tasks")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "¡Hola! Soy tu bot de tareas. ¿Qué quieres hacer?"
    
    if query: # Si venimos de un botón (CallbackQuery)
        query.edit_message_text(text=text, reply_markup=reply_markup)
    else: # Si es la primera vez (Mensaje)
        bot.send_message(chat_id=msg.chat_id, text=text, reply_markup=reply_markup)

def _handle_list_tasks(query):
    """Muestra las tareas pendientes como botones."""
    tasks = list_pending_tasks()
    keyboard = [] # Aquí irán los botones de tareas
    
    if not tasks:
        text = "No hay tareas pendientes en el servidor."
    else:
        text = "Selecciona una tarea de la lista:"
        for t in tasks:
            status_icon = "🟡" if t.get('status') == 'principal' else "🔴"
            # El callback_data es el "comando oculto" que enviará el botón
            keyboard.append([
                InlineKeyboardButton(
                    f"{status_icon} {t['title']}", 
                    callback_data=f"view_task:{t['title']}"
                )
            ])
    
    # Añadimos un botón para "Volver"
    keyboard.append([InlineKeyboardButton("« Volver al Menú", callback_data="main_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.edit_message_text(text=text, reply_markup=reply_markup)

def _handle_task_selected(query):
    """Muestra las opciones 'Hacer' o 'Ignorar' para una tarea."""
    # Extraemos el título del "comando oculto" (callback_data)
    try:
        task_title = query.data.split("view_task:", 1)[1]
    except IndexError:
        query.answer("Error al leer la tarea")
        return

    keyboard = [
        [InlineKeyboardButton("✅ Hacer (Marcar Principal)", callback_data=f"do_task:{task_title}")],
        [InlineKeyboardButton("❌ Ignorar (Marcar Hecha)", callback_data=f"ignore_task:{task_title}")],
        [InlineKeyboardButton("« Volver a la Lista", callback_data="list_tasks")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.edit_message_text(text=f"Tarea seleccionada:\n*'{task_title}'*\n\n¿Qué quieres hacer?", reply_markup=reply_markup, parse_mode=telegram.ParseMode.MARKDOWN)

def _handle_hacer_command(query):
    """Marca una tarea como 'principal' (Hacer)."""
    try:
        title = query.data.split("do_task:", 1)[1]
    except IndexError:
        query.answer("Error al leer la tarea")
        return
        
    task_id = mark_as_principal_by_title(title)
    if task_id:
        query.answer(text=f"✅ Tarea '{title}' marcada como principal.") # Pop-up de confirmación
    else:
        query.answer(text=f"😕 No encontré la tarea '{title}'.")
    
    _handle_list_tasks(query) # Volver a la lista de tareas

def _handle_ignorar_command(query):
    """Marca una tarea como 'done' (Ignorar)."""
    try:
        title = query.data.split("ignore_task:", 1)[1]
    except IndexError:
        query.answer("Error al leer la tarea")
        return

    task_id = mark_done_by_title(title)
    if task_id:
        query.answer(text=f"❌ Tarea '{title}' marcada como completada.") # Pop-up
    else:
        query.answer(text=f"😕 No encontré la tarea '{title}'.")
    
    _handle_list_tasks(query) # Volver a la lista de tareas

# --- RUTEO DE MENSAJES Y BOTONES ---

def _process_message(msg):
    """Procesa solo mensajes de TEXTO (comandos escritos)."""
    if not msg or not msg.text:
        return
    body = msg.text.strip()
    
    # 1. Comando /start
    if body == "/start":
        _handle_start_command(msg=msg)
        return

    # 2. Comando "lo voy a hacer" (comando de texto)
    m = re.match(r"^\s*lo voy a hacer\s+(.+)$", body, flags=re.IGNORECASE)
    if m:
        title = m.group(1).strip()
        task_id = mark_as_principal_by_title(title)
        if task_id:
            reply_text = f"✅ ¡Entendido! Tarea '{title}' marcada como principal (por comando de texto)."
        else:
            reply_text = f"😕 No encontré la tarea pendiente: '{title}'."
        bot.send_message(chat_id=msg.chat_id, text=reply_text)
        return

    # 3. Respuesta por defecto
    bot.send_message(chat_id=msg.chat_id, text="No entendí eso. Envía /start para usar los botones.")

def _process_callback_query(query):
    """Procesa solo clics en BOTONES INLINE."""
    
    # 1. Responde al 'clic' para que el icono de "cargando" desaparezca
    query.answer()
    
    data = query.data # El "comando oculto" (ej: "list_tasks")

    # 2. Enrutador de botones
    if data == "main_menu":
        _handle_start_command(query=query)
    
    elif data == "list_tasks":
        _handle_list_tasks(query)
        
    elif data.startswith("view_task:"):
        _handle_task_selected(query)

    elif data.startswith("do_task:"):
        _handle_hacer_command(query)
        
    elif data.startswith("ignore_task:"):
        _handle_ignorar_command(query)

def check_for_messages():
    """Función llamada por el scheduler (cada 5 seg) para buscar comandos."""
    global LAST_UPDATE_ID
    if not bot:
        return

    try:
        updates = bot.get_updates(offset=LAST_UPDATE_ID, timeout=10)
        
        for update in updates:
            if update.callback_query:
                # ¡NUEVO! Si es un clic en un botón
                _process_callback_query(update.callback_query)
            elif update.message:
                # Si es un mensaje de texto
                _process_message(update.message)
            
            LAST_UPDATE_ID = update.update_id + 1 
            
    except Exception as e:
        # Silenciar errores comunes de red, pero registrar los demás
        if "Timed out" not in str(e):
            print(f"Error durante el polling de Telegram: {e}")

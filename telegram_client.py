# telegram_client.py
import os
import re
from datetime import datetime, timedelta
import telegram
from telegram import ReplyKeyboardMarkup, KeyboardButton
import pytz 
from db import list_pending_tasks, mark_as_principal_by_title, mark_done_by_title

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


# --- Lógica del Menú ---

def _handle_start_command(msg):
    """Muestra el menú principal."""
    keyboard = [[KeyboardButton("Ver Lista de Tareas")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    bot.send_message(
        chat_id=msg.chat_id, 
        text="¡Hola! Soy tu bot de tareas. ¿Qué quieres hacer?",
        reply_markup=reply_markup
    )

def _handle_list_tasks(msg):
    """Muestra las tareas pendientes como botones."""
    tasks = list_pending_tasks()
    if not tasks:
        bot.send_message(chat_id=msg.chat_id, text="No hay tareas pendientes en el servidor.")
        _handle_start_command(msg) # Volver al menú principal
        return

    keyboard = []
    for t in tasks:
        # Añadimos un icono al botón para claridad
        status_icon = "🟡" if t.get('status') == 'principal' else "🔴"
        keyboard.append([KeyboardButton(f"{status_icon} {t['title']}")])

    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    bot.send_message(
        chat_id=msg.chat_id, 
        text="Selecciona una tarea de la lista:",
        reply_markup=reply_markup
    )

def _handle_task_selected(msg, task_title_with_icon):
    """Muestra las opciones 'Hacer' o 'Ignorar' para una tarea."""
    # Quitamos el icono del título para el texto del botón
    task_title = " ".join(task_title_with_icon.split(" ")[1:]) 
    
    keyboard = [
        [KeyboardButton(f"✅ Hacer: {task_title}")],
        [KeyboardButton(f"❌ Ignorar: {task_title}")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    bot.send_message(
        chat_id=msg.chat_id, 
        text=f"¿Qué quieres hacer con '{task_title}'?",
        reply_markup=reply_markup
    )

def _handle_hacer_command(msg, match):
    """Marca una tarea como 'principal' (Hacer)."""
    title = match.group(1).strip()
    task_id = mark_as_principal_by_title(title)
    if task_id:
        reply_text = f"✅ ¡Entendido! Tarea '{title}' marcada como principal."
    else:
        reply_text = f"😕 No encontré la tarea pendiente: '{title}'."
    bot.send_message(chat_id=msg.chat_id, text=reply_text)
    _handle_start_command(msg) # Volver al menú principal

def _handle_ignorar_command(msg, match):
    """Marca una tarea como 'done' (Ignorar)."""
    title = match.group(1).strip()
    task_id = mark_done_by_title(title)
    if task_id:
        reply_text = f"❌ Tarea '{title}' marcada como completada."
    else:
        reply_text = f"😕 No encontré la tarea pendiente: '{title}'."
    bot.send_message(chat_id=msg.chat_id, text=reply_text)
    _handle_start_command(msg) # Volver al menú principal

def _process_message(msg):
    """Procesa y enruta todos los mensajes entrantes."""
    if not msg or not msg.text:
        return

    body = msg.text.strip()
    
    # 1. Comandos del Menú
    if body == "/start":
        _handle_start_command(msg)
        return
    
    if body == "Ver Lista de Tareas":
        _handle_list_tasks(msg)
        return

    # 2. Comandos de Acción (con Regex)
    m_hacer = re.match(r"^\s*✅ Hacer: (.+)$", body)
    if m_hacer:
        _handle_hacer_command(msg, m_hacer)
        return

    m_ignorar = re.match(r"^\s*❌ Ignorar: (.+)$", body)
    if m_ignorar:
        _handle_ignorar_command(msg, m_ignorar)
        return

    # 3. Comprobar si es un botón de Tarea (ej: "🔴 Comprar pan")
    tasks = list_pending_tasks()
    # Creamos los títulos de botón exactos (con icono)
    task_button_titles = [f"{'🟡' if t.get('status') == 'principal' else '🔴'} {t['title']}" for t in tasks]
    
    if body in task_button_titles:
        _handle_task_selected(msg, body)
        return

    # 4. Respuesta por defecto
    bot.send_message(chat_id=msg.chat_id, text="No entendí ese comando. Usando el menú principal...")
    _handle_start_command(msg)


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

# telegram_client.py
import os
import re
import telegram
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime, timedelta
import pytz 
import google.generativeai as genai 

# Importamos las funciones necesarias de la base de datos
from db import (
    list_all_tasks, 
    mark_as_principal_by_title, 
    mark_done_by_title, 
    mark_pending_by_title, 
    get_task_by_title, 
    add_task_from_bot, 
    delete_task_by_title
)

# --- CONFIGURACIÓN ---
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Configurar Gemini
model = None
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('models/gemini-2.5-flash')
        print("✅ Gemini AI conectado correctamente.")
    except Exception as e:
        print(f"❌ Error configurando Gemini: {e}")
else:
    print("⚠️ ADVERTENCIA: Falta GEMINI_API_KEY. El modo IA no funcionará.")

# Configurar Bot Telegram
bot = None
if BOT_TOKEN:
    bot = telegram.Bot(token=BOT_TOKEN)
else:
    print("❌ Error: Falta TELEGRAM_BOT_TOKEN.")

LAST_UPDATE_ID = None

# Configurar Zona Horaria (España o UTC)
try:
    SERVER_TIMEZONE = pytz.timezone("Europe/Madrid")
except Exception:
    SERVER_TIMEZONE = pytz.utc

# --- FUNCIONES AUXILIARES ---

def _parse_due(due_value: str):
    """Convierte string ISO a objeto datetime."""
    if not due_value: return None
    try:
        return datetime.fromisoformat(due_value)
    except (ValueError, TypeError):
        return None 

def get_tasks_context():
    """Genera un texto legible con el estado actual de todas las tareas para la IA."""
    tasks = list_all_tasks()
    if not tasks:
        return "El usuario NO tiene tareas pendientes."
    
    text = "LISTA ACTUALIZADA DE TAREAS:\n"
    count = 0
    for t in tasks:
        if t['status'] == 'done': continue # Ignoramos las hechas para el contexto activo
        
        status = "PRIORIDAD ALTA" if t['status'] == 'principal' else "Pendiente"
        due = t['due'] if t['due'] else "Sin fecha límite"
        desc = f" ({t['description']})" if t.get('description') else ""
        
        text += f"• {t['title']}{desc} | Estado: {status} | Vence: {due}\n"
        count += 1
        
    if count == 0: return "El usuario no tiene tareas activas (todas están hechas)."
    return text

# ==============================================================================
# 🧠 LÓGICA DE IA AUTOMÁTICA (Resúmenes y Alertas)
# ==============================================================================

def send_routine_check():
    """
    Se ejecuta cada 5 horas (programado en web_server.py).
    Gemini analiza el día y manda un resumen motivacional.
    """
    if not bot or not model: return
    
    print(f"[{datetime.now()}] Ejecutando chequeo de rutina (5h)...")
    tasks_text = get_tasks_context()
    
    # Si no hay tareas, evitamos gastar tokens o molestar
    if "NO tiene tareas" in tasks_text or "no tiene tareas activas" in tasks_text:
        return 

    prompt = f"""
    Eres un Asistente Personal proactivo. Son las {datetime.now(SERVER_TIMEZONE).strftime('%H:%M')}.
    Tu trabajo es mantener al usuario enfocado.
    
    INSTRUCCIONES:
    1. Revisa la lista de tareas.
    2. Haz un resumen breve y amigable.
    3. Si hay tareas de Prioridad Alta, destácalas.
    4. Usa emojis. No seas robótico.
    
    {tasks_text}
    """
    
    try:
        response = model.generate_content(prompt)
        bot.send_message(
            chat_id=CHAT_ID, 
            text=f"⏰ *Reporte Automático (5h)*\n\n{response.text}", 
            parse_mode=telegram.ParseMode.MARKDOWN
        )
    except Exception as e:
        print(f"Error rutina IA: {e}")

def check_smart_urgency():
    """
    Se ejecuta cada 15 min (programado en web_server.py).
    
    Lógica de Frecuencia Dinámica:
    - Si vence en < 1 hora: Notifica SIEMPRE (frecuencia real: 15 min).
    - Si vence en < 4 horas: Notifica solo si los minutos < 15 (frecuencia real: 1 hora).
    """
    if not bot or not model: return

    all_tasks = list_all_tasks()
    now = datetime.now(SERVER_TIMEZONE)
    urgent_tasks = []
    
    for t in all_tasks:
        if t['status'] == 'done': continue
        
        due_naive = _parse_due(t.get('due'))
        if not due_naive: continue
        
        # Hacemos la fecha consciente de la zona horaria
        if due_naive.tzinfo is None:
            due_aware = SERVER_TIMEZONE.localize(due_naive)
        else:
            due_aware = due_naive.astimezone(SERVER_TIMEZONE)
            
        delta_seconds = (due_aware - now).total_seconds()
        
        # Lógica de tramos
        is_panic_mode = 0 < delta_seconds < 3600  # Menos de 1 hora
        is_urgent_mode = 3600 <= delta_seconds < 14400 # Entre 1 y 4 horas
        
        should_notify = False
        label = ""
        
        if is_panic_mode:
            should_notify = True # Avisar siempre (cada 15 min)
            label = "🚨 CRÍTICO (<1h)"
        elif is_urgent_mode:
            # Solo avisar una vez por hora (cuando el minuto actual es 0-14)
            if now.minute < 15:
                should_notify = True
                label = "⚠️ ATENCIÓN (<4h)"
        
        if should_notify:
            urgent_tasks.append(f"{label}: {t['title']} (Vence a las {due_aware.strftime('%H:%M')})")

    if not urgent_tasks:
        return # Nada urgente ahora mismo

    # Si hay urgencias, pedimos a la IA que redacte el aviso con tono de urgencia
    urgency_text = "\n".join(urgent_tasks)
    print(f"[{datetime.now()}] ¡Urgencia detectada! Enviando aviso IA.")
    
    prompt = f"""
    Eres un sistema de alertas de emergencia.
    El usuario tiene tareas a punto de vencer y debe actuar YA.
    
    TAREAS CRÍTICAS:
    {urgency_text}
    
    INSTRUCCIONES:
    1. Sé muy directo, breve y urgente.
    2. Usa iconos de alerta (🚨, 🔥).
    3. Dile el tiempo exacto que queda o la hora de vencimiento.
    4. NO saludes, ve al grano.
    """
    
    try:
        response = model.generate_content(prompt)
        bot.send_message(chat_id=CHAT_ID, text=response.text)
    except Exception as e:
        print(f"Error urgencia IA: {e}")

# ==============================================================================
# LÓGICA DE CHAT CON EL USUARIO
# ==============================================================================

def get_gemini_chat_response(user_message):
    """Responde mensajes directos del usuario usando el contexto de las tareas."""
    if not model: return "❌ La IA no está disponible."
    
    tasks_text = get_tasks_context()
    
    prompt = f"""
    Eres un Asistente de Productividad inteligente.
    
    CONTEXTO DE TAREAS: 
    {tasks_text}
    
    USUARIO DICE: "{user_message}"
    
    INSTRUCCIONES:
    1. Responde de forma útil basándote en sus tareas.
    2. Si pide recomendación, elige la más urgente o prioritaria.
    3. Sé breve.
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Tuve un problema pensando... ({e})"

# --- MANEJADORES DE COMANDOS TELEGRAM ---

def _handle_start_command(msg=None, query=None):
    keyboard = [
        [InlineKeyboardButton("📝 Ver Tareas", callback_data="list_tasks")],
        [InlineKeyboardButton("➕ Crear Tarea", callback_data="create_task")],
        [InlineKeyboardButton("💡 Ayuda IA", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = (
        "🤖 *Agente de Tareas IA Activo*\n\n"
        "Estoy monitoreando tus tareas:\n"
        "• Resumen cada 5 horas.\n"
        "• Alertas urgentes automáticas.\n\n"
        "Hablame para pedir consejos o usa los botones."
    )
    
    try:
        if query:
            query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode=telegram.ParseMode.MARKDOWN)
        else:
            bot.send_message(chat_id=msg.chat_id, text=text, reply_markup=reply_markup, parse_mode=telegram.ParseMode.MARKDOWN)
    except telegram.error.BadRequest:
        pass

def _handle_list_tasks(query, action="view"):
    tasks = list_all_tasks()
    keyboard = []
    
    if not tasks:
        text = "🎉 ¡Todo limpio! No hay tareas."
    else:
        text = "Selecciona una tarea:" if action == "view" else "Selecciona para ELIMINAR:"
        prefix = "view_task:" if action == "view" else "delete_task:"
        
        for t in tasks:
            # Iconos según estado
            if t['status'] == 'done': icon = "🟢"
            elif t['status'] == 'principal': icon = "🔥"
            else: icon = "🔹"
            
            keyboard.append([
                InlineKeyboardButton(f"{icon} {t['title']}", callback_data=f"{prefix}{t['title']}")
            ])
    
    # Botón Volver y opción de Borrar si estamos en vista normal
    nav_row = [InlineKeyboardButton("« Volver", callback_data="main_menu")]
    if action == "view" and tasks:
        nav_row.append(InlineKeyboardButton("🗑️ Borrar", callback_data="list_delete_tasks"))
        
    keyboard.append(nav_row)
    query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard))

def _handle_task_details(query):
    try: title = query.data.split("view_task:", 1)[1]
    except IndexError: return

    task = get_task_by_title(title)
    if not task:
        _handle_list_tasks(query)
        return

    desc = task.get('description') or "_Sin descripción_"
    info = f"📌 *{task['title']}*\n{desc}\n"
    if task.get('due'): info += f"\n⏰ Vence: {task['due']}"
    if task.get('tags'): info += f"\n🏷 Etiquetas: {task['tags']}"
    
    keyboard = [
        [InlineKeyboardButton("✅ Hecha", callback_data=f"set_status:done:{title}")],
        [InlineKeyboardButton("🔥 En Progreso", callback_data=f"set_status:principal:{title}")],
        [InlineKeyboardButton("💤 Pendiente", callback_data=f"set_status:pending:{title}")],
        [InlineKeyboardButton("« Volver", callback_data="list_tasks")]
    ]
    query.edit_message_text(text=info, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=telegram.ParseMode.MARKDOWN)

def _handle_status_change(query):
    try: _, status, title = query.data.split(":", 2)
    except IndexError: return

    if status == "done": mark_done_by_title(title)
    elif status == "principal": mark_as_principal_by_title(title)
    elif status == "pending": mark_pending_by_title(title)
    
    _handle_list_tasks(query)

def _handle_delete(query):
    try: title = query.data.split("delete_task:", 1)[1]
    except IndexError: return
    
    delete_task_by_title(title)
    _handle_list_tasks(query, action="delete")

def _handle_create_info(query):
    text = "Para crear una tarea, simplemente escribe:\n\n`/crear Comprar pan`\n\nO si quieres descripción:\n`/crear Informe | Para el lunes`"
    keyboard = [[InlineKeyboardButton("« Volver", callback_data="main_menu")]]
    query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=telegram.ParseMode.MARKDOWN)

def _handle_help(query):
    text = (
        "💡 *Ayuda del Agente IA*\n\n"
        "**Comandos:**\n"
        "`/crear [Titulo]` -> Nueva tarea rápida.\n"
        "`/start` -> Menú principal.\n\n"
        "**Chat Inteligente:**\n"
        "Puedes decirme cosas como:\n"
        "_\"¿Qué tengo urgente?\"_\n"
        "_\"Ayúdame a organizar la tarde\"_\n"
        "_\"Resumen de mis etiquetas\"_"
    )
    keyboard = [[InlineKeyboardButton("« Volver", callback_data="main_menu")]]
    query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=telegram.ParseMode.MARKDOWN)

# --- PROCESAMIENTO DE MENSAJES Y CALLBACKS ---

def _process_callback_query(query):
    query.answer()
    data = query.data
    
    if data == "main_menu": _handle_start_command(query=query)
    elif data == "list_tasks": _handle_list_tasks(query, "view")
    elif data == "list_delete_tasks": _handle_list_tasks(query, "delete")
    elif data == "create_task": _handle_create_info(query)
    elif data == "help": _handle_help(query)
    elif data.startswith("view_task:"): _handle_task_details(query)
    elif data.startswith("set_status:"): _handle_status_change(query)
    elif data.startswith("delete_task:"): _handle_delete(query)

def _process_message(msg):
    if not msg or not msg.text: return
    text = msg.text.strip()
    
    # Comando /start
    if text == "/start":
        _handle_start_command(msg=msg)
        return

    # Comando /crear
    if text.lower().startswith("/crear"):
        parts = text.split(" ", 1)
        if len(parts) > 1:
            raw_content = parts[1]
            if "|" in raw_content:
                title, desc = raw_content.split("|", 1)
                title = title.strip()
                desc = desc.strip()
            else:
                title = raw_content.strip()
                desc = ""
                
            add_task_from_bot(title, desc)
            bot.send_message(chat_id=msg.chat_id, text=f"✅ Tarea creada: *{title}*", parse_mode=telegram.ParseMode.MARKDOWN)
        else:
            bot.send_message(chat_id=msg.chat_id, text="⚠️ Escribe el título después de /crear.")
        return

    # Chat IA (Cualquier otro mensaje)
    bot.send_chat_action(chat_id=msg.chat_id, action=telegram.ChatAction.TYPING)
    ai_response = get_gemini_chat_response(text)
    bot.send_message(chat_id=msg.chat_id, text=ai_response)

def check_for_messages():
    """Loop de polling llamado por el Scheduler."""
    global LAST_UPDATE_ID
    if not bot: return
    try:
        updates = bot.get_updates(offset=LAST_UPDATE_ID, timeout=5)
        for update in updates:
            if update.message:
                _process_message(update.message)
            elif update.callback_query:
                _process_callback_query(update.callback_query)
            
            LAST_UPDATE_ID = update.update_id + 1
    except Exception as e:
        # Ignoramos timeouts de red normales
        if "Timed out" not in str(e):
            print(f"Error polling Telegram: {e}")

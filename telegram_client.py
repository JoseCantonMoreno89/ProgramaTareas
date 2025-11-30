# telegram_client.py
import os
import json
import telegram
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime
import pytz 
import google.generativeai as genai 

from db import (
    list_all_tasks, mark_as_principal_by_title, mark_done_by_title, 
    mark_pending_by_title, get_task_by_title, add_task_from_bot, 
    delete_task_by_title, update_task_description, delete_task_by_id
)

# --- CONFIGURACIÓN ---
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

model = None
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        print("✅ Gemini AI (Modo Avanzado) conectado.")
    except Exception as e:
        print(f"❌ Error Gemini: {e}")

bot = None
if BOT_TOKEN: bot = telegram.Bot(token=BOT_TOKEN)

LAST_UPDATE_ID = None
try: SERVER_TIMEZONE = pytz.timezone("Europe/Madrid")
except: SERVER_TIMEZONE = pytz.utc

# --- CONTEXTO ---
def get_tasks_context():
    tasks = list_all_tasks()
    if not tasks: return "No hay tareas registradas."
    text = "LISTA DE TAREAS (ID: Título - Desc):\n"
    for t in tasks:
        if t['status'] == 'done': continue
        desc = f" | Desc: {t['description']}" if t['description'] else ""
        text += f"• ID {t['id']}: {t['title']}{desc}\n"
    return text

# ==============================================================================
# 🧠 CEREBRO DE EJECUCIÓN (Action Engine)
# ==============================================================================

def process_ai_command(user_text):
    """
    Analiza el texto del usuario y decide si chatear o EJECUTAR una acción.
    Devuelve (respuesta_texto, accion_ejecutada_bool)
    """
    if not model: return "❌ IA no disponible.", False
    
    tasks_text = get_tasks_context()
    
    # Prompt de Ingeniería para forzar salida JSON controlada
    prompt = f"""
    Eres un Gestor de Tareas Inteligente. Tienes acceso directo a la base de datos.
    
    TUS HERRAMIENTAS:
    1. CREAR: Para nuevas tareas.
    2. BORRAR: Para eliminar tareas (necesitas el ID).
    3. MODIFICAR: Para cambiar la descripción (necesitas el ID).
    4. CHAT: Para conversar, aconsejar o resumir.

    INSTRUCCIONES CLAVE:
    - Si el usuario quiere realizar una acción (crear, borrar, cambiar), DEBES responder con un JSON.
    - Si el usuario solo charla, responde con texto normal (sin JSON).

    FORMATO JSON OBLIGATORIO PARA ACCIONES:
    {{
        "action": "create" | "delete" | "update_desc",
        "params": {{
            "title": "...",      // Para create
            "description": "...", // Para create o update_desc
            "id": 123            // Para delete o update_desc
        }},
        "reply": "Texto confirmando la acción al usuario"
    }}

    CONTEXTO ACTUAL:
    {tasks_text}

    USUARIO DICE: "{user_text}"
    """

    try:
        # Pedimos respuesta
        response = model.generate_content(prompt)
        raw_text = response.text.strip()
        
        # Intentamos detectar si es JSON (limpiando posibles bloques de código ```json ...)
        clean_text = raw_text.replace("```json", "").replace("```", "").strip()
        
        if clean_text.startswith("{") and clean_text.endswith("}"):
            # ¡Es un comando!
            cmd = json.loads(clean_text)
            action = cmd.get("action")
            params = cmd.get("params", {})
            reply = cmd.get("reply", "Hecho.")
            
            if action == "create":
                add_task_from_bot(params.get("title"), params.get("description", ""))
                return f"✅ {reply}", True
                
            elif action == "delete":
                tid = params.get("id")
                if tid:
                    delete_task_by_id(int(tid))
                    return f"🗑️ {reply}", True
                
            elif action == "update_desc":
                tid = params.get("id")
                new_desc = params.get("description")
                if tid and new_desc:
                    update_task_description(int(tid), new_desc)
                    return f"📝 {reply}", True
            
            return reply, True # Acción reconocida pero genérica
            
        else:
            # Es charla normal
            return raw_text, False

    except Exception as e:
        print(f"Error procesando IA: {e}")
        return "Tuve un error interno procesando tu solicitud.", False

# ==============================================================================
# RUTINAS AUTOMÁTICAS (Resumen y Alertas)
# ==============================================================================

def send_routine_check():
    if not bot or not model: return
    tasks = list_all_tasks()
    if not any(t['status'] != 'done' for t in tasks): return

    prompt = f"Resume brevemente estas tareas para motivar al usuario:\n{get_tasks_context()}"
    try:
        res = model.generate_content(prompt)
        bot.send_message(chat_id=CHAT_ID, text=f"⏰ *Resumen 5h*\n{res.text}", parse_mode=telegram.ParseMode.MARKDOWN)
    except: pass

def check_smart_urgency():
    # (Lógica simplificada para brevedad, mantiene funcionalidad anterior)
    if not bot: return
    now = datetime.now(SERVER_TIMEZONE)
    tasks = list_all_tasks()
    urgent = []
    for t in tasks:
        if t['status'] == 'done' or not t.get('due'): continue
        try:
            due = datetime.fromisoformat(t['due']).replace(tzinfo=None)
            due = SERVER_TIMEZONE.localize(due)
            delta = (due - now).total_seconds()
            if 0 < delta < 3600: urgent.append(f"🚨 {t['title']} (<1h)")
            elif 0 < delta < 14400 and now.minute < 15: urgent.append(f"⚠️ {t['title']} (<4h)")
        except: pass
    
    if urgent:
        msg = "¡Atención!\n" + "\n".join(urgent)
        bot.send_message(chat_id=CHAT_ID, text=msg)

# ==============================================================================
# MANEJO DE TELEGRAM
# ==============================================================================

def _handle_start_command(msg=None, query=None):
    kb = [[InlineKeyboardButton("Ver Tareas", callback_data="list_tasks")]]
    text = "🤖 *Agente Full-Access*\nAhora puedo CREAR, BORRAR y MODIFICAR tareas si me lo pides."
    if query: query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
    else: bot.send_message(msg.chat_id, text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')

def _handle_list_tasks(query):
    tasks = list_all_tasks()
    kb = []
    for t in tasks:
        if t['status'] == 'done': continue
        icon = "🔥" if t['status']=='principal' else "🔹"
        kb.append([InlineKeyboardButton(f"{icon} {t['title']}", callback_data=f"view:{t['title']}")])
    kb.append([InlineKeyboardButton("« Menú", callback_data="main_menu")])
    query.edit_message_text("Tus tareas activas:", reply_markup=InlineKeyboardMarkup(kb))

def _process_message(msg):
    if not msg or not msg.text: return
    text = msg.text.strip()
    
    if text == "/start": 
        _handle_start_command(msg=msg)
        return

    # Enviamos "Escribiendo..." porque la IA va a pensar y quizás ejecutar DB
    bot.send_chat_action(chat_id=msg.chat_id, action=telegram.ChatAction.TYPING)
    
    # Procesamos con el motor inteligente
    reply_text, action_done = process_ai_command(text)
    
    bot.send_message(chat_id=msg.chat_id, text=reply_text)

def _process_callback(query):
    query.answer()
    data = query.data
    if data == "main_menu": _handle_start_command(query=query)
    elif data == "list_tasks": _handle_list_tasks(query)
    # (Resto de botones simplificados, la lógica clave es la IA arriba)

def check_for_messages():
    global LAST_UPDATE_ID
    if not bot: return
    try:
        updates = bot.get_updates(offset=LAST_UPDATE_ID, timeout=5)
        for u in updates:
            if u.message: _process_message(u.message)
            elif u.callback_query: _process_callback(u.callback_query)
            LAST_UPDATE_ID = u.update_id + 1
    except: pass

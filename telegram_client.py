# telegram_client.py
import os
import json
import telegram
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime
import pytz 
import google.generativeai as genai 
import re

from db import (
    list_all_tasks, mark_as_principal_by_title, mark_done_by_title, 
    mark_pending_by_title, get_task_by_title, add_task_from_bot, 
    delete_task_by_title, update_task_description, delete_task_by_id,
    delete_all_tasks # <-- Importamos la nueva función
)

# --- CONFIGURACIÓN ---
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

model = None
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('models/gemini-2.5-flash')
    except Exception as e:
        print(f"Error Gemini: {e}")

bot = None
if BOT_TOKEN: bot = telegram.Bot(token=BOT_TOKEN)

LAST_UPDATE_ID = None
try: SERVER_TIMEZONE = pytz.timezone("Europe/Madrid")
except: SERVER_TIMEZONE = pytz.utc

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
# 🧠 PROCESADOR DE COMANDOS IA
# ==============================================================================

def process_ai_command(user_text):
    if not model: return "❌ IA no disponible.", False
    
    tasks_text = get_tasks_context()
    
    # Prompt actualizado con DELETE_ALL
    prompt = f"""
    Eres un Gestor de Tareas Inteligente. Tienes acceso directo a la base de datos.
    
    HERRAMIENTAS DISPONIBLES:
    1. CREAR ("create"): Para nuevas tareas.
    2. BORRAR ("delete"): Para eliminar tareas individuales (REQUIERE ID NUMÉRICO).
    3. BORRAR TODO ("delete_all"): Para borrar TODAS las tareas.
    4. MODIFICAR ("update_desc"): Para cambiar descripciones (REQUIERE ID NUMÉRICO).
    5. CHAT: Para conversar normal.

    INSTRUCCIONES:
    - Si detectas una intención de acción, devuelve SOLO el JSON.
    - Si es charla, devuelve texto normal.

    FORMATO JSON:
    {{
        "action": "create" | "delete" | "update_desc" | "delete_all",
        "params": {{
            "title": "...", 
            "description": "...", 
            "id": 123  // Debe ser un número entero
        }},
        "reply": "Texto de confirmación para el usuario"
    }}

    CONTEXTO:
    {tasks_text}

    USUARIO: "{user_text}"
    """

    try:
        response = model.generate_content(prompt)
        raw_text = response.text.strip()
        
        # Limpieza de JSON
        clean_text = raw_text.replace("```json", "").replace("```", "").strip()
        
        if clean_text.startswith("{") and clean_text.endswith("}"):
            cmd = json.loads(clean_text)
            action = cmd.get("action")
            params = cmd.get("params", {})
            reply = cmd.get("reply", "Hecho.")
            
            # --- ACCIÓN: CREAR ---
            if action == "create":
                add_task_from_bot(params.get("title"), params.get("description", ""))
                return f"✅ {reply}", True
                
            # --- ACCIÓN: BORRAR (Uno) ---
            elif action == "delete":
                tid = params.get("id")
                if tid:
                    # Limpieza extra por si la IA envía "ID 5" en vez de "5"
                    try:
                        clean_id = int(str(tid).lower().replace("id", "").strip())
                        delete_task_by_id(clean_id)
                        return f"🗑️ {reply}", True
                    except ValueError:
                        return f"⚠️ No entendí qué ID borrar. La IA envió: '{tid}'", False
                
            # --- ACCIÓN: BORRAR TODO ---
            elif action == "delete_all":
                delete_all_tasks()
                return f"🔥☢️ {reply} (Se han borrado todas las tareas)", True

            # --- ACCIÓN: MODIFICAR ---
            elif action == "update_desc":
                tid = params.get("id")
                new_desc = params.get("description")
                if tid and new_desc:
                    try:
                        clean_id = int(str(tid).lower().replace("id", "").strip())
                        update_task_description(clean_id, new_desc)
                        return f"📝 {reply}", True
                    except ValueError:
                         return f"⚠️ ID inválido para modificar.", False
            
            return reply, True
            
        else:
            return raw_text, False

    except Exception as e:
        print(f"Error procesando IA: {e}")
        # Devolvemos el error al chat para que sepas qué pasa
        return f"🐛 Error interno: {str(e)}", False

# ==============================================================================
# RUTINAS y MANEJO (Sin cambios mayores, solo mantener funcionalidad)
# ==============================================================================

def send_routine_check():
    if not bot or not model: return
    tasks = list_all_tasks()
    # Si no hay tareas activas, no molestamos
    if not any(t['status'] != 'done' for t in tasks): return

    prompt = f"Resume estas tareas para motivar:\n{get_tasks_context()}"
    try:
        res = model.generate_content(prompt)
        bot.send_message(chat_id=CHAT_ID, text=f"⏰ *Resumen IA*\n{res.text}", parse_mode='Markdown')
    except: pass

def check_smart_urgency():
    if not bot: return
    now = datetime.now(SERVER_TIMEZONE)
    tasks = list_all_tasks()
    urgent = []
    for t in tasks:
        if t['status'] == 'done' or not t.get('due'): continue
        try:
            # Parseo robusto
            due = datetime.fromisoformat(t['due'])
            if due.tzinfo is None: due = SERVER_TIMEZONE.localize(due)
            else: due = due.astimezone(SERVER_TIMEZONE)
            
            delta = (due - now).total_seconds()
            if 0 < delta < 3600: urgent.append(f"🚨 {t['title']} (<1h)")
            elif 3600 <= delta < 14400 and now.minute < 15: urgent.append(f"⚠️ {t['title']} (<4h)")
        except: pass
    
    if urgent:
        bot.send_message(chat_id=CHAT_ID, text="¡Atención!\n" + "\n".join(urgent))

def _handle_start_command(msg=None, query=None):
    kb = [[InlineKeyboardButton("Ver Tareas", callback_data="list_tasks")]]
    text = "🤖 *Agente IA Actualizado*\nPuedo crear, modificar, borrar una o **borrar todas** las tareas."
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
    
    bot.send_chat_action(chat_id=msg.chat_id, action=telegram.ChatAction.TYPING)
    reply_text, _ = process_ai_command(text)
    bot.send_message(chat_id=msg.chat_id, text=reply_text)

def _process_callback(query):
    query.answer()
    data = query.data
    if data == "main_menu": _handle_start_command(query=query)
    elif data == "list_tasks": _handle_list_tasks(query)

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

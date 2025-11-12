# web_server.py
from flask import Flask, request, Response, jsonify
from db import get_conn, init_db
import sqlite3
import atexit
from apscheduler.schedulers.background import BackgroundScheduler
import telegram_client
import pytz

app = Flask(__name__)

@app.route("/")
def home():
    return jsonify({
        "status": "active",
        "service": "Task Sync Server (con Telegram Bot - Modo Polling)",
        "endpoints": { "get_tasks": "GET /sync/tasks", "sync_tasks": "POST /sync/tasks", "health": "GET /sync/health" }
    })

@app.route("/sync/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok"})

@app.route("/sync/tasks", methods=["GET"])
def get_all_tasks():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM tasks ORDER BY due")
    tasks = [dict(row) for row in cur.fetchall()]
    conn.close()
    return jsonify({"tasks": tasks})

@app.route("/sync/tasks", methods=["POST"])
def sync_tasks_from_client():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "No JSON data received"}), 400
        
        tasks = data.get("tasks", [])
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM tasks")
        
        count = 0
        for task in tasks:
            cur.execute(
                # --- ¡FIX ETIQUETAS (Req 2)! ---
                """INSERT INTO tasks 
                (id, title, description, due, status, created, tags, whatsapp_sent) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    task.get('id'),
                    task.get('title'),
                    task.get('description'),
                    task.get('due'),
                    task.get('status'),
                    task.get('created'),
                    task.get('tags'), # <-- ¡GUARDANDO ETIQUETAS!
                    task.get('whatsapp_sent', 0)
                )
            )
            count += 1
        
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": f"Sincronizadas {count} tareas"})
    
    except Exception as e:
        print(f"Error en POST /sync/tasks: {e}")
        return jsonify({"status": "error", "message": f"Error: {str(e)}"}), 500

# --- Inicio de la Aplicación ---
if __name__ == "__main__":
    print("Iniciando aplicación de servidor...")
    init_db()
    print("Configurando el programador de tareas (APScheduler)...")
    try:
        server_timezone = pytz.timezone("Europe/Madrid")
    except Exception:
        server_timezone = pytz.utc
    scheduler = BackgroundScheduler(daemon=True, timezone=server_timezone)
    scheduler.add_job(
        telegram_client.check_and_send_reminders, 'interval', hours=5
    )
    scheduler.add_job(
        telegram_client.check_for_messages, 'interval', seconds=5
    )
    scheduler.start()
    print("Scheduler iniciado con 2 tareas: Recordatorios (c/ 5h) y Polling (c/ 5s).")
    atexit.register(lambda: scheduler.shutdown())
    print(f"Iniciando servidor Flask en puerto 8080...")
    app.run(host="0.0.0.0", port=8080, debug=False)

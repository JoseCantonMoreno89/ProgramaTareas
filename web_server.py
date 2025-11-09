# web_server.py
from flask import Flask, request, Response, jsonify
from db import get_conn, init_db
import sqlite3
import atexit

# Importar el scheduler y las funciones de Telegram
from apscheduler.schedulers.background import BackgroundScheduler
import telegram_client

# --- ¡CORRECCIÓN DE CÓDIGO! ---
# Importamos pytz para definir explícitamente la zona horaria
import pytz
# -------------------------------

app = Flask(__name__)

# --- Endpoints de Sincronización (para la App de PC) ---

@app.route("/")
def home():
    return jsonify({
        "status": "active",
        "service": "Task Sync Server (con Telegram Bot)",
        "endpoints": {
            "get_tasks": "GET /sync/tasks",
            "sync_tasks": "POST /sync/tasks",
            "health": "GET /sync/health",
            "telegram_webhook": "POST /telegram-webhook"
        }
    })

@app.route("/sync/health", methods=["GET"])
def health_check():
    """Endpoint para que el cliente (main.py) verifique la conexión"""
    return jsonify({"status": "ok"})

@app.route("/sync/tasks", methods=["GET"])
def get_all_tasks():
    """Endpoint para que el cliente DESCARGUE (sync_from_server)"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM tasks ORDER BY due")
    tasks = [dict(row) for row in cur.fetchall()]
    conn.close()
    return jsonify({"tasks": tasks})

@app.route("/sync/tasks", methods=["POST"])
def sync_tasks_from_client():
    """Endpoint para que el cliente SUBA (sync_to_server)"""
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
                """INSERT INTO tasks 
                (id, title, description, due, status, created, whatsapp_sent) 
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    task.get('id'),
                    task.get('title'),
                    task.get('description'),
                    task.get('due'),
                    task.get('status'),
                    task.get('created'),
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

# --- Endpoint de Telegram (para el Bot) ---

@app.route("/telegram-webhook", methods=["POST"])
def telegram_webhook():
    """Recibe actualizaciones (mensajes) desde Telegram."""
    try:
        telegram_client.handle_telegram_update(request.get_json(force=True))
    except Exception as e:
        print(f"Error al procesar webhook de Telegram: {e}")
    return "OK", 200

# --- Inicio de la Aplicación ---

if __name__ == "__main__":
    print("Iniciando aplicación de servidor...")
    init_db()
    
    print("Configurando el programador de tareas (APScheduler)...")
    
    # --- ¡CORRECCIÓN DE CÓDIGO! ---
    # Le decimos explícitamente al scheduler que use la zona horaria de Madrid.
    # Esto evita que intente adivinar la zona horaria del contenedor.
    try:
        server_timezone = pytz.timezone("Europe/Madrid")
    except Exception:
        print("No se encontró 'Europe/Madrid', usando 'UTC'.")
        server_timezone = pytz.utc
        
    scheduler = BackgroundScheduler(daemon=True, timezone=server_timezone)
    # -------------------------------
    
    scheduler.add_job(
        telegram_client.check_and_send_reminders,
        'interval',
        hours=5  # (o minutes=1 para tus pruebas)
    )
    scheduler.start()
    print("Scheduler iniciado. Enviará recordatorios cada 5 horas.")
    
    print("Configurando webhook de Telegram...")
    if not telegram_client.setup_telegram_webhook():
        print("¡ADVERTENCIA! No se pudo configurar el webhook. "
              "Revisa SERVER_URL y BOT_TOKEN.")
    
    atexit.register(lambda: scheduler.shutdown())

    print(f"Iniciando servidor Flask en puerto 5000...")
    app.run(host="0.0.0.0", port=5000, debug=False)

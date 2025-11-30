# web_server.py
from flask import Flask, request, jsonify
from db import get_conn, init_db
import atexit
from apscheduler.schedulers.background import BackgroundScheduler
import telegram_client
import pytz
import subprocess 

app = Flask(__name__)

# --- RUTAS DE LA API ---

@app.route("/")
def home():
    return jsonify({
        "status": "active",
        "service": "Task Sync Server + Gemini AI Agent",
        "endpoints": { 
            "get_tasks": "GET /sync/tasks", 
            "sync_tasks": "POST /sync/tasks", 
            "health": "GET /sync/health",
            "github_webhook": "POST /github-webhook-secreto-1a9b2c8d"
        }
    })

@app.route("/sync/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok"})

@app.route("/sync/tasks", methods=["GET"])
def get_all_tasks():
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM tasks ORDER BY due")
        tasks = [dict(row) for row in cur.fetchall()]
        conn.close()
        return jsonify({"tasks": tasks})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/sync/tasks", methods=["POST"])
def sync_tasks_from_client():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "No JSON data received"}), 400

        tasks = data.get("tasks", [])
        conn = get_conn()
        cur = conn.cursor()
        
        # Reemplazo total para asegurar sincronización exacta
        cur.execute("DELETE FROM tasks")

        count = 0
        for task in tasks:
            cur.execute(
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
                    task.get('tags'), 
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

@app.route("/github-webhook-secreto-1a9b2c8d", methods=["POST"])
def github_webhook():
    print("¡Webhook de GitHub recibido! Iniciando despliegue...")
    try:
        # Ruta absoluta dentro del contenedor Docker
        ruta_script = "/app/deploy.sh" 
        subprocess.Popen([ruta_script])
        return jsonify({"status": "despliegue iniciado"}), 200
    except Exception as e:
        print(f"Error al ejecutar deploy.sh: {e}")
        return jsonify({"status": "error"}), 500

# --- INICIO DE LA APLICACIÓN Y SCHEDULER ---

if __name__ == "__main__":
    print("--- Iniciando Servidor de Tareas con IA ---")
    
    # 1. Inicializar Base de Datos
    init_db()

    # 2. Configurar Zona Horaria
    try:
        server_timezone = pytz.timezone("Europe/Madrid")
    except Exception:
        server_timezone = pytz.utc
        print("Aviso: Usando UTC por defecto.")

    # 3. Configurar el Programador (Scheduler)
    print("Configurando Agente IA y Scheduler...")
    scheduler = BackgroundScheduler(daemon=True, timezone=server_timezone)

    # TAREA A: Resumen de Rutina (Cada 5 horas)
    # Gemini te dará un resumen general y motivacional.
    scheduler.add_job(
        telegram_client.send_routine_check,
        trigger='interval', 
        hours=5,
        id='routine_check'
    )

    # TAREA B: Monitor de Urgencia Inteligente (Cada 15 minutos)
    # Ejecuta 'check_smart_urgency', que decide internamente si enviarte mensaje
    # cada hora (si faltan < 4h) o cada 15 min (si falta < 1h).
    scheduler.add_job(
        telegram_client.check_smart_urgency, 
        trigger='interval', 
        minutes=15,
        id='urgency_check'
    )

    # TAREA C: Polling de Mensajes (Cada 5 segundos)
    # Para que puedas chatear con la IA en tiempo casi real.
    scheduler.add_job(
        telegram_client.check_for_messages, 
        trigger='interval', 
        seconds=5,
        id='msg_polling'
    )

    scheduler.start()
    print("✅ Scheduler activo: Resumen (5h), Urgencia (Dinámica) y Chat (5s).")

    # Asegurar que el scheduler se apague al cerrar la app
    atexit.register(lambda: scheduler.shutdown())

    # 4. Arrancar Flask
    print("🚀 Servidor escuchando en puerto 8080...")
    app.run(host="0.0.0.0", port=8080, debug=False)

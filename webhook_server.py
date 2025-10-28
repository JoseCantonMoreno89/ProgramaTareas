# webhook_server.py
from flask import Flask, request, Response
from db import mark_as_principal_by_title, get_conn
import re
import sqlite3

app = Flask(__name__)

@app.route("/twilio-webhook", methods=["POST"])
def twilio_webhook():
    body = request.values.get('Body', '').strip()
    # Buscamos patrón "lo voy a hacer <nombre tarea>" (case-insensitive)
    m = re.match(r"^\s*lo voy a hacer\s+(.+)$", body, flags=re.IGNORECASE)
    if m:
        title = m.group(1).strip()
        task_id = mark_as_principal_by_title(title)
        if task_id:
            resp_text = "Tarea marcada como principal en la app. ¡Gracias!"
        else:
            resp_text = "No encontré esa tarea. Revisa el título y prueba de nuevo."
    else:
        resp_text = ("Mensaje recibido. Para marcar una tarea como principal escribe: "
                     "'lo voy a hacer <nombre tarea>'.")

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
    <Response>
        <Message>{resp_text}</Message>
    </Response>"""
    return Response(twiml, mimetype="text/xml")

@app.route("/sync/tasks", methods=["GET"])
def get_all_tasks():
    """Devuelve todas las tareas del servidor en JSON"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM tasks ORDER BY due")
    tasks = []
    for row in cur.fetchall():
        task = dict(row)
        # Convertir bytes a string si es necesario
        for key, value in task.items():
            if isinstance(value, bytes):
                task[key] = value.decode('utf-8', errors='ignore')
        tasks.append(task)
    conn.close()
    return {"tasks": tasks}

@app.route("/sync/tasks", methods=["POST"])
def sync_tasks_from_client():
    """Recibe tareas desde tu PC y las sincroniza en el servidor"""
    try:
        data = request.get_json()
        if not data:
            return {"status": "error", "message": "No JSON data received"}, 400
        
        tasks = data.get("tasks", [])
        
        conn = get_conn()
        cur = conn.cursor()
        
        # Limpiar tareas existentes y insertar las nuevas
        cur.execute("DELETE FROM tasks")
        
        for task in tasks:
            # Asegurarnos de que todos los campos necesarios están presentes
            title = task.get('title', '')
            description = task.get('description', '')
            due = task.get('due', '')
            status = task.get('status', 'pending')
            created = task.get('created', '')
            whatsapp_sent = task.get('whatsapp_sent', 0)
            
            cur.execute(
                """INSERT INTO tasks 
                (title, description, due, status, created, whatsapp_sent) 
                VALUES (?, ?, ?, ?, ?, ?)""",
                (title, description, due, status, created, whatsapp_sent)
            )
        
        conn.commit()
        conn.close()
        return {"status": "success", "message": f"Sincronizadas {len(tasks)} tareas"}
    
    except Exception as e:
        return {"status": "error", "message": f"Error: {str(e)}"}, 500

@app.route("/sync/health", methods=["GET"])
def health_check():
    """Endpoint para verificar que el servidor está funcionando"""
    return {"status": "ok", "message": "Servidor de sincronización activo"}

@app.route("/", methods=["GET"])
def home():
    """Página de inicio para verificar que el servidor está vivo"""
    return {
        "status": "active",
        "service": "Twilio Webhook + Task Sync Server",
        "endpoints": {
            "home": "GET /",
            "twilio_webhook": "POST /twilio-webhook",
            "get_tasks": "GET /sync/tasks",
            "sync_tasks": "POST /sync/tasks",
            "health": "GET /sync/health"
        }
    }

if __name__ == "__main__":
    # Nota: en producción ejecuta con gunicorn/uvicorn detrás de nginx
    app.run(host="0.0.0.0", port=5000, debug=False)


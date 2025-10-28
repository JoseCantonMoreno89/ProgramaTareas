# webhook_server.py
from flask import Flask, request, Response
from db import mark_as_principal_by_title
import re

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


if __name__ == "__main__":
    # Nota: en producción ejecuta con gunicorn/uvicorn detrás de nginx
    app.run(host="0.0.0.0", port=5000)

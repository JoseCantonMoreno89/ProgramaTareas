# db.py
import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Optional

# VITAL: Lee la ruta de la variable de entorno, si no existe, usa una local.
# docker-compose.yml definirá esta variable.
DB_PATH = os.environ.get("DATABASE_PATH", "reminders_server.db")

def get_conn():
    # Asegurarse de que el directorio (si lo hay) exista
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
        
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    print(f"Inicializando base de datos del servidor en: {DB_PATH}")
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        due TEXT,
        created TEXT,
        status TEXT DEFAULT 'pending',
        whatsapp_sent INTEGER DEFAULT 0
    )
    """)
    conn.commit()
    conn.close()
    print("Base de datos del servidor lista.")

def list_pending_tasks():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM tasks WHERE status != 'done' ORDER BY due")
    rows = cur.fetchall()
    conn.close()
    tasks = [dict(r) for r in rows]
    return tasks

def mark_as_principal_by_title(title: str) -> Optional[int]:
    """Busca una tarea por título y la marca como 'principal'."""
    conn = get_conn()
    cur = conn.cursor()
    # Busca la primera tarea pendiente que coincida
    cur.execute("SELECT id FROM tasks WHERE title = ? AND status != 'done' LIMIT 1", (title,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return None
    task_id = row["id"]
    cur.execute("UPDATE tasks SET status = 'principal' WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()
    return task_id

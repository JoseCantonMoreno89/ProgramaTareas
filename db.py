# db.py (Servidor)
import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Optional

DB_PATH = os.environ.get("DATABASE_PATH", "reminders_server.db")

def get_conn():
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
        tags TEXT, -- ¡NUEVA COLUMNA!
        whatsapp_sent INTEGER DEFAULT 0
    )
    """)
    # Manejar migración
    try:
        cur.execute("SELECT tags FROM tasks LIMIT 1")
    except sqlite3.OperationalError:
        print("Migrando base de datos del servidor: Añadiendo columna 'tags'...")
        cur.execute("ALTER TABLE tasks ADD COLUMN tags TEXT")
        
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
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id FROM tasks WHERE title = ? AND status != 'done' COLLATE NOCASE LIMIT 1", (title,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return None
    task_id = row["id"]
    cur.execute("UPDATE tasks SET status = 'principal' WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()
    return task_id

def mark_done_by_title(title: str) -> Optional[int]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id FROM tasks WHERE title = ? AND status != 'done' COLLATE NOCASE LIMIT 1", (title,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return None
    task_id = row["id"]
    cur.execute("UPDATE tasks SET status = 'done' WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()
    return task_id

def mark_pending_by_title(title: str) -> Optional[int]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id FROM tasks WHERE title = ? AND status != 'done' COLLATE NOCASE LIMIT 1", (title,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return None
    task_id = row["id"]
    cur.execute("UPDATE tasks SET status = 'pending' WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()
    return task_id

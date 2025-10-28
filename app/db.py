# db.py
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional

DB_PATH = "reminders.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        due TEXT,                     -- ISO timestamp stored as TEXT
        created TEXT DEFAULT (datetime('now')),
        status TEXT DEFAULT 'pending', -- pending / done / principal
        whatsapp_sent INTEGER DEFAULT 0
    )
    """)
    conn.commit()
    conn.close()

def add_task(title: str, description: str = None, due: Optional[datetime] = None):
    conn = get_conn()
    cur = conn.cursor()
    due_iso = due.isoformat(sep=' ') if due else None
    cur.execute("INSERT INTO tasks (title, description, due) VALUES (?, ?, ?)",
                (title, description, due_iso))
    conn.commit()
    conn.close()

def list_pending_tasks():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM tasks WHERE status != 'done' ORDER BY due")
    rows = cur.fetchall()
    conn.close()
    tasks = []
    for r in rows:
        t = dict(r)
        tasks.append(t)
    return tasks

def mark_as_principal_by_title(title: str) -> Optional[int]:
    """Busca la primera tarea con ese título y la marca como 'principal'.
       Devuelve el id si se actualizó, o None si no se encontró."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id FROM tasks WHERE title = ? LIMIT 1", (title,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return None
    task_id = row["id"]
    cur.execute("UPDATE tasks SET status = 'principal' WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()
    return task_id

def mark_done(task_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE tasks SET status='done' WHERE id=?", (task_id,))
    conn.commit()
    conn.close()

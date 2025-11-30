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
        tags TEXT, 
        whatsapp_sent INTEGER DEFAULT 0
    )
    """)
    try:
        cur.execute("SELECT tags FROM tasks LIMIT 1")
    except sqlite3.OperationalError:
        cur.execute("ALTER TABLE tasks ADD COLUMN tags TEXT")
    conn.commit()
    conn.close()

# --- LECTURA ---
def list_all_tasks():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM tasks ORDER BY due")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_task_by_title(title: str) -> Optional[Dict]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM tasks WHERE title = ? COLLATE NOCASE LIMIT 1", (title,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

# --- ESCRITURA ---
def add_task_from_bot(title: str, description: str = ""):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO tasks (title, description, status) VALUES (?, ?, 'pending')", (title, description))
    conn.commit()
    conn.close()

def update_task_description(task_id: int, new_desc: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE tasks SET description = ? WHERE id = ?", (new_desc, task_id))
    conn.commit()
    conn.close()

def delete_task_by_id(task_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()

def delete_task_by_title(title: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id FROM tasks WHERE title = ? COLLATE NOCASE LIMIT 1", (title,))
    row = cur.fetchone()
    if row:
        cur.execute("DELETE FROM tasks WHERE id = ?", (row['id'],))
        conn.commit()
    conn.close()

# --- ¡NUEVA FUNCIÓN!: BORRAR TODO ---
def delete_all_tasks():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM tasks")
    conn.commit()
    conn.close()

# --- ESTADOS ---
def mark_as_principal_by_title(title: str): _update_status_by_title(title, 'principal')
def mark_done_by_title(title: str): _update_status_by_title(title, 'done')
def mark_pending_by_title(title: str): _update_status_by_title(title, 'pending')

def _update_status_by_title(title: str, status: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id FROM tasks WHERE title = ? COLLATE NOCASE LIMIT 1", (title,))
    row = cur.fetchone()
    if row:
        cur.execute("UPDATE tasks SET status = ? WHERE id = ?", (status, row['id']))
        conn.commit()
    conn.close()

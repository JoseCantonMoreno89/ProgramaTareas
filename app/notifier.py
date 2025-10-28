# notifier.py
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
from db import list_pending_tasks
from plyer import notification
import threading
import time

sched = None

def send_local_notification(title: str, msg: str):
    """Envía notificación usando plyer en un hilo para no bloquear."""
    def _send():
        try:
            # plyer uses 'timeout' (seconds) on some platforms, may be ignored on others
            notification.notify(title=title, message=msg, timeout=8)
        except Exception:
            # fallback no crítico: se puede loggear si es necesario
            pass

    t = threading.Thread(target=_send, daemon=True)
    t.start()

def _parse_due(due_value):
    """Convierte el campo 'due' (almacenado como ISO string) a datetime o None."""
    if not due_value:
        return None
    try:
        # Acepta tanto 'YYYY-MM-DD HH:MM:SS' como ISO
        try:
            # Python 3.11+ supports fromisoformat with space; use replace if necessary
            return datetime.fromisoformat(due_value)
        except Exception:
            # Fallback: intentar con formatos comunes
            from datetime import datetime as _dt
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
                try:
                    return _dt.strptime(due_value, fmt)
                except Exception:
                    continue
            return None
    except Exception:
        return None

def check_and_notify():
    tasks = list_pending_tasks()
    now = datetime.now()
    for t in tasks:
        due = _parse_due(t.get('due'))
        if due:
            delta = (due - now).total_seconds()
            # Regla: notificar si queda <= 1 hora y >= 0 s
            if 0 <= delta <= 3600:
                send_local_notification(f"Próxima tarea: {t['title']}",
                                        f"Entrega: {due.strftime('%Y-%m-%d %H:%M')}")
        else:
            # Opcional: notificar tareas sin fecha pendientes (se puede comentar)
            pass

def schedule_local_notifications():
    global sched
    if sched is None:
        sched = BackgroundScheduler()
        sched.add_job(check_and_notify, 'interval', minutes=15, next_run_time=None)
        sched.start()

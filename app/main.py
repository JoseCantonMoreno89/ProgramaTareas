# main.py
import sys
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QListWidget, QPushButton,
                               QHBoxLayout, QLabel, QLineEdit, QTextEdit, QDateTimeEdit, QMessageBox)
from PySide6.QtCore import Qt, QTimer, QDateTime
from db import init_db, list_pending_tasks, add_task, mark_done
from notifier import schedule_local_notifications

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Recordatorios - Mi App")
        self.resize(420, 720)
        layout = QVBoxLayout(self)

        header = QLabel("<h2>Recordatorios</h2>")
        layout.addWidget(header)

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        form_layout = QVBoxLayout()
        self.title_in = QLineEdit()
        self.title_in.setPlaceholderText("Título de la tarea")
        self.desc_in = QTextEdit()
        self.desc_in.setPlaceholderText("Descripción (opcional)")
        self.due_in = QDateTimeEdit(QDateTime.currentDateTime())
        self.due_in.setCalendarPopup(True)

        form_layout.addWidget(self.title_in)
        form_layout.addWidget(self.desc_in)
        form_layout.addWidget(QLabel("Fecha y hora de entrega:"))
        form_layout.addWidget(self.due_in)

        layout.addLayout(form_layout)

        btn_layout = QHBoxLayout()
        add_btn = QPushButton("Agregar tarea")
        add_btn.clicked.connect(self.add_task)
        done_btn = QPushButton("Marcar hecha")
        done_btn.clicked.connect(self.mark_done)
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(done_btn)

        layout.addLayout(btn_layout)

        # Actualizar lista periódicamente (cada 10 s)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_list)
        self.timer.start(10000)

        init_db()
        try:
            schedule_local_notifications()  # arrancar scheduler local
        except Exception:
            # en entornos donde plyer no pueda notificar (ej. contenedores sin dbus),
            # no rompemos la app: solo ignoramos
            pass
        self.refresh_list()

    def refresh_list(self):
        self.list_widget.clear()
        tasks = list_pending_tasks()
        for t in tasks:
            due = t['due'] if t['due'] else "Sin fecha"
            label = f"{t['id']}: {t['title']} — {due} — {t['status']}"
            self.list_widget.addItem(label)

    def add_task(self):
        title = self.title_in.text().strip()
        if not title:
            QMessageBox.warning(self, "Error", "El título es obligatorio.")
            return
        desc = self.desc_in.toPlainText().strip()
        due_dt = self.due_in.dateTime().toPython()
        add_task(title, desc, due_dt)
        self.title_in.clear()
        self.desc_in.clear()
        self.refresh_list()

    def mark_done(self):
        sel = self.list_widget.currentItem()
        if not sel:
            QMessageBox.information(self, "Nada seleccionado", "Selecciona una tarea.")
            return
        text = sel.text()
        try:
            task_id = int(text.split(":")[0])
        except Exception:
            QMessageBox.warning(self, "Error", "No pude extraer el id de la tarea.")
            return
        mark_done(task_id)
        self.refresh_list()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())

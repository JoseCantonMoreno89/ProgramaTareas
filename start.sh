#!/bin/bash
# start.sh - Script de inicio del contenedor

echo "🔧 Inicializando base de datos..."
python -c "from db import init_db; init_db()"

echo "🚀 Iniciando servidor webhook..."
python webhook_server.py

# Dockerfile
FROM python:3.9-slim

WORKDIR /app

# Forzamos la instalación de pytz
RUN pip install --no-cache-dir pytz

COPY requirements-server.txt .
RUN pip install --no-cache-dir -r requirements-server.txt

COPY . .

# Dar permisos de ejecución al script de inicio
RUN chmod +x start.sh

# --- ¡CAMBIO AQUÍ! ---
EXPOSE 8080

# Usar el script de inicio
CMD ["./start.sh"]

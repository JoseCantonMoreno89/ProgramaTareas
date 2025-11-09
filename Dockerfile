# Dockerfile
FROM python:3.9-slim

WORKDIR /app

# (Opcional) Dependencias del sistema si fueran necesarias
# RUN apt-get update && apt-get install -y pkg-config && rm -rf /var/lib/apt/lists/*

# --- ¡¡AQUÍ ESTÁ LA CORRECCIÓN!! ---
# Forzamos la instalación de pytz como un paso separado
# Esto evita cualquier problema de caché con el requirements.txt
RUN pip install --no-cache-dir pytz
# ------------------------------------

COPY requirements-server.txt .
RUN pip install --no-cache-dir -r requirements-server.txt

COPY . .

# Dar permisos de ejecución al script de inicio
RUN chmod +x start.sh

EXPOSE 5000

# Usar el script de inicio
CMD ["./start.sh"]

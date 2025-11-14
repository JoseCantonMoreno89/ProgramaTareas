# Dockerfile
FROM python:3.9-slim

WORKDIR /app

# --- ¡CAMBIO AQUÍ! ---
# Instalar dependencias del sistema: git y python3-pip
RUN apt-get update && apt-get install -y git python3-pip

# Instalar docker-compose usando pip
RUN pip install --no-cache-dir docker-compose

# Forzamos la instalación de pytz
RUN pip install --no-cache-dir pytz
# --- FIN DEL CAMBIO ---

COPY requirements-server.txt .
RUN pip install --no-cache-dir -r requirements-server.txt

COPY . .

# Dar permisos de ejecución a AMBOS scripts
RUN chmod +x start.sh
RUN chmod +x deploy.sh # <-- ¡IMPORTANTE!

EXPOSE 8080
CMD ["./start.sh"]

# Dockerfile
FROM python:3.9-slim

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y git python3-pip curl

# --- CORRECCIÓN: Instalar Docker Compose V2 (Más reciente) ---
RUN curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
RUN chmod +x /usr/local/bin/docker-compose

# Configurar SSH para GitHub (si lo usas)
RUN mkdir -p /root/.ssh && \
    ssh-keyscan github.com >> /root/.ssh/known_hosts

# Dependencias de Python
RUN pip install --no-cache-dir pytz

COPY requirements-server.txt .
# Aseguramos que se instalan las librerías nuevas (google-generativeai)
RUN pip install --no-cache-dir -r requirements-server.txt

COPY . .

# Permisos
RUN chmod +x start.sh
RUN chmod +x deploy.sh

EXPOSE 8080
CMD ["./start.sh"]

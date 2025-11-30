# Dockerfile
# Actualizamos a Python 3.11 para compatibilidad con Gemini AI
FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y git python3-pip curl

# Instalar Docker Compose V2 (Última versión oficial)
RUN curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
RUN chmod +x /usr/local/bin/docker-compose

# Configurar SSH para GitHub (necesario para el webhook de despliegue)
RUN mkdir -p /root/.ssh && \
    ssh-keyscan github.com >> /root/.ssh/known_hosts

# Instalar librerías de Python
# (pytz suele dar guerra, así que lo forzamos primero, aunque no es estrictamente necesario en 3.11)
RUN pip install --no-cache-dir pytz

COPY requirements-server.txt .
# Instalamos todas las dependencias del archivo
RUN pip install --no-cache-dir -r requirements-server.txt

COPY . .

# Dar permisos de ejecución a los scripts
RUN chmod +x start.sh
RUN chmod +x deploy.sh

EXPOSE 8080
CMD ["./start.sh"]

# Dockerfile
FROM python:3.9-slim

WORKDIR /app

# --- ¡CAMBIO AQUÍ! ---
# Instalar dependencias del sistema: git, pip y curl
RUN apt-get update && apt-get install -y git python3-pip curl

# Instalar docker-compose (el binario oficial)
RUN curl -L "https://github.com/docker/compose/releases/download/1.29.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
RUN chmod +x /usr/local/bin/docker-compose

RUN mkdir -p /root/.ssh && \
    ssh-keyscan github.com >> /root/.ssh/known_hosts

# Forzamos la instalación de pytz
RUN pip install --no-cache-dir pytz
# --- FIN DEL CAMBIO ---

COPY requirements-server.txt .
RUN pip install --no-cache-dir -r requirements-server.txt

COPY . .

# Dar permisos de ejecución a AMBOS scripts
RUN chmod +x start.sh
RUN chmod +x deploy.sh

EXPOSE 8080
CMD ["./start.sh"]


FROM python:3.9-slim

WORKDIR /app

# Solo dependencias básicas
RUN apt-get update && apt-get install -y pkg-config && rm -rf /var/lib/apt/lists/*

COPY requirements-server.txt .
RUN pip install --no-cache-dir -r requirements-server.txt

COPY . .

# Dar permisos de ejecución al script de inicio
RUN chmod +x start.sh

EXPOSE 5000

# Usar el script de inicio
CMD ["./start.sh"]


FROM python:3.9-slim

WORKDIR /app

# Solo dependencias básicas
RUN apt-get update && apt-get install -y pkg-config && rm -rf /var/lib/apt/lists/*

COPY requirements-server.txt .
RUN pip install --no-cache-dir -r requirements-server.txt

COPY . .

# Inicializar la base de datos al iniciar
RUN python -c "from db import init_db; init_db()"

EXPOSE 5000
CMD ["python", "webhook_server.py"]


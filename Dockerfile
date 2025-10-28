FROM python:3.9-slim

WORKDIR /app

# Copiar requirements
COPY requirements.txt .

# Instalar dependencias excluyendo pypiwin32 en Linux
RUN if [ -f requirements.txt ]; then \
        cat requirements.txt | grep -v "pypiwin32" > requirements_linux.txt && \
        pip install --no-cache-dir -r requirements_linux.txt; \
    fi

# Instalar dependencias básicas
RUN pip install flask requests

COPY . .

EXPOSE 5000
CMD ["python", "main.py"]
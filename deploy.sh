#!/bin/bash
# deploy.sh
set -e
# 1. Define tus rutas
PROJECT_DIR="/app"
LOCK_FILE="$PROJECT_DIR/deploy.lock" # Un archivo vacío que usaremos como bloqueo

# 2. Comprueba si el archivo de bloqueo existe
if [ -f "$LOCK_FILE" ]; then
    echo "Despliegue ya en progreso. Saliendo."
    exit 1
fi

# 3. Crea el archivo de bloqueo para evitar otros despliegues
touch "$LOCK_FILE"

# 4. Asegúrate de que el archivo de bloqueo se borre al
#    terminar el script (incluso si falla)
trap 'rm -f "$LOCK_FILE"' EXIT

# 5. Ve al directorio y ejecuta el despliegue
cd "$PROJECT_DIR"
echo "Iniciando despliegue..."

# Descarga los cambios (resetea cualquier cambio local)
git fetch --all
git reset --hard origin/main # O la rama que uses
git pull

# Reconstruye y reinicia
docker-compose up --build -d

echo "Despliegue completado."

# 6. El 'trap' se ejecuta aquí y borra el .lock automáticamente

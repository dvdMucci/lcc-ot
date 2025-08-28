#!/bin/bash

# Script para arreglar permisos de archivos creados por Docker
# Uso: ./fix_permissions.sh

echo "🔧 Arreglando permisos de archivos creados por Docker..."

# Verificar si estamos en el directorio correcto
if [ ! -f "docker-compose.yml" ]; then
    echo "❌ Error: Debes ejecutar este script desde el directorio raíz del proyecto"
    exit 1
fi

# Cambiar propietario de todos los archivos web/ al usuario actual
echo "📁 Cambiando propietario de archivos web/..."
sudo chown -R $(whoami):$(whoami) web/

# Cambiar propietario de archivos de media si existen
if [ -d "web/media" ]; then
    echo "📁 Cambiando propietario de archivos media/..."
    sudo chown -R $(whoami):$(whoami) web/media/
fi

# Cambiar propietario de archivos de logs si existen
if [ -d "logs" ]; then
    echo "📁 Cambiando propietario de archivos logs/..."
    sudo chown -R $(whoami):$(whoami) logs/
fi

# Verificar que no queden archivos con usuario root
echo "🔍 Verificando archivos con usuario root..."
ROOT_FILES=$(find web/ -user root 2>/dev/null | wc -l)

if [ "$ROOT_FILES" -eq 0 ]; then
    echo "✅ No se encontraron archivos con usuario root"
else
    echo "⚠️ Se encontraron $ROOT_FILES archivos con usuario root:"
    find web/ -user root 2>/dev/null
    echo "🔄 Intentando arreglar archivos restantes..."
    sudo find web/ -user root -exec chown $(whoami):$(whoami) {} \;
fi

# Establecer permisos correctos
echo "🔐 Estableciendo permisos correctos..."
chmod -R 664 web/
find web/ -type d -exec chmod 775 {} \;

# Hacer ejecutables los scripts
chmod +x *.sh 2>/dev/null
chmod +x web/*.py 2>/dev/null

echo "✅ Permisos arreglados correctamente"
echo ""
echo "📋 Resumen:"
echo "  - Propietario: $(whoami)"
echo "  - Archivos web/: $(find web/ -type f | wc -l)"
echo "  - Directorios web/: $(find web/ -type d | wc -l)"
echo "  - Archivos con root: $(find web/ -user root 2>/dev/null | wc -l)"
echo ""
echo "💡 Para evitar este problema en el futuro:"
echo "  1. Usa este script después de ejecutar Docker"
echo "  2. O configura Docker para usar tu usuario:"
echo "     docker compose run --user $(id -u):$(id -g) web python manage.py migrate"

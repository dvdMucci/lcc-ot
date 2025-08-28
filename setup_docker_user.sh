#!/bin/bash

# Script para configurar el usuario de Docker automáticamente
# Uso: ./setup_docker_user.sh

echo "🔧 Configurando usuario de Docker..."

# Obtener UID y GID del usuario actual
CURRENT_UID=$(id -u)
CURRENT_GID=$(id -g)
CURRENT_USER=$(whoami)

echo "👤 Usuario actual: $CURRENT_USER (UID: $CURRENT_UID, GID: $CURRENT_GID)"

# Verificar si existe el archivo .env
if [ ! -f ".env" ]; then
    echo "📝 Creando archivo .env desde env.example..."
    cp env.example .env
fi

# Actualizar UID y GID en .env
echo "🔧 Actualizando UID y GID en .env..."
sed -i "s/UID=.*/UID=$CURRENT_UID/" .env
sed -i "s/GID=.*/GID=$CURRENT_GID/" .env

echo "✅ Configuración completada"
echo ""
echo "📋 Variables configuradas:"
echo "  - UID: $CURRENT_UID"
echo "  - GID: $CURRENT_GID"
echo "  - Usuario: $CURRENT_USER"
echo ""
echo "🚀 Ahora puedes ejecutar Docker sin problemas de permisos:"
echo "   docker compose up"
echo ""
echo "💡 Si tienes problemas de permisos en el futuro, ejecuta:"
echo "   ./fix_permissions.sh"

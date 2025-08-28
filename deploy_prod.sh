#!/bin/bash

# Script de deployment para producción
# Uso: ./deploy_prod.sh

set -e  # Salir si hay algún error

echo "🚀 Iniciando deployment de producción..."

# Verificar que existe el archivo .env
if [ ! -f .env ]; then
    echo "❌ Error: No se encontró el archivo .env"
    echo "📝 Copia env.example a .env y configura las variables"
    exit 1
fi

# Crear directorio de logs si no existe
mkdir -p logs

# Detener contenedores existentes
echo "🛑 Deteniendo contenedores existentes..."
docker-compose -f docker-compose.prod.yml down

# Construir y levantar contenedores de producción
echo "🔨 Construyendo contenedores de producción..."
docker-compose -f docker-compose.prod.yml up -d --build

# Esperar a que la base de datos esté lista
echo "⏳ Esperando a que la base de datos esté lista..."
sleep 30

# Crear superusuario si no existe
echo "👤 Verificando superusuario..."
docker-compose -f docker-compose.prod.yml exec web python create_superuser.py

# Verificar que todo esté funcionando
echo "🔍 Verificando servicios..."
docker-compose -f docker-compose.prod.yml ps

echo "✅ Deployment completado!"
echo "🌐 La aplicación está disponible en: http://localhost:5800"
echo "📊 Logs disponibles en: ./logs/"
echo ""
echo "🔒 Configuraciones de seguridad aplicadas:"
echo "   - Gunicorn en lugar de runserver"
echo "   - Bot separado en contenedor independiente"
echo "   - Configuración de producción activada"
echo "   - Validación de archivos adjuntos"
echo "   - Throttling y paginación en DRF"
echo "   - Headers de seguridad"
echo "   - Logging configurado para producción"

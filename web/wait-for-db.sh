#!/bin/bash
# Espera a que MariaDB esté listo
echo "Esperando que la base de datos esté disponible..."

while ! nc -z db 3306; do
  sleep 1
done

echo "Base de datos lista. Ejecutando aplicación..."
exec "$@"
# Fin del script
# Este script se utiliza para esperar a que la base de datos esté disponible antes de ejecutar la
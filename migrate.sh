#!/bin/bash

echo "Ejecutando migraciones en el contenedor Docker..."

# Ejecutar migraciones dentro del contenedor
docker exec django_web_app python manage.py makemigrations worklog
docker exec django_web_app python manage.py migrate

echo "Migraciones completadas."

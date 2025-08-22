#!/bin/bash

echo "Ejecutando migración personalizada..."

# 1. Crear las migraciones
echo "Creando migraciones..."
docker exec django_web_app python manage.py makemigrations worklog --noinput

# 2. Aplicar migraciones
echo "Aplicando migraciones..."
docker exec django_web_app python manage.py migrate

# 3. Actualizar registros existentes
echo "Actualizando registros existentes..."
docker exec django_web_app python manage.py shell -c "
from worklog.models import WorkLog
from django.contrib.auth import get_user_model

User = get_user_model()

# Actualizar registros existentes que no tienen created_by
worklogs_without_creator = WorkLog.objects.filter(created_by__isnull=True)
for worklog in worklogs_without_creator:
    worklog.created_by = worklog.technician
    worklog.save()

print(f'Actualizados {worklogs_without_creator.count()} registros existentes')

# Actualizar registros existentes que no tienen status
worklogs_without_status = WorkLog.objects.filter(status__isnull=True)
for worklog in worklogs_without_status:
    worklog.status = 'pendiente'
    worklog.save()

print(f'Actualizados {worklogs_without_status.count()} registros de estado')
"

echo "Migración personalizada completada."

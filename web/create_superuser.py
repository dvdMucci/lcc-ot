import os
import django

# Configura los settings de Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.db import IntegrityError

User = get_user_model()

USERNAME = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
EMAIL = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@example.com')
PASSWORD = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'admin123')

if not User.objects.filter(username=USERNAME).exists():
    print(f"Creando superusuario '{USERNAME}'...")
    try:
        User.objects.create_superuser(USERNAME, EMAIL, PASSWORD)
        print(f"Superusuario '{USERNAME}' creado exitosamente.")
    except IntegrityError:
        print(f"Advertencia: El superusuario '{USERNAME}' ya existía o hubo un conflicto.")
    except Exception as e:
        print(f"Error al crear superusuario '{USERNAME}': {e}")
else:
    print(f"El superusuario '{USERNAME}' ya existe. Saltando creación.")
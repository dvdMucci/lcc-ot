import os
import django

# Configura los settings de Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.db import IntegrityError

User = get_user_model() # Obtiene tu CustomUser

USERNAME = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
EMAIL = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@example.com')
PASSWORD = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'admin123')

# Intenta obtener el usuario si ya existe
existing_user = User.objects.filter(username=USERNAME).first()

if not existing_user:
    print(f"Creando superusuario '{USERNAME}'...")
    try:
        # Crea el superusuario y asigna el tipo 'admin' y otros campos por defecto
        user = User.objects.create_superuser(username=USERNAME, email=EMAIL, password=PASSWORD)
        user.user_type = 'admin' # <--- Establece el tipo de usuario a 'admin'
        # Estos campos ya tienen default=False y default='0' en tu modelo,
        # pero es buena práctica asegurarlos si fuera necesario.
        # user.is_2fa_enabled = False
        # user.telegram_chat_id = '0'
        user.save() # Guarda los cambios en la base de datos
        print(f"Superusuario '{USERNAME}' creado exitosamente con user_type='admin'.")
    except IntegrityError:
        print(f"Advertencia: El superusuario '{USERNAME}' ya existía o hubo un conflicto.")
    except Exception as e:
        print(f"Error al crear superusuario '{USERNAME}': {e}")
else:
    print(f"El superusuario '{USERNAME}' ya existe. Verificando tipo de usuario...")
    # Si el usuario ya existe, asegúrate de que sea tipo 'admin'
    if existing_user.user_type != 'admin':
        existing_user.user_type = 'admin'
        existing_user.save()
        print(f"Tipo de usuario para '{USERNAME}' actualizado a 'admin'.")
    else:
        print(f"Superusuario '{USERNAME}' ya es de tipo 'admin'.")
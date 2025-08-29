
from pathlib import Path
import environ
import os

# Inicializar entorno
env = environ.Env()


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Leer archivo .env
environ.Env.read_env(os.path.join(BASE_DIR, '../.env'))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/3.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-qaldz7)v6sm7sruf@r%*wah$c5n5%&rj)y8#9(l)c4+8(k^k!y'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['*']


# Application definition

INSTALLED_APPS = [
    'rest_framework',
    'accounts',
    'worklog',
    'work_order',
    'core',
    'clients',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_otp',
    'django_otp.plugins.otp_totp',
    'django_otp.plugins.otp_static',
    'csp'
]

AUTH_USER_MODEL = 'accounts.CustomUser'  # Usar el modelo de usuario personalizado

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'csp.middleware.CSPMiddleware', # Middleware para CSP
    'web.middleware.AdminIPRestrictMiddleware', # Middleware para restringir acceso admin por IP
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django_otp.middleware.OTPMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'web.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]



WSGI_APPLICATION = 'web.wsgi.application'


# Database
# https://docs.djangoproject.com/en/3.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': env('DB_NAME'),
        'USER': env('DB_USER'),
        'PASSWORD': env('DB_PASSWORD'),
        'HOST': env('DB_HOST'),
        'PORT': env('DB_PORT'),
        'OPTIONS': {
            'sql_mode': 'traditional', # Modo SQL para compatibilidad
            'charset': 'utf8mb4',
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        },
        'CONN_MAX_AGE': 60,  # Mantener conexiones vivas por 60 segundos
        'ATOMIC_REQUESTS': True,  # Transacciones automáticas
    }
}

# Configuración de conexión a la base de datos
DB_CONNECTION_TIMEOUT = 20
DB_READ_TIMEOUT = 30
DB_WRITE_TIMEOUT = 30


# Password validation
# https://docs.djangoproject.com/en/3.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/3.2/topics/i18n/

LANGUAGE_CODE = 'es-es'
TIME_ZONE = 'America/Argentina/Buenos_Aires'
USE_I18N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.2/howto/static-files/

STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / 'static',  # Directorio static en la raíz del proyecto
]
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
# https://docs.djangoproject.com/en/3.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/accounts/login/'
# OTP Settings
OTP_TOTP_ISSUER = 'LCC OT' # Nombre del emisor para la aplicación 2FA
OTP_LOGIN_URL = '/accounts/login/' # URL de login para OTP

# =============================
# CONFIGURACIÓN DE SEGURIDAD CSP (Nuevo formato)
# =============================

# Content Security Policy - Nuevo formato para django-csp >= 4.0
CONTENT_SECURITY_POLICY = {
    'DIRECTIVES': {
        'default-src': ("'self'",),
        'script-src': (
            "'self'",
            "cdn.jsdelivr.net",           # Bootstrap JS
            "cdnjs.cloudflare.com",       # Font Awesome
        ),
        'style-src': (
            "'self'",
            "'unsafe-inline'",            # Permitir estilos inline (temporal)
            "cdn.jsdelivr.net",           # Bootstrap CSS
            "cdnjs.cloudflare.com",       # Font Awesome CSS
        ),
        'img-src': (
            "'self'",
            "data:",                      # Imágenes base64
        ),
        'font-src': (
            "'self'",
            "cdnjs.cloudflare.com",       # Font Awesome fonts
        ),
        'connect-src': ("'self'",),       # AJAX requests
        'object-src': ("'none'",),        # No flash/plugins
        'base-uri': ("'self'",),          # Base URLs permitidas
        'form-action': ("'self'",),       # Formularios solo a mismo origen
    }
}

# Opcional: Reportes de violaciones CSP
# CSP_REPORT_URI = '/csp-report/'

# =============================
# CONFIGURACIÓN DE SEGURIDAD ADMIN
# =============================

# IPs permitidas para acceder al panel admin de Django
ADMIN_ALLOWED_IPS = [
    '172.29.0.0/16',  # Rango de red Docker
    '127.0.0.1',      # Localhost
    '::1',            # IPv6 localhost
]
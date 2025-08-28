"""
Configuración de Django para producción
"""
import os
from pathlib import Path
from .settings import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

# Configuración de hosts permitidos para producción
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

# Configuración de CSRF para producción
CSRF_TRUSTED_ORIGINS = os.environ.get('CSRF_TRUSTED_ORIGINS', 'http://localhost:8000,https://localhost').split(',')

# Configuración de seguridad SSL/HTTPS
SECURE_SSL_REDIRECT = os.environ.get('SECURE_SSL_REDIRECT', 'False').lower() == 'true'
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True

# Headers de seguridad
SECURE_HSTS_SECONDS = 31536000  # 1 año
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# Si hay proxy (nginx, etc.)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Configuración de DRF para producción
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.AnonRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "user": "1000/day",
        "anon": "100/day",
    },
}

# Configuración de logging para producción
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': '/var/log/django/app.log',
            'formatter': 'verbose',
        },
        'console': {
            'level': 'WARNING',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'worklog': {
            'handlers': ['console', 'file'],
            'level': 'WARNING',  # Reducir logging de worklog en producción
            'propagate': False,
        },
    },
}

# Límites de subida de archivos
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB

# Configuración de sesiones
SESSION_COOKIE_AGE = 3600  # 1 hora
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

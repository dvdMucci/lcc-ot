"""
Configuración de Django para desarrollo
"""
from .settings import *

# Configuración específica para desarrollo
DEBUG = True

# Configuración de DRF para desarrollo (más permisiva)
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,  # Menos elementos en desarrollo
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "user": "10000/day",  # Más permisivo en desarrollo
    },
}

# Configuración de logging para desarrollo
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
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'worklog': {
            'handlers': ['console'],
            'level': 'DEBUG',  # Más logging en desarrollo
            'propagate': False,
        },
    },
}

# Límites de subida de archivos (más permisivo en desarrollo)
DATA_UPLOAD_MAX_MEMORY_SIZE = 25 * 1024 * 1024  # 25MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 25 * 1024 * 1024  # 25MB

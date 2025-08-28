"""
Configuración del bot de Telegram con parámetros de seguridad
"""
import os
from typing import Dict, Any

# Configuración de seguridad del bot
BOT_SECURITY_CONFIG = {
    # Límites de texto
    'MAX_TEXT_LENGTH': 2000,
    'MAX_CITY_NAME_LENGTH': 100,
    'MAX_DURATION_FORMAT_LENGTH': 10,
    
    # Límites de audio
    'MAX_AUDIO_DURATION_SECONDS': 600,  # 10 minutos
    'MAX_AUDIO_SIZE_MB': 50,
    
    # Límites numéricos
    'MAX_KM_VALUE': 9999,
    'MIN_KM_VALUE': 0,
    
    # Configuración de rate limiting
    'MAX_MESSAGES_PER_MINUTE': 10,
    'MAX_AUDIO_FILES_PER_HOUR': 20,
    
    # Configuración de logging
    'LOG_SECURITY_EVENTS': True,
    'LOG_FILE_PATH': '/var/log/django/bot_security.log',
    
    # Configuración de validación
    'VALIDATE_ALL_TEXT_INPUTS': True,
    'VALIDATE_AUDIO_FILES': True,
    'SANITIZE_TRANSCRIPTIONS': True,
    
    # Patrones de bloqueo (se pueden personalizar)
    'BLOCKED_PATTERNS': [
        # Comandos del sistema
        r'\b(rm\s+-rf|del\s+/s|format\s+c:|shutdown|reboot|kill|pkill)\b',
        # URLs
        r'https?://[^\s]+',
        # Scripts
        r'<script[^>]*>.*?</script>',
        r'javascript:',
        r'data:text/html',
        # SQL
        r'\b(union\s+select|drop\s+table|delete\s+from|insert\s+into|select\s+\*\s+from)\b',
    ],
    
    # Extensiones de audio permitidas
    'ALLOWED_AUDIO_EXTENSIONS': {
        '.ogg', '.oga', '.wav', '.mp3', '.m4a', '.aac', '.flac', '.wma'
    },
    
    # MIME types de audio permitidos
    'ALLOWED_AUDIO_MIME_TYPES': {
        'audio/ogg', 'audio/wav', 'audio/mpeg', 'audio/mp4', 
        'audio/aac', 'audio/flac', 'audio/x-ms-wma'
    }
}

# Configuración del bot
BOT_CONFIG = {
    'TOKEN': os.environ.get('TELEGRAM_BOT_TOKEN'),
    'WEBHOOK_URL': os.environ.get('TELEGRAM_WEBHOOK_URL'),
    'ADMIN_CHAT_ID': os.environ.get('TELEGRAM_ADMIN_CHAT_ID'),
    
    # Configuración de transcripción
    'WHISPER_MODEL': 'medium',
    'WHISPER_DEVICE': 'cpu',
    'WHISPER_COMPUTE_TYPE': 'int8',
    
    # Configuración de archivos
    'AUDIO_UPLOAD_DIR': 'worklog_audios',
    'MAX_CONCURRENT_TRANSCRIPTIONS': 3,
    
    # Configuración de respuestas
    'DEFAULT_LANGUAGE': 'es',
    'ENABLE_VOICE_RESPONSES': False,
    
    # Configuración de desarrollo
    'DEBUG_MODE': os.environ.get('BOT_DEBUG', 'False').lower() == 'true',
    'LOG_LEVEL': 'INFO' if not os.environ.get('BOT_DEBUG', 'False').lower() == 'true' else 'DEBUG'
}

def get_bot_config() -> Dict[str, Any]:
    """Obtiene la configuración del bot"""
    return BOT_CONFIG

def get_security_config() -> Dict[str, Any]:
    """Obtiene la configuración de seguridad del bot"""
    return BOT_SECURITY_CONFIG

def is_security_enabled() -> bool:
    """Verifica si las validaciones de seguridad están habilitadas"""
    return os.environ.get('BOT_SECURITY_ENABLED', 'True').lower() == 'true'

def get_max_audio_duration() -> int:
    """Obtiene la duración máxima de audio permitida"""
    return BOT_SECURITY_CONFIG['MAX_AUDIO_DURATION_SECONDS']

def get_max_audio_size() -> int:
    """Obtiene el tamaño máximo de audio permitido en bytes"""
    return BOT_SECURITY_CONFIG['MAX_AUDIO_SIZE_MB'] * 1024 * 1024

def get_max_text_length() -> int:
    """Obtiene la longitud máxima de texto permitida"""
    return BOT_SECURITY_CONFIG['MAX_TEXT_LENGTH']

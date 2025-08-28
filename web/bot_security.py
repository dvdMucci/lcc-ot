"""
Módulo de seguridad para el bot de Telegram
Valida texto y archivos de audio para prevenir ataques
"""
import os
import re
import mimetypes
import logging
from typing import Tuple, Optional
from pathlib import Path
from django.utils import timezone
from bot_config import get_security_config, is_security_enabled

logger = logging.getLogger(__name__)

# Obtener configuración de seguridad
SECURITY_CONFIG = get_security_config()
MAX_AUDIO_DURATION_SECONDS = SECURITY_CONFIG['MAX_AUDIO_DURATION_SECONDS']
MAX_AUDIO_SIZE_MB = SECURITY_CONFIG['MAX_AUDIO_SIZE_MB']
MAX_TEXT_LENGTH = SECURITY_CONFIG['MAX_TEXT_LENGTH']

# Patrones maliciosos en texto (desde configuración)
MALICIOUS_PATTERNS = SECURITY_CONFIG['BLOCKED_PATTERNS'] + [
    # Caracteres de control
    r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]',
    # Emojis y caracteres especiales excesivos
    r'[^\w\s\.,!?¿¡áéíóúÁÉÍÓÚñÑüÜ\-\(\)\[\]{}:;@#$%&*+=<>~`|\\/]',
]

# Extensiones de audio permitidas (desde configuración)
ALLOWED_AUDIO_EXTENSIONS = SECURITY_CONFIG['ALLOWED_AUDIO_EXTENSIONS']

# MIME types de audio permitidos (desde configuración)
ALLOWED_AUDIO_MIME_TYPES = SECURITY_CONFIG['ALLOWED_AUDIO_MIME_TYPES']

class BotSecurityError(Exception):
    """Excepción para errores de seguridad del bot"""
    pass

def validate_text(text: str) -> Tuple[bool, str]:
    """
    Valida texto para detectar contenido malicioso
    
    Args:
        text: Texto a validar
        
    Returns:
        Tuple[bool, str]: (es_válido, mensaje_error)
    """
    # Verificar si las validaciones están habilitadas
    if not is_security_enabled():
        return True, ""
    
    if not text or not isinstance(text, str):
        return False, "Texto vacío o inválido"
    
    # Verificar longitud
    if len(text) > MAX_TEXT_LENGTH:
        return False, f"Texto demasiado largo. Máximo {MAX_TEXT_LENGTH} caracteres"
    
    # Verificar caracteres de control
    if any(ord(char) < 32 and char not in '\n\r\t' for char in text):
        return False, "Texto contiene caracteres de control no permitidos"
    
    # Verificar patrones maliciosos
    for pattern in MALICIOUS_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return False, f"Texto contiene contenido no permitido"
    
    # Verificar emojis excesivos (más del 30% del texto)
    emoji_count = len(re.findall(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\U00002600-\U000027BF]', text))
    if emoji_count > len(text) * 0.3:
        return False, "Demasiados emojis en el texto"
    
    # Verificar repetición excesiva
    words = text.split()
    if len(words) > 3:
        word_counts = {}
        for word in words:
            word_counts[word.lower()] = word_counts.get(word.lower(), 0) + 1
            if word_counts[word.lower()] > len(words) * 0.5:
                return False, "Texto con repetición excesiva de palabras"
    
    return True, ""

def validate_audio_file(file_path: str, file_size: int, mime_type: Optional[str] = None) -> Tuple[bool, str]:
    """
    Valida archivo de audio para asegurar que es realmente un audio válido
    
    Args:
        file_path: Ruta al archivo
        file_size: Tamaño del archivo en bytes
        mime_type: MIME type del archivo (opcional)
        
    Returns:
        Tuple[bool, str]: (es_válido, mensaje_error)
    """
    # Verificar si las validaciones están habilitadas
    if not is_security_enabled():
        return True, ""
    
    try:
        # Verificar que el archivo existe
        if not os.path.exists(file_path):
            return False, "Archivo no encontrado"
        
        # Verificar tamaño
        max_size_bytes = MAX_AUDIO_SIZE_MB * 1024 * 1024
        if file_size > max_size_bytes:
            return False, f"Archivo demasiado grande. Máximo {MAX_AUDIO_SIZE_MB}MB"
        
        # Verificar extensión
        file_ext = Path(file_path).suffix.lower()
        if file_ext not in ALLOWED_AUDIO_EXTENSIONS:
            return False, f"Extensión de archivo no permitida: {file_ext}"
        
        # Verificar MIME type si se proporciona
        if mime_type:
            if mime_type not in ALLOWED_AUDIO_MIME_TYPES:
                return False, f"MIME type no permitido: {mime_type}"
        
        # Verificar que el archivo no esté vacío
        if file_size == 0:
            return False, "Archivo de audio vacío"
        
        # Verificar que el archivo sea legible
        try:
            with open(file_path, 'rb') as f:
                header = f.read(1024)  # Leer primeros 1KB
                
                # Verificar headers de archivos de audio comunes
                if file_ext == '.ogg':
                    if not header.startswith(b'OggS'):
                        return False, "Archivo OGG inválido"
                elif file_ext == '.wav':
                    if not header.startswith(b'RIFF'):
                        return False, "Archivo WAV inválido"
                elif file_ext == '.mp3':
                    if not (header.startswith(b'ID3') or header[0:2] in [b'\xff\xfb', b'\xff\xf3', b'\xff\xf2']):
                        return False, "Archivo MP3 inválido"
                elif file_ext == '.m4a':
                    if not (b'ftyp' in header or b'M4A' in header):
                        return False, "Archivo M4A inválido"
                
                # Verificar que no sea un archivo ejecutable disfrazado
                executable_headers = [b'MZ', b'\x7fELF', b'\xfe\xed\xfa', b'\xcf\xfa\xed\xfe']
                for exe_header in executable_headers:
                    if header.startswith(exe_header):
                        return False, "Archivo ejecutable detectado"
                
        except Exception as e:
            logger.error(f"Error leyendo archivo de audio: {e}")
            return False, "Error al leer archivo de audio"
        
        return True, ""
        
    except Exception as e:
        logger.error(f"Error validando archivo de audio: {e}")
        return False, f"Error validando archivo: {str(e)}"

def validate_audio_duration(duration_seconds: float) -> Tuple[bool, str]:
    """
    Valida la duración del audio
    
    Args:
        duration_seconds: Duración en segundos
        
    Returns:
        Tuple[bool, str]: (es_válido, mensaje_error)
    """
    # Verificar si las validaciones están habilitadas
    if not is_security_enabled():
        return True, ""
    
    if duration_seconds <= 0:
        return False, "Duración debe ser mayor a 0"
    
    if duration_seconds > MAX_AUDIO_DURATION_SECONDS:
        return False, f"Audio demasiado largo. Máximo {MAX_AUDIO_DURATION_SECONDS // 60} minutos"
    
    return True, ""

def sanitize_text(text: str) -> str:
    """
    Sanitiza texto removiendo caracteres peligrosos
    
    Args:
        text: Texto a sanitizar
        
    Returns:
        str: Texto sanitizado
    """
    if not text:
        return ""
    
    # Remover caracteres de control excepto saltos de línea
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
    
    # Limitar longitud
    if len(text) > MAX_TEXT_LENGTH:
        text = text[:MAX_TEXT_LENGTH] + "..."
    
    # Remover URLs
    text = re.sub(r'https?://[^\s]+', '[URL_REMOVIDA]', text)
    
    # Remover comandos del sistema
    text = re.sub(r'\b(rm\s+-rf|del\s+/s|format\s+c:|shutdown|reboot|kill|pkill)\b', '[COMANDO_REMOVIDO]', text, flags=re.IGNORECASE)
    
    # Remover caracteres de control restantes
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
    
    return text.strip()

def get_file_info(file_path: str) -> dict:
    """
    Obtiene información del archivo para logging
    
    Args:
        file_path: Ruta al archivo
        
    Returns:
        dict: Información del archivo
    """
    try:
        stat = os.stat(file_path)
        return {
            'size': stat.st_size,
            'extension': Path(file_path).suffix.lower(),
            'mime_type': mimetypes.guess_type(file_path)[0],
            'exists': True
        }
    except Exception as e:
        logger.error(f"Error obteniendo info del archivo {file_path}: {e}")
        return {
            'size': 0,
            'extension': '',
            'mime_type': None,
            'exists': False,
            'error': str(e)
        }

def log_security_event(event_type: str, details: dict, user_id: Optional[int] = None):
    """
    Registra eventos de seguridad
    
    Args:
        event_type: Tipo de evento (text_validation, audio_validation, etc.)
        details: Detalles del evento
        user_id: ID del usuario (opcional)
    """
    log_data = {
        'event_type': event_type,
        'user_id': user_id,
        'timestamp': timezone.now().isoformat(),
        **details
    }
    
    logger.warning(f"SECURITY_EVENT: {log_data}")
    
    # Aquí podrías agregar logging a un archivo específico o base de datos
    # para auditoría de seguridad

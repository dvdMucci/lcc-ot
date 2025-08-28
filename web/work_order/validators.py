"""
Validadores para archivos adjuntos de órdenes de trabajo
"""
import os
from django.core.exceptions import ValidationError
from django.conf import settings

# Extensiones permitidas
ALLOWED_EXTENSIONS = {
    '.pdf', '.jpg', '.jpeg', '.png', '.gif', 
    '.doc', '.docx', '.xls', '.xlsx', '.txt',
    '.zip', '.rar', '.7z'
}

# Tamaño máximo en bytes (10MB)
MAX_FILE_SIZE = 10 * 1024 * 1024

def validate_file_extension(value):
    """
    Valida que el archivo tenga una extensión permitida
    """
    ext = os.path.splitext(value.name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError(
            f'Extensión de archivo no permitida. Extensiones permitidas: {", ".join(ALLOWED_EXTENSIONS)}'
        )

def validate_file_size(value):
    """
    Valida que el archivo no exceda el tamaño máximo
    """
    if value.size > MAX_FILE_SIZE:
        raise ValidationError(
            f'El archivo es demasiado grande. Tamaño máximo: {MAX_FILE_SIZE // (1024*1024)}MB'
        )

def validate_workorder_attachment(value):
    """
    Validador completo para archivos adjuntos de órdenes de trabajo
    """
    validate_file_extension(value)
    validate_file_size(value)
    
    # Validación adicional: verificar que el archivo no esté vacío
    if value.size == 0:
        raise ValidationError('El archivo no puede estar vacío.')

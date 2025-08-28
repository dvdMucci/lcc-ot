# Características de Seguridad del Bot de Telegram

Este documento describe las medidas de seguridad implementadas en el bot de Telegram para prevenir ataques y validar contenido.

## 🛡️ Validaciones de Texto

### Contenido Bloqueado
- **Comandos del sistema**: `rm -rf`, `del /s`, `format c:`, `shutdown`, `reboot`, `kill`, `pkill`
- **URLs maliciosas**: Cualquier URL HTTP/HTTPS
- **Scripts y código**: `<script>`, `javascript:`, `data:text/html`, `vbscript:`
- **Inyección SQL**: `UNION SELECT`, `DROP TABLE`, `DELETE FROM`, `INSERT INTO`
- **Caracteres de control**: Bytes 0x00-0x08, 0x0B, 0x0C, 0x0E-0x1F, 0x7F

### Límites de Texto
- **Longitud máxima**: 2000 caracteres
- **Emojis**: Máximo 30% del texto
- **Repetición**: No más del 50% de palabras repetidas
- **Caracteres especiales**: Limitados a caracteres seguros

### Sanitización Automática
- URLs reemplazadas por `[URL_REMOVIDA]`
- Comandos reemplazados por `[COMANDO_REMOVIDO]`
- Caracteres de control eliminados
- Texto truncado si excede límites

## 🎵 Validaciones de Audio

### Límites de Archivo
- **Duración máxima**: 10 minutos (600 segundos)
- **Tamaño máximo**: 50MB
- **Extensiones permitidas**: `.ogg`, `.oga`, `.wav`, `.mp3`, `.m4a`, `.aac`, `.flac`, `.wma`

### Validación de Contenido
- **Headers de archivo**: Verificación de firmas de audio válidas
- **Archivos ejecutables**: Detección y bloqueo de `.exe`, `.elf`, etc.
- **Archivos vacíos**: Rechazo de archivos de 0 bytes
- **MIME types**: Validación de tipos de contenido

### Formatos Soportados
- **OGG**: Verifica header `OggS`
- **WAV**: Verifica header `RIFF`
- **MP3**: Verifica headers `ID3` o `\xff\xfb`, `\xff\xf3`, `\xff\xf2`
- **M4A**: Verifica presencia de `ftyp` o `M4A`

## 🔢 Validaciones Numéricas

### Kilómetros
- **Rango**: 0-9999 km
- **Formato**: Solo números enteros
- **Validación**: Rechaza caracteres no numéricos

### Duración
- **Formato**: `H:MM` o minutos
- **Límite**: Máximo 10 caracteres
- **Caracteres**: Solo números y dos puntos

### Nombres de Ciudad
- **Longitud**: Máximo 100 caracteres
- **Caracteres**: Solo letras, números, espacios, guiones y puntos
- **Sanitización**: Elimina caracteres especiales

## 📝 Logging de Seguridad

### Eventos Registrados
- **Texto rechazado**: Contenido malicioso detectado
- **Audio rechazado**: Archivo inválido o muy grande
- **Duración excedida**: Audio más largo que 10 minutos
- **Formato inválido**: Entrada en formato incorrecto
- **Transcripción rechazada**: Texto transcrito no válido

### Información Capturada
- **Usuario**: ID del usuario de Telegram
- **Timestamp**: Fecha y hora del evento
- **Tipo de evento**: Categoría del problema
- **Detalles**: Información específica del error
- **Datos originales**: Contenido que causó el rechazo

## ⚙️ Configuración

### Variables de Entorno
```bash
# Habilitar/deshabilitar seguridad
BOT_SECURITY_ENABLED=True

# Modo debug
BOT_DEBUG=False

# Token del bot
TELEGRAM_BOT_TOKEN=your_token_here

# Chat ID del administrador
TELEGRAM_ADMIN_CHAT_ID=123456789
```

### Configuración Personalizable
- **Límites**: Todos los límites son configurables
- **Patrones**: Lista de patrones maliciosos personalizable
- **Extensiones**: Formatos de audio permitidos configurables
- **Logging**: Nivel de detalle configurable

## 🧪 Pruebas de Seguridad

### Script de Pruebas
```bash
# Ejecutar todas las pruebas
./test_bot_security.py

# Verificar validaciones de texto
python -c "from web.bot_security import validate_text; print(validate_text('rm -rf /'))"

# Verificar validaciones de audio
python -c "from web.bot_security import validate_audio_duration; print(validate_audio_duration(700))"
```

### Casos de Prueba Incluidos
- ✅ Texto normal y válido
- ❌ Comandos del sistema
- ❌ URLs maliciosas
- ❌ Scripts XSS
- ❌ Inyección SQL
- ❌ Emojis excesivos
- ❌ Repetición de palabras
- ❌ Archivos ejecutables
- ❌ Audio muy largo
- ❌ Formatos inválidos

## 🚀 Implementación

### Archivos Modificados
- `web/bot.py`: Integración de validaciones
- `web/bot_security.py`: Módulo de seguridad
- `web/bot_config.py`: Configuración centralizada

### Funciones Principales
```python
# Validar texto
is_valid, error = validate_text(text)

# Validar archivo de audio
is_valid, error = validate_audio_file(file_path, file_size)

# Validar duración
is_valid, error = validate_audio_duration(seconds)

# Sanitizar texto
clean_text = sanitize_text(raw_text)

# Registrar evento de seguridad
log_security_event("event_type", details, user_id)
```

## 🔒 Beneficios de Seguridad

### Protección Contra
- **Ataques de inyección**: SQL, comandos del sistema
- **XSS**: Scripts maliciosos en texto
- **Malware**: Archivos ejecutables disfrazados
- **Spam**: Repetición excesiva de contenido
- **DoS**: Archivos muy grandes o muy largos
- **Phishing**: URLs maliciosas

### Auditoría
- **Logs detallados**: Todos los eventos de seguridad
- **Trazabilidad**: Usuario y timestamp de cada evento
- **Análisis**: Patrones de ataques detectados
- **Monitoreo**: Alertas para administradores

### Flexibilidad
- **Configuración**: Parámetros ajustables
- **Deshabilitación**: Opción de desactivar validaciones
- **Personalización**: Patrones y límites configurables
- **Escalabilidad**: Fácil agregar nuevas validaciones

## 📊 Estadísticas de Seguridad

### Métricas Capturadas
- **Eventos por tipo**: Distribución de problemas
- **Usuarios problemáticos**: Patrones de comportamiento
- **Contenido bloqueado**: Tipos de ataques más comunes
- **Falsos positivos**: Validaciones que pueden ser muy estrictas

### Monitoreo Recomendado
- Revisar logs de seguridad diariamente
- Analizar patrones de ataques semanalmente
- Ajustar configuraciones según necesidades
- Actualizar patrones de bloqueo mensualmente

## 🔧 Mantenimiento

### Tareas Regulares
1. **Revisar logs**: Verificar eventos de seguridad
2. **Actualizar patrones**: Agregar nuevos vectores de ataque
3. **Ajustar límites**: Optimizar según uso real
4. **Backup de config**: Respaldo de configuraciones
5. **Análisis de tendencias**: Identificar patrones

### Actualizaciones
- **Patrones de seguridad**: Nuevos vectores de ataque
- **Formatos de audio**: Nuevos codecs soportados
- **Límites**: Ajustes basados en uso real
- **Logging**: Mejoras en auditoría

# Guía de Permisos de Docker

Este documento explica cómo manejar los problemas de permisos que pueden surgir cuando Docker crea archivos en tu sistema.

## 🚨 Problema Común

Cuando Docker ejecuta comandos como `makemigrations` o `migrate`, crea archivos con el usuario `root` del contenedor. Esto causa problemas porque:

- No puedes editar los archivos desde tu editor
- No puedes guardar cambios
- Aparecen errores de permisos

## 🔧 Solución Inmediata

### Script Automático
```bash
# Arreglar permisos de todos los archivos
./fix_permissions.sh
```

### Comando Manual
```bash
# Cambiar propietario de todos los archivos web/
sudo chown -R ubuntu:ubuntu web/

# Verificar que no queden archivos con root
find web/ -user root -ls
```

## 🛠️ Solución Permanente

### 1. Configurar Usuario de Docker

Ejecuta el script de configuración:
```bash
./setup_docker_user.sh
```

Esto:
- Detecta tu UID y GID automáticamente
- Actualiza el archivo `.env` con las variables correctas
- Configura Docker para usar tu usuario

### 2. Variables de Entorno

El archivo `.env` debe contener:
```bash
# Configuración de usuario para Docker
UID=1001
GID=1001
```

### 3. Docker Compose Configurado

El `docker-compose.yml` incluye:
```yaml
web:
  user: "${UID:-1000}:${GID:-1000}"  # Usar tu usuario
```

## 📋 Scripts Disponibles

### `fix_permissions.sh`
- Arregla permisos de archivos existentes
- Cambia propietario a tu usuario
- Verifica que no queden archivos con root
- Establece permisos correctos

### `setup_docker_user.sh`
- Detecta tu UID y GID automáticamente
- Configura variables de entorno
- Prepara Docker para usar tu usuario

## 🚀 Uso Recomendado

### Primera Vez
```bash
# 1. Configurar usuario de Docker
./setup_docker_user.sh

# 2. Arreglar permisos existentes
./fix_permissions.sh

# 3. Ejecutar Docker
docker compose up
```

### Uso Diario
```bash
# Ejecutar Docker normalmente
docker compose up

# Si hay problemas de permisos
./fix_permissions.sh
```

### Después de Migraciones
```bash
# Ejecutar migraciones
docker compose exec web python manage.py makemigrations
docker compose exec web python manage.py migrate

# Arreglar permisos si es necesario
./fix_permissions.sh
```

## 🔍 Verificación

### Verificar Permisos
```bash
# Ver archivos con usuario root
find web/ -user root -ls

# Ver permisos de una carpeta específica
ls -la web/work_order/
```

### Verificar Configuración
```bash
# Ver variables de entorno
grep -E "UID|GID" .env

# Ver usuario actual
id
```

## 🐛 Problemas Comunes

### Error: "Permission denied"
```bash
# Solución
./fix_permissions.sh
```

### Error: "Cannot save file"
```bash
# Verificar propietario
ls -la archivo_problematico

# Cambiar propietario
sudo chown ubuntu:ubuntu archivo_problematico
```

### Docker no puede escribir archivos
```bash
# Verificar variables de entorno
cat .env | grep -E "UID|GID"

# Reconfigurar si es necesario
./setup_docker_user.sh
```

## 📊 Información del Sistema

### Tu Usuario
- **Usuario**: `ubuntu`
- **UID**: `1001`
- **GID**: `1001`

### Archivos Afectados
- `web/work_order/migrations/` - Migraciones de Django
- `web/worklog/migrations/` - Migraciones de Django
- `web/media/` - Archivos subidos por usuarios
- `web/` - Código fuente

## 💡 Consejos

### Para Desarrolladores
1. **Siempre** ejecuta `./fix_permissions.sh` después de migraciones
2. **Configura** tu editor para usar tu usuario
3. **Verifica** permisos antes de hacer commits

### Para Producción
1. **No uses** estos scripts en producción
2. **Configura** Docker para usar un usuario específico
3. **Mantén** permisos estrictos en producción

### Para Equipos
1. **Documenta** el proceso en el README
2. **Incluye** los scripts en el repositorio
3. **Entrena** al equipo en el uso

## 🔒 Seguridad

### Permisos Recomendados
```bash
# Archivos
chmod 664 archivo.py

# Directorios
chmod 775 directorio/

# Scripts
chmod +x script.sh
```

### Usuario de Docker
- **Desarrollo**: Usar tu usuario local
- **Producción**: Usar usuario específico del contenedor
- **Nunca**: Usar root en producción

## 📚 Referencias

- [Docker User Namespaces](https://docs.docker.com/engine/security/userns-remap/)
- [Docker Compose User](https://docs.docker.com/compose/compose-file/compose-file-v3/#user)
- [Linux File Permissions](https://www.gnu.org/software/coreutils/manual/html_node/File-permissions.html)

# Usa la misma imagen base para consistencia
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Instala ffmpeg y dependencias necesarias
RUN apt-get update && apt-get install -y netcat-openbsd && rm -rf /var/lib/apt/lists/*
    

# Crea un directorio para el bot
WORKDIR /app

COPY requirements.txt .

# Instala whisper y sus dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Copia los archivos del bot al contenedor
COPY . .


# Damos permisos de ejecución
RUN chmod +x wait-for-db.sh
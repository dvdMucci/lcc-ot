# Usa una imagen base oficial de Python
FROM python:3.11-slim

# Evita que Python escriba archivos .pyc
ENV PYTHONDONTWRITEBYTECODE=1
# Asegura que la salida de Python se muestre en la terminal sin buffer
ENV PYTHONUNBUFFERED=1

# Configuración de hilos para faster-whisper
ENV OMP_NUM_THREADS=1
ENV OPENBLAS_NUM_THREADS=1
ENV MKL_NUM_THREADS=1
ENV NUMEXPR_NUM_THREADS=1

# Configurar variables de entorno para Hugging Face
ENV HF_HOME=/app/.cache/huggingface
ENV TRANSFORMERS_CACHE=/app/.cache/huggingface/transformers
ENV HF_DATASETS_CACHE=/app/.cache/huggingface/datasets

RUN apt-get update && apt-get install -y git libsndfile1 ffmpeg netcat-openbsd gcc htop default-libmysqlclient-dev python3-dev pkg-config build-essential && rm -rf /var/lib/apt/lists/*

# Crear usuario no-root
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Establece el directorio de trabajo dentro del contenedor
WORKDIR /app

# Crear directorio de cache con permisos correctos
RUN mkdir -p /app/.cache/huggingface && chown -R appuser:appuser /app/.cache

# Copia e instala las dependencias primero para aprovechar el caché de Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia el resto del código de tu aplicación al contenedor
COPY . .

# Crear directorio de archivos estáticos si no existe
RUN mkdir -p /app/web/static/web

# Cambiar propietario de todos los archivos al usuario appuser
RUN chown -R appuser:appuser /app

# Damos permisos de ejecución
RUN chmod +x wait-for-db.sh

# Cambiar al usuario no-root
USER appuser


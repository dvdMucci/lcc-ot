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

RUN apt-get update && apt-get install -y git libsndfile1 ffmpeg netcat-openbsd gcc htop default-libmysqlclient-dev python3-dev pkg-config build-essential && rm -rf /var/lib/apt/lists/*

# Establece el directorio de trabajo dentro del contenedor
WORKDIR /app

# Copia e instala las dependencias primero para aprovechar el caché de Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia el resto del código de tu aplicación al contenedor
COPY . .

# Damos permisos de ejecución
RUN chmod +x wait-for-db.sh


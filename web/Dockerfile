# Usa una imagen base oficial de Python
FROM python:3.11-slim

# Evita que Python escriba archivos .pyc
ENV PYTHONDONTWRITEBYTECODE 1
# Asegura que la salida de Python se muestre en la terminal sin buffer
ENV PYTHONUNBUFFERED 1

RUN apt-get update && apt-get install -y netcat-openbsd\
    gcc \
    htop \
    default-libmysqlclient-dev \
    python3-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*\

# Establece el directorio de trabajo dentro del contenedor
WORKDIR /app

# Copia e instala las dependencias primero para aprovechar el caché de Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia el resto del código de tu aplicación al contenedor
COPY . .

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
# Dockerfile para backend Django - NARA
FROM python:3.11-slim

# Definir variáveis de ambiente
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=nara_api.settings

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Criar diretório de trabalho
WORKDIR /app

# Copiar requirements e instalar dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código do projeto
COPY . .

# Criar diretório de uploads
RUN mkdir -p uploads

# Expor porta
EXPOSE 8001

# Comando padrão
CMD ["python", "manage.py", "runserver", "0.0.0.0:8001"]

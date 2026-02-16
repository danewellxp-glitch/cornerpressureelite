# CPES - Corner Pressure Elite (API + Main + Monitor)
FROM python:3.12-slim

WORKDIR /app

# Dependências do sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código
COPY . .
RUN mkdir -p data logs

# Porta padrão (API)
EXPOSE 8000

# Comando padrão: API (para docker-compose api service)
# O service "main" sobrescreve com: python main.py
CMD ["uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000"]

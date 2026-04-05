FROM python:3.12-slim

# Устанавливаем Docker CLI и curl для healthcheck
RUN apt-get update && apt-get install -y docker.io curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Запускаем от root (безопасность обеспечивается cap_drop и no-new-privileges в compose)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8092"]
COPY . .

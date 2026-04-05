FROM python:3.12-slim

RUN apt-get update && apt-get install -y curl build-essential g++ && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt --timeout 60

RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

COPY . .

RUN mkdir -p /app/01_ЦЕХ/01_ЖУРНАЛЫ

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8090"]

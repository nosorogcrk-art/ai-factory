FROM python:3.12-slim-bookworm
WORKDIR /app
COPY requirements.txt .
RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir --timeout 100 --retries 5 -r requirements.txt
COPY . .
CMD ["python", "indexer.py"]

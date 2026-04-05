FROM python:3.12-slim-bookworm
WORKDIR /app
COPY requirements.txt .
RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir --timeout 100 --retries 5 -r requirements.txt
COPY . .
ENV PORT=5005
EXPOSE 5005
CMD ["uvicorn", "semantic_search:app", "--host", "0.0.0.0", "--port", "5005"]

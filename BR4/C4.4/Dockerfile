FROM python:3.12-slim
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY . .
EXPOSE 8112
CMD ["python", "-m", "http.server", "8112"]

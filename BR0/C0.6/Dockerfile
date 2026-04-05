FROM python:3.12-slim
WORKDIR /app
COPY . .
CMD ["python", "-c", "import time; print('Chaos Monkey ready'); time.sleep(3600)"]
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --timeout 200 -r requirements.txt
COPY . .
ENV PORT=8094
EXPOSE 8094
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8094"]

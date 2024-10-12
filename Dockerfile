# backend/Dockerfile
FROM python:3.10-slim

RUN apt-get update && apt-get install -y \
    redis-server \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
# Copy the entire backend directory
COPY . .
RUN pip install --no-cache-dir -r requirements.txt
# Expose the port the app runs on
EXPOSE 80

CMD redis-server --daemonize yes && uvicorn app.main:app --host 0.0.0.0 --port 80

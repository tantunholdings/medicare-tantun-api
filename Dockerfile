# backend/Dockerfile
FROM python:alpine3.20

WORKDIR /app
# Copy the entire backend directory
COPY . .
RUN pip install --no-cache-dir -r requirements.txt
# Expose the port the app runs on
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "80"]

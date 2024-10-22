#!/bin/bash

# Start Redis in the background
redis-server --daemonize yes

# Start the FastAPI app
uvicorn app.main:app --host 0.0.0.0 --port 80


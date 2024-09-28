# main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.auth import auth_router
from app.blog import blog_router
from app.faq import faq_router

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Allow only the frontend origin
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all headers
)

# Include authentication routes
app.include_router(auth_router)
app.include_router(blog_router)
app.include_router(faq_router)
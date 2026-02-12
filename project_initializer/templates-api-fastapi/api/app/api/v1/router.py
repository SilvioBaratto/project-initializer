"""API v1 router - imports and includes all route modules"""

from fastapi import APIRouter

from app.api.v1.test import router as test_router
from app.api.v1.chatbot import router as chatbot_router

# Create the main API router
api_router = APIRouter()

# Include all route modules
api_router.include_router(test_router)
api_router.include_router(chatbot_router)

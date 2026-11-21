"""Assembles the routers of API version 1."""

from fastapi import APIRouter, status

from app.api.errors import error_responses
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.items import router as items_router
from app.api.v1.endpoints.test import router as test_router

# The limiter answers before any route runs, so every versioned route can
# return 429 whatever else it documents.
api_router = APIRouter(responses=error_responses(status.HTTP_429_TOO_MANY_REQUESTS))
api_router.include_router(auth_router)
api_router.include_router(test_router)
api_router.include_router(items_router)

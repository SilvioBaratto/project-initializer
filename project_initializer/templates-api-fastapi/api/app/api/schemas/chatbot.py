"""Chatbot request/response schemas (API-layer re-export).

The chatbot DTOs are the use-case contract and live in
``app/application/dto/chatbot.py`` so the application service can reference them
without importing the API layer. They are re-exported here so API-layer code and
``app.api.schemas`` consumers keep a stable ``app.api.schemas.chatbot`` import.
"""

from app.application.dto.chatbot import (
    ChatRequest,
    ChatResponse,
    ConversationHistory,
    StreamChunk,
)

__all__ = [
    "ChatRequest",
    "ChatResponse",
    "ConversationHistory",
    "StreamChunk",
]

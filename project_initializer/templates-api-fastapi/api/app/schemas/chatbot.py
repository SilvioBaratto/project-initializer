"""
Chatbot Schemas
===============

Schemas for chatbot request/response validation.
Designed to match BAML function inputs/outputs.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field

from app.schemas import utc_now


# ===========================
# Request/Response Schemas
# ===========================

class ConversationHistory(BaseModel):
    """
    Conversation history for context.
    Matches BAML ConversationHistory class.
    """
    messages: List[str] = Field(
        default_factory=list,
        description="List of previous messages in the conversation"
    )


class ChatRequest(BaseModel):
    """
    Request schema for chat endpoint.
    Maps to BAML Chat and StreamChat function inputs.
    """
    user_question: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="The user's question or message",
        examples=["Tell me about Silvio's portfolio"]
    )
    conversation_history: Optional[ConversationHistory] = Field(
        default=None,
        description="Previous conversation messages for context",
        examples=[None]
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "user_question": "Tell me about Silvio's portfolio"
                },
                {
                    "user_question": "What projects has he worked on?",
                    "conversation_history": {
                        "messages": [
                            "User: Tell me about Silvio",
                            "Assistant: Silvio Baratto is a full-stack developer..."
                        ]
                    }
                }
            ]
        }
    }


class ChatResponse(BaseModel):
    """
    Response schema for chat endpoint.
    Maps to BAML ChatResponse class.
    """
    answer: str = Field(
        ...,
        description="The chatbot's response"
    )


class StreamChunk(BaseModel):
    """
    Schema for streaming response chunks.
    Sent as Server-Sent Events (SSE).
    """
    content: str = Field(
        ...,
        description="Partial or complete response content"
    )
    done: bool = Field(
        default=False,
        description="Whether this is the final chunk"
    )

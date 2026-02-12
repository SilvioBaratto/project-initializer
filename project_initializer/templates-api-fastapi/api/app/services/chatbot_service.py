"""
Chatbot Service
===============

Service layer for chatbot business logic using BAML.
"""

from typing import AsyncGenerator

from baml_client.async_client import b as baml_async_client
from baml_client.types import ConversationHistory

from app.schemas.chatbot import (
    ChatRequest,
    ChatResponse,
    StreamChunk,
)


class ChatbotService:
    """Service for chatbot operations using BAML."""

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """
        Process a chat request and return a response.

        Args:
            request: The chat request containing user question and context

        Returns:
            ChatResponse with answer
        """
        baml_history = None
        if request.conversation_history:
            baml_history = ConversationHistory(
                messages=request.conversation_history.messages
            )

        result = await baml_async_client.Chat(
            user_question=request.user_question,
            conversation_history=baml_history,
        )

        return ChatResponse(answer=result.answer)

    async def stream_chat(
        self,
        request: ChatRequest
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Process a chat request with streaming response.

        Args:
            request: The chat request containing user question and context

        Yields:
            StreamChunk objects with partial responses
        """
        baml_history = None
        if request.conversation_history:
            baml_history = ConversationHistory(
                messages=request.conversation_history.messages
            )

        stream = baml_async_client.stream.StreamChat(
            user_question=request.user_question,
            conversation_history=baml_history,
        )

        async for partial in stream:
            if partial and partial.answer:
                yield StreamChunk(
                    content=partial.answer,
                    done=False
                )

        final = await stream.get_final_response()
        yield StreamChunk(
            content=final.answer,
            done=True
        )

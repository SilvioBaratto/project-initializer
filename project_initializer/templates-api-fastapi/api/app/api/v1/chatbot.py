"""
Chatbot Endpoints
=================

API endpoints for chatbot interactions.
Supports both standard and streaming responses.
"""

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.schemas import (
    ChatRequest,
    ChatResponse,
    StreamChunk,
)
from app.services.chatbot_service import ChatbotService


router = APIRouter(prefix="/chat", tags=["Chatbot"])


# ===========================
# Dependency Injection
# ===========================

def get_chatbot_service() -> ChatbotService:
    """
    Dependency that provides a ChatbotService instance.

    Returns:
        ChatbotService instance

    Note:
        Currently creates a new instance per request.
        Can be modified to use caching or singleton pattern if needed.
    """
    return ChatbotService()


# ===========================
# Endpoints
# ===========================

@router.post("/", response_model=ChatResponse, status_code=status.HTTP_200_OK)
async def chat(
    request: ChatRequest,
    service: Annotated[ChatbotService, Depends(get_chatbot_service)]
):
    """
    Send a chat message and receive a complete response.

    This endpoint returns the full response at once (non-streaming).

    Args:
        request: ChatRequest containing the user's question and optional context
        service: Injected ChatbotService instance

    Returns:
        ChatResponse with the bot's answer and relevant URLs

    Raises:
        HTTPException: 500 if chat processing fails

    Example Request:
    ```json
    {
        "user_question": "Tell me about Silvio's portfolio",
        "conversation_history": {
            "messages": [
                "User: Hi, I'm interested in learning more",
                "Assistant: Sure! What would you like to know?"
            ]
        }
    }
    ```

    Example Response:
    ```json
    {
        "answer": "You can view Silvio's portfolio at https://silviobaratto.com. He specializes in AI/ML and full-stack development..."
    }
    ```
    """
    try:
        response = await service.chat(request)
        return response
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process chat request: {str(e)}"
        )


@router.post("/stream", status_code=status.HTTP_200_OK)
async def chat_stream(
    request: ChatRequest,
    service: Annotated[ChatbotService, Depends(get_chatbot_service)]
):
    """
    Send a chat message and receive a streaming response.

    This endpoint uses Server-Sent Events (SSE) to stream the response
    token by token as it's generated.

    Args:
        request: ChatRequest containing the user's question and optional context
        service: Injected ChatbotService instance

    Returns:
        StreamingResponse with text/event-stream content type

    Response Format:
        Each chunk is sent as a JSON object with the following structure:
        ```json
        {
            "content": "partial or complete response text",
            "done": false
        }
        ```

        The final chunk includes:
        ```json
        {
            "content": "complete response text",
            "done": true
        }
        ```

    Example Usage (JavaScript):
    ```javascript
    const response = await fetch('/api/v1/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            user_question: "Tell me about stockpy"
        })
    });

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
        const {done, value} = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\\n');

        for (const line of lines) {
            if (line.startsWith('data: ')) {
                const data = JSON.parse(line.slice(6));
                console.log(data.content);

                if (data.done) {
                    console.log('Stream complete');
                }
            }
        }
    }
    ```

    Example Usage (Python):
    ```python
    import httpx

    async with httpx.AsyncClient() as client:
        async with client.stream(
            'POST',
            'http://localhost:8000/api/v1/chat/stream',
            json={"user_question": "Tell me about stockpy"}
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith('data: '):
                    data = json.loads(line[6:])
                    print(data['content'])
                    if data['done']:
                        print('Stream complete')
    ```
    """
    async def event_generator():
        """
        Generator that yields Server-Sent Events (SSE) formatted chunks.

        Yields:
            SSE formatted strings: "data: {json}\\n\\n"
        """
        try:
            async for chunk in service.stream_chat(request):
                # Format as SSE (Server-Sent Events)
                chunk_json = chunk.model_dump_json()
                yield f"data: {chunk_json}\n\n"

                # If this is the final chunk, we're done
                if chunk.done:
                    break

        except Exception as e:
            # Send error as SSE
            error_chunk = StreamChunk(
                content=f"Error: {str(e)}",
                done=True
            )
            yield f"data: {error_chunk.model_dump_json()}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable buffering in nginx
        }
    )


@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    """
    Health check endpoint for the chatbot service.

    Returns:
        Simple success message

    Example Response:
    ```json
    {
        "status": "healthy",
        "service": "chatbot"
    }
    ```
    """
    return {
        "status": "healthy",
        "service": "chatbot"
    }

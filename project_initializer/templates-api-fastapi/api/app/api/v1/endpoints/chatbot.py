"""Chatbot routes: a complete reply, or the reply streamed as server-sent events.

Both routes require an authenticated caller, because every call is paid for at
the LLM provider. A provider failure reaches the client as a generic 503. On the
stream route that holds until the first token is ready; a failure after the
stream has started can only travel as a final event that carries an
``error_code``. The cause is logged, never returned.
"""

import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse

from app.api.auth_deps import get_current_user
from app.api.deps import ChatbotServiceDep
from app.api.errors import AUTHENTICATED_ROUTE_ERRORS, error_responses
from app.api.handlers import INTERNAL_ERROR_CODE, resolve_mapping
from app.api.schemas.chatbot import ChatRequest, ChatResponse, StreamChunk
from app.application.dto.chatbot import ChatStreamChunk
from app.domain.exceptions import DomainError

logger = logging.getLogger(__name__)

STREAM_FAILURE_MESSAGE = "The reply could not be completed. Please try again."
STREAM_FAILED_LOG_MESSAGE = "chat.stream_failed"
SSE_MEDIA_TYPE = "text/event-stream"
SSE_HEADERS = {
    "Cache-Control": "no-cache",
    # nginx would otherwise buffer the stream and release it all at once.
    "X-Accel-Buffering": "no",
}

CHAT_ERRORS = {
    **AUTHENTICATED_ROUTE_ERRORS,
    **error_responses(status.HTTP_422_UNPROCESSABLE_CONTENT),
}

router = APIRouter(
    prefix="/chat", tags=["Chatbot"], dependencies=[Depends(get_current_user)]
)


def _server_sent_event(chunk: StreamChunk) -> str:
    return f"data: {chunk.model_dump_json(exclude_none=True)}\n\n"


def _failure_event(error_code: str) -> str:
    return _server_sent_event(
        StreamChunk(content=STREAM_FAILURE_MESSAGE, done=True, error_code=error_code)
    )


def _content_event(chunk: ChatStreamChunk) -> str:
    return _server_sent_event(StreamChunk(content=chunk.content, done=chunk.done))


async def _stream_events(
    first_chunk: ChatStreamChunk | None, remaining: AsyncIterator[ChatStreamChunk]
) -> AsyncIterator[str]:
    try:
        if first_chunk is not None:
            yield _content_event(first_chunk)
        async for chunk in remaining:
            yield _content_event(chunk)
    except DomainError as error:
        # The status line is already sent, so the failure can only travel as a
        # final event. It is an expected kind of failure, so no traceback.
        logger.log(
            resolve_mapping(type(error)).log_level,
            STREAM_FAILED_LOG_MESSAGE,
            extra={"error_code": error.error_code, "context": error.log_context},
        )
        yield _failure_event(error.error_code)
    except Exception:
        # Whatever broke, the client must receive a terminated stream and no
        # internal detail.
        logger.exception(STREAM_FAILED_LOG_MESSAGE)
        yield _failure_event(INTERNAL_ERROR_CODE)


@router.post(
    "/",
    response_model=ChatResponse,
    summary="Ask the chatbot",
    response_description="The complete reply.",
    responses=CHAT_ERRORS,
)
async def chat(request: ChatRequest, service: ChatbotServiceDep) -> ChatResponse:
    """Answer a question in one response.

    ``conversation_history`` carries earlier turns as ``"user: text"`` and
    ``"assistant: text"`` strings, oldest first.
    """
    answer = await service.answer(request.to_query())
    return ChatResponse(answer=answer.answer)


@router.post(
    "/stream",
    response_class=StreamingResponse,
    summary="Ask the chatbot, streaming the reply",
    response_description="Server-sent events: JSON objects with `content` and `done`.",
    responses={
        status.HTTP_200_OK: {"content": {SSE_MEDIA_TYPE: {}}},
        **CHAT_ERRORS,
    },
)
async def chat_stream(
    request: ChatRequest, service: ChatbotServiceDep
) -> StreamingResponse:
    """Answer a question as server-sent events.

    Each event is ``data: {"content": "...", "done": false}``. The last event has
    ``done`` true and holds the complete reply. When the stream breaks after it
    has started, the last event instead holds a generic message and an
    ``error_code``.
    """
    remaining = aiter(service.stream_answer(request.to_query()))
    # Reading the first chunk here, before the response starts, lets a failure
    # that precedes any output (an outage, a refused history) become a proper
    # error response instead of a 200 whose body carries the error.
    first_chunk = await anext(remaining, None)
    return StreamingResponse(
        _stream_events(first_chunk, remaining),
        media_type=SSE_MEDIA_TYPE,
        headers=SSE_HEADERS,
    )

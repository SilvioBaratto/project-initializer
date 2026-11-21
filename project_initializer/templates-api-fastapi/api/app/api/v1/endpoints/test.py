"""Demo routes that exercise the stack without touching the database."""

from typing import Annotated

from fastapi import APIRouter, Path, status

from app.api.errors import error_responses
from app.api.schemas.demo import (
    ECHO_MESSAGE_MAX_LENGTH,
    EchoRequest,
    EchoResponse,
    MessageResponse,
)

VALIDATION_ERRORS = error_responses(status.HTTP_422_UNPROCESSABLE_CONTENT)

router = APIRouter(prefix="/test", tags=["Test"])


@router.get("/ping", response_model=MessageResponse, summary="Ping the API")
async def ping() -> MessageResponse:
    """Confirm the API answers requests."""
    return MessageResponse(message="pong")


@router.get(
    "/echo/{message}",
    response_model=EchoResponse,
    summary="Echo a message",
    responses=VALIDATION_ERRORS,
)
async def echo_get(
    message: Annotated[str, Path(max_length=ECHO_MESSAGE_MAX_LENGTH)],
) -> EchoResponse:
    """Send back the message given in the path."""
    return EchoResponse(echo=message)


@router.post(
    "/echo",
    response_model=EchoResponse,
    summary="Echo a request body",
    responses=VALIDATION_ERRORS,
)
async def echo_post(request: EchoRequest) -> EchoResponse:
    """Send back the message and labels given in the body."""
    return EchoResponse(echo=request.message, metadata=request.metadata)

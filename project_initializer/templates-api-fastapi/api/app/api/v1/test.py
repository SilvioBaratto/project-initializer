"""Test endpoints for API demonstration.

Health/echo demos only. The item CRUD demo that used an in-memory ``_items_store``
has been retired in favour of the DB-backed router at ``app/api/v1/items.py``
(``/api/v1/items``), which persists items across requests.
"""

from fastapi import APIRouter

from app.schemas import (
    utc_now,
    MessageResponse,
    EchoRequest,
    EchoResponse,
)

router = APIRouter(prefix="/test", tags=["Test"])


# ===========================
# Health/Echo Endpoints
# ===========================

@router.get("/ping", response_model=MessageResponse)
async def ping():
    """
    Simple ping endpoint to verify API is responding.

    Returns:
        {"message": "pong"}
    """
    return {"message": "pong"}


@router.get("/echo/{message}", response_model=EchoResponse)
async def echo_get(message: str):
    """
    Echo back the message provided in the path.

    Args:
        message: The message to echo back

    Returns:
        Echo response with the message and timestamp
    """
    return EchoResponse(
        echo=message,
        received_at=utc_now(),
        metadata=None
    )


@router.post("/echo", response_model=EchoResponse)
async def echo_post(request: EchoRequest):
    """
    Echo back the message provided in the request body.

    Args:
        request: EchoRequest containing the message

    Returns:
        Echo response with the message and timestamp
    """
    return EchoResponse(
        echo=request.message,
        received_at=utc_now(),
        metadata=request.metadata
    )

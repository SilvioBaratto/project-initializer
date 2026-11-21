"""Models of the demo routes under ``/test``, which exercise the stack."""

from datetime import UTC, datetime
from typing import Annotated

from pydantic import BaseModel, Field

ECHO_MESSAGE_MAX_LENGTH = 1000
ECHO_METADATA_MAX_ITEMS = 20
ECHO_METADATA_KEY_MAX_LENGTH = 50
ECHO_METADATA_VALUE_MAX_LENGTH = 200

MetadataKey = Annotated[str, Field(max_length=ECHO_METADATA_KEY_MAX_LENGTH)]
MetadataValue = Annotated[str, Field(max_length=ECHO_METADATA_VALUE_MAX_LENGTH)]


class MessageResponse(BaseModel):
    """A plain text message.

    Attributes:
        message: The text.
    """

    message: str = Field(examples=["pong"])


class EchoRequest(BaseModel):
    """Body of ``POST /test/echo``.

    Attributes:
        message: Text to send back.
        metadata: Optional labels to send back; bounded in size and length.
    """

    message: str = Field(
        max_length=ECHO_MESSAGE_MAX_LENGTH,
        description="Message to echo back",
        examples=["hello"],
    )
    metadata: dict[MetadataKey, MetadataValue] | None = Field(
        default=None,
        max_length=ECHO_METADATA_MAX_ITEMS,
        description="Optional labels to echo back",
        examples=[{"source": "docs"}],
    )


class EchoResponse(BaseModel):
    """Body returned by both echo routes.

    Attributes:
        echo: The message that was sent.
        received_at: When the server handled the request, in UTC.
        metadata: The labels that were sent, if any.
    """

    echo: str
    received_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, str] | None = None

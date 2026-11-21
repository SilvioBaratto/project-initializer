"""Helper that lets a middleware add headers to the response it wraps."""

from collections.abc import Mapping

from starlette.datastructures import MutableHeaders
from starlette.types import Message, Send


def with_response_headers(send: Send, headers: Mapping[str, str]) -> Send:
    """Wrap ``send`` so the response start carries extra headers.

    Args:
        send: The ASGI send callable of the next outer layer.
        headers: Headers to set on the response. A header the application already
            set is replaced, not duplicated.

    Returns:
        A send callable to hand to the inner application.
    """

    async def send_with_headers(message: Message) -> None:
        """Add the headers to a response start message and forward it."""
        if message["type"] == "http.response.start":
            message.setdefault("headers", [])
            MutableHeaders(scope=message).update(headers)
        await send(message)

    return send_with_headers

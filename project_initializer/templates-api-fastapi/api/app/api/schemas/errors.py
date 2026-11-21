"""Error envelope returned for every non-2xx response the application produces.

One shape serves the exception handlers, the rate limiter and the ``responses=``
metadata of the routes, so the OpenAPI document describes what clients really get.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class FieldError(BaseModel):
    """One rejected input field of a failed request validation.

    Attributes:
        field: Dotted path of the field, for example ``name`` or ``items.0.price``.
        message: What is wrong with it. Never contains the submitted value.
    """

    field: str = Field(description="Dotted path of the rejected field")
    message: str = Field(description="Why the field was rejected")


class ErrorBody(BaseModel):
    """Details of one error.

    Attributes:
        code: Stable machine-readable error code.
        message: Human-readable text that is safe to show to an end user.
        timestamp: When the error response was produced, in UTC.
        request_id: Correlation id that also appears in the server logs.
        details: Per-field problems; present only for validation failures.
    """

    code: str = Field(description="Stable machine-readable error code")
    message: str = Field(description="Message that is safe to show to an end user")
    timestamp: datetime = Field(description="When the error response was produced")
    request_id: str | None = Field(
        default=None, description="Correlation id to quote when reporting a problem"
    )
    details: list[FieldError] | None = Field(
        default=None, description="Per-field problems of a validation failure"
    )


class ErrorEnvelope(BaseModel):
    """Body of every error response.

    Attributes:
        error: The error itself.
    """

    error: ErrorBody

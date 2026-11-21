"""Field types shared by the request models."""

from typing import Annotated

from pydantic import AfterValidator

NUL_CHARACTER = "\x00"


def reject_nul(value: str) -> str:
    """Refuse text that contains a NUL character.

    PostgreSQL drivers cannot bind a NUL character in a text parameter, so one
    that reaches the repository becomes a server error instead of a validation
    error.

    Args:
        value: Text submitted by a client.

    Returns:
        The same text, unchanged.

    Raises:
        ValueError: The text contains a NUL character. Pydantic turns it into a
            field error that does not repeat the submitted value.
    """
    if NUL_CHARACTER in value:
        raise ValueError("must not contain NUL characters")
    return value


NulFreeStr = Annotated[str, AfterValidator(reject_nul)]
"""Text that may be stored in the database: any string without a NUL character.

Combine it with ``Field`` for length bounds, for example
``name: NulFreeStr = Field(min_length=1, max_length=100)``.
"""

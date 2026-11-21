"""Helpers shared by the request and response schema tests."""

import pytest
from pydantic import ValidationError


def error_fields(error: pytest.ExceptionInfo[ValidationError]) -> set[str]:
    """Name the top-level fields a validation failure rejected.

    Args:
        error: The ``pytest.raises(ValidationError)`` capture to inspect.

    Returns:
        The first path segment of every reported error, so a test can assert
        that exactly the intended field failed and no other.
    """
    return {str(failure["loc"][0]) for failure in error.value.errors()}

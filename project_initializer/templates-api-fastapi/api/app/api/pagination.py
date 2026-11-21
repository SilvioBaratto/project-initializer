"""Offset pagination parameters shared by every list route."""

from typing import Annotated

from fastapi import Depends, Query

from app.domain.constants import DEFAULT_PAGE_SIZE, MAX_OFFSET, MAX_PAGE_SIZE


class PaginationParams:
    """Validated ``skip`` and ``limit`` query parameters.

    FastAPI enforces the bounds before the constructor runs and publishes them in
    the OpenAPI schema, so a request outside them is a 422 and never reaches a
    route.

    Args:
        skip: Number of items to skip, from ``0`` to ``MAX_OFFSET``. Query
            parameter ``skip``.
        limit: Maximum number of items to return, from ``1`` to
            ``MAX_PAGE_SIZE``. Query parameter ``limit``.

    Attributes:
        offset: Number of items to skip.
        limit: Maximum number of items to return.
    """

    def __init__(
        self,
        skip: Annotated[
            int,
            Query(ge=0, le=MAX_OFFSET, description="Number of items to skip"),
        ] = 0,
        limit: Annotated[
            int,
            Query(ge=1, le=MAX_PAGE_SIZE, description="Maximum number of items"),
        ] = DEFAULT_PAGE_SIZE,
    ) -> None:
        self.offset = skip
        self.limit = limit


Pagination = Annotated[PaginationParams, Depends()]

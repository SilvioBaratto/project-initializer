"""DB-backed items router (router -> service -> repository -> model -> DB).

Sync handlers: the service, repository, and ``get_db`` session are all
synchronous, so FastAPI runs these ``def`` handlers in its threadpool. The
service owns the transaction; the router only translates domain results into
HTTP — ``None``/``False`` from the service become ``404``.
"""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, status

from app.api.deps import CurrentUser, Pagination, get_item_service
from app.api.schemas.item import ItemCreate, ItemListResponse, ItemResponse, ItemUpdate
from app.application.services.item_service import ItemService
from app.infrastructure.audit import write_audit_log

# UUID string ids — Path(min_length=1) rejects an empty segment (a numeric
# constraint like ge= would not apply to a str).
ItemId = Annotated[str, Path(min_length=1)]

# Shared 404 OpenAPI doc for the three id-addressed routes (DRY). Spread with
# ``{**...}`` at each call site so every decorator gets its own dict instance.
ITEM_NOT_FOUND_RESPONSE = {404: {"description": "Item not found"}}

router = APIRouter(prefix="/items", tags=["Items"])


@router.get(
    "",
    response_model=ItemListResponse,
    summary="List items",
    response_description="A page of items plus the full row count.",
)
def list_items(
    pagination: Pagination,
    service: ItemService = Depends(get_item_service),
) -> ItemListResponse:
    """List items for the requested page; total is the full row count."""
    items = service.list(skip=pagination.skip, limit=pagination.limit)
    return ItemListResponse(items=items, total=service.count())


@router.post(
    "",
    response_model=ItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an item",
    response_description="The newly created item.",
)
def create_item(
    item_in: ItemCreate,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser,
    service: ItemService = Depends(get_item_service),
) -> ItemResponse:
    """Create a new item (write — requires an authenticated user).

    Schedules a non-blocking audit-log task that runs after the response is
    sent (FastAPI ``BackgroundTasks`` demo) — it never delays the 201.
    """
    item = service.create(item_in)
    background_tasks.add_task(write_audit_log, "item.create", item.id)
    return item


@router.get(
    "/{item_id}",
    response_model=ItemResponse,
    summary="Get an item",
    response_description="The requested item.",
    responses={**ITEM_NOT_FOUND_RESPONSE},
)
def get_item(
    item_id: ItemId, service: ItemService = Depends(get_item_service)
) -> ItemResponse:
    """Get a single item by id, or 404 if it does not exist."""
    item = service.get(item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Item not found")
    return item


@router.put(
    "/{item_id}",
    response_model=ItemResponse,
    summary="Update an item",
    response_description="The updated item.",
    responses={**ITEM_NOT_FOUND_RESPONSE},
)
def update_item(
    item_id: ItemId,
    item_in: ItemUpdate,
    current_user: CurrentUser,
    service: ItemService = Depends(get_item_service),
) -> ItemResponse:
    """Update an existing item (write — requires auth), or 404 if missing."""
    item = service.update(item_id, item_in)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Item not found")
    return item


@router.delete(
    "/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an item",
    response_description="The item was deleted (no content).",
    responses={**ITEM_NOT_FOUND_RESPONSE},
)
def delete_item(
    item_id: ItemId,
    current_user: CurrentUser,
    service: ItemService = Depends(get_item_service),
) -> None:
    """Delete an item (write — requires auth), or 404 if it does not exist."""
    if not service.delete(item_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Item not found")

"""Item routes: a thin HTTP adapter over ``ItemService``.

The handlers are sync ``def`` because the service, the repository and the session
are synchronous, so FastAPI runs them in its worker threadpool. They only convert
between HTTP models and application commands: a missing item is an
``EntityNotFoundError`` raised by the service, which the exception handlers turn
into 404.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Path, status

from app.api.auth_deps import CurrentUser
from app.api.deps import ItemServiceDep
from app.api.errors import AUTHENTICATED_ROUTE_ERRORS, error_responses
from app.api.pagination import Pagination
from app.api.schemas.item import ItemCreate, ItemListResponse, ItemResponse, ItemUpdate
from app.infrastructure.audit import write_audit_log

AUDIT_ITEM_CREATE = "item.create"
AUDIT_ITEM_UPDATE = "item.update"
AUDIT_ITEM_DELETE = "item.delete"

# Item ids are generated UUIDs. Parsing the path as one rejects every other
# value, such as a NUL character or an oversized string, before it can reach the
# database.
ItemId = Annotated[UUID, Path(description="Item identifier")]

READ_ERRORS = error_responses(
    status.HTTP_404_NOT_FOUND,
    status.HTTP_422_UNPROCESSABLE_CONTENT,
    status.HTTP_503_SERVICE_UNAVAILABLE,
)
LIST_ERRORS = error_responses(
    status.HTTP_422_UNPROCESSABLE_CONTENT, status.HTTP_503_SERVICE_UNAVAILABLE
)
CREATE_ERRORS = {
    **AUTHENTICATED_ROUTE_ERRORS,
    **error_responses(status.HTTP_409_CONFLICT, status.HTTP_422_UNPROCESSABLE_CONTENT),
}
UPDATE_ERRORS = {
    **CREATE_ERRORS,
    **error_responses(status.HTTP_404_NOT_FOUND),
}
DELETE_ERRORS = {
    **AUTHENTICATED_ROUTE_ERRORS,
    **error_responses(status.HTTP_404_NOT_FOUND, status.HTTP_422_UNPROCESSABLE_CONTENT),
}

router = APIRouter(prefix="/items", tags=["Items"])


@router.get(
    "",
    response_model=ItemListResponse,
    summary="List items",
    response_description="A page of items plus the full item count.",
    responses=LIST_ERRORS,
)
def list_items(pagination: Pagination, service: ItemServiceDep) -> ItemListResponse:
    """List one page of items, newest first."""
    page = service.list_items(offset=pagination.offset, limit=pagination.limit)
    return ItemListResponse.model_validate(page)


@router.post(
    "",
    response_model=ItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an item",
    response_description="The newly created item.",
    responses=CREATE_ERRORS,
)
def create_item(
    item_in: ItemCreate,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser,
    service: ItemServiceDep,
) -> ItemResponse:
    """Create an item; requires an authenticated caller."""
    item = service.create_item(item_in.to_command())
    # Runs after the response is sent, so a slow audit sink never delays the 201.
    background_tasks.add_task(
        write_audit_log, AUDIT_ITEM_CREATE, item.id, current_user.id
    )
    return ItemResponse.model_validate(item)


@router.get(
    "/{item_id}",
    response_model=ItemResponse,
    summary="Get an item",
    response_description="The requested item.",
    responses=READ_ERRORS,
)
def get_item(item_id: ItemId, service: ItemServiceDep) -> ItemResponse:
    """Get one item by id."""
    return ItemResponse.model_validate(service.get_item(str(item_id)))


@router.put(
    "/{item_id}",
    response_model=ItemResponse,
    summary="Update an item",
    response_description="The updated item.",
    responses=UPDATE_ERRORS,
)
def update_item(
    item_id: ItemId,
    item_in: ItemUpdate,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser,
    service: ItemServiceDep,
) -> ItemResponse:
    """Change the fields the body contains; requires an authenticated caller."""
    item = service.update_item(item_in.to_command(str(item_id)))
    background_tasks.add_task(
        write_audit_log, AUDIT_ITEM_UPDATE, item.id, current_user.id
    )
    return ItemResponse.model_validate(item)


@router.delete(
    "/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an item",
    response_description="The item was deleted.",
    responses=DELETE_ERRORS,
)
def delete_item(
    item_id: ItemId,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser,
    service: ItemServiceDep,
) -> None:
    """Delete an item; requires an authenticated caller."""
    resource_id = str(item_id)
    service.delete_item(resource_id)
    background_tasks.add_task(
        write_audit_log, AUDIT_ITEM_DELETE, resource_id, current_user.id
    )

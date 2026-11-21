"""End-to-end tests of the OpenAPI document the application publishes.

The document is read in-process from the application object, so these tests do
not depend on whether the docs routes are served (see ``test_app_boot.py``).
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.docs import OPENAPI_PATH
from app.domain.constants import (
    ITEM_DESCRIPTION_MAX_LENGTH,
    ITEM_NAME_MAX_LENGTH,
    ITEM_PRICE_MAX,
)
from app.infrastructure.settings import settings
from app.main import TAGS_METADATA

pytestmark = pytest.mark.e2e

DEFAULT_SUCCESS_DESCRIPTION = "Successful Response"
ERROR_ENVELOPE_REF = "/ErrorEnvelope"
AUTHENTICATED_ERROR_STATUSES = {"401", "403", "503"}
HTTP_METHODS = ("get", "put", "post", "delete", "patch")
ITEM_OPERATIONS = [
    pytest.param("get", "/items", "List items", id="list"),
    pytest.param("post", "/items", "Create an item", id="create"),
    pytest.param("get", "/items/{item_id}", "Get an item", id="get"),
    pytest.param("put", "/items/{item_id}", "Update an item", id="update"),
    pytest.param("delete", "/items/{item_id}", "Delete an item", id="delete"),
]
PROTECTED_OPERATIONS = [
    pytest.param("post", "/items", id="items-create"),
    pytest.param("put", "/items/{item_id}", id="items-update"),
    pytest.param("delete", "/items/{item_id}", id="items-delete"),
    pytest.param("get", "/auth/me", id="current-user"),
]
PUBLIC_OPERATIONS = [
    pytest.param("get", "/items", id="items-list"),
    pytest.param("get", "/items/{item_id}", id="items-get"),
    pytest.param("get", "/test/ping", id="ping"),
]


def operations(schema: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    """Every (path, method, operation) triple of the document."""
    return [
        (path, method, operation)
        for path, item in schema["paths"].items()
        for method, operation in item.items()
        if method in HTTP_METHODS
    ]


def error_schema_ref(operation: dict[str, Any], status: str) -> str:
    """The schema reference of an error response, or an empty string."""
    content = operation["responses"][status].get("content", {})
    return content.get("application/json", {}).get("schema", {}).get("$ref", "")


def constraint_of(schema: dict[str, Any], keyword: str) -> Any:
    """Find a validation keyword in a property schema, including nullable branches."""
    if keyword in schema:
        return schema[keyword]
    for branch in schema.get("anyOf", []):
        if keyword in branch:
            return branch[keyword]
    return None


def test_when_the_document_is_read_then_info_carries_the_configured_identity(
    openapi_schema,
):
    """when OpenAPI is generated, info holds identity, summary, contact and license.

    Validates app.main.create_application().
    """
    info = openapi_schema["info"]

    assert (info["title"], info["version"]) == (settings.project_name, settings.version)
    assert info["summary"]
    assert info["contact"]["name"]
    assert info["contact"]["email"]
    assert info["license"]["name"]


def test_when_the_document_is_read_then_every_documented_tag_has_a_description(
    openapi_schema,
):
    """when OpenAPI is generated, each documented tag has a non-empty description.

    Validates app.main.TAGS_METADATA.
    """
    described = {tag["name"]: tag["description"] for tag in openapi_schema["tags"]}

    assert all(described.values())


def test_when_the_document_is_read_then_every_operation_uses_a_documented_tag(
    openapi_schema,
):
    """when OpenAPI is generated, no operation is filed under an undocumented tag.

    Validates app.main.TAGS_METADATA.
    """
    documented = {tag["name"] for tag in openapi_schema["tags"]}

    used = {
        tag
        for _, _, operation in operations(openapi_schema)
        for tag in operation["tags"]
    }

    assert used <= documented


@pytest.mark.parametrize(("method", "suffix", "summary"), ITEM_OPERATIONS)
def test_when_the_document_is_read_then_each_item_route_has_a_curated_summary(
    openapi_schema, api_prefix, method, suffix, summary
):
    """when OpenAPI is generated, item routes carry explicit summaries and descriptions.

    FastAPI derives a summary from the function name, so the curated text proves
    one was written; the success description must not be the framework default.

    Validates app.api.v1.endpoints.items.router.
    """
    operation = openapi_schema["paths"][f"{api_prefix}{suffix}"][method]
    success = next(
        response
        for status, response in operation["responses"].items()
        if status.startswith("2")
    )

    assert operation["summary"] == summary
    assert success["description"] != DEFAULT_SUCCESS_DESCRIPTION


def test_when_the_document_is_read_then_current_user_has_a_curated_summary(
    openapi_schema, api_prefix
):
    """when OpenAPI is generated, /auth/me has an explicit summary and description.

    Validates app.api.v1.endpoints.auth.router.
    """
    operation = openapi_schema["paths"][f"{api_prefix}/auth/me"]["get"]

    assert operation["summary"] == "Get the current user"
    assert operation["responses"]["200"]["description"] != DEFAULT_SUCCESS_DESCRIPTION


def test_when_the_document_is_read_then_every_api_error_uses_the_error_envelope(
    openapi_schema, api_prefix
):
    """when OpenAPI is generated, every 4xx or 5xx of a versioned route is an envelope.

    The document must describe the body clients actually receive.

    Validates app.api.errors.error_responses().
    """
    mismatched = [
        (method, path, status)
        for path, method, operation in operations(openapi_schema)
        if path.startswith(api_prefix)
        for status in operation["responses"]
        if status[0] in "45"
        and not error_schema_ref(operation, status).endswith(ERROR_ENVELOPE_REF)
    ]

    assert mismatched == []


@pytest.mark.parametrize(("method", "suffix"), PROTECTED_OPERATIONS)
def test_when_the_document_is_read_then_protected_routes_declare_auth_errors(
    openapi_schema, api_prefix, method, suffix
):
    """when OpenAPI is generated, routes needing a principal document 401, 403, 503.

    The 403 and 503 come from the auth variants that verify tokens with a scope
    check or an identity provider, which share these routes.

    Validates app.api.errors.AUTHENTICATED_ROUTE_ERRORS.
    """
    operation = openapi_schema["paths"][f"{api_prefix}{suffix}"][method]

    assert set(operation["responses"]) >= AUTHENTICATED_ERROR_STATUSES


@pytest.mark.parametrize(("method", "suffix"), PUBLIC_OPERATIONS)
def test_when_the_document_is_read_then_public_routes_do_not_declare_a_401(
    openapi_schema, api_prefix, method, suffix
):
    """when OpenAPI is generated, public routes do not promise a 401.

    Validates app.api.errors.error_responses().
    """
    operation = openapi_schema["paths"][f"{api_prefix}{suffix}"][method]

    assert "401" not in operation["responses"]


def test_when_the_document_is_read_then_the_item_id_path_parameter_is_a_uuid(
    openapi_schema, api_prefix
):
    """when OpenAPI is generated, the item id is published as a UUID string.

    Validates app.api.v1.endpoints.items.ItemId.
    """
    parameters = openapi_schema["paths"][f"{api_prefix}/items/{{item_id}}"]["get"][
        "parameters"
    ]
    item_id = next(p for p in parameters if p["name"] == "item_id")["schema"]

    assert (item_id["type"], item_id["format"]) == ("string", "uuid")


def test_when_the_document_is_read_then_item_schema_bounds_match_the_domain_limits(
    openapi_schema,
):
    """when OpenAPI is generated, ItemCreate publishes the domain limits.

    Validates app.api.schemas.item.ItemCreate.
    """
    properties = openapi_schema["components"]["schemas"]["ItemCreate"]["properties"]

    assert constraint_of(properties["name"], "minLength") == 1
    assert constraint_of(properties["name"], "maxLength") == ITEM_NAME_MAX_LENGTH
    assert (
        constraint_of(properties["description"], "maxLength")
        == ITEM_DESCRIPTION_MAX_LENGTH
    )
    assert constraint_of(properties["price"], "minimum") == 0
    assert constraint_of(properties["price"], "maximum") == ITEM_PRICE_MAX


def test_when_the_error_envelope_is_published_then_only_three_fields_are_required(
    openapi_schema,
):
    """when OpenAPI is generated, ErrorBody requires code, message and timestamp only.

    The request id and the field details are present only when they apply.

    Validates app.api.schemas.errors.ErrorBody.
    """
    body = openapi_schema["components"]["schemas"]["ErrorBody"]

    assert set(body["required"]) == {"code", "message", "timestamp"}
    assert {"request_id", "details"} <= set(body["properties"])


def test_when_docs_are_served_then_the_openapi_route_returns_the_same_document(
    build_app,
):
    """when the schema route is enabled, it serves the metadata the object reports.

    Validates app.main.create_application().
    """
    application = build_app(environment="test", api_docs_enabled=True)

    served = TestClient(application).get(OPENAPI_PATH).json()

    assert served == application.openapi()
    assert served["info"]["contact"]["name"]
    assert {tag["name"] for tag in served["tags"]} == {
        tag["name"] for tag in TAGS_METADATA
    }


def test_when_the_document_is_read_then_every_versioned_route_documents_the_rate_limit(
    openapi_schema, api_prefix
):
    """when OpenAPI is generated, each route under the API prefix can answer 429.

    The health routes are exempt from the limiter and are not under the prefix.

    Validates app.api.v1.router.api_router.
    """
    missing = [
        (method, path)
        for path, method, operation in operations(openapi_schema)
        if path.startswith(api_prefix) and "429" not in operation["responses"]
    ]

    assert missing == []


def test_when_the_document_is_read_then_delete_does_not_promise_a_conflict(
    openapi_schema, api_prefix
):
    """when OpenAPI is generated, deleting an item documents no 409.

    Deleting never conflicts with existing state, so the document must not claim
    it can.

    Validates app.api.v1.endpoints.items.delete_item().
    """
    operation = openapi_schema["paths"][f"{api_prefix}/items/{{item_id}}"]["delete"]

    assert "409" not in operation["responses"]

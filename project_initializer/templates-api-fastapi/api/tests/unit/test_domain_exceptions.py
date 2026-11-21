"""Unit tests for the domain exception hierarchy."""

import pytest

from app.domain.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    DomainError,
    DomainValidationError,
    EntityNotFoundError,
    ExternalServiceError,
)

ERROR_CONTRACTS = [
    pytest.param(
        DomainValidationError,
        "VALIDATION_ERROR",
        "The request violates a business rule",
        id="validation",
    ),
    pytest.param(
        ConflictError,
        "CONFLICT",
        "The request conflicts with the current state",
        id="conflict",
    ),
    pytest.param(
        AuthenticationError,
        "AUTHENTICATION_ERROR",
        "Invalid or missing credentials",
        id="authentication",
    ),
    pytest.param(
        AuthorizationError,
        "AUTHORIZATION_ERROR",
        "Insufficient permissions",
        id="authorization",
    ),
    pytest.param(
        ExternalServiceError,
        "SERVICE_UNAVAILABLE",
        "A required service is temporarily unavailable",
        id="external-service",
    ),
]
ERROR_TYPES = [
    pytest.param(contract.values[0], id=contract.id) for contract in ERROR_CONTRACTS
]


@pytest.mark.unit
@pytest.mark.parametrize(
    ("error_type", "error_code", "default_message"), ERROR_CONTRACTS
)
def test_when_error_built_without_message_then_default_message_is_public(
    error_type, error_code, default_message
):
    """when no message is given, the class default is the public message.

    Validates app.domain.exceptions.DomainError.__init__().
    """
    error = error_type()

    assert error.error_code == error_code
    assert error.public_message == default_message
    assert str(error) == default_message


@pytest.mark.unit
@pytest.mark.parametrize(
    ("error_type", "error_code", "default_message"), ERROR_CONTRACTS
)
def test_when_error_built_with_message_then_message_replaces_default(
    error_type, error_code, default_message
):
    """when a message is given, it replaces the default but keeps the error code.

    Validates app.domain.exceptions.DomainError.__init__().
    """
    error = error_type("Specific reason")

    assert error.public_message == "Specific reason"
    assert error.error_code == error_code


@pytest.mark.unit
def test_when_message_is_empty_then_default_message_is_used():
    """when the message is an empty string, the default message is used.

    Validates app.domain.exceptions.DomainError.__init__().
    """
    assert ConflictError("").public_message == ConflictError.default_message


@pytest.mark.unit
def test_when_error_has_log_context_then_context_stays_out_of_public_text():
    """when log context is given, it is kept apart from the public message.

    Validates app.domain.exceptions.DomainError.__init__().
    """
    error = DomainValidationError(
        "Item name must not be blank",
        log_context={"field": "name", "internal": "secret-detail"},
    )

    assert error.log_context == {"field": "name", "internal": "secret-detail"}
    assert "secret-detail" not in error.public_message
    assert "secret-detail" not in str(error)
    assert "secret-detail" not in repr(error)


@pytest.mark.unit
def test_when_error_built_without_log_context_then_context_is_empty():
    """when no log context is given, the context is an empty dict.

    Validates app.domain.exceptions.DomainError.__init__().
    """
    assert DomainError().log_context == {}


@pytest.mark.unit
def test_when_source_mapping_changes_then_error_context_is_unaffected():
    """when the caller edits its mapping afterwards, the error keeps its own copy.

    Validates app.domain.exceptions.DomainError.__init__().
    """
    source = {"field": "name"}
    error = DomainValidationError(log_context=source)

    source["field"] = "changed"

    assert error.log_context == {"field": "name"}


@pytest.mark.unit
def test_when_entity_not_found_built_then_message_names_the_entity():
    """when an entity is missing, the public message names it without detail.

    Validates app.domain.exceptions.EntityNotFoundError.__init__().
    """
    error = EntityNotFoundError("Item", log_context={"item_id": "abc"})

    assert error.entity == "Item"
    assert error.error_code == "NOT_FOUND"
    assert error.public_message == "Item not found"
    assert error.log_context == {"item_id": "abc"}
    assert "abc" not in str(error)


@pytest.mark.unit
@pytest.mark.parametrize("error_type", ERROR_TYPES)
def test_when_error_caught_as_domain_error_then_every_subclass_matches(error_type):
    """when any domain error is raised, a handler for DomainError catches it.

    Validates app.domain.exceptions.DomainError.
    """
    with pytest.raises(DomainError):
        raise error_type()


@pytest.mark.unit
def test_when_entity_not_found_raised_then_a_domain_error_handler_catches_it():
    """when an entity is missing, a handler for DomainError catches the error.

    Validates app.domain.exceptions.EntityNotFoundError.
    """
    with pytest.raises(DomainError):
        raise EntityNotFoundError("Item")

"""Domain exception hierarchy.

Every error carries two separate payloads: ``public_message`` is safe to show a
client, ``log_context`` holds diagnostic detail for the logs only. Keeping them
apart means a caller cannot leak internals by formatting the exception. The HTTP
status for each class lives in ``app/api/handlers.py``, not here.
"""

from collections.abc import Mapping
from typing import ClassVar


class DomainError(Exception):
    """Base class for errors the application translates into a client response.

    Attributes:
        error_code: Stable machine-readable code exposed to clients.
        default_message: Public message used when none is given.
        public_message: Text safe to return to the client.
        log_context: Diagnostic fields for structured logs. Never sent to the
            client and never part of ``str(error)``.
    """

    error_code: ClassVar[str] = "DOMAIN_ERROR"
    default_message: ClassVar[str] = "The request could not be completed"

    def __init__(
        self,
        message: str | None = None,
        *,
        log_context: Mapping[str, object] | None = None,
    ) -> None:
        """Build the error.

        Args:
            message: Public message. Falls back to ``default_message`` when None.
            log_context: Diagnostic fields for the logs. Must not hold secrets or
                personal data; it is copied, so later changes to the caller's
                mapping do not affect the error.
        """
        self.public_message = message or self.default_message
        self.log_context: dict[str, object] = dict(log_context or {})
        super().__init__(self.public_message)


class DomainValidationError(DomainError):
    """A business rule rejected the input."""

    error_code: ClassVar[str] = "VALIDATION_ERROR"
    default_message: ClassVar[str] = "The request violates a business rule"


class EntityNotFoundError(DomainError):
    """The requested entity does not exist.

    Attributes:
        entity: Human-readable entity name, for example ``"Item"``.
    """

    error_code: ClassVar[str] = "NOT_FOUND"

    def __init__(
        self,
        entity: str,
        *,
        log_context: Mapping[str, object] | None = None,
    ) -> None:
        """Build the error.

        Args:
            entity: Entity name used in the public message ``"<entity> not found"``.
            log_context: Diagnostic fields for the logs, such as the looked-up id.
        """
        self.entity = entity
        super().__init__(f"{entity} not found", log_context=log_context)


class ConflictError(DomainError):
    """The request conflicts with the current state, such as a unique-key clash."""

    error_code: ClassVar[str] = "CONFLICT"
    default_message: ClassVar[str] = "The request conflicts with the current state"


class AuthenticationError(DomainError):
    """The caller's credentials are missing or invalid.

    Use one generic message for every cause so a response never reveals which
    part of the credentials was wrong.
    """

    error_code: ClassVar[str] = "AUTHENTICATION_ERROR"
    default_message: ClassVar[str] = "Invalid or missing credentials"


class AuthorizationError(DomainError):
    """The caller is authenticated but lacks the permission for the action."""

    error_code: ClassVar[str] = "AUTHORIZATION_ERROR"
    default_message: ClassVar[str] = "Insufficient permissions"


class ExternalServiceError(DomainError):
    """A dependency outside the application, such as the database or an LLM, failed.

    The public message never names the dependency; put its name in ``log_context``.
    """

    error_code: ClassVar[str] = "SERVICE_UNAVAILABLE"
    default_message: ClassVar[str] = "A required service is temporarily unavailable"

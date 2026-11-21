"""Bearer-token verification against Supabase Auth.

Each token is checked by asking Supabase Auth for the user it belongs to, rather
than by verifying its signature locally against the project's published keys.
The remote answer also rejects tokens of signed-out sessions and deleted users,
which a local check would accept until the token expires, at the price of one
HTTP round trip per request. A project that prefers to avoid that round trip can
verify against its JWKS endpoint instead and accept that revocation lags. The
call blocks, so the dependency that uses it is a plain ``def``, which FastAPI
runs in a worker thread.
"""

from enum import StrEnum
from http import HTTPStatus
from typing import Protocol, Self

import httpx
from pydantic import ValidationError
from supabase import (
    AuthApiError,
    AuthRetryableError,
    AuthUnknownError,
    ClientOptions,
    create_client,
)
from supabase_auth.types import User, UserResponse

from app.domain.entities.authenticated_user import AuthenticatedUser
from app.domain.exceptions import AuthenticationError, ExternalServiceError
from app.infrastructure.auth_settings import AuthSettings

SUPABASE_AUTH_METHOD = "supabase"
SERVICE_NAME = "supabase_auth"
# Supabase's anonymous sign-in issues a real session with the role
# ``authenticated``, so the role alone cannot tell such a caller from a person.
ANONYMOUS_ROLE = "anonymous"


class RejectionReason(StrEnum):
    """Why Supabase Auth refused a token; goes to the log, never to the caller."""

    REJECTED_BY_SUPABASE = "rejected_by_supabase"
    NO_USER = "no_user"


class SupabaseAuthApi(Protocol):
    """The slice of the Supabase auth client that token verification needs."""

    def get_user(self, jwt: str) -> UserResponse | None:
        """Look up the user an access token belongs to.

        Args:
            jwt: Raw access token. An empty token makes the real client look for
                a stored session, which this service never keeps.

        Returns:
            The user, or None when Supabase knows no user for the token.

        Raises:
            AuthApiError: Supabase answered with an error status. 401 and 403
                mean the token is refused, and 429 and 5xx mean no verdict.
            AuthRetryableError: A gateway or timeout status that is worth
                retrying.
            AuthUnknownError: The answer could not be read.
            httpx.HTTPError: The request failed in transport.
            pydantic.ValidationError: A 200 answer was not a user document.
        """
        ...


class SupabaseClient(Protocol):
    """A Supabase client, reduced to its auth API so tests can supply a fake."""

    auth: SupabaseAuthApi


def _is_unavailable(status: int) -> bool:
    # Supabase answers these statuses when it could not judge the token at all,
    # so they must not be reported to the caller as an invalid credential.
    return (
        status == HTTPStatus.TOO_MANY_REQUESTS
        or status >= HTTPStatus.INTERNAL_SERVER_ERROR
    )


def _unavailable(error: Exception) -> ExternalServiceError:
    # Only the class name is logged: the message of a transport error can carry
    # the request URL, and nothing here should echo the token.
    return ExternalServiceError(
        log_context={"service": SERVICE_NAME, "error": type(error).__name__}
    )


def _rejected(reason: RejectionReason, **context: object) -> AuthenticationError:
    return AuthenticationError(log_context={"reason": reason, **context})


def _roles_of(user: User) -> tuple[str, ...]:
    if user.is_anonymous:
        return (ANONYMOUS_ROLE,)
    return (user.role,) if user.role else ()


class SupabaseTokenVerifier:
    """``TokenVerifierPort`` backed by Supabase Auth."""

    def __init__(self, client: SupabaseClient) -> None:
        """Wrap a Supabase client.

        Args:
            client: Client whose auth API answers token lookups. It must not
                refresh or persist sessions, because one instance serves every
                request of the process.
        """
        self._client = client

    @classmethod
    def from_settings(cls, auth_settings: AuthSettings) -> Self:
        """Build the verifier for the configured Supabase project.

        The HTTP client carries an explicit timeout, so a slow Supabase cannot
        hold a worker thread indefinitely. It lives as long as the process.

        Args:
            auth_settings: Source of the project URL, key and request timeout.

        Returns:
            A verifier that never refreshes or stores sessions.

        Raises:
            SupabaseException: The URL or the key is empty or not a valid URL.
        """
        options = ClientOptions(
            auto_refresh_token=False,
            persist_session=False,
            httpx_client=httpx.Client(timeout=auth_settings.supabase_auth_timeout),
        )
        client = create_client(
            auth_settings.supabase_url, auth_settings.supabase_publishable_key, options
        )
        return cls(client)

    def verify(self, token: str) -> AuthenticatedUser:
        """Identify the owner of an access token.

        Args:
            token: Raw access token issued by Supabase Auth.

        Returns:
            The principal. ``email`` is None for users without one, such as
            phone-only accounts. ``roles`` holds the user's Supabase role, or
            ``anonymous`` for an anonymous sign-in, so that a guard asking for
            ``authenticated`` does not admit a caller who never identified
            themselves.

        Raises:
            AuthenticationError: Supabase Auth does not accept the token.
            ExternalServiceError: Supabase Auth could not be reached, failed or
                throttled the request, or answered with something that is not a
                user.
        """
        user = self._lookup(token)
        return AuthenticatedUser(
            id=user.id,
            auth_method=SUPABASE_AUTH_METHOD,
            email=user.email or None,
            roles=_roles_of(user),
        )

    def _lookup(self, token: str) -> User:
        try:
            response = self._client.auth.get_user(token)
        except AuthApiError as error:
            if _is_unavailable(error.status):
                raise _unavailable(error) from error
            raise _rejected(
                RejectionReason.REJECTED_BY_SUPABASE,
                status=error.status,
                code=error.code,
            ) from error
        except (
            AuthRetryableError,
            AuthUnknownError,
            httpx.HTTPError,
            ValidationError,
        ) as error:
            # A 200 whose body is not a user fails validation inside the client.
            # Its message quotes the offending document, which can hold an email,
            # so only the class name travels on.
            raise _unavailable(error) from error
        if response is None:
            raise _rejected(RejectionReason.NO_USER)
        return response.user

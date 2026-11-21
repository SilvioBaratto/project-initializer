"""Stand-ins for the Supabase auth client, shared by the Supabase variant's tests."""

from datetime import UTC, datetime

from pydantic import ValidationError
from supabase_auth.types import User, UserResponse

from tests.auth_test_env import AUTH_TEST_ENV

SUPABASE_USER_ID = "7c3a1f0e-5b9d-4e2a-8c61-2d4f9a0b1e33"
SUPABASE_USER_EMAIL = "jane.doe@example.com"
ACCESS_TOKEN = "supabase-access-token"
PROJECT_URL = AUTH_TEST_ENV["SUPABASE_URL"]
PROJECT_API_KEY = AUTH_TEST_ENV["SUPABASE_PUBLISHABLE_KEY"]


def make_user_response(**overrides: object) -> UserResponse:
    """Build the response Supabase Auth returns for a signed-in user.

    Args:
        **overrides: Fields of ``supabase_auth.types.User`` to replace, such as
            ``email=None`` for a phone-only account.

    Returns:
        A response for an authenticated user with an email address.
    """
    fields: dict[str, object] = {
        "id": SUPABASE_USER_ID,
        "app_metadata": {},
        "user_metadata": {},
        "aud": "authenticated",
        "created_at": datetime(2026, 1, 15, tzinfo=UTC),
        "email": SUPABASE_USER_EMAIL,
        "role": "authenticated",
    }
    fields.update(overrides)
    return UserResponse(user=User(**fields))


def make_malformed_user_error() -> ValidationError:
    """Build the error the Supabase client raises when a 200 body is not a user.

    Its message quotes the offending input, which here holds an email address, so
    a test can check that nothing of it reaches a log.

    Returns:
        The validation error of a document that lacks the required user fields.
    """
    try:
        UserResponse.model_validate({"user": {"email": SUPABASE_USER_EMAIL}})
    except ValidationError as error:
        return error
    raise AssertionError("the sample document must not validate as a user")


class FakeSupabaseAuthApi:
    """Answers ``get_user`` with a canned response or raises a canned error."""

    def __init__(
        self,
        *,
        response: UserResponse | None = None,
        error: Exception | None = None,
    ) -> None:
        """Configure the outcome.

        Args:
            response: Returned for every token; None models "no user".
            error: Raised instead of returning the response.
        """
        self._response = response
        self._error = error
        self.tokens: list[str] = []

    def get_user(self, jwt: str) -> UserResponse | None:
        """Record the token, then return the response or raise the error."""
        self.tokens.append(jwt)
        if self._error is not None:
            raise self._error
        return self._response


class FakeSupabaseClient:
    """Supabase client whose only feature is a fake auth API."""

    def __init__(
        self,
        *,
        response: UserResponse | None = None,
        error: Exception | None = None,
    ) -> None:
        """Configure the auth API; see ``FakeSupabaseAuthApi``."""
        self.auth = FakeSupabaseAuthApi(response=response, error=error)

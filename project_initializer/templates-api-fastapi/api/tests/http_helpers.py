"""Request helpers shared by the authentication tests of every variant.

``me_url`` is a fixture: a test module that needs it imports it by name, and
pytest then finds it in that module's namespace.
"""

import pytest

HANDLER_LOGGER = "app.api.handlers"
ME_ROUTE = "/auth/me"


def bearer(token: str) -> dict[str, str]:
    """Build the ``Authorization`` header that carries ``token``."""
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def me_url(api_prefix: str) -> str:
    """URL of the current-user route, under the application's API prefix."""
    return f"{api_prefix}{ME_ROUTE}"

"""Assertions the authentication tests of the token variant share."""

from http import HTTPStatus

from httpx2 import Response

BEARER_CHALLENGE = "Bearer"


def assert_authentication_failure(response: Response) -> None:
    """Assert the 401 envelope with the bearer challenge, whatever the cause."""
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json()["error"]["code"] == "AUTHENTICATION_ERROR"
    assert response.headers["WWW-Authenticate"] == BEARER_CHALLENGE

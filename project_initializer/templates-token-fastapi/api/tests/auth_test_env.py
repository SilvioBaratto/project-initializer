"""Environment the token variant needs to import the app, and the values tests share.

``conftest.py`` applies ``AUTH_TEST_ENV`` before ``app.main`` is imported, so a
developer's ``.env`` cannot change a result. The secrets are test-only values
and meet the length minimums of a production-like stage, which lets tests build
such settings without special cases.
"""

from collections.abc import Mapping

TEST_AUTH_TOKEN = "test-static-token-0123456789"
TEST_JWT_SECRET_KEY = "test-jwt-secret-key-0123456789-abcdef"
TEST_JWT_ALGORITHM = "HS256"
TEST_ACCESS_TOKEN_EXPIRE_MINUTES = 30

AUTH_TEST_ENV: Mapping[str, str] = {
    "AUTH_TOKEN": TEST_AUTH_TOKEN,
    "JWT_SECRET_KEY": TEST_JWT_SECRET_KEY,
    "JWT_ALGORITHM": TEST_JWT_ALGORITHM,
    "ACCESS_TOKEN_EXPIRE_MINUTES": str(TEST_ACCESS_TOKEN_EXPIRE_MINUTES),
}

"""Environment variables the Entra variant needs to import the app.

``conftest.py`` applies these before ``app.main`` is imported. The identifiers
belong to no real tenant: tokens are signed by a key pair the tests generate.
"""

from collections.abc import Mapping

TEST_TENANT_ID = "4b1f2d3c-8a6e-4f70-9c25-6e0d7a1b3f84"
TEST_API_CLIENT_ID = "9d2c7e41-5b3a-4c68-a1f0-3e8b6d5a2c97"

AUTH_TEST_ENV: Mapping[str, str] = {
    "ENTRA_TENANT_ID": TEST_TENANT_ID,
    "ENTRA_API_CLIENT_ID": TEST_API_CLIENT_ID,
    "ENTRA_API_AUDIENCE": f"api://{TEST_API_CLIENT_ID}",
    "ENTRA_API_SCOPE": f"api://{TEST_API_CLIENT_ID}/access_as_user",
}

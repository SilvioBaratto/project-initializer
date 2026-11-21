"""Environment variables the Supabase variant needs to import the app.

``conftest.py`` applies these before ``app.main`` is imported. The values point
at a project that does not exist: no test reaches the network, because every
test that needs a verifier injects a fake one.
"""

from collections.abc import Mapping

AUTH_TEST_ENV: Mapping[str, str] = {
    "SUPABASE_URL": "https://test-project.supabase.co",
    "SUPABASE_PUBLISHABLE_KEY": "sb_publishable_test_key",
}

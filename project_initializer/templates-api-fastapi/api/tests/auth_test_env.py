"""Environment variables the authentication variant needs to import the app.

``conftest.py`` applies these before ``app.main`` is imported. The base variant
has no authentication settings, so the mapping is empty; each authentication
overlay replaces this module with the values its ``AuthSettings`` requires.
"""

from collections.abc import Mapping

AUTH_TEST_ENV: Mapping[str, str] = {}

"""Integration tests: several components working together.

The real application is driven through ``TestClient`` over an in-memory SQLite
database that every test rolls back, and the SQLAlchemy adapters run against
the same engine. Authentication is replaced by the ``authenticated_client`` and
``unauthenticated_client`` fixtures. Mark each test ``integration``.
"""

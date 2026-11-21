"""Layered FastAPI application: domain, application, infrastructure and api layers.

Dependencies point inward only, which ``tests/unit/test_architecture.py`` enforces.
``app.main`` builds the application and ``app.api`` is its HTTP surface.
"""

"""Unit tests: one rule at a time, with no external service and no network.

Domain and application code runs against the in-memory fakes of
``tests/fakes.py``. HTTP-facing units (schemas, handlers, middleware) run on a
small probe application, never on a live server, and a unit may use in-memory
SQLite when the rule under test needs a database. Mark each test ``unit``.
"""

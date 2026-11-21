"""Test suite of the API.

Levels, each selectable with ``-m``:

- ``unit``: no external service and no HTTP server. Domain, application and
  schema rules run against the in-memory fakes in ``tests/fakes.py``; code that
  needs a database or a request may use in-memory SQLite or a probe
  application driven by ``TestClient``.
- ``integration``: the real FastAPI application driven by ``TestClient`` over an
  in-memory SQLite database, plus the SQLAlchemy repositories.
- ``e2e``: smoke tests of application boot and the OpenAPI surface.

The directories mirror these levels, but the marker is what ``-m`` reads.

Shared setup lives in ``tests/conftest.py``. It pins a test environment before
the application is imported, so a developer's ``.env`` cannot change a result,
and it provides database, client and authentication fixtures. The base tests
authenticate through the ``authenticated_client`` and ``unauthenticated_client``
fixtures, which replace ``get_current_user``, so the same tests pass in every
authentication variant. Each variant keeps its credential checks in its own
``tests/integration/test_auth.py`` and its test environment in
``tests/auth_test_env.py``.

Traceability: every test carries a docstring line ``Validates <module.function()>``
naming the code it checks. A test that covers a requirement also carries
``@pytest.mark.requirement("<id>")``; the marker is registered in ``pytest.ini``.

Commands, run from ``api/``::

    pytest                                   # everything, gated on coverage
    pytest -m unit --no-cov                  # one level
    pytest tests/unit/test_handlers.py --no-cov   # one file
    pytest -k rate_limit --no-cov            # by name
    pytest --cov-report=html                 # browsable coverage in htmlcov/

The whole suite fails when line and branch coverage of ``app`` drops below the
``--cov-fail-under`` value in ``pytest.ini``. A subset cannot reach it, so run
subsets with ``--no-cov``.
"""

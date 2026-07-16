# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Run Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run development server (port 8000)
uvicorn app.main:app --reload

# Run with specific host/port
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Run tests
pytest

# Run single test file
pytest path/to/test_file.py

# Database migrations
alembic upgrade head              # Apply migrations
alembic revision --autogenerate -m "description"  # Create migration
alembic downgrade -1              # Rollback one migration

# Regenerate BAML client (after modifying .baml files)
baml-cli generate
```

## Architecture Overview

This is a FastAPI application with BAML-powered AI chatbot functionality.

### Core Structure (clean / hexagonal — four layers)

```
app/
├── main.py                     # App factory: load_configuration → logging → lifespan → CORS → router
├── domain/                     # Pure core — NO framework/ORM imports
│   ├── entities/               # Plain dataclasses (e.g. Item) — no SQLAlchemy/Pydantic
│   ├── ports/                  # Abstract repository interfaces (e.g. ItemRepositoryPort)
│   ├── services/               # Pure domain logic
│   └── exceptions.py           # Domain exception types (framework-free)
├── application/                # Use-case orchestration — depends on domain only
│   ├── services/               # Application services (depend on ports, own the transaction)
│   ├── dto/                    # Use-case DTOs (e.g. chatbot request/response)
│   └── commands/               # Command DTOs
├── infrastructure/             # The ONLY tech layer
│   ├── config.py               # Walk-up .env loader (load_configuration)
│   ├── settings.py             # Settings (pydantic-settings, reads os.environ)
│   ├── database.py             # DatabaseManager: sync SQLAlchemy + psycopg2 pooling
│   ├── orm/                    # SQLAlchemy models (Base in base.py)
│   ├── repositories/           # Port adapters (e.g. ItemRepository) + BaseRepository
│   └── audit.py                # Audit-log helper
└── api/                        # HTTP surface
    ├── deps.py                 # FastAPI deps (auth, pagination, rate limiting)
    ├── handlers.py             # Centralized exception handlers
    ├── schemas/                # Pydantic request/response schemas
    ├── middleware/             # Security, logging, rate limiting
    └── v1/                     # router.py aggregates endpoints/ (all under /api/v1)

baml_src/                       # BAML definitions for LLM functions
baml_client/                    # Auto-generated BAML Python client (don't edit)
```

Dependency direction: `api → application → domain`, `infrastructure → domain`.
`domain` imports nothing outward; `application` never imports `infrastructure`/`api`.
Enforced by `tests/unit/test_architecture.py` (AST fitness test).

### Key Patterns

**Database Access**: Use `get_db` dependency or `database_manager.get_session()` context manager. Sessions use `autoflush=False` and `expire_on_commit=False`.

**Sync vs async**: DB-backed endpoints are sync `def` handlers; BAML/LLM endpoints are `async def`. Pick the keyword from the I/O, not by convention.

- Sync `def` path operations (and `def` dependencies) are offloaded to an `anyio` threadpool, so a blocking sync SQLAlchemy `Session` runs in a worker thread and never blocks the event loop. This is the **default and correct** path for DB routes — see `app/api/v1/endpoints/items.py`.
- `async def` runs directly on the event loop; a blocking call inside it stalls the whole loop. Reserve `async def` for real async I/O — specifically BAML/LLM `await` calls — see `app/application/services/chatbot_service.py`. Never add `async def` for stylistic consistency, and never mix a sync `Session` into an `async def` handler.
- An opt-in async DB path (async engine + `AsyncSession`) exists and is gated behind a generator flag; the sync path above stays the default.

**API Routes**: All v1 routes go through `/api/v1` prefix. Add an endpoint module under `app/api/v1/endpoints/` and register it in `app/api/v1/router.py`.

**BAML Integration**: Define LLM functions in `baml_src/*.baml`, regenerate client with `baml-cli generate`. Access via `from baml_client.async_client import b as baml_async_client`.

**Schema Naming**: `<Entity>Create`, `<Entity>Update`, `<Entity>Response` pattern.

**Models**: Inherit from `Base` (for custom) or `BaseModel` (includes UUID PK + timestamps).

### Environment Configuration

Settings are loaded from `.env` file. Key variables:
- `DATABASE_URL` - PostgreSQL connection string
- `ANTHROPIC_API_KEY` - For Claude models via BAML
- `ENVIRONMENT` - "development", "staging", or "production"
- `DEBUG` - Enable debug mode

### Middleware Stack (execution order)

1. CORS (outermost)
2. Rate limiting (production/staging only)
3. Security headers
4. Request logging (debug mode)

### BAML Clients

Defined in `baml_src/clients.baml`. Currently configured:
- `CustomSonnet45` - Claude Sonnet 4.5 (default for chatbot)
- `CustomOpus45` - Claude Opus 4.5
- `CustomGPT5`, `Gemini`, `Ollama` - Alternative providers

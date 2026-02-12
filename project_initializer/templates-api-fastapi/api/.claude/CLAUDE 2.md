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

### Core Structure

```
app/
├── main.py           # Application factory, middleware setup, lifespan events
├── config.py         # Settings via pydantic-settings (loads from .env)
├── database.py       # DatabaseManager with sync SQLAlchemy + psycopg2 pooling
├── dependencies.py   # FastAPI dependencies (auth, pagination, rate limiting)
├── exceptions.py     # Custom exceptions with centralized handlers
├── api/v1/           # API endpoints (router.py aggregates all routes)
├── models/           # SQLAlchemy models (Base in base.py)
├── schemas/          # Pydantic schemas for validation
├── services/         # Business logic layer
└── middleware/       # Security, logging, rate limiting middleware

baml_src/             # BAML definitions for LLM functions
baml_client/          # Auto-generated BAML Python client (don't edit)
```

### Key Patterns

**Database Access**: Use `get_db` dependency or `database_manager.get_session()` context manager. Sessions use `autoflush=False` and `expire_on_commit=False`.

**API Routes**: All v1 routes go through `/api/v1` prefix. Add new routers in `app/api/v1/router.py`.

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

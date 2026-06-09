# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Full-stack application with **FastAPI** backend, Angular frontend, and Docker orchestration.

## Build & Run Commands

```bash
# Run full stack with Docker
docker compose up -d --build

# Individual services
cd api && uvicorn app.main:app --reload          # Backend on :8000
cd frontend && ng serve                           # Frontend on :4200

# API development
cd api
pip install -r requirements.txt
pytest                                            # Run tests
alembic upgrade head                              # Apply migrations
alembic revision --autogenerate -m "description"  # Create migration
baml-cli generate                                 # Regenerate BAML client
```

## API Template (`api/`)

FastAPI application with layered architecture:

| Layer | Purpose |
|-------|---------|
| `app/api/v1/` | Routes with `/api/v1` prefix |
| `app/services/` | Business logic |
| `app/repositories/` | Data access (BaseRepository with CRUD) |
| `app/models/` | SQLAlchemy models (inherit BaseModel for UUID + timestamps) |
| `app/schemas/` | Pydantic schemas (`<Entity>Create`, `<Entity>Update`, `<Entity>Response`) |
| `app/middleware/` | Security, logging, rate limiting |
| `baml_src/` | LLM function definitions (regenerate client with `baml-cli generate`) |

**Sync vs async**: DB endpoints are sync `def` (offloaded to a threadpool with the sync `Session`); `async def` is reserved for BAML/LLM calls. See `api/.claude/CLAUDE.md` for the full rule.

### Mapping from the FastAPI tutorial

The official FastAPI "Bigger Applications" tutorial organizes path operations into a `routers/` package where each file creates an `APIRouter` and defines route functions — but those route functions also contain inline database queries, business logic, and raw return values. This scaffold maps the tutorial's `routers/` directly to `app/api/v1/`: each router file still owns an `APIRouter` and declares path operations (aggregated in `app/api/v1/router.py`, all under the `/api/v1` prefix), but nothing beyond that. What the tutorial keeps inline inside a route function is here split across four layers: router → `app/services/` (business logic) → `app/repositories/` (data access via the generic `BaseRepository`) → `app/models/` (SQLAlchemy) → `app/schemas/` (Pydantic `<Entity>Create`/`<Entity>Update`/`<Entity>Response`).

This is a **conceptual documentation mapping only — no code is moved or restructured.** See `api/.claude/CLAUDE.md` for the deeper architecture doc.

## Token auth (`--auth token`)

When the `token` overlay is applied, `POST /auth/validate` is a validity **probe**: it returns **HTTP 200 with `authenticated=false`** for an invalid token, because both outcomes are successful *answers* to "is this token valid?". **401 is reserved for guarded endpoints that refuse access** (`/auth/me`, item writes), never for the probe. Consumers must inspect the `authenticated` body flag, not the status code alone — generic middleware that treats any 2xx as "pass" will not catch an invalid token. The supabase variant has **no** `/auth/validate` endpoint; token validity is resolved server-side via JWT / `supabase.auth.getUser()` instead.

## Docker Services

| Service | Port | Description |
|---------|------|-------------|
| `db` | 5433:5432 | PostgreSQL 16 |
| `api` | 8000:8000 | FastAPI with hot reload |
| `frontend` | 4200:80 | Angular + nginx (proxies `/api/` to backend) |
| `adminer` | 8080:8080 | Database admin UI |

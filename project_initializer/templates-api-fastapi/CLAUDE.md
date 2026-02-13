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

## Docker Services

| Service | Port | Description |
|---------|------|-------------|
| `db` | 5433:5432 | PostgreSQL 16 |
| `api` | 8000:8000 | FastAPI with hot reload |
| `frontend` | 4200:80 | Angular + nginx (proxies `/api/` to backend) |
| `adminer` | 8080:8080 | Database admin UI |

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a pip-installable CLI tool (`project-initializer`) that scaffolds full-stack projects with FastAPI, Angular, and Docker. The repository contains both the CLI tool and the template files it copies.

## Build & Run Commands

```bash
# Install CLI tool in development mode
pip install -e .

# Run the CLI
project-initializer my-project      # Create new project
project-initializer . --force       # Scaffold in current directory

# Run full stack with Docker
docker-compose up -d

# Individual services
cd api && uvicorn app.main:app --reload          # Backend on :8000
cd frontend && ng serve                           # Frontend on :4200
```

## Repository Structure

```
project-initializer/
├── project_initializer/           # CLI package (pip installable)
│   ├── cli.py                     # Entry point, argument parsing
│   └── templates/                 # Template files copied to new projects
├── api/                           # FastAPI backend template
│   └── .claude/CLAUDE.md          # Detailed API guidance
├── frontend/                      # Angular frontend template
│   └── .claude/CLAUDE.md          # Detailed frontend guidance
├── docker-compose.yml             # Full stack orchestration
└── pyproject.toml                 # Package config with console_scripts
```

**Note:** For detailed guidance on each template, see:
- `api/.claude/CLAUDE.md` - FastAPI patterns, BAML integration, database access
- `frontend/.claude/CLAUDE.md` - Angular best practices, signals, components

## CLI Package (`project_initializer/`)

Entry point defined in `pyproject.toml`:
```toml
[project.scripts]
project-initializer = "project_initializer.cli:main"
```

The CLI copies everything from `project_initializer/templates/` to the target directory, excluding `.git`, `node_modules`, `__pycache__`, `.env`, and build artifacts.

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

Key commands:
```bash
pytest                                            # Run tests
alembic upgrade head                              # Apply migrations
alembic revision --autogenerate -m "description"  # Create migration
```

## Frontend Template (`frontend/`)

Angular 21 with Tailwind CSS. Key conventions:

- **Standalone components only** (no NgModules, don't set `standalone: true` - it's default)
- **Signals for state**: Use `signal()`, `computed()`, `input()`, `output()`
- **Native control flow**: Use `@if`, `@for`, `@switch` instead of `*ngIf`, `*ngFor`
- **OnPush change detection**: Set `changeDetection: ChangeDetectionStrategy.OnPush`
- **Inject function**: Use `inject()` instead of constructor injection

Key commands:
```bash
ng serve                    # Dev server on :4200
ng build                    # Production build
ng test                     # Unit tests
```

## Docker Services

| Service | Port | Description |
|---------|------|-------------|
| `db` | 5433:5432 | PostgreSQL 16 |
| `api` | 8000:8000 | FastAPI with hot reload |
| `frontend` | 4200:80 | Angular + nginx (proxies `/api/` to backend) |

## Template Sync

After modifying `api/` or `frontend/`, sync to templates:
```bash
rsync -av --exclude='.git' --exclude='node_modules' --exclude='__pycache__' \
  --exclude='.env' --exclude='dist' --exclude='baml_client' --exclude='.angular' \
  . project_initializer/templates/
```

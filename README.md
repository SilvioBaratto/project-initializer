# project-initializer

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/silviobaratto/project-initializer/actions/workflows/test-package.yml/badge.svg)](https://github.com/silviobaratto/project-initializer/actions)

CLI tool to scaffold full-stack projects with **FastAPI** or **NestJS**, **Angular**, and **Docker** — with optional authentication via token or Supabase.

## Installation

```bash
pip install project-initializer
```

Or install from source:

```bash
git clone https://github.com/silviobaratto/project-initializer.git
cd project-initializer
pip install -e .
```

## Quick Start

```bash
project-initializer my-project
cd my-project
# Edit api/.env with your real keys
docker-compose up -d
```

## Framework Selection

Choose a backend framework with `--fastapi` (default) or `--nestjs`:

```bash
project-initializer my-app --fastapi    # FastAPI backend (default)
project-initializer my-app --nestjs     # NestJS backend
```

| Feature | FastAPI | NestJS |
|---------|---------|--------|
| Language | Python 3.12 | TypeScript (Node 20) |
| ORM | SQLAlchemy + Alembic | Prisma |
| AI/LLM | BAML (Python) | BAML (TypeScript) |
| API style | REST with Pydantic | REST with class-validator |
| Architecture | Layered (routes/services/repos) | Modular (controllers/services/modules) |

## Authentication Modes

Add authentication with `--auth token` or `--auth supabase`:

```bash
project-initializer my-app --auth token      # Simple bearer-token auth
project-initializer my-app --auth supabase    # Supabase JWT auth + RLS
```

- **No auth** (default) — No authentication middleware. Good for prototyping.
- **Token auth** (`--auth token`) — Bearer-token middleware on the API. Frontend gets a login guard and an HTTP interceptor that attaches the token.
- **Supabase auth** (`--auth supabase`) — Supabase JWT validation on the API. Frontend integrates `@supabase/supabase-js` for login/signup. Docker Compose omits the local `db` service since Supabase hosts the database.

## All 6 Variants

| Command | Backend | Auth |
|---------|---------|------|
| `project-initializer app` | FastAPI | None |
| `project-initializer app --auth token` | FastAPI | Token |
| `project-initializer app --auth supabase` | FastAPI | Supabase |
| `project-initializer app --nestjs` | NestJS | None |
| `project-initializer app --nestjs --auth token` | NestJS | Token |
| `project-initializer app --nestjs --auth supabase` | NestJS | Supabase |

Additional flags:

```bash
project-initializer my-project --force     # Overwrite existing files
project-initializer .                      # Scaffold in current directory
project-initializer --version              # Show version
```

## Generated Project Structure

```
my-project/
├── api/                    # Backend (FastAPI or NestJS)
│   ├── .env                # Auto-generated from variant
│   ├── Dockerfile
│   └── ...
├── frontend/               # Angular + Tailwind CSS
│   ├── Dockerfile
│   ├── nginx.conf
│   └── src/
├── docker-compose.yml      # Full-stack orchestration
├── .env.example            # Reference for environment variables
└── CLAUDE.md               # AI assistant guidance
```

## Docker Services

| Service | Port | Description | Supabase variants |
|---------|------|-------------|-------------------|
| `db` | 5433:5432 | PostgreSQL 16 | Omitted (Supabase hosts DB) |
| `adminer` | 8080:8080 | DB management UI | Omitted |
| `api` | 8000:8000 | Backend with hot reload | Present |
| `frontend` | 4200:80 | Angular + nginx (proxies `/api/` to backend) | Present |

## Environment Configuration

The CLI auto-generates `api/.env` based on the chosen variant. A root `.env.example` documents all possible variables.

For Supabase variants, configure these in `api/.env`:
```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_PUBLISHABLE_KEY=your-anon-key
```

## Development

### FastAPI

```bash
cd api
pip install -r requirements.txt
uvicorn app.main:app --reload          # API on :8000
alembic upgrade head                   # Run migrations
pytest                                 # Run tests
```

### NestJS

```bash
cd api
npm install
npm run start:dev                      # API on :8000
npx prisma migrate dev                 # Run migrations
npm run test                           # Run tests
```

### Frontend (Angular)

```bash
cd frontend
npm install
ng serve                               # Dev server on :4200
ng build                               # Production build
ng test                                # Unit tests
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, template architecture, and PR guidelines.

## License

MIT

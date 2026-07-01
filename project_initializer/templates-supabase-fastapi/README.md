# Project

Full-stack application with **FastAPI**, **Angular**, and **Supabase**.

No local database required - uses hosted Supabase for database and authentication.

## Getting Started

```bash
# Edit api/.env with your Supabase credentials:
#   DATABASE_URL, DIRECT_DATABASE_URL, SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY
docker compose up -d --build
```

Services will be available at:
- Frontend: http://localhost:4200
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## Development

### Backend (FastAPI)

```bash
cd api
pip install -r requirements.txt
uvicorn app.main:app --reload          # Runs on :8000

# Database
alembic upgrade head                   # Apply migrations
alembic revision --autogenerate -m "description"

# Tests
pytest

# BAML (AI/LLM)
baml-cli generate
```

### Frontend (Angular)

```bash
cd frontend
npm install --legacy-peer-deps         # See note below
ng serve                               # Runs on :4200
ng test
```

> **Why `--legacy-peer-deps`?** `@angular/build` declares an optional peer dependency on
> `vitest@^4`, but the project pins `vitest@^3`. npm 7+ treats this mismatch as a hard
> `ERESOLVE` error and aborts `npm install`. `--legacy-peer-deps` skips npm's peer-dependency
> check and installs anyway. Safe here: `vitest` is a test-only devDependency and Angular's build
> only optionally peers it, so app build/serve are unaffected.

## Docker Services

| Service | Port | Description |
|---------|------|-------------|
| `api` | 8000:8000 | FastAPI with hot reload |
| `frontend` | 4200:80 | Angular + nginx |

## License

MIT

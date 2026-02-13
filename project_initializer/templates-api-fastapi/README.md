# Project

Full-stack application with **FastAPI**, **Angular**, and **Docker**.

## Getting Started

```bash
# Edit api/.env with your real keys
docker compose up -d --build
```

Services will be available at:
- Frontend: http://localhost:4200
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Adminer: http://localhost:8080

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
npm install
ng serve                               # Runs on :4200
ng test
```

## Docker Services

| Service | Port | Description |
|---------|------|-------------|
| `db` | 5433:5432 | PostgreSQL 16 |
| `api` | 8000:8000 | FastAPI with hot reload |
| `frontend` | 4200:80 | Angular + nginx |
| `adminer` | 8080:8080 | Database admin UI |

## License

MIT

# Project

Full-stack application with **NestJS**, **Angular**, and **Docker**.

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

### Backend (NestJS)

```bash
cd api
npm install
npm run start:dev                      # Runs on :8000

# Database (Prisma)
npx prisma migrate dev                 # Create + apply migration
npx prisma migrate deploy              # Apply migrations (production)
npx prisma generate                    # Regenerate Prisma client
npx prisma studio                      # Visual DB editor

# Tests
npm test

# BAML (AI/LLM)
npx baml-cli generate
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
| `api` | 8000:8000 | NestJS with hot reload |
| `frontend` | 4200:80 | Angular + nginx |
| `adminer` | 8080:8080 | Database admin UI |

## License

MIT

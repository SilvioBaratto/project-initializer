# Project

Full-stack application with **NestJS**, **Angular**, and **Microsoft Entra ID** authentication.

Local Docker PostgreSQL database — no hosted auth backend required at runtime.

## Prerequisites

Two Entra app registrations in your tenant:

1. **API registration** — expose a scope (`access_as_user`), set `requestedAccessTokenVersion: 2` in the manifest.
   > **Important:** the default manifest value (`null`) issues v1 tokens with an `sts.windows.net` issuer; this backend validates the v2 issuer and every request will fail with 401 unless you set `requestedAccessTokenVersion: 2`.
2. **SPA registration** — single-page application (public client), add `http://localhost:4200` as a redirect URI.

Map the IDs to your `api/.env`:

| Registration | Value | Env var |
|---|---|---|
| Tenant | Directory (tenant) ID | `ENTRA_TENANT_ID` |
| API app | Application (client) ID | `ENTRA_API_CLIENT_ID` |
| API app | App ID URI or GUID | `ENTRA_API_AUDIENCE` |
| API app | Scope URI | `ENTRA_API_SCOPE` |
| SPA app | Application (client) ID | `ENTRA_SPA_CLIENT_ID` |

No client secret is needed — the backend validates tokens via RS256 signature only.

## Getting Started

```bash
# Edit api/.env with your Entra credentials
cp api/.env.example api/.env
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

# Tests
npm test

# BAML (AI/LLM)
npx baml-cli generate
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
| `db` | 5433:5432 | PostgreSQL 16 |
| `redis` | internal | Redis (BullMQ) |
| `api` | 8000:8000 | NestJS with hot reload |
| `frontend` | 4200:80 | Angular + nginx |
| `adminer` | 8080:8080 | Database admin UI |

## License

MIT

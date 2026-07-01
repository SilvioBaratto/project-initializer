# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.5] - 2026-07-01

### Added
- **`--auth entra`** — Microsoft Entra ID (formerly Azure AD) OIDC auth mode, bringing the scaffolder to **8 variants** (2 frameworks × 4 auth modes):
  - FastAPI & NestJS: in-process RS256 JWT validation with JWKS auto-refresh and tenant/audience/scope checks; no client secret stored on the API.
  - Angular frontend: MSAL login, auth guard, and HTTP interceptor.
  - New `templates-entra-fastapi/`, `templates-entra-nestjs/`, and `templates-entra-frontend/` overlays, plus entra legs in the CI matrix.

### Fixed
- **BAML**: bumped the template generator to `0.223.0` to match the pinned `baml-py` / `@boundaryml/baml` package (BAML enforces a major/minor match), unblocking every backend CI job.
- **entra Docker**: override the host-facing `DATABASE_URL` / `DIRECT_URL` (`localhost:5433`) with the compose-network address (`db:5432`) so the API container can reach Postgres.
- **entra FastAPI**: added the missing `email-validator` dependency required by the base `EmailStr` user schemas.
- **entra NestJS**: fixed the `jwks-rsa` import (`import { JwksClient }` + `new`) that failed to compile under the template's tsconfig.

### CI
- Pinned `baml-py==0.223.0` in the FastAPI test-package legs (NestJS already pins via `package.json`) to prevent future version drift.

## [0.3.4] - 2026-06-18

### Fixed
- Repaired the frontend component catalog and rebuilt the chat input as a Gemini-style pill.

## [0.3.3] - 2026-06-18

### Added
- Angular UI component library with full test coverage.

## [0.3.2] - 2026-06-16

### Added
- Scope-aware layer selection and file transforms (`--scope api` / `--scope frontend`).
- `--async-db` opt-in async SQLAlchemy path for FastAPI, documented in the README.
- FastAPI template alignment with the official tutorial; hardened NestJS Prisma TLS with build-verification tests.
- Responsive frontend shell with theme toggle.
- GitHub Actions workflows for a green-gate CI.

### Fixed
- Forced LF on entrypoint scripts to stop CRLF `ENTRYPOINT` failures.
- NestJS user response schema whitelist and several CI pipeline repairs (BAML version, ruff path, frontend install resilience).

## [0.2.0] - 2026-02-13

### Added
- Early full-stack scaffolding across FastAPI and NestJS with token and Supabase auth overlays.

## [0.1.1] - 2026-01-25

### Added
- Initial public release of the `project-initializer` CLI.

[Unreleased]: https://github.com/SilvioBaratto/project-initializer/compare/v0.3.5...HEAD
[0.3.5]: https://github.com/SilvioBaratto/project-initializer/compare/v0.3.4...v0.3.5
[0.3.4]: https://github.com/SilvioBaratto/project-initializer/compare/v0.3.3...v0.3.4
[0.3.3]: https://github.com/SilvioBaratto/project-initializer/compare/v0.3.2...v0.3.3
[0.3.2]: https://github.com/SilvioBaratto/project-initializer/compare/v0.2.0...v0.3.2
[0.2.0]: https://github.com/SilvioBaratto/project-initializer/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/SilvioBaratto/project-initializer/releases/tag/v0.1.1

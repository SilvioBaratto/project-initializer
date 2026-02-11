# project-initializer

CLI tool to scaffold full-stack projects with FastAPI, Angular, and Docker.

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

## Usage

Create a new project in a directory:

```bash
project-initializer my-project
```

Create a project in the current directory:

```bash
project-initializer .
```

Force overwrite existing files:

```bash
project-initializer my-project --force
```

Show version:

```bash
project-initializer --version
```

## What's Included

The generated project includes:

- **api/** - FastAPI backend with:
  - SQLAlchemy models and Alembic migrations
  - BAML for AI/LLM integrations
  - JWT authentication ready
  - Docker configuration

- **frontend/** - Angular 19 frontend with:
  - Tailwind CSS configured
  - Environment configurations
  - Docker/nginx setup

- **docker-compose.yml** - Full stack orchestration with:
  - PostgreSQL database
  - FastAPI backend
  - Angular frontend with nginx
  - Adminer database management UI

## Getting Started

After creating a project:

```bash
cd my-project
docker-compose up -d
```

The services will be available at:
- Frontend: http://localhost:4200
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Adminer: http://localhost:8080

## License

MIT

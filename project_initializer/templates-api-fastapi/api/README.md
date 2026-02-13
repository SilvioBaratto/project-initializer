# FastAPI Backend

## Quick Start

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload    # http://localhost:8000
```

## Key Commands

```bash
pytest                                            # Run tests
alembic upgrade head                              # Apply migrations
alembic revision --autogenerate -m "description"  # Create migration
baml-cli generate                                 # Regenerate BAML client
```

## Architecture

```
app/
├── main.py           # Application factory, middleware, lifespan
├── config.py         # Settings via pydantic-settings
├── database.py       # SQLAlchemy + psycopg2 pooling
├── dependencies.py   # FastAPI dependencies
├── exceptions.py     # Custom exception handlers
├── api/v1/           # API endpoints
├── models/           # SQLAlchemy models
├── schemas/          # Pydantic schemas
├── services/         # Business logic
├── repositories/     # Data access
└── middleware/        # Security, logging, rate limiting

baml_src/             # BAML LLM function definitions
baml_client/          # Auto-generated BAML client (don't edit)
```

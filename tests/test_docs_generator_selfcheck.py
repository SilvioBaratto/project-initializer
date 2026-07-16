"""Self-enforcement guards for the generated docs (anti-drift).

The docs a scaffolded project ships are built by ``docs_generator`` per flag.
These tests assert two invariants across the full flag matrix:

1. **No stale paths** — a generated doc must never reference the pre-hexagonal
   FastAPI layout (``app/services/``, ``app/models/``, ``app/repositories/``,
   ``app/dependencies.py`` …), the old ``api/.env`` location, or the old
   "3 auth modes" / "6 variants" wording. This is the guard that would have
   caught the drift the static docs accumulated.
2. **Required content present** — the doc set for each variant contains the
   sections/strings that make it useful (stack line, docker services, backend
   dev commands, license), so a future edit cannot silently gut a document.

Framework-fixed reference blocks (the NestJS readiness checklist, the Angular
guidance) are covered by their own dedicated tests; here we sweep the whole
matrix for drift rather than re-assert every string.
"""

import pytest

from project_initializer.docs_generator import (
    generate_api_claude,
    generate_api_readme,
    generate_root_claude,
    generate_root_readme,
)

FRAMEWORKS = ["fastapi", "nestjs"]
AUTHS = [None, "token", "supabase", "entra"]

# Substrings that must NEVER appear in any generated doc — each is a concrete
# regression that already happened once (pre-hexagonal layout) or would mislead.
_BANNED = [
    "app/services/",
    "app/models/",
    "app/repositories/",
    "app/schemas/",
    "app/middleware/",
    "app/dependencies.py",
    "app/database.py",
    "app/config.py",
    "api/.env",          # docs must point at the root .env now
    "3 auth modes",
    "three auth modes",
    "6 variants",
    "six variants",
    "layered architecture",  # FastAPI is hexagonal now
]


def _all_docs(framework, auth):
    """Every generated doc string for a fullstack variant of (framework, auth)."""
    return {
        "root README": generate_root_readme(framework, auth),
        "root CLAUDE": generate_root_claude(framework, auth),
        "api README": generate_api_readme(framework),
        "api CLAUDE": generate_api_claude(framework, auth),
    }


@pytest.mark.parametrize("framework", FRAMEWORKS)
@pytest.mark.parametrize("auth", AUTHS)
def test_when_docs_generated_then_no_banned_stale_strings_appear(framework, auth):
    """No generated doc may contain a stale-layout / old-wording substring."""
    for name, doc in _all_docs(framework, auth).items():
        for banned in _BANNED:
            assert banned not in doc, (
                f"[{framework}/{auth}] {name} contains banned stale string "
                f"{banned!r} — docs drifted from the current layout"
            )


@pytest.mark.parametrize("framework", FRAMEWORKS)
@pytest.mark.parametrize("auth", AUTHS)
def test_when_root_readme_generated_then_core_sections_present(framework, auth):
    """The root README always documents the stack, startup, services, and license."""
    doc = generate_root_readme(framework, auth)
    assert doc.startswith("# Project")
    assert "docker compose up -d --build" in doc
    assert "## Docker Services" in doc
    assert "## License" in doc
    # framework name is stated
    label = "FastAPI" if framework == "fastapi" else "NestJS"
    assert label in doc


@pytest.mark.parametrize("framework", FRAMEWORKS)
def test_when_api_claude_generated_then_it_names_the_right_orm_layer(framework):
    """FastAPI api CLAUDE speaks hexagonal + SQLAlchemy; NestJS speaks Prisma."""
    doc = generate_api_claude(framework, None)
    if framework == "fastapi":
        assert "domain/" in doc and "infrastructure/" in doc
        assert "SQLAlchemy" in doc
        assert "Prisma" not in doc
    else:
        assert "Prisma" in doc
        assert "SQLAlchemy" not in doc


def test_when_supabase_then_docker_table_omits_local_db():
    """Supabase variants have no local db/adminer service in the generated README."""
    for framework in FRAMEWORKS:
        doc = generate_root_readme(framework, "supabase")
        assert "PostgreSQL 16" not in doc
        assert "adminer" not in doc.lower()


def test_when_non_supabase_then_docker_table_has_local_db():
    """Non-supabase variants keep the local db + adminer rows."""
    for framework in FRAMEWORKS:
        for auth in (None, "token", "entra"):
            doc = generate_root_readme(framework, auth)
            assert "PostgreSQL 16" in doc
            assert "adminer" in doc.lower()


def test_when_frontend_scope_then_root_docs_have_no_backend_commands():
    """A frontend-only scaffold's root docs must not tell you to run the backend."""
    readme = generate_root_readme("fastapi", None, api=False, frontend=True)
    claude = generate_root_claude("fastapi", None, api=False, frontend=True)
    for doc in (readme, claude):
        assert "uvicorn" not in doc
        assert "npm run start:dev" not in doc

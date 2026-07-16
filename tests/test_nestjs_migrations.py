"""Guard: every scaffolded NestJS variant ships a migration matching its schema.

The NestJS entrypoint runs `prisma migrate deploy`, which is a no-op when
`prisma/migrations/` holds no migration — it logs "No migration found in
prisma/migrations" and exits 0. The stack then comes up with an empty database:
`/health/readiness` reports `database: down` and any query 500s. The template
shipped only a `.gitkeep`, so that was the out-of-the-box state.

The tables each variant needs differ, and the overlay system is what resolves it:
the supabase overlay maps its model to `profiles` instead of `users`, and its
migration reuses the base migration's *directory name* so it overwrites rather
than stacks. If it did not, a supabase scaffold would apply both migrations and
create a stray `users` table — hence the exact-table assertions below.
"""

import re

import pytest

from project_initializer.cli import copy_template

# The table each NestJS variant's schema maps its model to.
_EXPECTED_TABLES = {
    None: "users",
    "token": "users",
    "supabase": "profiles",
    "entra": "users",
}


def _created_tables(migrations_dir) -> list[str]:
    """Return every table name the variant's migration SQL creates."""
    tables: list[str] = []
    for sql_file in sorted(migrations_dir.rglob("migration.sql")):
        for match in re.finditer(
            r'CREATE TABLE "([^"]+)"', sql_file.read_text(encoding="utf-8")
        ):
            tables.append(match.group(1))
    return tables


@pytest.mark.integration
@pytest.mark.parametrize("auth", list(_EXPECTED_TABLES))
def test_scaffolded_nestjs_ships_a_migration(tmp_path, auth):
    """`prisma migrate deploy` must have something to apply, or the DB stays empty."""
    copy_template(tmp_path, "app", auth=auth, framework="nestjs", scope="api")
    migrations = tmp_path / "api" / "prisma" / "migrations"

    migration_dirs = [p for p in migrations.iterdir() if p.is_dir()]
    assert migration_dirs, (
        f"nestjs+{auth or 'none'}: prisma/migrations/ has no migration — "
        "`prisma migrate deploy` would create no tables and readiness reports "
        "'database: down'"
    )
    assert (migrations / "migration_lock.toml").exists(), (
        f"nestjs+{auth or 'none'}: migration_lock.toml is missing; prisma needs it "
        "to know the migration provider"
    )
    for migration_dir in migration_dirs:
        assert (migration_dir / "migration.sql").exists(), (
            f"nestjs+{auth or 'none'}: {migration_dir.name} has no migration.sql"
        )


@pytest.mark.integration
@pytest.mark.parametrize("auth,expected", _EXPECTED_TABLES.items())
def test_scaffolded_nestjs_migration_matches_its_schema(tmp_path, auth, expected):
    """The migration must create exactly the table the variant's schema maps to.

    Supabase maps to `profiles`; the others to `users`. Asserting the exact set
    also catches the overlay stacking failure — a supabase scaffold that kept the
    base migration alongside its own would create `users` here too.
    """
    copy_template(tmp_path, "app", auth=auth, framework="nestjs", scope="api")

    tables = _created_tables(tmp_path / "api" / "prisma" / "migrations")
    assert tables == [expected], (
        f"nestjs+{auth or 'none'}: migrations create {tables}, expected exactly "
        f"['{expected}'] — the schema maps its model to '{expected}'"
    )


@pytest.mark.integration
@pytest.mark.parametrize("auth", list(_EXPECTED_TABLES))
def test_scaffolded_nestjs_migration_covers_every_schema_model(tmp_path, auth):
    """Every model's @@map target must have a CREATE TABLE in the migrations."""
    copy_template(tmp_path, "app", auth=auth, framework="nestjs", scope="api")

    schema = (tmp_path / "api" / "prisma" / "schema.prisma").read_text("utf-8")
    mapped = set(re.findall(r'@@map\("([^"]+)"\)', schema))
    created = set(_created_tables(tmp_path / "api" / "prisma" / "migrations"))

    assert mapped - created == set(), (
        f"nestjs+{auth or 'none'}: schema maps models to {sorted(mapped - created)} "
        "but no migration creates them — regenerate with `prisma migrate dev`"
    )

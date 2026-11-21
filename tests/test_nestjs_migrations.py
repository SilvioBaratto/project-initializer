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

Each migration also ships a `down.sql` (the code standard asks for a rollback script per
migration). It overwrites by path just like `migration.sql`, so the supabase `init/down.sql`
must replace the base one: left behind, it would drop `users`, which a supabase database does
not have, instead of `profiles`. Supabase tables also get Row Level Security, because the
Data API is reachable with the publishable key, and that includes Prisma's own
``_prisma_migrations`` bookkeeping table, which sits in ``public`` too.

A down script never leaves a copy of the rows it drops in ``public``: the backup goes to
the ``migration_backup`` schema, which the Data API does not serve, under a name with a
microsecond timestamp so repeated rollbacks cannot collide.
"""

import re

import pytest

from project_initializer.cli import copy_template

# The tables each NestJS variant's migrations create, in migration order: the variant's own
# model first, then the shared `items` sample.
_EXPECTED_TABLES = {
    None: ["users", "items"],
    "token": ["users", "items"],
    "supabase": ["profiles", "items"],
    "entra": ["users", "items"],
}

_INIT_MIGRATION = "20260716000000_init"
_PRISMA_BOOKKEEPING_TABLE = "_prisma_migrations"
_BACKUP_SCHEMA = "migration_backup"
_MICROSECOND_TIMESTAMP_FORMAT = "'YYYYMMDDHH24MISSUS'"


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
    """`prisma migrate deploy` must have something to apply, or the DB stays empty.

    Validates project_initializer/templates-{api,supabase}-nestjs/api/prisma/migrations.
    """
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
    """The migrations must create exactly the tables the variant's schema maps to.

    Supabase maps its model to `profiles`; the others to `users`; all add `items`.
    Asserting the exact list also catches the overlay stacking failure — a supabase
    scaffold that kept the base init migration alongside its own would create `users` too.

    Validates project_initializer/templates-{api,supabase}-nestjs/api/prisma/migrations against the Prisma schema of each variant.
    """
    copy_template(tmp_path, "app", auth=auth, framework="nestjs", scope="api")

    tables = _created_tables(tmp_path / "api" / "prisma" / "migrations")
    assert tables == expected, (
        f"nestjs+{auth or 'none'}: migrations create {tables}, expected exactly "
        f"{expected} — the schema maps its models to those tables"
    )


@pytest.mark.integration
@pytest.mark.parametrize("auth", list(_EXPECTED_TABLES))
def test_scaffolded_nestjs_migration_covers_every_schema_model(tmp_path, auth):
    """Every model's @@map target must have a CREATE TABLE in the migrations.

    Validates project_initializer/templates-{api,supabase}-nestjs/api/prisma/migrations against the Prisma schema of each variant.
    """
    copy_template(tmp_path, "app", auth=auth, framework="nestjs", scope="api")

    schema = (tmp_path / "api" / "prisma" / "schema.prisma").read_text("utf-8")
    mapped = set(re.findall(r'@@map\("([^"]+)"\)', schema))
    created = set(_created_tables(tmp_path / "api" / "prisma" / "migrations"))

    assert mapped - created == set(), (
        f"nestjs+{auth or 'none'}: schema maps models to {sorted(mapped - created)} "
        "but no migration creates them — regenerate with `prisma migrate dev`"
    )


def _rls_tables(sql: str, verb: str) -> set[str]:
    """Return the tables a migration script switches row level security ``verb`` on."""
    return set(re.findall(rf'ALTER TABLE "([^"]+)" {verb} ROW LEVEL SECURITY', sql))


def _migration_dirs(tmp_path):
    migrations = tmp_path / "api" / "prisma" / "migrations"
    return sorted(p for p in migrations.iterdir() if p.is_dir())


@pytest.mark.integration
@pytest.mark.parametrize("auth", list(_EXPECTED_TABLES))
def test_scaffolded_nestjs_every_migration_has_a_down_script(tmp_path, auth):
    """A migration without `down.sql` cannot be rolled back (reversibility is required).

    Validates project_initializer/templates-{api,supabase}-nestjs/api/prisma/migrations.
    """
    copy_template(tmp_path, "app", auth=auth, framework="nestjs", scope="api")

    for migration_dir in _migration_dirs(tmp_path):
        assert (migration_dir / "down.sql").is_file(), (
            f"nestjs+{auth or 'none'}: {migration_dir.name} has no down.sql"
        )


@pytest.mark.integration
@pytest.mark.parametrize("auth", list(_EXPECTED_TABLES))
def test_scaffolded_nestjs_down_script_unrecords_its_own_migration(tmp_path, auth):
    """`migrate resolve --rolled-back` rejects an applied migration, so each down.sql removes
    its own row from `_prisma_migrations`; without that `migrate deploy` would skip it.

    Validates project_initializer/templates-{api,supabase}-nestjs/api/prisma/migrations.
    """
    copy_template(tmp_path, "app", auth=auth, framework="nestjs", scope="api")

    for migration_dir in _migration_dirs(tmp_path):
        down = (migration_dir / "down.sql").read_text(encoding="utf-8")
        assert re.search(
            rf"DELETE FROM \"_prisma_migrations\"[^;]*'{re.escape(migration_dir.name)}'",
            down,
        ), (
            f"nestjs+{auth or 'none'}: {migration_dir.name}/down.sql does not un-record "
            "its own migration from _prisma_migrations"
        )


@pytest.mark.integration
@pytest.mark.parametrize("auth", list(_EXPECTED_TABLES))
def test_scaffolded_nestjs_down_script_unrecords_as_its_last_statement(tmp_path, auth):
    """The un-record is the final statement: the data is already safe when it runs.

    Un-recording first would leave a database that `migrate deploy` re-applies while
    the rollback is half done.

    Validates project_initializer/templates-{api,supabase}-nestjs/api/prisma/migrations.
    """
    copy_template(tmp_path, "app", auth=auth, framework="nestjs", scope="api")

    for migration_dir in _migration_dirs(tmp_path):
        down = (migration_dir / "down.sql").read_text(encoding="utf-8")
        statements = [
            statement.strip()
            for statement in re.sub(r"--[^\n]*", "", down).split(";")
            if statement.strip()
        ]
        assert statements[-1].startswith(
            f'DELETE FROM "{_PRISMA_BOOKKEEPING_TABLE}"'
        ), (
            f"nestjs+{auth or 'none'}: {migration_dir.name}/down.sql does not end by "
            "un-recording its migration"
        )


def _down_scripts_that_drop_a_table(tmp_path) -> list:
    return [
        down
        for down in sorted(
            (tmp_path / "api" / "prisma" / "migrations").rglob("down.sql")
        )
        if "DROP TABLE" in down.read_text(encoding="utf-8")
    ]


@pytest.mark.integration
@pytest.mark.parametrize("auth", list(_EXPECTED_TABLES))
def test_scaffolded_nestjs_down_scripts_back_up_into_the_backup_schema_not_public(
    tmp_path, auth
):
    """A down script copies each dropped table into ``migration_backup``, never ``public``.

    A copy in ``public`` is served by the Supabase Data API, with none of the access
    rules of the table it copies. The schema is created closed to everybody else.

    Validates project_initializer/templates-{api,supabase}-nestjs/api/prisma/migrations.
    """
    copy_template(tmp_path, "app", auth=auth, framework="nestjs", scope="api")

    scripts = _down_scripts_that_drop_a_table(tmp_path)
    assert scripts, f"nestjs+{auth or 'none'}: no down script drops a table"
    for down in scripts:
        text = down.read_text(encoding="utf-8")
        executable = re.sub(r"--[^\n]*", "", text)
        assert f"CREATE SCHEMA IF NOT EXISTS {_BACKUP_SCHEMA};" in executable
        assert f"REVOKE ALL ON SCHEMA {_BACKUP_SCHEMA} FROM PUBLIC;" in executable
        created = re.findall(r"CREATE TABLE ([^\s]+)", executable)
        assert created, f"{down.parent.name}/down.sql creates no backup table"
        for target in created:
            assert target.startswith(f"{_BACKUP_SCHEMA}."), (
                f"nestjs+{auth or 'none'}: {down.parent.name}/down.sql backs up into "
                f"{target}, outside {_BACKUP_SCHEMA}"
            )
        assert "public." not in executable


@pytest.mark.integration
@pytest.mark.parametrize("auth", list(_EXPECTED_TABLES))
def test_scaffolded_nestjs_backup_names_end_in_a_microsecond_timestamp(tmp_path, auth):
    """Two rollbacks inside one second must not collide on the backup table name.

    Validates project_initializer/templates-{api,supabase}-nestjs/api/prisma/migrations.
    """
    copy_template(tmp_path, "app", auth=auth, framework="nestjs", scope="api")

    for down in _down_scripts_that_drop_a_table(tmp_path):
        text = down.read_text(encoding="utf-8")
        assert "__rollback_%s" in text
        assert _MICROSECOND_TIMESTAMP_FORMAT in text, (
            f"nestjs+{auth or 'none'}: {down.parent.name}/down.sql names its backup "
            "with less than microsecond resolution"
        )
        assert "clock_timestamp()" in text, (
            "now() is fixed inside a transaction, so two backups in one would collide"
        )


@pytest.mark.integration
def test_scaffolded_supabase_init_down_script_drops_profiles_not_users(tmp_path):
    """The supabase init down.sql replaces the base one by path; a base copy would drop `users`.

    Validates project_initializer/templates-supabase-nestjs/api/prisma/migrations/20260716000000_init/down.sql.
    """
    copy_template(tmp_path, "app", auth="supabase", framework="nestjs", scope="api")

    down = (
        tmp_path / "api" / "prisma" / "migrations" / _INIT_MIGRATION / "down.sql"
    ).read_text(encoding="utf-8")
    assert 'DROP TABLE "profiles"' in down, "supabase init down.sql must drop profiles"
    assert "users" not in down, (
        "supabase init down.sql still refers to `users`: the base down.sql was not replaced"
    )


@pytest.mark.integration
@pytest.mark.parametrize("auth", [None, "token", "entra"])
def test_scaffolded_nestjs_init_down_script_drops_users(tmp_path, auth):
    """The base init down script drops ``users``, the table of the variants that are not Supabase.

    Validates project_initializer/templates-api-nestjs/api/prisma/migrations/20260716000000_init/down.sql.
    """
    copy_template(tmp_path, "app", auth=auth, framework="nestjs", scope="api")

    down = (
        tmp_path / "api" / "prisma" / "migrations" / _INIT_MIGRATION / "down.sql"
    ).read_text(encoding="utf-8")
    assert 'DROP TABLE "users"' in down and "profiles" not in down


@pytest.mark.integration
def test_scaffolded_supabase_enables_row_level_security_on_every_table(tmp_path):
    """Supabase exposes tables through its Data API: each one needs RLS, or the publishable
    key would read and write it. The API connects as the table owner, which bypasses RLS.

    Validates project_initializer/templates-supabase-nestjs/api/prisma/migrations.
    """
    copy_template(tmp_path, "app", auth="supabase", framework="nestjs", scope="api")

    migrations = tmp_path / "api" / "prisma" / "migrations"
    created = set(_created_tables(migrations))
    sql = "\n".join(
        f.read_text(encoding="utf-8") for f in sorted(migrations.rglob("migration.sql"))
    )
    secured = set(re.findall(r'ALTER TABLE "([^"]+)" ENABLE ROW LEVEL SECURITY', sql))
    assert created - secured == set(), (
        f"supabase tables without Row Level Security: {sorted(created - secured)}"
    )


@pytest.mark.integration
def test_scaffolded_supabase_secures_the_prisma_bookkeeping_table_and_can_undo_it(
    tmp_path,
):
    """``_prisma_migrations`` lists every migration name and sits in ``public``.

    The Data API would serve it to the publishable key, so the RLS migration covers
    it, and its down script disables the same tables it enabled.

    Validates project_initializer/templates-supabase-nestjs/api/prisma/migrations/20261121000100_enable_row_level_security.
    """
    copy_template(tmp_path, "app", auth="supabase", framework="nestjs", scope="api")

    (rls_dir,) = [
        path for path in _migration_dirs(tmp_path) if "row_level_security" in path.name
    ]
    up = (rls_dir / "migration.sql").read_text(encoding="utf-8")
    down = (rls_dir / "down.sql").read_text(encoding="utf-8")
    enabled = _rls_tables(up, "ENABLE")
    disabled = _rls_tables(down, "DISABLE")

    assert _PRISMA_BOOKKEEPING_TABLE in enabled
    assert enabled == disabled
    assert "CREATE POLICY" not in up.upper(), (
        "a policy would open a table to the Data API roles"
    )
    assert "FORCE" not in up.upper(), (
        "forcing RLS would lock out the API, which connects as the table owner"
    )


@pytest.mark.integration
@pytest.mark.parametrize("auth", [None, "token", "entra"])
def test_scaffolded_non_supabase_nestjs_does_not_ship_the_rls_migration(tmp_path, auth):
    """The local-Postgres variants have no Data API, and the RLS migration names `profiles`.

    Validates project_initializer/templates-api-nestjs/api/prisma/migrations (no row level security).
    """
    copy_template(tmp_path, "app", auth=auth, framework="nestjs", scope="api")

    sql = "\n".join(
        f.read_text(encoding="utf-8")
        for f in (tmp_path / "api" / "prisma" / "migrations").rglob("*.sql")
    )
    assert "ROW LEVEL SECURITY" not in sql

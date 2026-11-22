"""Runtime guards for the shipped Docker stack (anti-drift).

These invariants encode bugs that made a freshly scaffolded ``docker-compose up``
unhealthy or collide with another project, and that no other test caught because
they only surface at container runtime:

1. **Frontend healthcheck must use IPv4** — ``nginx.conf`` listens on IPv4 only
   (``listen 80;``), so a healthcheck against ``localhost`` resolves to ``::1``
   and fails forever while nginx serves correctly.

2. **Compose files stay collision-free** — no pinned ``container_name`` and every
   published host port parametrized, because both are global to the Docker daemon.

3. **Entrypoints and images match the runtime** — the entrypoints wait on the
   database the application uses, and the images ship what the entrypoints need.
"""

import re
from pathlib import Path

import pytest

_TEMPLATES = Path(__file__).resolve().parent.parent / "project_initializer"

_FASTAPI_API = _TEMPLATES / "templates-api-fastapi" / "api"
_NESTJS_API = _TEMPLATES / "templates-api-nestjs" / "api"
_FRONTEND_DOCKERFILE = _TEMPLATES / "templates" / "frontend" / "Dockerfile"


@pytest.mark.unit
def test_no_compose_file_hardcodes_container_names():
    """No shipped compose may pin container_name — it collides across projects.

    A fixed `container_name: app_db` is global to the Docker daemon, so a second
    scaffolded project (or any unrelated project using the same name) fails to
    start with "container name is already in use". Without it, compose derives
    `<project>-<service>-1` from the directory, which is unique per project.

    Validates every project_initializer/templates-*/docker-compose*.yml.
    """
    offenders = []
    for compose in _TEMPLATES.rglob("docker-compose*.yml"):
        for lineno, line in enumerate(
            compose.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if line.strip().startswith("container_name:"):
                offenders.append(f"{compose.relative_to(_TEMPLATES)}:{lineno}")
    assert offenders == [], (
        "compose files pin container_name, which collides across projects:\n"
        + "\n".join(offenders)
    )


@pytest.mark.unit
def test_every_published_host_port_is_parametrized():
    """Published host ports must come from a ${VAR:-default}, never a literal.

    A fixed host port is as much a cross-project collision as a fixed container
    name: the second `docker compose up` dies with "port is already allocated".
    Adminer shipped a literal `8080:8080` while every other service was already
    parametrized, which is exactly how it slipped through.

    Validates every project_initializer/templates-*/docker-compose*.yml.
    """
    offenders = []
    for compose in _TEMPLATES.rglob("docker-compose*.yml"):
        for lineno, line in enumerate(
            compose.read_text(encoding="utf-8").splitlines(), start=1
        ):
            stripped = line.strip()
            # A ports entry looks like: - "<host>:<container>"
            if not stripped.startswith("- \""):
                continue
            if ":" not in stripped:
                continue
            host_side = stripped.split('"')[1].split(":")[0]
            if "${" not in host_side:
                offenders.append(f"{compose.relative_to(_TEMPLATES)}:{lineno} -> {stripped}")
    assert offenders == [], (
        "compose files publish literal host ports, which collide across projects:\n"
        + "\n".join(offenders)
    )


@pytest.mark.unit
def test_generated_frontend_compose_has_no_container_name():
    """The synthesised frontend-only compose must not pin container_name either."""
    from project_initializer.file_transforms import generate_frontend_compose

    assert "container_name:" not in generate_frontend_compose()


@pytest.mark.unit
def test_frontend_healthcheck_targets_ipv4():
    """The frontend HEALTHCHECK must not use localhost — nginx is IPv4-only."""
    dockerfile = _FRONTEND_DOCKERFILE.read_text(encoding="utf-8")
    healthcheck = [
        line for line in dockerfile.splitlines() if "wget" in line and "/health" in line
    ]
    assert healthcheck, "no wget-based HEALTHCHECK found in the frontend Dockerfile"

    for line in healthcheck:
        assert "//localhost" not in line, (
            "frontend HEALTHCHECK targets localhost, which resolves to ::1 while "
            "nginx.conf listens on IPv4 only — the container would report unhealthy "
            "forever. Use 127.0.0.1."
        )
        assert "//127.0.0.1" in line, f"expected an IPv4 healthcheck target, got: {line}"


@pytest.mark.unit
@pytest.mark.parametrize("framework", ["fastapi", "nestjs"])
def test_nginx_listens_ipv4_only_justifying_the_healthcheck(framework):
    """Pin the assumption the healthcheck guard rests on: nginx binds IPv4 only.

    If a future change adds `listen [::]:80;`, this fails as a prompt to revisit
    the healthcheck guard above rather than leave a stale rationale behind.
    """
    nginx_conf = _TEMPLATES / f"templates-api-{framework}" / "frontend" / "nginx.conf"
    text = nginx_conf.read_text(encoding="utf-8")
    assert "listen 80;" in text
    assert "listen [::]:80" not in text


_FASTAPI_DOCKERFILE = _FASTAPI_API / "Dockerfile"
_FASTAPI_ENTRYPOINT = _FASTAPI_API / "entrypoint.sh"
_NESTJS_DOCKERFILE = _NESTJS_API / "Dockerfile"
_NESTJS_ENTRYPOINT = _NESTJS_API / "entrypoint.sh"
_FASTAPI_COMPOSE_FILES = (
    _TEMPLATES / "templates-api-fastapi" / "docker-compose.yml",
    _TEMPLATES / "templates-supabase-fastapi" / "docker-compose.yml",
)


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.mark.unit
def test_fastapi_server_does_not_write_the_unstructured_access_log():
    """Uvicorn's access log prints the client address and query string as plain text.

    The structured ``http.request`` record of the logging middleware replaces it, so
    every command that starts the server passes ``--no-access-log``.

    Validates project_initializer/templates-api-fastapi/api/Dockerfile and templates-{api,supabase}-fastapi docker-compose.yml.
    """
    commands = [
        line
        for path in (_FASTAPI_DOCKERFILE, *_FASTAPI_COMPOSE_FILES)
        for line in _text(path).splitlines()
        if "uvicorn app.main:app" in line or '"uvicorn", "app.main:app"' in line
    ]

    assert len(commands) == 3, "expected the Dockerfile CMD and two compose commands"
    for command in commands:
        assert "--no-access-log" in command, command


@pytest.mark.unit
def test_fastapi_image_keeps_the_application_code_root_owned():
    """The unprivileged process must not be able to rewrite the code it runs.

    ``COPY`` leaves files root-owned, so any ``chown`` or ``--chown`` of ``/app``
    would hand the code to ``appuser``.

    Validates project_initializer/templates-api-fastapi/api/Dockerfile.
    """
    dockerfile = _text(_FASTAPI_DOCKERFILE)

    assert "chown" not in dockerfile
    assert "USER appuser" in dockerfile
    assert "PYTHONDONTWRITEBYTECODE=1" in dockerfile


@pytest.mark.unit
def test_fastapi_entrypoint_waits_on_the_database_the_application_will_use():
    """The wait reads host and port from DATABASE_URL and gives up after a deadline.

    A hardcoded ``db`` host hangs forever, or passes against the wrong server, as
    soon as the database is not the compose service.

    Validates project_initializer/templates-api-fastapi/api/entrypoint.sh.
    """
    entrypoint = _text(_FASTAPI_ENTRYPOINT)

    assert ': "${DATABASE_URL:?' in entrypoint
    assert "urlsplit" in entrypoint
    assert '--host "$database_host"' in entrypoint
    assert '--port "$database_port"' in entrypoint
    assert 'DB_WAIT_TIMEOUT_SECONDS="${DB_WAIT_TIMEOUT_SECONDS:-60}"' in entrypoint
    assert "deadline=$((SECONDS + DB_WAIT_TIMEOUT_SECONDS))" in entrypoint
    assert "exit 1" in entrypoint
    assert "pg_isready" in entrypoint
    assert "alembic upgrade head" in entrypoint


@pytest.mark.unit
def test_fastapi_dockerfile_installs_the_client_the_entrypoint_needs():
    """``pg_isready`` ships in postgresql-client; the entrypoint fails without it.

    Validates project_initializer/templates-api-fastapi/api/Dockerfile.
    """
    assert "postgresql-client" in _text(_FASTAPI_DOCKERFILE)


@pytest.mark.unit
def test_nestjs_entrypoint_waits_on_the_database_the_application_will_use():
    """The NestJS wait is derived from DATABASE_URL and bounded by the same variable.

    Validates project_initializer/templates-api-nestjs/api/entrypoint.sh.
    """
    entrypoint = _text(_NESTJS_ENTRYPOINT)

    assert ': "${DATABASE_URL:?' in entrypoint
    assert "new URL(process.env.DATABASE_URL)" in entrypoint
    assert 'DB_WAIT_TIMEOUT_SECONDS="${DB_WAIT_TIMEOUT_SECONDS:-60}"' in entrypoint
    assert "deadline=$(($(date +%s) + DB_WAIT_TIMEOUT_SECONDS))" in entrypoint
    assert 'nc -z -w "$DB_CONNECT_TIMEOUT_SECONDS" "$db_host" "$db_port"' in entrypoint
    assert "exit 1" in entrypoint
    assert "prisma migrate deploy" in entrypoint


@pytest.mark.unit
def test_when_the_nestjs_dockerfile_is_read_then_every_stage_is_node_26_alpine():
    """The dev and production stages run the Node 26 LTS; ``builder`` inherits ``dev``.

    A stage left on an older Node would build and run the API on a runtime the
    manifests' ``@types/node`` no longer describes.

    Validates project_initializer/templates-api-nestjs/api/Dockerfile.
    """
    images = re.findall(r"^FROM (node:\S+)", _text(_NESTJS_DOCKERFILE), re.M)

    assert images == ["node:26-alpine", "node:26-alpine"]


@pytest.mark.unit
def test_nestjs_production_image_ships_the_prisma_config_the_entrypoint_needs():
    """``prisma migrate deploy`` takes its datasource URL from prisma.config.ts.

    Validates project_initializer/templates-api-nestjs/api/Dockerfile.
    """
    dockerfile = _text(_NESTJS_DOCKERFILE)
    runtime = dockerfile[dockerfile.rindex("FROM node:") :]

    assert "COPY --from=builder /app/prisma.config.ts ./prisma.config.ts" in runtime
    assert "USER appuser" in runtime

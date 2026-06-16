"""Scope-aware docker-compose file transforms.

Pure functions — no I/O, no external dependencies, stdlib only.
"""

import re

_NGINX_PROXY_RE = re.compile(
    r"[ \t]*# API proxy to backend\n"
    r"[ \t]*location /api/ \{\n"
    r".*?"
    r"[ \t]*\}\n\n?",
    re.DOTALL,
)


def strip_nginx_proxy_block(text: str) -> str:
    """Remove the dead /api/ reverse-proxy block (frontend scope has no backend).

    Anchored on the '# API proxy to backend' + 'location /api/ {' sentinels;
    matches through the block's closing brace (no nested braces). Idempotent.
    """
    return _NGINX_PROXY_RE.sub("", text)


def _service_header_index(lines: list[str], name: str) -> int:
    """Return the index of the ``  <name>:`` header line, or -1."""
    header = f"  {name}:"
    for i, line in enumerate(lines):
        if line.rstrip() == header:
            return i
    return -1


def _block_end(lines: list[str], start: int) -> int:
    """Return the index of the first line after the service block body.

    Body lines are indented 4+ spaces or are blank; terminates at a
    2-space key/comment or a column-0 key or EOF.
    """
    i = start + 1
    while i < len(lines):
        stripped = lines[i].rstrip()
        if stripped == "":
            i += 1
            continue
        if stripped.startswith("    "):
            i += 1
            continue
        break
    return i


def _remove_service(text: str, name: str) -> str:
    """Remove the named service block (header + body + preceding comment)."""
    lines = text.splitlines(keepends=True)
    idx = _service_header_index(lines, name)
    if idx == -1:
        return text
    end = _block_end(lines, idx)
    comment_start = (
        idx - 1 if idx > 0 and lines[idx - 1].strip().startswith("#") else idx
    )
    del lines[comment_start:end]
    return "".join(lines)


def filter_compose(text: str, scope: str) -> str:
    """Return compose text with the frontend service removed when scope is 'api'.

    Args:
        text: Raw docker-compose.yml content.
        scope: Scaffold scope; only ``"api"`` triggers removal.

    Returns:
        Filtered text, or the original text unchanged for any other scope.
    """
    if scope == "api":
        return _remove_service(text, "frontend")
    return text


_FRONTEND_COMPOSE = """\
services:
  # Angular Frontend with nginx
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: app_frontend
    ports:
      - "4200:80"
    networks:
      - app_network

networks:
  app_network:
"""


def generate_frontend_compose() -> str:
    """Synthesise a standalone frontend-only docker-compose.yml.

    Returns:
        Compose YAML string with a single ``frontend`` service and
        an ``app_network`` network definition; no ``depends_on``.
    """
    return _FRONTEND_COMPOSE


# Pinned to match SQLAlchemy==2.0.50 already in the base requirements; the
# extras form pulls greenlet for the async path. asyncpg is the async driver.
# aiosqlite is used for unit testing with in-memory SQLite.
_ASYNC_REQUIREMENTS = (
    "\n# Async DB path (--async-db) — opt-in asyncpg driver + asyncio extras\n"
    "asyncpg==0.31.0\n"
    "sqlalchemy[asyncio]==2.0.50\n"
    "aiosqlite==0.20.0\n"
)


def append_async_requirements(text: str) -> str:
    """Append the async DB deps to a requirements.txt body (pure, idempotent).

    Returns ``text`` unchanged when ``asyncpg`` is already present so a re-run
    over an already-async requirements file never double-appends.
    """
    if "asyncpg" in text:
        return text
    return text + _ASYNC_REQUIREMENTS

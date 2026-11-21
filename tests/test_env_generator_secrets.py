"""Generated secrets in the scaffolded ``.env`` and blank secrets in ``.env.example``.

Earlier releases shipped ``AUTH_TOKEN=changeme`` and ``JWT_SECRET_KEY=changeme`` in a
``.env`` that was byte-identical to the committed ``.env.example``: every project had the
same well-known credential. The generator now creates one random secret per key per
scaffold, and the example file never carries a value for them.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from project_initializer.cli import TEMPLATES_ROOT, copy_template
from project_initializer.env_generator import (
    GENERATED_SECRET_KEYS,
    LEGACY_PLACEHOLDER,
    generate_env,
    generate_env_file,
    new_generated_secrets,
    parse_env,
)

# The strictest minimum any template enforces: the NestJS token variant requires 32.
MIN_SECRET_LENGTH = 32
URL_SAFE = re.compile(r"^[A-Za-z0-9_-]+$")

# Stand-in for a value an operator wrote into the root .env by hand. It is not a credential.
EXPLICIT_VALUE = "explicit-value-from-the-root-env"

FRAMEWORKS = ("fastapi", "nestjs")
AUTH_MODES = (None, "token", "supabase", "entra")


def _expected_secret_keys(framework: str, auth: str | None) -> set[str]:
    """The secret keys a variant's env file declares."""
    keys: set[str] = set()
    if auth == "token":
        keys.add("AUTH_TOKEN")
        if framework == "fastapi":
            keys.add("JWT_SECRET_KEY")
    if framework == "nestjs":
        keys.add("QUEUE_MONITOR_PASSWORD")
    return keys


def parse_env_text(text: str) -> dict[str, str]:
    """Parse generated .env text the way the generator's own ``parse_env`` does."""
    env: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        key, _, value = stripped.partition("=")
        env[key.strip()] = value.strip().strip('"')
    return env


def _scaffold(dest: Path, framework: str, auth: str | None) -> tuple[dict, dict]:
    """Scaffold an api project and return its parsed ``.env`` and ``.env.example``."""
    copy_template(dest, "app", auth=auth, framework=framework, scope="api")
    return parse_env(dest / ".env"), parse_env(dest / ".env.example")


# --- new_generated_secrets --------------------------------------------------


@pytest.mark.unit
def test_when_secret_keys_listed_then_credential_keys_are_covered():
    """The generated set names every credential the templates read.

    Validates project_initializer/env_generator.py GENERATED_SECRET_KEYS.
    """
    assert set(GENERATED_SECRET_KEYS) == {
        "AUTH_TOKEN",
        "JWT_SECRET_KEY",
        "QUEUE_MONITOR_PASSWORD",
    }


@pytest.mark.unit
def test_when_secrets_generated_then_every_key_has_a_long_url_safe_value():
    """Each value clears the strictest template minimum and needs no .env quoting.

    Validates project_initializer/env_generator.py new_generated_secrets().
    """
    secrets = new_generated_secrets()

    assert set(secrets) == set(GENERATED_SECRET_KEYS)
    for key, value in secrets.items():
        assert len(value) >= MIN_SECRET_LENGTH, key
        assert URL_SAFE.match(value), key


@pytest.mark.unit
def test_when_secrets_generated_then_values_are_unique_per_key_and_per_call():
    """No two keys share a value, and a second call returns fresh values.

    Validates project_initializer/env_generator.py new_generated_secrets().
    """
    first = new_generated_secrets()
    second = new_generated_secrets()

    assert len(set(first.values())) == len(first)
    assert not set(first.values()) & set(second.values())


# --- generate_env: filling secrets ------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize("framework", FRAMEWORKS)
@pytest.mark.parametrize("auth", AUTH_MODES)
def test_when_secrets_supplied_then_only_the_variants_own_keys_are_emitted(
    framework, auth
):
    """Each variant declares exactly its secret keys, filled from the supplied mapping.

    Validates project_initializer/env_generator.py generate_env().
    """
    secrets = new_generated_secrets()

    env = parse_env_text(generate_env(framework, auth, {}, secrets=secrets))

    emitted = {key for key in GENERATED_SECRET_KEYS if key in env}
    assert emitted == _expected_secret_keys(framework, auth)
    for key in emitted:
        assert env[key] == secrets[key]


@pytest.mark.unit
def test_when_source_holds_an_explicit_value_then_the_supplied_secret_does_not_replace_it():
    """A value chosen in the root .env wins over a generated one.

    Validates project_initializer/env_generator.py generate_env().
    """
    secrets = new_generated_secrets()
    source = {"AUTH_TOKEN": EXPLICIT_VALUE, "JWT_SECRET_KEY": EXPLICIT_VALUE}

    env = parse_env_text(generate_env("fastapi", "token", source, secrets=secrets))

    assert env["AUTH_TOKEN"] == EXPLICIT_VALUE
    assert env["JWT_SECRET_KEY"] == EXPLICIT_VALUE


@pytest.mark.unit
@pytest.mark.parametrize("stale", ["", LEGACY_PLACEHOLDER])
def test_when_source_is_blank_or_legacy_then_the_supplied_secret_fills_it(stale):
    """An empty value and the old shipped placeholder both count as unset.

    Validates project_initializer/env_generator.py generate_env().
    """
    secrets = new_generated_secrets()
    source = {"AUTH_TOKEN": stale, "JWT_SECRET_KEY": stale}

    env = parse_env_text(generate_env("fastapi", "token", source, secrets=secrets))

    assert env["AUTH_TOKEN"] == secrets["AUTH_TOKEN"]
    assert env["JWT_SECRET_KEY"] == secrets["JWT_SECRET_KEY"]


@pytest.mark.unit
def test_when_no_secrets_supplied_then_blank_keys_stay_blank():
    """Without a generator the file never invents a guessable fallback.

    Validates project_initializer/env_generator.py generate_env().
    """
    env = parse_env_text(generate_env("fastapi", "token", {}))

    assert env["AUTH_TOKEN"] == ""
    assert env["JWT_SECRET_KEY"] == ""
    assert LEGACY_PLACEHOLDER not in generate_env("fastapi", "token", {})


# --- generate_env: placeholders ---------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize("framework", FRAMEWORKS)
def test_when_placeholders_requested_then_secret_keys_are_blank_whatever_the_source(
    framework,
):
    """An example file stays blank even when the source env holds real values.

    Validates project_initializer/env_generator.py generate_env(use_placeholders=True).
    """
    source = dict.fromkeys(GENERATED_SECRET_KEYS, EXPLICIT_VALUE)

    env = parse_env_text(
        generate_env(framework, "token", source, use_placeholders=True)
    )

    for key in _expected_secret_keys(framework, "token"):
        assert key in env
        assert env[key] == ""


@pytest.mark.unit
def test_when_placeholders_and_secrets_are_both_given_then_the_call_is_rejected():
    """The two options contradict each other, so the call fails instead of picking one.

    Validates project_initializer/env_generator.py generate_env().
    """
    with pytest.raises(ValueError, match="use_placeholders"):
        generate_env(
            "fastapi",
            "token",
            {},
            secrets=new_generated_secrets(),
            use_placeholders=True,
        )


@pytest.mark.unit
def test_when_placeholders_requested_then_non_secret_defaults_are_kept():
    """Only credentials go blank; the dev defaults that make the stack boot stay.

    Validates project_initializer/env_generator.py generate_env(use_placeholders=True).
    """
    env = parse_env_text(generate_env("fastapi", "entra", use_placeholders=True))

    assert env["ENTRA_TENANT_ID"]
    assert env["DATABASE_URL"]


# --- generate_env: server and database hardening ----------------------------


@pytest.mark.unit
@pytest.mark.parametrize("auth", AUTH_MODES)
def test_when_fastapi_env_generated_then_debug_is_false(auth):
    """DEBUG renders tracebacks to clients, so it is never emitted on.

    Validates project_initializer/env_generator.py generate_env().
    """
    env = parse_env_text(generate_env("fastapi", auth, {}))

    assert env["DEBUG"] == "false"
    assert env["ENVIRONMENT"] == "development"


@pytest.mark.unit
def test_when_supabase_fastapi_env_generated_then_tls_and_pool_recycle_are_pinned():
    """The pooler needs TLS on and connections recycled well under its idle timeout.

    Validates project_initializer/env_generator.py generate_env().
    """
    env = parse_env_text(generate_env("fastapi", "supabase", {}))

    assert env["DATABASE_SSL_MODE"] == "require"
    assert env["DATABASE_POOL_RECYCLE"] == "300"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("framework", "auth"),
    [
        ("fastapi", None),
        ("fastapi", "token"),
        ("fastapi", "entra"),
        ("nestjs", "supabase"),
    ],
)
def test_when_variant_is_not_supabase_fastapi_then_ssl_and_pool_keys_are_absent(
    framework, auth
):
    """The TLS and recycle pins belong to the Supabase FastAPI variant only.

    Validates project_initializer/env_generator.py generate_env().
    """
    env = parse_env_text(generate_env(framework, auth, {}))

    assert "DATABASE_SSL_MODE" not in env
    assert "DATABASE_POOL_RECYCLE" not in env


# --- generate_env: queue dashboard ------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize("auth", AUTH_MODES)
def test_when_nestjs_env_generated_then_queue_dashboard_block_is_present(auth):
    """Every NestJS variant mounts the dashboard, so every one declares its credentials.

    Validates project_initializer/env_generator.py generate_env().
    """
    text = generate_env("nestjs", auth, {})
    env = parse_env_text(text)

    assert "# Queue dashboard" in text
    assert env["QUEUE_MONITOR_USER"] == "admin"
    assert env["QUEUE_MONITOR_PASSWORD"] == ""


@pytest.mark.unit
def test_when_source_sets_queue_user_then_it_overrides_the_default():
    """QUEUE_MONITOR_USER follows the source env; only the password is generated.

    Validates project_initializer/env_generator.py generate_env().
    """
    env = parse_env_text(generate_env("nestjs", None, {"QUEUE_MONITOR_USER": "ops"}))

    assert env["QUEUE_MONITOR_USER"] == "ops"


@pytest.mark.unit
def test_when_fastapi_env_generated_then_queue_dashboard_is_absent():
    """The dashboard is a NestJS/BullMQ feature, so FastAPI never gets its keys.

    Validates project_initializer/env_generator.py generate_env().
    """
    text = generate_env("fastapi", "token", {}, secrets=new_generated_secrets())

    assert "QUEUE_MONITOR" not in text


# --- env_defaults.env -------------------------------------------------------


@pytest.mark.unit
def test_when_env_defaults_read_then_no_credential_default_exists():
    """The shipped defaults carry no secret key and no legacy placeholder.

    Validates project_initializer/env_defaults.env.
    """
    defaults = parse_env(TEMPLATES_ROOT / "env_defaults.env")

    assert not set(defaults) & set(GENERATED_SECRET_KEYS)
    assert LEGACY_PLACEHOLDER not in defaults.values()


# --- generate_env_file ------------------------------------------------------


@pytest.mark.unit
def test_when_env_file_generated_then_blank_secrets_are_filled_and_explicit_ones_kept(
    tmp_path,
):
    """The standalone generator writes a bootable .env and respects the root .env.

    Validates project_initializer/env_generator.py generate_env_file().
    """
    source = tmp_path / "root.env"
    source.write_text(
        f"AUTH_TOKEN=\nJWT_SECRET_KEY={EXPLICIT_VALUE}\n", encoding="utf-8"
    )
    dest = tmp_path / "api" / ".env"

    generate_env_file("fastapi", "token", source, dest)

    env = parse_env(dest)
    assert len(env["AUTH_TOKEN"]) >= MIN_SECRET_LENGTH
    assert env["JWT_SECRET_KEY"] == EXPLICIT_VALUE


# --- scaffold ---------------------------------------------------------------
# Not marked ``integration``: copying the template tree takes milliseconds, and CI
# runs ``pytest -m "not integration"``, so the secret guarantees must stay unmarked.


@pytest.mark.parametrize("framework", FRAMEWORKS)
@pytest.mark.parametrize("auth", AUTH_MODES)
def test_when_project_scaffolded_then_env_has_secrets_and_example_is_blank(
    tmp_path, framework, auth
):
    """The .env boots with strong secrets; the committed example holds none.

    Validates project_initializer/cli.py _write_env_files() and project_initializer/cli.py _secrets_for_env().
    """
    env, example = _scaffold(tmp_path / "app", framework, auth)

    for key in _expected_secret_keys(framework, auth):
        assert len(env[key]) >= MIN_SECRET_LENGTH, key
        assert URL_SAFE.match(env[key]), key
        assert example[key] == "", key
    for key in set(GENERATED_SECRET_KEYS) - _expected_secret_keys(framework, auth):
        assert key not in env
        assert key not in example


@pytest.mark.parametrize("framework", FRAMEWORKS)
@pytest.mark.parametrize("auth", AUTH_MODES)
def test_when_project_scaffolded_then_env_and_example_declare_the_same_keys(
    tmp_path, framework, auth
):
    """The example documents every key the .env sets, and only secrets differ in value.

    Validates project_initializer/cli.py _write_env_files() and project_initializer/cli.py _secrets_for_env().
    """
    env, example = _scaffold(tmp_path / "app", framework, auth)

    assert set(env) == set(example)
    differing = {key for key in env if env[key] != example[key]}
    assert differing == _expected_secret_keys(framework, auth)


@pytest.mark.parametrize("framework", FRAMEWORKS)
def test_when_two_projects_scaffolded_then_their_secrets_differ(tmp_path, framework):
    """Two scaffolds never share a credential.

    Validates project_initializer/cli.py _write_env_files() and project_initializer/cli.py _secrets_for_env().
    """
    first, _ = _scaffold(tmp_path / "one", framework, "token")
    second, _ = _scaffold(tmp_path / "two", framework, "token")

    for key in _expected_secret_keys(framework, "token"):
        assert first[key] != second[key], key


@pytest.mark.parametrize("framework", FRAMEWORKS)
def test_when_project_rescaffolded_then_existing_secrets_are_kept(tmp_path, framework):
    """Re-running over a project must not silently rotate credentials in use.

    Validates project_initializer/cli.py _write_env_files() and project_initializer/cli.py _secrets_for_env().
    """
    dest = tmp_path / "app"
    first, _ = _scaffold(dest, framework, "token")

    second, _ = _scaffold(dest, framework, "token")

    for key in _expected_secret_keys(framework, "token"):
        assert second[key] == first[key], key


def test_when_existing_env_holds_legacy_placeholder_then_rescaffold_replaces_it(
    tmp_path,
):
    """A project scaffolded by an earlier release gets a real secret, not 'changeme'.

    Validates project_initializer/cli.py _write_env_files() and project_initializer/cli.py _secrets_for_env().
    """
    dest = tmp_path / "app"
    dest.mkdir()
    (dest / ".env").write_text(
        f"AUTH_TOKEN={LEGACY_PLACEHOLDER}\nJWT_SECRET_KEY={LEGACY_PLACEHOLDER}\n",
        encoding="utf-8",
    )

    env, _ = _scaffold(dest, "fastapi", "token")

    assert LEGACY_PLACEHOLDER not in (dest / ".env").read_text(encoding="utf-8")
    assert len(env["AUTH_TOKEN"]) >= MIN_SECRET_LENGTH
    assert len(env["JWT_SECRET_KEY"]) >= MIN_SECRET_LENGTH


def test_when_existing_env_has_operator_chosen_value_then_rescaffold_keeps_it(tmp_path):
    """A hand-written secret survives a re-scaffold; the example still ships blank.

    Validates project_initializer/cli.py _write_env_files() and project_initializer/cli.py _secrets_for_env().
    """
    dest = tmp_path / "app"
    dest.mkdir()
    (dest / ".env").write_text(f"AUTH_TOKEN={EXPLICIT_VALUE}\n", encoding="utf-8")

    env, example = _scaffold(dest, "fastapi", "token")

    assert env["AUTH_TOKEN"] == EXPLICIT_VALUE
    assert example["AUTH_TOKEN"] == ""

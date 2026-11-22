"""Doc-drift guard for the NestJS compliance rewrite.

The generated NestJS docs must describe the templates as they are now: one shared root module
with an ``app.auth.ts`` seam, a non-global ``PrismaModule``, a ``down.sql`` per migration with
the one-command rollback, and the traceability convention.
Each assertion pins a statement that was wrong, or missing, before the rewrite.
"""

import re

import pytest

from project_initializer.cli import copy_template
from project_initializer.docs_generator import (
    generate_api_claude,
    generate_api_readme,
    generate_root_claude,
    generate_root_readme,
)

AUTHS = [None, "token", "supabase", "entra"]


def _api_claude(auth=None) -> str:
    return generate_api_claude("nestjs", auth)


@pytest.mark.parametrize("auth", AUTHS)
def test_when_api_claude_generated_then_removed_artifacts_are_not_described(auth):
    """The docs must not describe code the rewrite deleted.

    Validates project_initializer/docs_generator.py generate_api_claude().
    """
    doc = _api_claude(auth)
    assert "TransformInterceptor" not in doc, "the interceptor was deleted as a no-op"
    assert "SupabaseAuthGuard" not in doc and "EntraAuthGuard" not in doc
    assert "@Global() PrismaModule" not in doc


@pytest.mark.parametrize("auth", AUTHS)
def test_when_api_claude_generated_then_prisma_is_documented_as_not_global(auth):
    """PrismaModule is imported where needed, so the docs must not call it global.

    Validates project_initializer/docs_generator.py generate_api_claude().
    """
    doc = _api_claude(auth)
    assert "`PrismaModule` is **not** `@Global()`" in doc
    assert "`PrismaModule` is not global" in doc


@pytest.mark.parametrize("auth", AUTHS)
def test_when_api_claude_generated_then_filters_are_registered_in_configure_app(auth):
    """Filters are registered in configureApp, which main.ts and the e2e harness both call.

    Validates project_initializer/docs_generator.py generate_api_claude().
    """
    doc = _api_claude(auth)
    assert "configureApp" in doc and "src/app.setup.ts" in doc
    assert "test/support/create-e2e-app.ts" in doc, (
        "the e2e harness must share the pipeline"
    )
    # Wording other tests pin: the APP_FILTER escape hatch and the main.ts contrast.
    assert "APP_FILTER" in doc and "useGlobalFilters" in doc and "main.ts" in doc


@pytest.mark.parametrize("auth", AUTHS)
def test_when_api_claude_generated_then_guard_comes_from_the_auth_seam(auth):
    """The global guard comes in through the app.auth.ts seam and the verifier token.

    Validates project_initializer/docs_generator.py generate_api_claude().
    """
    doc = _api_claude(auth)
    assert "src/app.auth.ts" in doc
    assert "AccessTokenGuard" in doc and "ACCESS_TOKEN_VERIFIER" in doc


@pytest.mark.parametrize("auth", AUTHS)
def test_when_api_claude_generated_then_env_schema_lives_in_env_base(auth):
    """The shared env schema is documented at its new home, env.base.ts.

    Validates project_initializer/docs_generator.py generate_api_claude().
    """
    doc = _api_claude(auth)
    assert "src/config/env.base.ts" in doc and "baseEnvSchema" in doc


@pytest.mark.parametrize("auth", AUTHS)
def test_when_api_claude_generated_then_rollback_is_one_command_per_migration(auth):
    """Rollback is one command per migration; the P3012-prone resolve step may only be forbidden.

    Validates project_initializer/docs_generator.py generate_api_claude().
    """
    doc = _api_claude(auth)
    assert "npx prisma db execute --file prisma/migrations/<dir>/down.sql" in doc
    assert "newest first" in doc.lower()
    # `migrate resolve --rolled-back` fails with P3012 on an applied migration; the docs may
    # only name it to forbid it.
    for line in doc.splitlines():
        if "resolve --rolled-back" in line:
            assert "Do not use" in line, (
                f"rollback docs recommend a command that fails: {line}"
            )


@pytest.mark.parametrize("auth", AUTHS)
def test_when_api_claude_generated_then_traceability_convention_is_documented(auth):
    """The traceability convention names requirement and code, and says the templates ship no ids.

    Validates project_initializer/docs_generator.py generate_api_claude().
    """
    doc = _api_claude(auth)
    assert "[REQ-<AREA>-<NNN>]" in doc
    assert "Validates REQ-" in doc and "Validates ItemsService.remove()" in doc
    assert "ships none" in doc, "the templates carry no requirement ids"


@pytest.mark.parametrize("auth", AUTHS)
def test_when_api_claude_generated_then_lint_format_and_coverage_gate_are_documented(
    auth,
):
    """The lint, format and coverage-gate commands are documented.

    Validates project_initializer/docs_generator.py generate_api_claude().
    """
    doc = _api_claude(auth)
    for needle in ("npm run lint", "npm run format:check", "npm run test:cov", "75%"):
        assert needle in doc, f"{needle} missing from the NestJS api CLAUDE.md"


@pytest.mark.parametrize("auth", AUTHS)
def test_when_nestjs_docs_generated_then_the_jest_flag_is_documented(auth):
    """Every doc that lists the test commands says why the scripts pass the flag.

    A direct ``npx jest`` or an IDE runner skips the scripts, so the docs are the
    only place a scaffold user learns that it needs the flag too. ``jwks-rsa`` is
    named only in the Entra docs, the one variant that depends on it.

    Validates project_initializer/docs_generator.py generate_root_readme(), generate_api_readme() and generate_api_claude().
    """
    docs = (
        generate_root_readme("nestjs", auth),
        generate_api_readme("nestjs", auth=auth),
        generate_api_claude("nestjs", auth),
    )
    for doc in docs:
        assert "`--experimental-vm-modules`" in doc
        assert "`NODE_OPTIONS=--experimental-vm-modules`" in doc
        assert "Node 24.9" in doc
        assert "`@nestjs/common`" in doc and "`@nestjs/core`" in doc
        assert "`@nestjs/config`" in doc and "`@nestjs/terminus`" in doc
        assert ("`jwks-rsa`" in doc) == (auth == "entra")


def test_when_supabase_then_rls_and_init_rollback_replacement_are_documented():
    """Supabase docs cover RLS and the init down.sql that replaces the base one.

    Validates project_initializer/docs_generator.py generate_api_claude().
    """
    doc = _api_claude("supabase")
    assert "Row Level Security" in doc
    assert "enable_row_level_security" in doc
    assert "drops `profiles`, not `users`" in doc
    assert "SUPABASE_SECRET_KEY" not in doc


@pytest.mark.parametrize("auth", [None, "token", "entra"])
def test_when_not_supabase_then_rls_section_is_absent(auth):
    """Variants on local Postgres have no Data API, so no RLS how-to section.

    Validates project_initializer/docs_generator.py generate_api_claude().
    """
    assert "### Row Level Security" not in _api_claude(auth)


def test_when_token_then_secret_length_and_service_to_service_scope_are_documented():
    """Token docs state the 32-character floor, the service-to-service scope and the 200 probe.

    Validates project_initializer/docs_generator.py generate_api_claude().
    """
    doc = _api_claude("token")
    assert "at least 32 characters" in doc
    assert "service-to-service" in doc
    assert "200 with `authenticated: false`" in doc


def test_when_entra_then_scope_is_documented_as_compared_by_bare_name():
    """Entra docs state that the scope is compared by bare name and no POSTGRES_* is needed.

    Validates project_initializer/docs_generator.py generate_api_claude().
    """
    doc = _api_claude("entra")
    assert "bare name" in doc and "ENTRA_API_SCOPE" in doc
    assert "POSTGRES_" not in doc


@pytest.mark.parametrize("auth", AUTHS)
def test_when_module_lists_generated_then_auth_appears_only_with_auth(auth):
    """The module list names auth only when an auth mode is chosen.

    Validates project_initializer/docs_generator.py generate_root_claude(), generate_api_readme() and generate_api_claude().
    """
    claude = generate_root_claude("nestjs", auth)
    readme = generate_api_readme("nestjs", auth=auth)
    api = _api_claude(auth)
    for doc in (claude, readme, api):
        match = re.search(r"health, items, test(, auth)?", doc)
        assert match, "module list missing or reordered"
        assert bool(match.group(1)) is (auth is not None), (
            f"auth={auth}: module list says {match.group(0)!r}"
        )


@pytest.mark.parametrize("auth", AUTHS)
def test_when_root_docs_generated_then_prisma_is_not_called_global(auth):
    """The root CLAUDE.md and the api README must not call PrismaModule global.

    Validates project_initializer/docs_generator.py generate_root_claude() and generate_api_readme().
    """
    for doc in (
        generate_root_claude("nestjs", auth),
        generate_api_readme("nestjs", auth=auth),
    ):
        assert "Global PrismaModule" not in doc and "@Global()" not in doc
        assert "not global" in doc


@pytest.mark.parametrize("auth", AUTHS)
def test_when_root_readme_generated_then_generated_secret_is_explained_only_for_token(
    auth,
):
    """The root README explains the generated AUTH_TOKEN only where token auth generates one.

    Validates project_initializer/docs_generator.py generate_root_readme().
    """
    doc = generate_root_readme("nestjs", auth)
    assert ("generated random `AUTH_TOKEN`" in doc) is (auth == "token")
    assert ("`.env.example` leaves it empty" in doc) is (auth == "token")


def test_when_fastapi_docs_generated_then_nestjs_only_passages_are_absent():
    """NestJS-only passages never leak into the FastAPI docs.

    Validates project_initializer/docs_generator.py generate_root_claude(), generate_root_readme() and generate_api_claude() for FastAPI.
    """
    for doc in (
        generate_root_claude("fastapi", None),
        generate_root_readme("fastapi", None),
        generate_api_claude("fastapi", None),
    ):
        assert "app.auth.ts" not in doc


@pytest.mark.integration
@pytest.mark.parametrize("auth", AUTHS)
def test_when_nestjs_scaffolded_then_api_readme_lists_auth_module_only_with_auth(
    tmp_path, auth
):
    """The scaffold must hand the auth mode to the api README generator.

    Validates project_initializer/cli.py copy_template() writing api/README.md through project_initializer/docs_generator.py generate_api_readme().
    """
    copy_template(tmp_path, "app", auth=auth, framework="nestjs", scope="api")

    readme = (tmp_path / "api" / "README.md").read_text(encoding="utf-8")
    match = re.search(r"health, items, test(, auth)?", readme)
    assert match, "module list missing from the scaffolded api/README.md"
    assert bool(match.group(1)) is (auth is not None)

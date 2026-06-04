"""Capstone integration verification for the cycle (#21).

Confirms the three bug fixes hold end-to-end across every scaffold target:

* **Fast, unconditional** — all 9 scaffold commands exit 0 (via the real CLI),
  the generated NestJS ``prisma.service.ts`` wires conditional SSL (#17), and
  that file is byte-identical across the three NestJS auth variants (one
  inherited file, no override).
* **Heavy, opt-in** — a full ``npm install`` + ``npm run build`` proving the
  ``tsc-alias`` rewrite (#18) leaves no ``@generated/`` literal in ``dist`` and
  that ``node dist/src/main`` boots without a module-resolution error. Gated
  behind ``INTEGRATION_BUILD=1`` + ``npm`` on PATH so the default suite stays
  fast; the gate is a ``skipif`` with a reason (no silent skips).

Docker stack health (``GET /health`` 200) for the 6 fullstack variants is
exercised by the CI matrix in ``.github/workflows/test-package.yml`` (#20) and
is intentionally not duplicated here.
"""

import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from project_initializer.cli import copy_template

CLI = [sys.executable, "-m", "project_initializer.cli"]

# (id, CLI flags) — the 9 scaffold targets for the cycle.
SCAFFOLD_TARGETS = [
    ("fastapi", ["--fastapi"]),
    ("fastapi-token", ["--fastapi", "--auth", "token"]),
    ("fastapi-supabase", ["--fastapi", "--auth", "supabase"]),
    ("nestjs", ["--nestjs"]),
    ("nestjs-token", ["--nestjs", "--auth", "token"]),
    ("nestjs-supabase", ["--nestjs", "--auth", "supabase"]),
    ("fastapi-scope-api", ["--fastapi", "--scope", "api"]),
    ("nestjs-scope-api", ["--nestjs", "--scope", "api"]),
    ("frontend", ["--scope", "frontend"]),
]

# (id, copy_template kwargs) for the NestJS dirs that must build.
NESTJS_BUILD = [
    ("nestjs", {"framework": "nestjs"}),
    ("nestjs-token", {"framework": "nestjs", "auth": "token"}),
    ("nestjs-supabase", {"framework": "nestjs", "auth": "supabase"}),
    ("nestjs-scope-api", {"framework": "nestjs", "scope": "api"}),
]
NESTJS_AUTH_VARIANTS = [
    ("nestjs", {"framework": "nestjs"}),
    ("nestjs-token", {"framework": "nestjs", "auth": "token"}),
    ("nestjs-supabase", {"framework": "nestjs", "auth": "supabase"}),
]

_INTEGRATION_BUILD = (
    os.environ.get("INTEGRATION_BUILD") == "1" and shutil.which("npm") is not None
)
_skip_build = pytest.mark.skipif(
    not _INTEGRATION_BUILD,
    reason="heavy NestJS build; set INTEGRATION_BUILD=1 with npm on PATH to enable",
)


def _prisma_service(dest: Path) -> Path:
    return dest / "api" / "src" / "prisma" / "prisma.service.ts"


def _scaffold_inproc(dest: Path, **kwargs) -> Path:
    copy_template(dest, "app", **kwargs)
    return dest


# --- unconditional: every target scaffolds via the real CLI ----------------


@pytest.mark.parametrize(
    "variant,flags", SCAFFOLD_TARGETS, ids=[t[0] for t in SCAFFOLD_TARGETS]
)
def test_when_variant_scaffolded_cli_exits_zero(tmp_path, variant, flags):
    result = subprocess.run(
        CLI + [str(tmp_path / variant), *flags, "--force"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


# --- unconditional: conditional SSL is wired (#17) --------------------------


@pytest.mark.parametrize(
    "variant,kwargs", NESTJS_AUTH_VARIANTS, ids=[t[0] for t in NESTJS_AUTH_VARIANTS]
)
def test_when_nestjs_scaffolded_prisma_service_wires_conditional_ssl(
    tmp_path, variant, kwargs
):
    dest = _scaffold_inproc(tmp_path / variant, **kwargs)
    service = _prisma_service(dest).read_text(encoding="utf-8")
    util = (dest / "api" / "src" / "prisma" / "prisma-ssl.util.ts").read_text(
        encoding="utf-8"
    )
    assert "deriveSslOption" in service and "ssl" in service
    # The conditional itself: TLS branch + local-plaintext branch.
    assert "rejectUnauthorized: false" in util
    assert "localhost" in util


def test_when_three_nestjs_variants_scaffolded_prisma_service_is_byte_identical(
    tmp_path,
):
    digests = set()
    for variant, kwargs in NESTJS_AUTH_VARIANTS:
        dest = _scaffold_inproc(tmp_path / variant, **kwargs)
        digests.add(hashlib.sha256(_prisma_service(dest).read_bytes()).hexdigest())
    assert len(digests) == 1


# --- opt-in heavy: build proves the tsc-alias rewrite (#18) -----------------


def _run(cmd: list[str], cwd: Path) -> None:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    assert result.returncode == 0, f"{' '.join(cmd)} failed:\n{result.stderr}"


def _dist_files_with_alias(dist: Path) -> list[str]:
    return [
        str(p.relative_to(dist))
        for p in dist.rglob("*.js")
        if "@generated/" in p.read_text(encoding="utf-8")
    ]


def _assert_boots_without_module_error(api: Path) -> None:
    proc = subprocess.Popen(
        ["node", str(api / "dist" / "src" / "main")],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=api,
    )
    try:
        _, stderr = proc.communicate(timeout=12)
        pytest.fail(f"node exited early (code {proc.returncode}):\n{stderr.decode()}")
    except subprocess.TimeoutExpired:
        proc.kill()  # still running => booted past all requires
        _, stderr = proc.communicate()
    assert "Cannot find module" not in stderr.decode()


@_skip_build
@pytest.mark.parametrize(
    "variant,kwargs", NESTJS_BUILD, ids=[t[0] for t in NESTJS_BUILD]
)
def test_when_nestjs_variant_built_dist_has_no_generated_alias_and_boots(
    tmp_path, variant, kwargs
):
    api = _scaffold_inproc(tmp_path / variant, **kwargs) / "api"
    _run(["npm", "install", "--no-audit", "--no-fund"], api)  # guarded postinstall
    _run(["npm", "run", "build"], api)  # nest build && tsc-alias
    assert _dist_files_with_alias(api / "dist") == []
    _assert_boots_without_module_error(api)

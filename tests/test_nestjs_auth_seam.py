"""The NestJS auth seam: one ``src/app.auth.ts`` shared by every auth overlay.

``AppModule`` imports ``AUTH_MODULES`` and ``AUTH_GUARDS`` from ``src/app.auth.ts``.
The base layer ships an empty seam (no auth module, no guard); each auth overlay
replaces the file with the same wiring: ``AuthModule`` plus the global
``AccessTokenGuard``. What differs between token, supabase and entra is the
verifier behind ``AuthModule``, never this file, so three copies must stay
byte-identical. A copy that drifts would give one variant a different guard order
or a missing guard without any other test noticing.
"""

from pathlib import Path

import pytest

_PACKAGE = Path(__file__).resolve().parent.parent / "project_initializer"
_SEAM = Path("api") / "src" / "app.auth.ts"
_OVERLAYS = ("token", "supabase", "entra")


def _seam(layer: str) -> Path:
    return _PACKAGE / f"templates-{layer}-nestjs" / _SEAM


def test_when_the_auth_overlays_are_listed_then_each_ships_the_seam():
    """Each auth overlay replaces the base seam, or its routes would stay unguarded.

    Validates project_initializer/templates-{token,supabase,entra}-nestjs/api/src/app.auth.ts.
    """
    for overlay in _OVERLAYS:
        assert _seam(overlay).is_file(), (
            f"templates-{overlay}-nestjs has no app.auth.ts"
        )


def test_when_the_overlay_seams_are_compared_then_they_are_byte_identical():
    """The token, supabase and entra seams wire the same module and the same guard.

    Validates project_initializer/templates-{token,supabase,entra}-nestjs/api/src/app.auth.ts.
    """
    reference = _seam(_OVERLAYS[0]).read_bytes()

    for overlay in _OVERLAYS[1:]:
        assert _seam(overlay).read_bytes() == reference, (
            f"templates-{overlay}-nestjs/api/src/app.auth.ts differs from the "
            f"{_OVERLAYS[0]} copy; change all three together"
        )


@pytest.mark.parametrize("overlay", _OVERLAYS)
def test_when_an_overlay_seam_is_read_then_the_guard_follows_the_rate_limiter(
    overlay: str,
):
    """The seam registers ``AuthModule`` and a global ``AccessTokenGuard``.

    The guard is applied after the rate limiter, so a request that fails
    authentication still counts against the limit.

    Validates project_initializer/templates-{token,supabase,entra}-nestjs/api/src/app.auth.ts.
    """
    text = _seam(overlay).read_text(encoding="utf-8")

    assert "AUTH_MODULES: ReadonlyArray<Type<unknown>> = [AuthModule]" in text
    assert "{ provide: APP_GUARD, useClass: AccessTokenGuard }" in text
    assert "after the rate limiter" in text


def test_when_the_base_seam_is_read_then_it_registers_no_auth():
    """The no-auth variant ships an empty seam; the overlays are what add auth.

    Validates project_initializer/templates-api-nestjs/api/src/app.auth.ts.
    """
    text = (_PACKAGE / "templates-api-nestjs" / _SEAM).read_text(encoding="utf-8")

    assert "AUTH_MODULES: ReadonlyArray<Type<unknown>> = [];" in text
    assert "AUTH_GUARDS: ReadonlyArray<Provider> = [];" in text
    assert "import { AuthModule }" not in text
    assert "import { APP_GUARD }" not in text

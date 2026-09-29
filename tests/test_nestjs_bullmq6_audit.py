"""
Guard for the bullmq 6 upgrade (T4): the NestJS template must keep using only the
bullmq API surface that survived the 5 -> 6 major bump.

bullmq 6 removed several APIs (legacy repeatable jobs, ``Queue#client``, the ``debounce``
add-option) and dropped its bundled ioredis (now an explicit peer, added as a direct dep
in T2). Our template only uses ``@Processor``/``WorkerHost``/``OnWorkerEvent`` (the worker
abstraction), ``Queue`` enqueue/``getJob`` and ``BullModule.forRoot({ connection })`` — none
of the removed surface. These tests lock that so a later edit cannot silently reintroduce a
removed API. The live BullMQ -> ioredis -> Redis path is proved by the T5 readiness smoke.

Source-blind: template files are inspected as plain text; no runtime import is performed.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from hypothesis import given, strategies as st

REPO_ROOT = Path(__file__).resolve().parent.parent
TPL = REPO_ROOT / "project_initializer"

BASE_SRC = TPL / "templates-api-nestjs/api/src"
TOKEN_SRC = TPL / "templates-token-nestjs/api/src"
SUPABASE_SRC = TPL / "templates-supabase-nestjs/api/src"
ENTRA_SRC = TPL / "templates-entra-nestjs/api/src"

_ALL_SRC_ROOTS = [BASE_SRC, TOKEN_SRC, SUPABASE_SRC, ENTRA_SRC]

CHAT_PROCESSOR = BASE_SRC / "modules/chatbot/chat.processor.ts"
CHAT_JOB_SERVICE = BASE_SRC / "modules/chatbot/chat-job.service.ts"
CHATBOT_MODULE = BASE_SRC / "modules/chatbot/chatbot.module.ts"

_APP_MODULES = [
    (BASE_SRC / "app.module.ts", "base"),
    (TOKEN_SRC / "app.module.ts", "token"),
    (SUPABASE_SRC / "app.module.ts", "supabase"),
    (ENTRA_SRC / "app.module.ts", "entra"),
]

# Literal substrings that only appear when a removed bullmq 6 API is used. Each maps to why
# it is gone, so a violation message points the reader at the migration, not just the token.
REMOVED_BULLMQ6_APIS = {
    ".client": "Queue#client was removed in bullmq 6 — use the connection/getters instead",
    "getRepeatableJobs": "legacy repeatable-jobs API removed in bullmq 6 — use Job Schedulers",
    "removeRepeatableByKey": "legacy repeatable-jobs API removed in bullmq 6 — use Job Schedulers",
    "debounce": "the add-option `debounce` was removed in bullmq 6 — use deduplication",
}


# ── helpers ─────────────────────────────────────────────────────────────────────


def _read(path: Path) -> str:
    assert path.exists(), f"Expected template file not found: {path}"
    return path.read_text(encoding="utf-8")


def _removed_apis_in(text: str) -> list[str]:
    """Return the removed-bullmq-6 tokens present in ``text`` (empty when clean)."""
    return [token for token in REMOVED_BULLMQ6_APIS if token in text]


def _bullmq_touching_files(root: Path) -> list[Path]:
    """Non-spec .ts files under ``root`` that reference bullmq (queue/worker code)."""
    if not root.exists():
        return []
    return [
        p
        for p in root.rglob("*.ts")
        if ".spec." not in p.name and re.search(r"bullmq", p.read_text(encoding="utf-8"), re.I)
    ]


# ── removed-API guard ────────────────────────────────────────────────────────────


def test_when_bullmq_files_are_scanned_then_no_removed_bullmq6_api_is_used() -> None:
    """No bullmq-touching source file in any overlay may reference a removed bullmq 6 API.

    Reintroducing one compiles under @nestjs/bullmq's types but breaks at runtime against
    bullmq 6, which the unit suite would not catch — hence this static guard.
    """
    files = [f for root in _ALL_SRC_ROOTS for f in _bullmq_touching_files(root)]
    assert files, (
        "No bullmq-touching .ts files found — expected at least chat.processor.ts and "
        "chat-job.service.ts under templates-api-nestjs/."
    )
    violations = {
        str(f): found for f in files if (found := _removed_apis_in(_read(f)))
    }
    assert not violations, (
        "These files use a bullmq API removed in v6:\n"
        + "\n".join(
            f"  {path}: {', '.join(f'{t} ({REMOVED_BULLMQ6_APIS[t]})' for t in toks)}"
            for path, toks in violations.items()
        )
    )


# Completeness property — the detector must never miss an embedded removed token, whatever
# surrounds it, or the guard above would be a silent false-negative.
@given(
    prefix=st.text(),
    suffix=st.text(),
    token=st.sampled_from(sorted(REMOVED_BULLMQ6_APIS)),
)
def test_when_source_contains_a_removed_api_then_detector_flags_it(
    prefix: str, suffix: str, token: str
) -> None:
    """Invariant: _removed_apis_in returns any removed token embedded in arbitrary text."""
    assert token in _removed_apis_in(prefix + token + suffix)


# ── supported-surface guard (positive) ───────────────────────────────────────────


def test_when_processor_is_read_then_it_uses_the_supported_worker_api() -> None:
    """The chat processor must stay on the @nestjs/bullmq WorkerHost abstraction, which is
    unchanged across the bullmq 6 bump (unlike the removed standalone-Worker options)."""
    text = _read(CHAT_PROCESSOR)
    assert "WorkerHost" in text, "chat.processor.ts must extend WorkerHost"
    assert re.search(r"@Processor\(", text), "chat.processor.ts must use the @Processor decorator"


def test_when_job_service_is_read_then_it_enqueues_via_injected_queue() -> None:
    """Enqueue must go through an @InjectQueue-provided Queue with .add(), the supported
    bullmq 6 producer surface."""
    text = _read(CHAT_JOB_SERVICE)
    assert re.search(r"@InjectQueue\(", text), "chat-job.service.ts must inject the queue with @InjectQueue"
    assert re.search(r"\.add\(", text), "chat-job.service.ts must enqueue via queue.add()"


@pytest.mark.parametrize("app_module,label", _APP_MODULES)
def test_when_app_module_is_read_then_bull_module_forroot_wires_a_connection(
    app_module: Path, label: str
) -> None:
    """Every variant must configure BullModule.forRoot with a `connection`, the object bullmq 6
    hands to ioredis (its now-explicit peer) to reach Redis."""
    text = _read(app_module)
    assert re.search(r"BullModule\.forRoot", text), (
        f"[{label}] app.module.ts must configure BullModule.forRoot"
    )
    assert "connection" in text, (
        f"[{label}] BullModule.forRoot must pass a `connection` so bullmq 6 can build its "
        "ioredis connection to Redis"
    )

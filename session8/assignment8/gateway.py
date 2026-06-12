"""Bridge to llm_gatewayV8.

V8 is V7 plus three things: (1) every `/v1/chat` accepts an optional
`agent: str` tag the gateway logs and uses for cost-by-agent rollups
and provider pinning; (2) a `/v1/chat/batch` endpoint that runs N
chat requests concurrently with bounded parallelism — what the
DAG-style orchestrator hits when firing a ready batch; (3) one retry
on 5xx / timeout with `retries` surfaced in the response.

Auto-starts the gateway on port 8108 if it is not already up, then
re-exports the V8 `LLM` client and a module-level `embed()` helper.

GATEWAY_URL is read from `.env` (GATEWAY_URL=http://localhost:8108)
per the assignment's "no hardcoded ports/URLs" rule; the gateway dir
in this layout is a direct child of assignment8/, not a sibling.
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

GATEWAY_V8_DIR = Path(
    os.environ.get("EAGV3_GATEWAY_DIR")
    or (ROOT / "llm_gatewayV8")
).resolve()
GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8108")
# llm_gatewayV8/client.py reads its default base_url from LLM_GATEWAY_V8_URL.
# We don't write code inside llm_gatewayV8/, so we feed it our .env-derived
# GATEWAY_URL via the env var it already understands, before importing it.
os.environ.setdefault("LLM_GATEWAY_V8_URL", GATEWAY_URL)


def _is_up() -> bool:
    try:
        httpx.get(f"{GATEWAY_URL}/v1/routers", timeout=2.0)
        return True
    except Exception:
        return False


def ensure_gateway() -> None:
    """Start V8 if it is not already running. Idempotent."""
    if _is_up():
        return
    if not GATEWAY_V8_DIR.exists():
        raise RuntimeError(
            f"Gateway V8 directory not found at {GATEWAY_V8_DIR}. "
            "Build llm_gatewayV8 (Session 8 prerequisite) before running S8 code."
        )
    print(f"[gateway] launching llm_gatewayV8 from {GATEWAY_V8_DIR}")
    subprocess.Popen(
        ["uv", "run", "main.py"],
        cwd=str(GATEWAY_V8_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(45):
        time.sleep(1)
        if _is_up():
            print(f"[gateway] up on {GATEWAY_URL}")
            return
    raise RuntimeError(f"Gateway V8 failed to start within 45s. Check {GATEWAY_V8_DIR}")


# Load V8's client.py without polluting sys.path. The gateway dir has its
# own `schemas.py`, which would shadow ours if we put it on the path.
import importlib.util as _importlib_util

_client_path = GATEWAY_V8_DIR / "client.py"
if _client_path.exists():
    _spec = _importlib_util.spec_from_file_location("llm_gatewayV8_client", _client_path)
    _mod = _importlib_util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    LLM = _mod.LLM
else:
    LLM = None  # populated once V8 is built; importers should ensure_gateway() first


def embed(text: str, task_type: str = "retrieval_document") -> dict:
    """Compute an embedding for `text` via the gateway's embed endpoint.

    Returns the full response dict: `{embedding, dim, model, provider,
    latency_ms, ...}`. The chosen embedding model is fixed at the gateway
    level. Changing it invalidates every FAISS index built against the old
    vectors, so callers should treat the model as a project-level constant.
    """
    ensure_gateway()
    if LLM is None:
        raise RuntimeError(
            "Gateway V8 client unavailable. Confirm llm_gatewayV8/client.py exists."
        )
    return LLM().embed(text, task_type=task_type)


__all__ = ["ensure_gateway", "LLM", "GATEWAY_URL", "GATEWAY_V8_DIR", "embed"]

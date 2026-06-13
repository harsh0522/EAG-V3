"""Bridge to llm_gatewayV9.

V9 is V8 plus two things: (1) `/v1/vision` — typed shim for single-image
vision calls that the Browser skill's Layer-3 driver hits; (2) per-agent
USD pricing on `/v1/cost/by_agent` so the ledger surfaces dollars in
addition to tokens. V8's `agent` tagging, `/v1/chat/batch`, and retry-
on-5xx carry forward unchanged.

The session-version mapping (V9 for Session 9) lets V8 stay frozen for
Session 8.

Auto-starts the gateway on port 8109 if it is not already up, then
re-exports the V9 `LLM` client and a module-level `embed()` helper.
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

GATEWAY_V9_DIR = Path(__file__).resolve().parent / "llm_gatewayV9"
GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8109")


def _is_up() -> bool:
    try:
        httpx.get(f"{GATEWAY_URL}/v1/routers", timeout=2.0)
        return True
    except Exception:
        return False


def ensure_gateway() -> None:
    """Start V9 if it is not already running. Idempotent."""
    if _is_up():
        return
    if not GATEWAY_V9_DIR.exists():
        raise RuntimeError(
            f"Gateway V9 directory not found at {GATEWAY_V9_DIR}. "
            "Build llm_gatewayV9 (Session 9 prerequisite) before running S9 code."
        )
    print(f"[gateway] launching llm_gatewayV9 from {GATEWAY_V9_DIR}")
    subprocess.Popen(
        ["uv", "run", "main.py"],
        cwd=str(GATEWAY_V9_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(45):
        time.sleep(1)
        if _is_up():
            print(f"[gateway] up on {GATEWAY_URL}")
            return
    raise RuntimeError(f"Gateway V9 failed to start within 45s. Check {GATEWAY_V9_DIR}")


# Load V9's client.py without polluting sys.path. The gateway dir has its
# own `schemas.py`, which would shadow ours if we put it on the path.
import importlib.util as _importlib_util

_client_path = GATEWAY_V9_DIR / "client.py"
if _client_path.exists():
    _spec = _importlib_util.spec_from_file_location("llm_gatewayV9_client", _client_path)
    _mod = _importlib_util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)

    # Agents are pinned to a single provider via agent_routing.yaml, which
    # makes the gateway treat that pin as an explicit override: on a 502/503
    # (provider rate-limited or unavailable) it raises immediately instead of
    # failing over to an idle provider. Wrap `chat()` so callers still get a
    # fallback to groq/cerebras in that case, with a short pause between
    # attempts to give the rate limit a moment to clear.
    class LLM(_mod.LLM):
        _FALLBACK_PROVIDERS = ("groq", "cerebras")
        # RPM-based 429 backoff on the router is 60s (see router.py LIMITS).
        # If every provider is in cooldown at once (likely from rapid
        # repeated test runs), one pass through the list won't help — wait
        # out most of that window and try the whole cycle again.
        _MAX_ROUNDS = 3
        _ROUND_WAIT_S = 20

        def chat(self, *args, **kwargs):
            requested = kwargs.get("provider")
            providers_to_try = [requested]
            providers_to_try += [p for p in self._FALLBACK_PROVIDERS if p != requested]

            last_exc = None
            for round_num in range(self._MAX_ROUNDS):
                for i, provider in enumerate(providers_to_try):
                    attempt = dict(kwargs)
                    if provider is not None:
                        attempt["provider"] = provider
                    try:
                        return super().chat(*args, **attempt)
                    except httpx.HTTPStatusError as e:
                        if e.response.status_code not in (502, 503):
                            raise
                        last_exc = e
                        if i < len(providers_to_try) - 1:
                            print(
                                f"[gateway] {provider or 'pinned provider'} unavailable "
                                f"({e.response.status_code}); retrying with "
                                f"{providers_to_try[i + 1]}"
                            )
                            time.sleep(3)
                if round_num < self._MAX_ROUNDS - 1:
                    print(
                        f"[gateway] all providers unavailable "
                        f"({last_exc.response.status_code}); waiting "
                        f"{self._ROUND_WAIT_S}s for quota to recover "
                        f"(round {round_num + 1}/{self._MAX_ROUNDS})"
                    )
                    time.sleep(self._ROUND_WAIT_S)
            raise last_exc
else:
    LLM = None  # populated once V9 is built; importers should ensure_gateway() first


def embed(text: str, task_type: str = "retrieval_document") -> dict:
    """Compute an embedding for `text` via the gateway's embed endpoint."""
    ensure_gateway()
    if LLM is None:
        raise RuntimeError(
            "Gateway V9 client unavailable. Confirm llm_gatewayV9/client.py exists."
        )
    return LLM().embed(text, task_type=task_type)


__all__ = ["ensure_gateway", "LLM", "GATEWAY_URL", "GATEWAY_V9_DIR", "embed"]

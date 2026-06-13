"""Framework-free client for llm_gatewayV9.

Plain httpx — no LangChain, no provider SDKs. The shipped Browser skill
talks to the gateway over HTTP, the same way every other S-session skill
does. Provider rotation, retries, agent tagging are the gateway's job.

Two methods: `vision()` hits /v1/vision for Layer-3 set-of-marks calls,
`chat()` hits /v1/chat for Layer-2b a11y-text calls (no image, cheaper,
doesn't require a vision-capable provider). `cost_by_agent()` queries the
gateway's V8 ledger so tests can pull real numbers.
"""
from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Base URL must always come from .env — never hardcode the port (S9 rule).
GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8109")

# The browser agent is pinned to a single provider via agent_routing.yaml,
# which makes the gateway treat that pin as an explicit override: a 502/503
# (provider rate-limited or unavailable) is raised immediately instead of
# failing over to an idle provider. Retry with these providers in turn,
# pausing briefly between attempts, before giving up.
_FALLBACK_PROVIDERS = ("groq", "cerebras")

# RPM-based 429 backoff on the router is 60s (see llm_gatewayV9/router.py
# LIMITS). If every provider is in cooldown at once (likely from rapid
# repeated test runs), one pass through the list won't help — wait out most
# of that window and try the whole cycle again.
_MAX_ROUNDS = 3
_ROUND_WAIT_S = 20


async def _post_with_fallback(url: str, body: dict, timeout: float) -> dict:
    requested = body.get("provider")
    providers_to_try = [requested] + [p for p in _FALLBACK_PROVIDERS if p != requested]

    last_resp: httpx.Response | None = None
    for round_num in range(_MAX_ROUNDS):
        for i, provider in enumerate(providers_to_try):
            attempt = dict(body)
            if provider is not None:
                attempt["provider"] = provider
            else:
                attempt.pop("provider", None)
            async with httpx.AsyncClient(timeout=timeout) as c:
                r = await c.post(url, json=attempt)
            if r.status_code not in (502, 503):
                r.raise_for_status()
                return r.json()
            last_resp = r
            if i < len(providers_to_try) - 1:
                await asyncio.sleep(3)
        if round_num < _MAX_ROUNDS - 1:
            await asyncio.sleep(_ROUND_WAIT_S)
    last_resp.raise_for_status()


@dataclass
class GatewayResult:
    """Normalised reply from either /v1/vision or /v1/chat."""
    parsed: dict | None
    text: str
    provider: str
    model: str
    latency_ms: int
    input_tokens: int
    output_tokens: int


# Back-compat alias — the early SoM driver imports `VisionResult`.
VisionResult = GatewayResult


class V9Client:
    """One client, two methods: vision() and chat(). Both speak to V9."""
    def __init__(
        self,
        base_url: str = GATEWAY_URL,
        agent: str = "s9_browser",
        timeout: float = 120.0,
        session: Optional[str] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.agent = agent
        self.timeout = timeout
        # Default session tag for ledger attribution. Per-call overrides win.
        self.session = session

    @staticmethod
    def _normalise(d: dict) -> GatewayResult:
        return GatewayResult(
            parsed=d.get("parsed"),
            text=d.get("text") or "",
            provider=d.get("provider", ""),
            model=d.get("model", ""),
            latency_ms=int(d.get("latency_ms") or 0),
            input_tokens=int(d.get("input_tokens") or 0),
            output_tokens=int(d.get("output_tokens") or 0),
        )

    async def vision(
        self,
        image_data_url: str,
        prompt: str,
        *,
        schema: Optional[dict] = None,
        schema_name: str = "out",
        system: Optional[str] = None,
        max_tokens: int = 1024,
        session: Optional[str] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> GatewayResult:
        body: dict[str, Any] = {
            "image": image_data_url,
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": 0.0,
            "agent": self.agent,
        }
        if schema:        body["schema"] = schema
        if schema:        body["schema_name"] = schema_name
        if system:        body["system"] = system
        s = session or self.session
        if s:             body["session"] = s
        if model:         body["model"] = model
        if provider:      body["provider"] = provider

        data = await _post_with_fallback(f"{self.base_url}/v1/vision", body, self.timeout)
        return self._normalise(data)

    async def chat(
        self,
        prompt: str,
        *,
        schema: Optional[dict] = None,
        schema_name: str = "out",
        system: Optional[str] = None,
        max_tokens: int = 1024,
        session: Optional[str] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> GatewayResult:
        """Plain text-only call. Used by the Layer-2b a11y driver: legend +
        goal in, action JSON out. Skipping the image cuts ~1K input tokens
        per turn vs vision()."""
        body: dict[str, Any] = {
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.0,
            "agent": self.agent,
        }
        if schema:
            body["response_format"] = {
                "type": "json_schema", "schema": schema,
                "name": schema_name, "strict": True,
            }
        if system:    body["system"] = system
        s = session or self.session
        if s:         body["session"] = s
        if model:     body["model"] = model
        if provider:  body["provider"] = provider

        data = await _post_with_fallback(f"{self.base_url}/v1/chat", body, self.timeout)
        return self._normalise(data)

    async def cost_by_agent(self, agent: Optional[str] = None,
                            session: Optional[str] = None) -> dict:
        """Pull the V9 ledger for this agent/session — tests use it to
        report real numbers rather than wall-clock estimates."""
        params: dict[str, Any] = {}
        if agent:   params["agent"] = agent
        if session: params["session"] = session
        async with httpx.AsyncClient(timeout=self.timeout) as c:
            r = await c.get(f"{self.base_url}/v1/cost/by_agent", params=params)
            r.raise_for_status()
            return r.json()


# Back-compat alias.
V9VisionClient = V9Client


# ── module-level convenience wrappers (CLAUDE.md spec names) ─────────────────
# Thin pass-through over V9Client for callers that just want one-shot text or
# vision calls without managing a client instance. Internally everything still
# routes through V9Client.chat()/vision() — same gateway, same ledger tagging.
async def call_llm(prompt: str, system: Optional[str] = None, **kw: Any) -> GatewayResult:
    """One-shot text call to GATEWAY_URL/v1/chat."""
    return await V9Client().chat(prompt, system=system, **kw)


async def call_vision(image_b64: str, prompt: str, **kw: Any) -> GatewayResult:
    """One-shot vision call to GATEWAY_URL/v1/vision. `image_b64` may be a
    raw base64 PNG string or a ready-made `data:image/...;base64,...` URL —
    both are accepted by the gateway's /v1/vision endpoint."""
    image_data_url = image_b64 if image_b64.startswith("data:") else f"data:image/png;base64,{image_b64}"
    return await V9Client().vision(image_data_url, prompt, **kw)

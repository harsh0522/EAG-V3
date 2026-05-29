"""Decision: single LLM call, returns either an answer or a ToolCall."""
from __future__ import annotations
import asyncio
import json
import os
import time
from pathlib import Path

import httpx

import logger as log
from schemas import DecisionOutput, Goal, MemoryItem, ToolCall

GATEWAY_URL = os.getenv("LLM_GATEWAY_V7_URL", "http://localhost:8107")
_SYSTEM_PROMPT = Path(__file__).parent / "prompts" / "decision_system.md"
_ARTIFACT_DISPLAY_LIMIT = 8 * 1024  # 8 KB — large artifacts cause gateway 503s


class Decision:
    async def next_step(
        self,
        goal: Goal,
        hits: list[MemoryItem],
        attached: list[tuple[str, bytes]],
        history: list[dict],
        mcp_tools: list[dict],
    ) -> DecisionOutput:
        system = _SYSTEM_PROMPT.read_text(encoding="utf-8")

        # Memory hits — include chunk content for fact items
        hits_lines = []
        for h in hits:
            line = f"  {h.kind}: {h.descriptor}"
            if h.artifact_id:
                line += f" [handle: {h.artifact_id}]"
            if h.kind == "fact" and h.value.get("chunk"):
                line += f"\n    chunk: {h.value['chunk'][:400]}"
            hits_lines.append(line)
        hits_text = "\n".join(hits_lines) if hits_lines else "  (none)"

        # History (last 8)
        hist_lines = []
        for ev in history[-8:]:
            if ev["kind"] == "action":
                arg_str = json.dumps(ev.get("arguments", {}))[:80]
                art = f" → art:{ev['artifact_id']}" if ev.get("artifact_id") else ""
                hist_lines.append(
                    f"iter {ev['iter']} [{ev['goal_id']}] action {ev['tool']}({arg_str})"
                    f" → {ev.get('result_descriptor','')[:100]}{art}"
                )
            elif ev["kind"] == "answer":
                hist_lines.append(f"iter {ev['iter']} [{ev['goal_id']}] answer: {ev['text'][:100]}")
        hist_text = "\n".join(hist_lines) if hist_lines else "  (none)"

        # Attached artifacts
        art_section = ""
        if attached:
            parts = []
            for art_id, blob in attached:
                text = blob.decode("utf-8", errors="replace")
                if len(text) > _ARTIFACT_DISPLAY_LIMIT:
                    text = text[:_ARTIFACT_DISPLAY_LIMIT] + "\n[...truncated...]"
                parts.append(
                    f"--- {art_id} ({len(blob)} bytes) ---\n{text}\n--- end ---"
                )
            art_section = "\n\nATTACHED ARTIFACTS:\n" + "\n\n".join(parts)

        user_msg = (
            f"CURRENT GOAL: {goal.text}\n\n"
            f"MEMORY HITS:\n{hits_text}\n\n"
            f"HISTORY:\n{hist_text}"
            f"{art_section}"
        )

        t0 = time.time()
        resp = await _gateway_call(
            messages=[{"role": "user", "content": user_msg}],
            system=system,
            auto_route="decision",
            tools=mcp_tools if mcp_tools else None,
            tool_choice="auto" if mcp_tools else None,
            max_tokens=2048,
            temperature=0.7,
        )
        duration_ms = int((time.time() - t0) * 1000)

        tool_calls = resp.get("tool_calls", [])
        if tool_calls:
            tc = tool_calls[0]
            if isinstance(tc, dict):
                name = tc.get("name", "")
                arguments = tc.get("arguments", {})
            else:
                name = getattr(tc, "name", "")
                arguments = getattr(tc, "arguments", {})
            out = log.log_construct(DecisionOutput, tool_call=ToolCall(name=name, arguments=arguments))
        else:
            text = resp.get("text", "").strip() or "No answer generated."
            out = log.log_construct(DecisionOutput, answer=text)

        llm_meta = _build_llm_meta(resp, duration_ms)
        log.decision(log._CURRENT_ITER, out, goal_id=goal.id, llm_meta=llm_meta)
        return out


def _build_llm_meta(resp: dict, duration_ms: int) -> dict:
    rd = resp.get("router_decision")
    rd_dict = rd if isinstance(rd, dict) else (rd.model_dump() if rd and hasattr(rd, "model_dump") else None)
    return {
        "provider": resp.get("provider"),
        "model": resp.get("model"),
        "router_decision": rd_dict,
        "messages_in_tokens": resp.get("input_tokens", 0),
        "tokens_out": resp.get("output_tokens", 0),
        "reasoning_applied": resp.get("reasoning_applied", False),
        "cache_read_input_tokens": resp.get("cache_read_input_tokens", 0),
        "cache_creation_input_tokens": resp.get("cache_creation_input_tokens", 0),
        "fallback_used": bool(rd_dict and rd_dict.get("fallback_used")) if rd_dict else False,
        "duration_ms": duration_ms,
    }


async def _gateway_call(messages: list, **kwargs) -> dict:
    body = {"messages": messages}
    for k, v in kwargs.items():
        if v is not None:
            body[k] = v
    delays = [15, 30, 60]
    for attempt, wait in enumerate(delays + [None]):
        async with httpx.AsyncClient(timeout=180) as client:
            r = await client.post(f"{GATEWAY_URL}/v1/chat", json=body)
            if r.status_code == 503 and wait is not None:
                print(f"[gateway] 503 on attempt {attempt + 1}, retrying in {wait}s…")
                await asyncio.sleep(wait)
                continue
            r.raise_for_status()
            return r.json()

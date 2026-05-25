"""Perception: orchestrates goal decomposition, progress tracking, and artifact attachment."""
from __future__ import annotations
import json
import os
import time
from pathlib import Path
from typing import Any

import httpx

import logger as log
from schemas import Goal, MemoryItem, Observation

GATEWAY_URL = os.getenv("LLM_GATEWAY_V3_URL", "http://localhost:8101")
_SYSTEM_PROMPT = Path(__file__).parent / "prompts" / "perception_system.md"

_SYNTHESIS_KEYWORDS = {"synthesise", "synthesize", "extract", "list", "compare", "decide"}

_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "goals": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "done": {"type": "boolean"},
                    "attach_artifact_index": {"type": "integer"},
                },
                "required": ["text", "done"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["goals"],
    "additionalProperties": False,
}


class Perception:
    async def observe(
        self,
        query: str,
        hits: list[MemoryItem],
        history: list[dict],
        prior_goals: list[Goal],
        run_id: str,
    ) -> Observation:
        system = _SYSTEM_PROMPT.read_text(encoding="utf-8")

        # Build the hits section with artifact_index
        hits_lines = []
        for i, h in enumerate(hits):
            line = f"[{i}] kind={h.kind} descriptor={h.descriptor!r}"
            if h.artifact_id:
                line += f" artifact_index={i}"
            hits_lines.append(line)
        hits_text = "\n".join(hits_lines) if hits_lines else "(none)"

        # Build history section (last 8)
        hist_lines = []
        for ev in history[-8:]:
            if ev["kind"] == "action":
                arg_str = json.dumps(ev.get("arguments", {}))[:80]
                art = f" art={ev['artifact_id']}" if ev.get("artifact_id") else ""
                hist_lines.append(
                    f"iter {ev['iter']} action {ev['tool']}({arg_str}) "
                    f"→ {ev.get('result_descriptor','')[:80]}{art}"
                )
            elif ev["kind"] == "answer":
                hist_lines.append(f"iter {ev['iter']} answer goal={ev['goal_id']}: {ev['text'][:400]}")
        hist_text = "\n".join(hist_lines) if hist_lines else "(none)"

        # Build prior goals section
        if prior_goals:
            goals_lines = []
            for g in prior_goals:
                status = "done" if g.done else "open"
                art_str = f" attach={g.attach_artifact_id}" if g.attach_artifact_id else ""
                goals_lines.append(f"[{g.id}] [{status}] {g.text}{art_str}")
            goals_text = "\n".join(goals_lines)
        else:
            goals_text = "(none — this is the first iteration, decompose the query)"

        user_msg = (
            f"QUERY: {query}\n\n"
            f"MEMORY HITS (use artifact_index values for attach_artifact_index):\n{hits_text}\n\n"
            f"HISTORY (last 8 events):\n{hist_text}\n\n"
            f"PRIOR GOALS (preserve order, update done flags only):\n{goals_text}"
        )

        t0 = time.time()
        resp = await _gateway_call(
            messages=[{"role": "user", "content": user_msg}],
            system=system,
            provider="g",
            temperature=1.0,
            max_tokens=1024,
            response_format={
                "type": "json_schema",
                "schema": _OUTPUT_SCHEMA,
                "name": "Observation",
                "strict": True,
            },
        )
        duration_ms = int((time.time() - t0) * 1000)

        # Extract JSON
        parsed = resp.get("parsed") or {}
        if not parsed:
            text = resp.get("text", "").strip()
            # Strip markdown code fences
            if text.startswith("```"):
                text = "\n".join(text.split("\n")[1:])
                text = text.rstrip("`").strip()
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = {"goals": []}

        raw_goals = parsed.get("goals", [])

        # Assign goal ids by position; map attach_artifact_index → art: handle
        goals = []
        for i, g in enumerate(raw_goals):
            art_id = None
            idx = g.get("attach_artifact_index")
            if idx is not None:
                try:
                    idx = int(idx)
                    if 0 <= idx < len(hits) and hits[idx].artifact_id:
                        art_id = hits[idx].artifact_id
                except (ValueError, TypeError):
                    pass

            goals.append(Goal(
                id=f"g{i + 1}",
                text=g.get("text", f"goal {i+1}"),
                done=bool(g.get("done", False)),
                attach_artifact_id=art_id,
            ))

        # Force-attach web_search artifact to "read/fetch search results" goals
        if goals:
            first_open = next((g for g in goals if not g.done), None)
            if first_open is not None and first_open.attach_artifact_id is None:
                words = set(first_open.text.lower().split())
                is_read_results_goal = bool(
                    words & {"results", "result"}
                    and words & {"read", "fetch", "top", "search"}
                )
                if is_read_results_goal:
                    ws_hits = [h for h in hits if h.artifact_id and h.descriptor
                               and "web_search" in h.descriptor.lower()]
                    if ws_hits:
                        first_open.attach_artifact_id = ws_hits[-1].artifact_id

        # Force-attach safety net for Query D (synthesis keywords)
        if goals:
            first_open = next((g for g in goals if not g.done), None)
            if first_open is not None:
                words = set(first_open.text.lower().split())
                if words & _SYNTHESIS_KEYWORDS:
                    artifact_hits = [h for h in hits if h.artifact_id]
                    if artifact_hits and first_open.attach_artifact_id is None:
                        first_open.attach_artifact_id = artifact_hits[-1].artifact_id

        obs = Observation(goals=goals)

        # Build LLM meta for logger
        llm_meta = _build_llm_meta(resp, duration_ms, provider="g", temperature=1.0)
        log.perception(log._CURRENT_ITER, obs, llm_meta=llm_meta)
        log.pydantic_ok("Observation", {}, obs.model_dump())

        return obs


def _build_llm_meta(resp: dict, duration_ms: int, **kwargs) -> dict:
    rd = resp.get("router_decision")
    rd_dict = rd if isinstance(rd, dict) else (rd.model_dump() if rd and hasattr(rd, "model_dump") else rd)
    return {
        "provider": resp.get("provider", kwargs.get("provider")),
        "model": resp.get("model"),
        "router_decision": rd_dict,
        "messages_in_tokens": resp.get("input_tokens", 0),
        "tokens_out": resp.get("output_tokens", 0),
        "temperature": kwargs.get("temperature"),
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
    async with httpx.AsyncClient(timeout=180) as client:
        r = await client.post(f"{GATEWAY_URL}/v1/chat", json=body)
        r.raise_for_status()
        return r.json()

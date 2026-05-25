"""Structured event logger with stdout, JSONL file, and SSE dashboard sinks."""
from __future__ import annotations
import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_LOGS_DIR = Path(__file__).parent / "logs"
_CURRENT_RUN_ID: str = "init"
_CURRENT_ITER: int = 0
_LOG_FILE = None
_SSE_QUEUE: asyncio.Queue | None = None


def set_sse_queue(q: asyncio.Queue):
    global _SSE_QUEUE
    _SSE_QUEUE = q


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _open_log(run_id: str):
    global _LOG_FILE, _CURRENT_RUN_ID
    _CURRENT_RUN_ID = run_id
    _LOGS_DIR.mkdir(exist_ok=True)
    path = _LOGS_DIR / f"run-{run_id}.jsonl"
    _LOG_FILE = open(path, "a", encoding="utf-8")
    return path


def _close_log():
    global _LOG_FILE
    if _LOG_FILE:
        _LOG_FILE.flush()
        _LOG_FILE.close()
        _LOG_FILE = None


def _emit(event: dict):
    """Write to all three sinks."""
    event.setdefault("ts", _now())
    line = json.dumps(event, default=str)

    # stdout — short human-readable
    _print_human(event)

    # JSONL file
    if _LOG_FILE:
        _LOG_FILE.write(line + "\n")
        _LOG_FILE.flush()

    # SSE dashboard (non-blocking push)
    if _SSE_QUEUE is not None:
        try:
            _SSE_QUEUE.put_nowait(line)
        except asyncio.QueueFull:
            pass


def _print_human(ev: dict):
    role = ev.get("role", "")
    event = ev.get("event", "")
    it = ev.get("iter", "")
    prefix = f"[{role}.{event}]" if role else f"[{event}]"
    if it:
        prefix = f"[iter {it}] {prefix}"

    output = ev.get("output", {})
    inp = ev.get("input", {})

    if event == "iter_start":
        print(f"\n── iter {it} ──", flush=True)
        return

    if event == "run_start":
        q = inp.get("query", "")[:80]
        print(f"[run_start] run_id={ev.get('run_id')} query={q!r}", flush=True)
        return

    if event == "run_end":
        final = output.get("final", "")[:200]
        print(f"[run_end]   FINAL: {final}", flush=True)
        return

    if event == "all_done":
        print(f"[done] all {len(output.get('goals', []))} goals satisfied", flush=True)
        return

    if event == "memory_read" or event == "read":
        hits = output.get("hits_count", output.get("hits", []))
        count = hits if isinstance(hits, int) else len(hits)
        print(f"[memory.read]    {count} hits", flush=True)
        return

    if event == "remember":
        item = output.get("item")
        if item:
            print(f"[memory.remember] classified → {item.get('kind')}: {item.get('descriptor', '')[:60]}", flush=True)
        else:
            print(f"[memory.remember] no durable content", flush=True)
        return

    if event == "record_outcome":
        item = output.get("item", {})
        print(f"[memory.outcome]  {item.get('descriptor', '')[:80]}", flush=True)
        return

    if event == "observe":
        goals = output.get("goals", [])
        for g in goals:
            status = "[done]" if g.get("done") else "[open]"
            attach = f" attach={g.get('attach_artifact_id')}" if g.get("attach_artifact_id") else ""
            print(f"[perception]     {status} {g.get('text', '')[:70]}{attach}", flush=True)
        llm = ev.get("llm", {})
        if llm.get("router_decision"):
            rd = llm["router_decision"]
            if isinstance(rd, dict):
                print(f"                 router={rd.get('chosen_worker_provider','?')} tier={rd.get('tier','?')}", flush=True)
        return

    if event == "next_step":
        out = output.get("output", {})
        if out.get("tool_call"):
            tc = out["tool_call"]
            args_str = json.dumps(tc.get("arguments", {}))[:80]
            print(f"[decision]       TOOL_CALL: {tc.get('name')}({args_str})", flush=True)
        elif out.get("answer"):
            ans = out["answer"][:100]
            print(f"[decision]       ANSWER: {ans}", flush=True)
        return

    if event == "execute":
        tc = inp.get("tool_call", {})
        res = output.get("result_text", "")[:120]
        art = output.get("artifact_id")
        art_str = f" [art:{art}]" if art else ""
        print(f"[action]         → {res}{art_str}", flush=True)
        return

    if event == "guarded":
        print(f"[action.guarded] ⚠ artifact handle leaked as path/url: {inp.get('tool_call', {}).get('name')}", flush=True)
        return

    if event == "attach":
        print(f"[attach]         {output.get('art_id')} ({output.get('size_bytes')} bytes)", flush=True)
        return

    if event == "attach_dropped":
        print(f"[attach_dropped] {output.get('art_id')}: {output.get('reason')}", flush=True)
        return

    if event == "put":
        print(f"[artifacts.put]  {output.get('art_id')} ({output.get('size_bytes')} bytes, {inp.get('content_type')})", flush=True)
        return

    if event == "construct":
        model = inp.get("model", "?")
        ok = output.get("validated", True)
        mark = "✓" if ok else "✗"
        print(f"[pydantic {mark}]   {model}", flush=True)
        return

    if event == "error" and ev.get("role") == "pydantic":
        model = inp.get("model", "?")
        errs = output.get("errors", [])
        print(f"[pydantic ✗]   {model}: {errs}", flush=True)
        return


# ─── Public API ───────────────────────────────────────────────────────────────

def run_start(run_id: str, query: str):
    global _CURRENT_RUN_ID, _CURRENT_ITER
    _CURRENT_RUN_ID = run_id
    _CURRENT_ITER = 0
    _open_log(run_id)
    _emit({"run_id": run_id, "iter": 0, "role": "loop", "event": "run_start",
           "input": {"query": query}, "output": {}})


def run_end(run_id: str, final: str):
    _emit({"run_id": run_id, "iter": _CURRENT_ITER, "role": "loop", "event": "run_end",
           "input": {}, "output": {"final": final}})
    _close_log()


def iter_start(it: int):
    global _CURRENT_ITER
    _CURRENT_ITER = it
    _emit({"run_id": _CURRENT_RUN_ID, "iter": it, "role": "loop", "event": "iter_start",
           "input": {}, "output": {}})


def all_done(it: int, goals: list):
    _emit({"run_id": _CURRENT_RUN_ID, "iter": it, "role": "loop", "event": "all_done",
           "input": {}, "output": {"goals": [g.model_dump() for g in goals]}})


def attach(it: int, art_id: str, size: int):
    _emit({"run_id": _CURRENT_RUN_ID, "iter": it, "role": "loop", "event": "attach",
           "input": {}, "output": {"art_id": art_id, "size_bytes": size}})


def attach_dropped(it: int, art_id: str, reason: str):
    _emit({"run_id": _CURRENT_RUN_ID, "iter": it, "role": "loop", "event": "attach_dropped",
           "input": {}, "output": {"art_id": art_id, "reason": reason}})


def memory_remember(item):
    data = item.model_dump(mode="json") if item else None
    _emit({"run_id": _CURRENT_RUN_ID, "iter": 0, "role": "memory", "event": "remember",
           "input": {}, "output": {"item": data}})


def memory_read(it: int, hits: list):
    _emit({"run_id": _CURRENT_RUN_ID, "iter": it, "role": "memory", "event": "read",
           "input": {}, "output": {
               "hits_count": len(hits),
               "hits": [h.model_dump(mode="json") for h in hits],
           }})


def memory_record_outcome(it: int, item):
    _emit({"run_id": _CURRENT_RUN_ID, "iter": it, "role": "memory", "event": "record_outcome",
           "input": {}, "output": {"item": item.model_dump(mode="json")}})


def perception(it: int, observation, llm_meta: dict | None = None):
    ev: dict[str, Any] = {
        "run_id": _CURRENT_RUN_ID, "iter": it,
        "role": "perception", "event": "observe",
        "input": {}, "output": {"goals": [g.model_dump() for g in observation.goals]},
    }
    if llm_meta:
        ev["llm"] = llm_meta
    _emit(ev)


def decision(it: int, output, goal_id: str, llm_meta: dict | None = None):
    ev: dict[str, Any] = {
        "run_id": _CURRENT_RUN_ID, "iter": it,
        "role": "decision", "event": "next_step",
        "input": {"goal_id": goal_id},
        "output": {"output": output.model_dump()},
    }
    if llm_meta:
        ev["llm"] = llm_meta
    _emit(ev)


def action(it: int, tool_call, result_text: str, artifact_id: str | None, llm_meta: dict | None = None):
    ev: dict[str, Any] = {
        "run_id": _CURRENT_RUN_ID, "iter": it,
        "role": "action", "event": "execute",
        "input": {"tool_call": tool_call.model_dump()},
        "output": {"result_text": result_text[:500], "artifact_id": artifact_id},
    }
    if llm_meta:
        ev["llm"] = llm_meta
    _emit(ev)


def action_guarded(it: int, tool_call):
    _emit({"run_id": _CURRENT_RUN_ID, "iter": it, "role": "action", "event": "guarded",
           "input": {"tool_call": tool_call.model_dump()},
           "output": {"reason": "artifact handle passed as path/url"}})


def artifact_put(art_id: str, size_bytes: int, content_type: str, source: str, descriptor: str):
    _emit({"run_id": _CURRENT_RUN_ID, "iter": _CURRENT_ITER,
           "role": "artifacts", "event": "put",
           "input": {"content_type": content_type, "source": source, "descriptor": descriptor},
           "output": {"art_id": art_id, "size_bytes": size_bytes}})


def pydantic_ok(model: str, data: dict, result: dict):
    _emit({"run_id": _CURRENT_RUN_ID, "iter": _CURRENT_ITER,
           "role": "pydantic", "event": "construct",
           "input": {"model": model, "data": _safe_truncate(data)},
           "output": {"validated": True, "errors": [], "result": _safe_truncate(result)}})


def pydantic_err(model: str, data: dict, errors: list):
    _emit({"run_id": _CURRENT_RUN_ID, "iter": _CURRENT_ITER,
           "role": "pydantic", "event": "error",
           "input": {"model": model, "data": _safe_truncate(data)},
           "output": {"validated": False, "errors": errors}})


def gateway_call(role: str, meta: dict):
    _emit({"run_id": _CURRENT_RUN_ID, "iter": _CURRENT_ITER,
           "role": "gateway", "event": "call",
           "input": {"role": role}, "output": meta})


def error(exc: Exception):
    _emit({"run_id": _CURRENT_RUN_ID, "iter": _CURRENT_ITER,
           "role": "loop", "event": "error",
           "input": {}, "output": {"error": str(exc)}})


def _safe_truncate(d: Any, max_len: int = 500) -> Any:
    if isinstance(d, dict):
        return {k: _safe_truncate(v) for k, v in list(d.items())[:20]}
    if isinstance(d, (list, tuple)):
        return [_safe_truncate(v) for v in d[:10]]
    if isinstance(d, str) and len(d) > max_len:
        return d[:max_len] + "…"
    return d


def log_construct(model_cls, **data):
    """Construct a Pydantic model, logging success/failure."""
    from pydantic import ValidationError
    try:
        obj = model_cls(**data)
        pydantic_ok(model=model_cls.__name__, data=data, result=obj.model_dump(mode="json"))
        return obj
    except ValidationError as e:
        pydantic_err(model=model_cls.__name__, data=data, errors=e.errors())
        raise

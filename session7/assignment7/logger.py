"""Structured event logger with stdout and JSONL file sinks."""
from __future__ import annotations
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
    event.setdefault("ts", _now())
    line = json.dumps(event, default=str)
    _print_human(event)
    if _LOG_FILE:
        _LOG_FILE.write(line + "\n")
        _LOG_FILE.flush()


def _print_human(ev: dict):
    role = ev.get("role", "")
    event = ev.get("event", "")
    it = ev.get("iter", "")

    if event == "iter_start":
        print(f"\n── iter {it} ──", file=sys.stderr, flush=True)
        return

    if event == "run_start":
        q = ev.get("input", {}).get("query", "")[:80]
        print(f"[run_start] run_id={ev.get('run_id')} query={q!r}", file=sys.stderr, flush=True)
        return

    if event == "run_end":
        final = ev.get("output", {}).get("final", "")[:200]
        print(f"[run_end]   FINAL: {final}", file=sys.stderr, flush=True)
        return

    if event == "all_done":
        print(f"[done] all {len(ev.get('output', {}).get('goals', []))} goals satisfied", file=sys.stderr, flush=True)
        return

    if event in ("memory_read", "read"):
        output = ev.get("output", {})
        hits = output.get("hits_count", output.get("hits", []))
        count = hits if isinstance(hits, int) else len(hits)
        method = output.get("method", "")
        method_str = f" via {method}" if method else ""
        print(f"[memory.read]    {count} hits{method_str}", file=sys.stderr, flush=True)
        return

    if event == "remember":
        item = ev.get("output", {}).get("item")
        if item:
            print(f"[memory.remember] classified → {item.get('kind')}: {item.get('descriptor', '')[:60]}", file=sys.stderr, flush=True)
        else:
            print(f"[memory.remember] no durable content", file=sys.stderr, flush=True)
        return

    if event == "record_outcome":
        item = ev.get("output", {}).get("item", {})
        print(f"[memory.outcome]  {item.get('descriptor', '')[:80]}", file=sys.stderr, flush=True)
        return

    if event == "add_fact":
        print(f"[memory.add_fact] {ev.get('output', {}).get('descriptor', '')[:60]}", file=sys.stderr, flush=True)
        return

    if event == "observe":
        goals = ev.get("output", {}).get("goals", [])
        for g in goals:
            status = "[done]" if g.get("done") else "[open]"
            attach = f" attach={g.get('attach_artifact_id')}" if g.get("attach_artifact_id") else ""
            print(f"[perception]     {status} {g.get('text', '')[:70]}{attach}", file=sys.stderr, flush=True)
        llm = ev.get("llm", {})
        if llm.get("router_decision"):
            rd = llm["router_decision"]
            if isinstance(rd, dict):
                print(f"                 router={rd.get('chosen_worker_provider','?')} tier={rd.get('tier','?')}", file=sys.stderr, flush=True)
        return

    if event == "next_step":
        out = ev.get("output", {}).get("output", {})
        if out.get("tool_call"):
            tc = out["tool_call"]
            args_str = json.dumps(tc.get("arguments", {}))[:80]
            print(f"[decision]       TOOL_CALL: {tc.get('name')}({args_str})", file=sys.stderr, flush=True)
        elif out.get("answer"):
            print(f"[decision]       ANSWER: {out['answer'][:100]}", file=sys.stderr, flush=True)
        return

    if event == "execute":
        tc = ev.get("input", {}).get("tool_call", {})
        res = ev.get("output", {}).get("result_text", "")[:120]
        art = ev.get("output", {}).get("artifact_id")
        art_str = f" [art:{art}]" if art else ""
        print(f"[action]         → {res}{art_str}", file=sys.stderr, flush=True)
        return

    if event == "guarded":
        print(f"[action.guarded] ⚠ artifact handle leaked as path/url: {ev.get('input', {}).get('tool_call', {}).get('name')}", file=sys.stderr, flush=True)
        return

    if event == "attach":
        print(f"[attach]         {ev.get('output', {}).get('art_id')} ({ev.get('output', {}).get('size_bytes')} bytes)", file=sys.stderr, flush=True)
        return

    if event == "attach_dropped":
        print(f"[attach_dropped] {ev.get('output', {}).get('art_id')}: {ev.get('output', {}).get('reason')}", file=sys.stderr, flush=True)
        return

    if event == "put":
        print(f"[artifacts.put]  {ev.get('output', {}).get('art_id')} ({ev.get('output', {}).get('size_bytes')} bytes, {ev.get('input', {}).get('content_type')})", file=sys.stderr, flush=True)
        return

    if event == "construct":
        model = ev.get("input", {}).get("model", "?")
        ok = ev.get("output", {}).get("validated", True)
        mark = "✓" if ok else "✗"
        print(f"[pydantic {mark}]   {model}", file=sys.stderr, flush=True)
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


def memory_read(it: int, hits: list, method: str = ""):
    _emit({"run_id": _CURRENT_RUN_ID, "iter": it, "role": "memory", "event": "read",
           "input": {}, "output": {
               "hits_count": len(hits),
               "method": method,
               "hits": [h.model_dump(mode="json") for h in hits],
           }})


def memory_record_outcome(it: int, item):
    _emit({"run_id": _CURRENT_RUN_ID, "iter": it, "role": "memory", "event": "record_outcome",
           "input": {}, "output": {"item": item.model_dump(mode="json")}})


def memory_add_fact(it: int, descriptor: str):
    _emit({"run_id": _CURRENT_RUN_ID, "iter": it, "role": "memory", "event": "add_fact",
           "input": {}, "output": {"descriptor": descriptor}})


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


def action(it: int, tool_call, result_text: str, artifact_id: str | None):
    ev: dict[str, Any] = {
        "run_id": _CURRENT_RUN_ID, "iter": it,
        "role": "action", "event": "execute",
        "input": {"tool_call": tool_call.model_dump()},
        "output": {"result_text": result_text[:500], "artifact_id": artifact_id},
    }
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
    from pydantic import ValidationError
    try:
        obj = model_cls(**data)
        pydantic_ok(model=model_cls.__name__, data=data, result=obj.model_dump(mode="json"))
        return obj
    except ValidationError as e:
        pydantic_err(model=model_cls.__name__, data=data, errors=e.errors())
        raise

#!/usr/bin/env python3
"""Entry point for the Session 8 DAG agent.

    python run.py "<query>"
    python run.py "" --resume <session_id>

Loads `.env`, sets up four timestamped log files under `logs/`, runs the
agent through `flow.Executor` (orchestrator — not modified), then writes
a node-trace log, a gateway-calls log (read back from the V8 SQLite
ledger), and a cost-summary log (read back from `/v1/cost/by_agent`).
Prints the final answer, the session id, and the replay-viewer URL.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

from flow import Executor
from gateway import GATEWAY_URL, GATEWAY_V8_DIR
from persistence import SessionStore
from schemas import AgentResult, NodeState

LOG_DIR = ROOT / "logs"
TS_FMT = "%Y-%m-%d %H:%M:%S"


# ── stdout tee — agent_run log mirrors everything flow.py prints ────────────

class _Tee:
    """Writes to the real stdout and a timestamped log file. flow.py's
    Executor narrates the run with plain `print()` (session banner, per-node
    status lines, recovery/critic notes); we are not allowed to modify
    flow.py, so we capture that narrative verbatim into agent_run_<ts>.log
    by mirroring stdout rather than re-deriving the same lines twice."""

    def __init__(self, *streams):
        self._streams = streams

    def write(self, data):
        for s in self._streams:
            s.write(data)
            s.flush()

    def flush(self):
        for s in self._streams:
            s.flush()


# ── post-run log builders ────────────────────────────────────────────────────

def _write_node_trace(states: list[NodeState], path: Path) -> None:
    lines = []
    for st in states:
        ts = datetime.fromtimestamp(st.completed_at or st.started_at or time.time()).strftime(TS_FMT)
        r: AgentResult | None = st.result
        lines.append(f"[{ts}] NODE {st.node_id} {st.skill} status={st.status} retries={st.retries}")
        lines.append(f"    inputs: {st.inputs}")
        if st.prompt_sent:
            lines.append(f"    prompt_sent (truncated): {st.prompt_sent[:500]!r}")
        if r is not None:
            lines.append(f"    output: {json.dumps(r.output, default=str)[:500]}")
            if r.artifacts:
                lines.append(f"    artifacts: {r.artifacts}")
            lines.append(f"    success={r.success} provider={r.provider} "
                         f"cost={r.cost:.5f} elapsed_s={r.elapsed_s:.2f}")
            if r.error:
                lines.append(f"    error: {r.error[:500]}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _gateway_calls(session_id: str) -> list[dict]:
    db_path = GATEWAY_V8_DIR / "gateway_v8.db"
    if not db_path.exists():
        return []
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT ts, agent, provider, model, input_tokens, output_tokens, "
            "latency_ms, status FROM calls WHERE session = ? ORDER BY ts",
            (session_id,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except sqlite3.Error:
        return []


def _write_gateway_calls_log(session_id: str, path: Path) -> list[dict]:
    calls = _gateway_calls(session_id)
    lines = []
    if not calls:
        lines.append(f"[{datetime.now().strftime(TS_FMT)}] no gateway calls recorded "
                     f"for session={session_id} (ledger empty or gateway not reachable)")
    for c in calls:
        ts = datetime.fromtimestamp(c["ts"]).strftime(TS_FMT)
        lines.append(
            f"[{ts}] agent={c.get('agent')} session={session_id} "
            f"model={c.get('model')} provider={c.get('provider')} "
            f"in_tok={c.get('input_tokens')} out_tok={c.get('output_tokens')} "
            f"latency_ms={c.get('latency_ms')} status={c.get('status')}"
        )
    path.write_text("\n".join(lines), encoding="utf-8")
    return calls


def _cost_by_agent(session_id: str) -> dict:
    import httpx
    try:
        r = httpx.get(f"{GATEWAY_URL}/v1/cost/by_agent", params={"session": session_id}, timeout=10.0)
        r.raise_for_status()
        return r.json()
    except Exception:
        return {}


def _write_cost_summary(session_id: str, by_agent: dict, path: Path) -> None:
    lines = [f"[{datetime.now().strftime(TS_FMT)}] cost summary for session={session_id}"]
    total_in = total_out = total_calls = 0
    for agent, rows in sorted(by_agent.items()):
        for r in rows:
            total_in += r.get("in_tok") or 0
            total_out += r.get("out_tok") or 0
            total_calls += r.get("calls") or 0
            lines.append(
                f"  agent={agent:16s} provider={r.get('provider'):12s} "
                f"calls={r.get('calls')} in_tok={r.get('in_tok')} "
                f"out_tok={r.get('out_tok')} errors={r.get('errors')}"
            )
    lines.append(f"  TOTAL calls={total_calls} input_tokens={total_in} output_tokens={total_out}")
    payload = {
        "session": session_id,
        "by_agent": by_agent,
        "total_input_tokens": total_in,
        "total_output_tokens": total_out,
    }
    lines.append("")
    lines.append(json.dumps(payload, indent=2))
    path.write_text("\n".join(lines), encoding="utf-8")


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("query", nargs="?", default="")
    parser.add_argument("--resume", default=None)
    args = parser.parse_args()

    LOG_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_paths = {
        "agent_run": LOG_DIR / f"agent_run_{ts}.log",
        "node_trace": LOG_DIR / f"node_trace_{ts}.log",
        "gateway_calls": LOG_DIR / f"gateway_calls_{ts}.log",
        "cost_summary": LOG_DIR / f"cost_summary_{ts}.log",
    }

    session_id = args.resume or f"s8-{uuid.uuid4().hex[:8]}"

    real_stdout = sys.stdout
    log_f = open(log_paths["agent_run"], "w", encoding="utf-8")
    sys.stdout = _Tee(real_stdout, log_f)
    try:
        print(f"[{datetime.now().strftime(TS_FMT)}] SESSION {session_id}")
        print(f"[{datetime.now().strftime(TS_FMT)}] QUERY: {args.query!r}"
              + (f"  (--resume {args.resume})" if args.resume else ""))

        t0 = time.time()
        answer = asyncio.run(Executor().run(
            args.query, session_id=session_id, resume=bool(args.resume),
        ))
        wall_clock = time.time() - t0
        print(f"[{datetime.now().strftime(TS_FMT)}] SESSION COMPLETE "
              f"wall_clock={wall_clock:.2f}s")
    finally:
        sys.stdout = real_stdout
        log_f.close()

    # Post-run logs assembled from the persisted session + gateway ledger.
    store = SessionStore(session_id)
    states = sorted(store.read_all_nodes(), key=lambda s: s.completed_at or s.started_at or 0)
    _write_node_trace(states, log_paths["node_trace"])
    calls = _write_gateway_calls_log(session_id, log_paths["gateway_calls"])
    by_agent = _cost_by_agent(session_id)
    _write_cost_summary(session_id, by_agent, log_paths["cost_summary"])

    print(f"\nAnswer:\n{answer}")
    print(f"\nSession ID: {session_id}")
    print(f"Logs:       {LOG_DIR}")
    print(f"Viewer:     file://{(ROOT / 'viewer' / 'index.html').resolve()}"
          f"?session={session_id}")
    print(f"            (or: python -m http.server 8200, then "
          f"http://localhost:8200/viewer/index.html?session={session_id})")


if __name__ == "__main__":
    main()

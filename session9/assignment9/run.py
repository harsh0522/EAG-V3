"""Entry point for the Session 9 Browser Comparison Agent.

    python run.py "Compare top 3 Hugging Face text-generation models sorted by likes"

Loads .env, sets up timestamped logging under logs/, runs the agent via
flow.py's Executor, persists a replay-ready trace under
state/sessions/<run_id>/, and prints the viewer URL.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import shutil
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

import httpx

from flow import Executor
from gateway import GATEWAY_URL, GATEWAY_V9_DIR
from persistence import SessionStore
from schemas import AgentResult, NodeState

LOG_DIR = ROOT / "logs"
SESSIONS_ROOT = ROOT / "state" / "sessions"

LOG_FORMAT = "[%(asctime)s] [%(levelname)s] [%(module)s] %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


# ── setup helpers ────────────────────────────────────────────────────────────

def _file_and_stdout_logger(name: str, path: Path, *, propagate: bool = True) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = propagate
    fmt = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
    fh = logging.FileHandler(path, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    if not propagate:
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(fmt)
        logger.addHandler(sh)
    return logger


def _setup_logging(ts: str) -> dict[str, Path]:
    LOG_DIR.mkdir(exist_ok=True)
    paths = {
        "agent_run": LOG_DIR / f"agent_run_{ts}.log",
        "browser_actions": LOG_DIR / f"browser_actions_{ts}.log",
        "gateway_calls": LOG_DIR / f"gateway_calls_{ts}.log",
        "cost_summary": LOG_DIR / f"cost_summary_{ts}.log",
    }
    # Root logger -> agent_run.log + stdout. Every module that does
    # `logging.getLogger(__name__)` (or plain `print`, which we leave alone
    # for flow.py's existing banner output) lands here.
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers[:] = []
    fmt = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
    fh = logging.FileHandler(paths["agent_run"], encoding="utf-8")
    fh.setFormatter(fmt)
    root.addHandler(fh)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    root.addHandler(sh)

    # browser.actions -> its own file (+ stdout), not the agent_run log.
    _file_and_stdout_logger("browser.actions", paths["browser_actions"], propagate=False)
    return paths


def _slugify(goal: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "", goal.lower())
    return (s[:6] or "run000")


def _make_run_id(goal: str) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{ts}_{_slugify(goal)}"


# ── post-run trace assembly ──────────────────────────────────────────────────

def _node_summary(state: NodeState) -> dict:
    r: AgentResult | None = state.result
    recovered = state.status == "complete" and state.retries > 0
    return {
        "node_id": state.node_id,
        "skill": state.skill,
        "status": "recovered" if recovered else state.status,
        "inputs": state.inputs,
        "metadata_keys": [],
        "retries": state.retries,
        "started_at": state.started_at,
        "completed_at": state.completed_at,
        "elapsed_s": (r.elapsed_s if r else None),
        "provider": (r.provider if r else None),
        "success": (r.success if r else None),
        "error": (r.error if r else None),
        "error_code": (r.error_code if r else None),
        "output": (r.output if r else None),
        "prompt_sent": state.prompt_sent,
    }


def _write_trace(store: SessionStore, run_id: str, query: str,
                 final_answer: str, out_dir: Path) -> list[dict]:
    states = sorted(store.read_all_nodes(), key=lambda s: s.completed_at or s.started_at or 0)
    graph = store.read_graph()
    edges = list(graph.edges()) if graph is not None else []
    nodes = [_node_summary(s) for s in states]
    trace = {
        "run_id": run_id,
        "query": query,
        "final_answer": final_answer,
        "nodes": nodes,
        "edges": [{"source": u, "target": v} for u, v in edges],
    }
    (out_dir / "trace.json").write_text(json.dumps(trace, indent=2, default=str))
    return nodes


def _write_browser_output(nodes: list[dict], out_dir: Path) -> dict | None:
    for n in nodes:
        if n["skill"] == "browser" and n["output"]:
            (out_dir / "browser_output.json").write_text(json.dumps(n["output"], indent=2))
            return n["output"]
    return None


def _write_final_table(nodes: list[dict], out_dir: Path) -> str:
    table_md = ""
    for n in reversed(nodes):
        if n["skill"] == "formatter" and n["output"]:
            table_md = n["output"].get("final_answer", "") or ""
            break
    (out_dir / "final_table.md").write_text(table_md)
    return table_md


def _copy_screenshots(run_id: str, out_dir: Path) -> int:
    """Layer-3 turn screenshots land under
    state/sessions/<sid>/browser/browser_<ts>/vision/turn_NN_marked.png —
    the viewer expects them flattened at screenshots/turn_<N>_annotated.png."""
    src_root = SESSIONS_ROOT / run_id / "browser"
    dst = out_dir / "screenshots"
    if not src_root.exists():
        return 0
    count = 0
    for marked in sorted(src_root.glob("**/vision/turn_*_marked.png")):
        m = re.search(r"turn_(\d+)_marked\.png", marked.name)
        if not m:
            continue
        dst.mkdir(parents=True, exist_ok=True)
        turn = int(m.group(1))
        shutil.copyfile(marked, dst / f"turn_{turn}_annotated.png")
        count += 1
    return count


def _gateway_calls(run_id: str) -> list[dict]:
    db_path = GATEWAY_V9_DIR / "gateway_v9.db"
    if not db_path.exists():
        return []
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT ts, agent, provider, model, input_tokens, output_tokens, "
            "latency_ms, status FROM calls WHERE session = ? ORDER BY ts",
            (run_id,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except sqlite3.Error:
        return []


def _write_gateway_calls_log(run_id: str, path: Path) -> list[dict]:
    calls = _gateway_calls(run_id)
    logger = _file_and_stdout_logger("gateway.calls", path, propagate=False)
    if not calls:
        logger.info("no gateway calls recorded for session=%s (ledger empty or gateway not running)", run_id)
    for c in calls:
        ts = datetime.fromtimestamp(c["ts"]).strftime(DATE_FORMAT)
        logger.info(
            "endpoint=%s model=%s input_tokens=%s output_tokens=%s latency_ms=%s status=%s [%s]",
            c.get("agent"), c.get("model"), c.get("input_tokens"),
            c.get("output_tokens"), c.get("latency_ms"), c.get("status"), ts,
        )
    return calls


def _cost_by_agent(run_id: str) -> dict:
    try:
        r = httpx.get(f"{GATEWAY_URL}/v1/cost/by_agent", params={"session": run_id}, timeout=10.0)
        r.raise_for_status()
        return r.json()
    except Exception:
        return {}


def _write_cost_summary(run_id: str, nodes: list[dict], calls: list[dict],
                        cost_by_agent: dict, log_path: Path, out_dir: Path) -> None:
    turns_by_layer: dict[str, int] = {}
    for n in nodes:
        if n["skill"] == "browser" and n["output"]:
            path = n["output"].get("path")
            turns = n["output"].get("turns", 0)
            if path:
                turns_by_layer[path] = turns_by_layer.get(path, 0) + turns

    total_in = sum(c.get("input_tokens") or 0 for c in calls)
    total_out = sum(c.get("output_tokens") or 0 for c in calls)
    total_cost = 0.0
    for rows in cost_by_agent.values():
        for r in rows:
            try:
                total_cost += float(str(r.get("dollars", "0")).lstrip("$") or 0)
            except ValueError:
                pass

    cost = {
        "total_tokens": total_in + total_out,
        "input_tokens": total_in,
        "output_tokens": total_out,
        "total_cost": total_cost,
        "turns_by_layer": turns_by_layer,
    }
    (out_dir / "cost.json").write_text(json.dumps(cost, indent=2))

    logger = _file_and_stdout_logger("cost.summary", log_path, propagate=False)
    logger.info("run_id=%s", run_id)
    for layer, turns in turns_by_layer.items():
        logger.info("layer=%s total_turns=%d", layer, turns)
    logger.info("total_tokens=%d (in=%d, out=%d)", total_in + total_out, total_in, total_out)
    logger.info("total_cost=$%.6f", total_cost)
    for agent, rows in cost_by_agent.items():
        for r in rows:
            logger.info("agent=%s provider=%s calls=%s in_tok=%s out_tok=%s dollars=%s",
                        agent, r.get("provider"), r.get("calls"),
                        r.get("in_tok"), r.get("out_tok"), r.get("dollars"))


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    if len(sys.argv) < 2:
        print('usage: python run.py "<goal>"')
        sys.exit(2)
    goal = " ".join(sys.argv[1:])

    run_id = _make_run_id(goal)
    ts = run_id.split("_", 2)[0] + "_" + run_id.split("_", 2)[1]
    log_paths = _setup_logging(ts)

    run_log = logging.getLogger("run")
    run_log.info("goal received: %s", goal)
    run_log.info("run_id=%s", run_id)

    out_dir = SESSIONS_ROOT / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    final_answer = asyncio.run(Executor().run(goal, session_id=run_id))
    elapsed = time.time() - t0
    run_log.info("run complete in %.1fs", elapsed)

    store = SessionStore(run_id)
    nodes = _write_trace(store, run_id, goal, final_answer, out_dir)
    _write_browser_output(nodes, out_dir)
    _write_final_table(nodes, out_dir)
    n_shots = _copy_screenshots(run_id, out_dir)
    if n_shots:
        run_log.info("copied %d Layer-3 screenshot(s) to %s", n_shots, out_dir / "screenshots")

    calls = _write_gateway_calls_log(run_id, log_paths["gateway_calls"])
    cost_by_agent = _cost_by_agent(run_id)
    _write_cost_summary(run_id, nodes, calls, cost_by_agent, log_paths["cost_summary"], out_dir)

    run_log.info("trace saved to %s", out_dir)

    print(f"\nRun complete. Open the replay viewer:")
    print(f"  cd {ROOT}")
    print(f"  python -m http.server 8200")
    print(f"  Then open: http://localhost:8200/viewer/index.html?session={run_id}")


if __name__ == "__main__":
    main()

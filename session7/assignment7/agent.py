from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).parent.parent / ".env")  # Session 7 root .env

import asyncio
import json
import os
import subprocess
import sys
import time
import traceback
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
IST = timezone(timedelta(hours=5, minutes=30))

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

import logger as log
from action import Action
from decision import Decision
from memory import ArtifactStore, Memory
from perception import Perception
from schemas import Goal

MAX_ITERATIONS = 16
GATEWAY_URL = os.getenv("LLM_GATEWAY_V7_URL", "http://localhost:8107")
GATEWAY_DIR = Path(__file__).parent.parent / "llm_gatewayV7"

memory = Memory()
artifacts = ArtifactStore()
perception = Perception()
decision = Decision()
action = Action(artifacts)

BANNER = """\
╔══════════════════════════════════════════════════════════════╗
║  EAGV3 Session 7 — Memory & Retrieval: RAG Agent (S7)       ║
╚══════════════════════════════════════════════════════════════╝
"""


# ─── TraceLogger ──────────────────────────────────────────────────────────────

class TraceLogger:
    def __init__(self, query: str, output_dir: str = "traces"):
        self.run_id = str(uuid.uuid4())[:8]
        self.query = query
        self.started_at = datetime.now(IST).isoformat()
        self.iterations: list[dict] = []
        self.gateway_calls: list[dict] = []
        self.memory_ops: list[dict] = []
        self.output_dir = Path(output_dir)

    def log_iteration(self, i: int, perception_data: dict, decision_data: dict, action_data: dict | None):
        self.iterations.append({
            "iteration": i,
            "timestamp": datetime.now(IST).isoformat(),
            "perception": perception_data,
            "decision": decision_data,
            "action": action_data,
        })

    def log_gateway_call(self, kind: str, model: str, provider: str,
                         tokens_in: int, tokens_out: int, latency_ms: int,
                         prompt_preview: str, response_preview: str, iteration: int):
        self.gateway_calls.append({
            "iteration": iteration, "kind": kind, "model": model,
            "provider": provider, "tokens_in": tokens_in,
            "tokens_out": tokens_out, "latency_ms": latency_ms,
            "prompt_preview": (prompt_preview or "")[:500],
            "response_preview": (response_preview or "")[:500],
            "timestamp": datetime.now(IST).isoformat(),
        })

    def log_memory_op(self, op: str, item_id: str | None, query: str,
                      hits: int, iteration: int):
        self.memory_ops.append({
            "iteration": iteration, "op": op, "item_id": item_id,
            "query": query, "hits": hits,
            "timestamp": datetime.now(IST).isoformat(),
        })

    def save(self, filename: str):
        path = self.output_dir / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "run_id": self.run_id,
            "query": self.query,
            "started_at": self.started_at,
            "ended_at": datetime.now(IST).isoformat(),
            "total_iterations": len(self.iterations),
            "iterations": self.iterations,
            "gateway_calls": self.gateway_calls,
            "memory_ops": self.memory_ops,
        }, indent=2))
        # Also write human-readable log
        log_path = path.with_suffix(".log")
        lines = [f"QUERY: {self.query}", ""]
        for it in self.iterations:
            lines.append(f"=== ITERATION {it['iteration']} ===")
            lines.append(f"Perception goals: {it['perception'].get('goals')}")
            lines.append(f"Decision: {it['decision'].get('action')}")
            if it["action"]:
                lines.append(f"Action result: {str(it['action'])[:300]}")
            lines.append("")
        log_path.write_text("\n".join(lines))
        print(f"[tracer] saved {path} + {log_path.name}", flush=True)


# Module-level tracer (one per agent run)
_tracer: TraceLogger | None = None


# ─── Gateway lifecycle ────────────────────────────────────────────────────────

_gateway_proc: subprocess.Popen | None = None


def ensure_gateway():
    global _gateway_proc
    try:
        r = httpx.get(f"{GATEWAY_URL}/v1/providers", timeout=3)
        if r.status_code == 200:
            print(f"[gateway] connected to llm_gatewayV7 at {GATEWAY_URL} ... ok", flush=True)
            return
    except Exception:
        pass

    print(f"[gateway] starting llm_gatewayV7 at {GATEWAY_URL} ...", flush=True)
    env = {**os.environ}
    venv_python = GATEWAY_DIR / ".venv" / "bin" / "python"
    python = str(venv_python) if venv_python.exists() else sys.executable

    _gateway_proc = subprocess.Popen(
        [python, str(GATEWAY_DIR / "main.py")],
        cwd=str(GATEWAY_DIR),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    for _ in range(30):
        time.sleep(1)
        try:
            r = httpx.get(f"{GATEWAY_URL}/v1/providers", timeout=2)
            if r.status_code == 200:
                print(f"[gateway] llm_gatewayV7 at {GATEWAY_URL} ... ok", flush=True)
                return
        except Exception:
            pass

    raise RuntimeError(f"Gateway V7 failed to start at {GATEWAY_URL}")


# ─── MCP session ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def mcp_session():
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(Path(__file__).parent / "mcp_server.py")],
        cwd=str(Path(__file__).parent),
        env={**os.environ},
    )
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print(f"[mcp] spawned mcp_server.py ({len(tools.tools)} tools)", flush=True)
            yield session


async def load_tools(session: ClientSession) -> list:
    result = await session.list_tools()
    return result.tools


def mcp_tools_for_decision(tools) -> list[dict]:
    out = []
    for t in tools:
        schema = {}
        if hasattr(t, "inputSchema") and t.inputSchema:
            schema = t.inputSchema if isinstance(t.inputSchema, dict) else t.inputSchema.model_dump()
        out.append({
            "name": t.name,
            "description": t.description or "",
            "input_schema": schema,
        })
    return out


# ─── Final answer extraction ──────────────────────────────────────────────────

def final_answer_from(history: list[dict]) -> str:
    answers = [ev for ev in history if ev["kind"] == "answer"]
    if answers:
        return answers[-1]["text"]
    # No answer event: prefer the last answer-like action (web_search text result, not raw artifact)
    for ev in reversed(history):
        if ev.get("kind") == "action":
            desc = ev.get("result_descriptor", "")
            # Skip entries that are just artifact handles with previews of binary/CSS content
            if desc and not desc.startswith("[artifact art:"):
                return desc[:500]
    return "Agent reached iteration limit without producing a final answer."


# ─── Main run loop ────────────────────────────────────────────────────────────

async def run(query: str, trace_filename: str | None = None) -> str:
    global _tracer
    ensure_gateway()
    run_id = uuid.uuid4().hex[:8]
    _tracer = TraceLogger(query)
    _tracer.run_id = run_id  # use same run_id as agent loop

    log.run_start(run_id=run_id, query=query)
    memory.set_current_run(run_id)
    history: list[dict] = []
    prior_goals: list[Goal] = []

    classified = await memory.remember(query, source="user_query", run_id=run_id)
    log.memory_remember(classified)
    if classified:
        _tracer.log_memory_op("remember", classified.id, query, 0, 0)

    async with mcp_session() as session:
        mcp_tools = await load_tools(session)
        tools_for_decision = mcp_tools_for_decision(mcp_tools)

        for it in range(1, MAX_ITERATIONS + 1):
            log.iter_start(it)

            hits = memory.read(query, history)
            _tracer.log_memory_op("read", None, query, len(hits), it)

            obs = await perception.observe(query, hits, history, prior_goals, run_id)
            prior_goals = obs.goals

            if all(g.done for g in obs.goals):
                log.all_done(it, goals=obs.goals)
                break

            goal = next(g for g in obs.goals if not g.done)

            attached: list[tuple[str, bytes]] = []
            if goal.attach_artifact_id and artifacts.exists(goal.attach_artifact_id):
                blob = artifacts.get_bytes(goal.attach_artifact_id)
                attached.append((goal.attach_artifact_id, blob))
                log.attach(it, art_id=goal.attach_artifact_id, size=len(blob))
            elif goal.attach_artifact_id:
                log.attach_dropped(it, art_id=goal.attach_artifact_id,
                                   reason="artifact not found in store")

            out = await decision.next_step(goal, hits, attached, history, tools_for_decision)

            perception_data = {"goals": [g.model_dump() for g in obs.goals]}
            decision_data = {"action": out.model_dump()}
            action_data = None

            if out.answer is not None:
                history.append({
                    "iter": it, "kind": "answer",
                    "goal_id": goal.id, "text": out.answer,
                })
                _tracer.log_iteration(it, perception_data, decision_data, action_data)
                continue

            result_text, art_id = await action.execute(session, out.tool_call)
            log.action(it, tool_call=out.tool_call, result_text=result_text, artifact_id=art_id)

            action_data = {
                "tool": out.tool_call.name,
                "arguments": out.tool_call.arguments,
                "result": result_text[:500],
                "artifact_id": art_id,
            }

            memory.record_outcome(
                tool_call=out.tool_call, result_text=result_text,
                artifact_id=art_id, run_id=run_id, goal_id=goal.id,
            )
            history.append({
                "iter": it, "kind": "action",
                "goal_id": goal.id, "tool": out.tool_call.name,
                "arguments": out.tool_call.arguments,
                "result_descriptor": result_text[:300],
                "artifact_id": art_id,
            })

            _tracer.log_iteration(it, perception_data, decision_data, action_data)

    final = final_answer_from(history)
    log.run_end(run_id=run_id, final=final)

    if trace_filename:
        _tracer.save(trace_filename)

    _save_query_answer(run_id, query, final)

    return final


def _save_query_answer(run_id: str, query: str, answer: str):
    folder = Path(__file__).parent / "queries"
    folder.mkdir(exist_ok=True)
    ts = datetime.now(IST).strftime("%Y%m%d_%H%M%S")
    slug = "".join(c if c.isalnum() else "_" for c in query[:40]).strip("_")
    filename = folder / f"{ts}_{slug}.txt"
    filename.write_text(
        f"Run ID : {run_id}\n"
        f"Time   : {datetime.now(IST).isoformat()}\n"
        f"Query  : {query}\n"
        f"Answer :\n{answer}\n",
        encoding="utf-8",
    )
    print(f"[query] saved → queries/{filename.name}", flush=True)


# ─── CLI entry ────────────────────────────────────────────────────────────────

async def main():
    import argparse
    parser = argparse.ArgumentParser(description="EAGV3 S7 RAG Agent")
    parser.add_argument("query", nargs="?", help="Single query (non-interactive mode)")
    parser.add_argument("--trace", help="Trace filename to save (e.g. base/A_shannon.json)")
    parser.add_argument("--index", metavar="DIR", help="Index all .md files in DIR, then exit")
    args = parser.parse_args()

    print(BANNER, flush=True)

    if args.index:
        # Index mode: embed all .md files in the given directory
        ensure_gateway()
        index_dir = Path(args.index)
        md_files = list(index_dir.glob("**/*.md"))
        print(f"[index] found {len(md_files)} markdown files in {args.index}", flush=True)
        from memory import Memory as _Mem
        m = _Mem()
        run_id = uuid.uuid4().hex[:8]
        m.set_current_run(run_id)
        from mcp_server import _sliding_window, _extract_keywords, _project_path
        total = 0
        for md_file in sorted(md_files):
            rel = md_file.relative_to(Path(__file__).parent)
            text = md_file.read_text(encoding="utf-8", errors="replace")
            chunks = _sliding_window(text, 400, 80)
            for i, chunk_text in enumerate(chunks):
                descriptor = f"[{rel} chunk {i+1}/{len(chunks)}]"
                m.add_fact(
                    descriptor=descriptor,
                    value={"chunk": chunk_text, "source": str(rel),
                           "chunk_index": i, "total_chunks": len(chunks)},
                    keywords=_extract_keywords(chunk_text),
                    source=f"--index:{rel}",
                    run_id=run_id,
                )
                total += 1
            print(f"  indexed {rel} → {len(chunks)} chunks", flush=True)
        print(f"[index] total chunks indexed: {total}", flush=True)
        return

    print(f"[memory] {memory.count()} items in state/memory.json", flush=True)
    print(f"[artifacts] {artifacts.count()} artifacts in state/artifacts/", flush=True)

    if args.query:
        # Non-interactive: single query, save trace to --trace if given
        try:
            final = await run(args.query, trace_filename=args.trace)
        except Exception as e:
            traceback.print_exc()
            print(f"ERROR: {e}", flush=True)
            return
        print(f"\nFINAL: {final}", flush=True)
    else:
        # Interactive REPL
        while True:
            try:
                query = input("\nEnter query > ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nbye.", flush=True)
                break
            if not query or query.lower() in {":quit", ":q", "exit"}:
                print("bye.", flush=True)
                break
            trace_file = input("Trace filename (blank to skip) > ").strip() or None
            try:
                final = await run(query, trace_filename=trace_file)
            except Exception as e:
                if isinstance(e, ExceptionGroup):
                    for exc in e.exceptions:
                        traceback.print_exception(type(exc), exc, exc.__traceback__)
                else:
                    traceback.print_exc()
                log.error(e)
                print(f"ERROR: {e}", flush=True)
                continue
            print(f"\nFINAL: {final}", flush=True)

    if _gateway_proc:
        _gateway_proc.terminate()


if __name__ == "__main__":
    asyncio.run(main())

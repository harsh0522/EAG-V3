from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).parent / ".env")

import asyncio
import json
import os
import subprocess
import sys
import time
import traceback
import uuid
from contextlib import asynccontextmanager

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

import logger as log
from action import Action
from decision import Decision
from memory import ArtifactStore, Memory
from perception import Perception
from schemas import Goal

MAX_ITERATIONS = 14
GATEWAY_URL = os.getenv("LLM_GATEWAY_V3_URL", "http://localhost:8101")
GATEWAY_DIR = Path(__file__).parent.parent / "llm_gatewayV3"

memory = Memory()
artifacts = ArtifactStore()
perception = Perception()
decision = Decision()
action = Action(artifacts)

BANNER = """\
╔══════════════════════════════════════════════════════════╗
║  EAGV3 Session 6 — Agentic Architecture (assignment6)   ║
╚══════════════════════════════════════════════════════════╝
[dashboard] serving at http://localhost:8102  (open in browser)
"""


# ─── Gateway lifecycle ────────────────────────────────────────────────────────

_gateway_proc: subprocess.Popen | None = None


def ensure_gateway():
    global _gateway_proc
    try:
        r = httpx.get(f"{GATEWAY_URL}/v1/providers", timeout=3)
        if r.status_code == 200:
            print(f"[gateway] connecting to llm_gatewayV3 at {GATEWAY_URL} ... ok", flush=True)
            return
    except Exception:
        pass

    # Gateway not running — start it
    print(f"[gateway] starting llm_gatewayV3 at {GATEWAY_URL} ...", flush=True)
    env = {**os.environ}
    venv_python = GATEWAY_DIR / ".venv" / "bin" / "python"
    if venv_python.exists():
        python = str(venv_python)
    else:
        python = sys.executable

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
                print(f"[gateway] connecting to llm_gatewayV3 at {GATEWAY_URL} ... ok", flush=True)
                return
        except Exception:
            pass

    raise RuntimeError(f"Gateway failed to start at {GATEWAY_URL}")


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
            print(f"[mcp] spawning mcp_server.py over stdio ... ok ({len(tools.tools)} tools loaded)", flush=True)
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
    # Collect all answer events, preferring the last goal's answer
    answers = [ev for ev in history if ev["kind"] == "answer"]
    if not answers:
        # Fall back to the last action result
        actions = [ev for ev in history if ev["kind"] == "action"]
        if actions:
            return actions[-1].get("result_descriptor", "")[:500]
        return "No answer produced."
    # Return the last substantive answer
    return answers[-1]["text"]


# ─── Main run loop ────────────────────────────────────────────────────────────

async def run(query: str) -> str:
    ensure_gateway()
    run_id = uuid.uuid4().hex[:8]
    log.run_start(run_id=run_id, query=query)
    history: list[dict] = []
    prior_goals: list[Goal] = []

    # Durable-memory contract
    classified = await memory.remember(query, source="user_query", run_id=run_id)
    log.memory_remember(classified)

    async with mcp_session() as session:
        mcp_tools = await load_tools(session)
        tools_for_decision = mcp_tools_for_decision(mcp_tools)

        for it in range(1, MAX_ITERATIONS + 1):
            log.iter_start(it)

            hits = memory.read(query, history)
            log.memory_read(it, hits=hits)

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

            if out.answer is not None:
                history.append({
                    "iter": it, "kind": "answer",
                    "goal_id": goal.id, "text": out.answer,
                })
                continue

            result_text, art_id = await action.execute(session, out.tool_call)
            log.action(it, tool_call=out.tool_call, result_text=result_text, artifact_id=art_id)

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

    final = final_answer_from(history)
    log.run_end(run_id=run_id, final=final)
    return final


# ─── Dashboard startup ────────────────────────────────────────────────────────

async def start_dashboard():
    from dashboard import create_app
    import uvicorn

    app, sse_queue = create_app()
    log.set_sse_queue(sse_queue)

    config = uvicorn.Config(app, host="0.0.0.0", port=8102, log_level="warning")
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    # Give the server a moment to bind
    await asyncio.sleep(0.5)
    return task


# ─── REPL ─────────────────────────────────────────────────────────────────────

async def main():
    await start_dashboard()
    print(BANNER, flush=True)
    print(f"[memory] loaded state/memory.json ({memory.count()} items)", flush=True)
    print(f"[artifacts] state/artifacts/ contains {artifacts.count()} files", flush=True)

    while True:
        try:
            query = input("\nEnter query > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nbye.", flush=True)
            break
        if not query or query.lower() in {":quit", ":q", "exit"}:
            print("bye.", flush=True)
            break
        try:
            final = await run(query)
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

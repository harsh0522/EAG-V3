"""FastAPI dashboard at :8102 with SSE event stream (broadcast to all clients)."""
from __future__ import annotations
import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

_STATIC = Path(__file__).parent / "static"
_STATE_DIR = Path(__file__).parent / "state"
_LOGS_DIR = Path(__file__).parent / "logs"


def create_app() -> tuple[FastAPI, asyncio.Queue]:
    intake_queue: asyncio.Queue = asyncio.Queue(maxsize=2048)
    # One queue per connected browser; broadcaster fans out from intake_queue
    subscribers: list[asyncio.Queue] = []

    async def _broadcaster():
        while True:
            data = await intake_queue.get()
            dead = []
            for q in subscribers:
                try:
                    q.put_nowait(data)
                except asyncio.QueueFull:
                    dead.append(q)
            for q in dead:
                try:
                    subscribers.remove(q)
                except ValueError:
                    pass

    @asynccontextmanager
    async def lifespan(*_):
        asyncio.create_task(_broadcaster())
        yield

    app = FastAPI(title="assignment6 dashboard", lifespan=lifespan)

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return (_STATIC / "index.html").read_text(encoding="utf-8")

    app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")

    @app.get("/events")
    async def events(request):
        q: asyncio.Queue = asyncio.Queue(maxsize=512)
        subscribers.append(q)

        async def generator() -> AsyncIterator[dict]:
            try:
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        data = await asyncio.wait_for(q.get(), timeout=15)
                        yield {"data": data}
                    except asyncio.TimeoutError:
                        yield {"data": json.dumps({"event": "ping"})}
            finally:
                try:
                    subscribers.remove(q)
                except ValueError:
                    pass

        return EventSourceResponse(generator())

    @app.get("/api/state")
    async def api_state():
        mem_file = _STATE_DIR / "memory.json"
        artifacts_dir = _STATE_DIR / "artifacts"
        memory = []
        if mem_file.exists():
            try:
                memory = json.loads(mem_file.read_text())
            except Exception:
                pass
        artifacts = []
        if artifacts_dir.exists():
            for p in sorted(artifacts_dir.glob("*.json")):
                try:
                    artifacts.append(json.loads(p.read_text()))
                except Exception:
                    pass
        return JSONResponse({"memory": memory, "artifacts": artifacts})

    @app.get("/api/runs")
    async def api_runs():
        _LOGS_DIR.mkdir(exist_ok=True)
        runs = [p.stem.removeprefix("run-") for p in sorted(_LOGS_DIR.glob("run-*.jsonl"))]
        return JSONResponse({"runs": runs})

    @app.get("/api/runs/{run_id}")
    async def api_run(run_id: str):
        log_file = _LOGS_DIR / f"run-{run_id}.jsonl"
        if not log_file.exists():
            return JSONResponse({"error": "not found"}, status_code=404)
        lines = log_file.read_text(encoding="utf-8").strip().splitlines()
        events = []
        for line in lines:
            try:
                events.append(json.loads(line))
            except Exception:
                pass
        return JSONResponse({"run_id": run_id, "events": events})

    return app, intake_queue

import asyncio
import json
import logging
import os
import time
from collections import deque

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

from agent import GeoIntelAgent
from usage_tracker import tracker

# ── Server log buffer ──────────────────────────────────────────────────────────
_log_buffer: deque[dict] = deque(maxlen=300)


class _BufHandler(logging.Handler):
    def emit(self, record):
        try:
            _log_buffer.append({
                "ts":    round(record.created * 1000),
                "level": record.levelname,
                "msg":   self.format(record),
            })
        except Exception:
            pass


_handler = _BufHandler()
_handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))
logging.getLogger().addHandler(_handler)
logging.getLogger("uvicorn").addHandler(_handler)
logging.getLogger("uvicorn.access").addHandler(_handler)
logging.getLogger("uvicorn.error").addHandler(_handler)

logger = logging.getLogger("geointel")


# ── Telegram auto-notify helper ────────────────────────────────────────────────
async def _send_telegram_auto(region: str, report: str):
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = tracker.last_telegram_chat_id
    if not token or not chat_id:
        return
    # Send a short summary (first ~800 chars of report)
    snippet = report[:800].strip()
    if len(report) > 800:
        snippet += "\n\n…_(full report in web app)_"
    text = f"🌍 *GeoIntel Auto-Report: {region}*\n\n{snippet}"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": "Markdown",
                    "disable_web_page_preview": True,
                },
            )
        tracker.record_telegram_message(chat_id=chat_id)
        logger.info(f"Auto-Telegram sent for {region} to chat {chat_id}")
    except Exception as e:
        logger.warning(f"Auto-Telegram failed: {e}")


# ── App ────────────────────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    region: str


app = FastAPI(title="GeoIntel Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/analyze")
async def analyze(req: AnalyzeRequest):
    agent = GeoIntelAgent()
    logger.info(f"Analysis started: {req.region}")

    async def event_stream():
        try:
            async for event in agent.run(req.region):
                yield f"data: {json.dumps(event, default=str)}\n\n"
                await asyncio.sleep(0)
                # Auto-send Telegram when final answer is ready
                if event.get("type") == "final_answer":
                    asyncio.create_task(
                        _send_telegram_auto(req.region, event.get("content", ""))
                    )
        except Exception as e:
            logger.error(f"Analysis error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        finally:
            yield "data: {\"type\": \"stream_end\"}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/limits")
async def limits():
    return tracker.snapshot()


@app.get("/api/server-logs")
async def server_logs(since: float = 0):
    return JSONResponse([l for l in _log_buffer if l["ts"] > since])


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "gemini_key_set": bool(os.getenv("GEMINI_API_KEY")),
        "youtube_key_set": bool(
            os.getenv("YOUTUBE_API_KEY") and
            os.getenv("YOUTUBE_API_KEY") != "YOUR_YOUTUBE_API_KEY_HERE"
        ),
        "telegram_chat_id": tracker.last_telegram_chat_id,
    }


app.mount("/", StaticFiles(directory="static", html=True), name="static")

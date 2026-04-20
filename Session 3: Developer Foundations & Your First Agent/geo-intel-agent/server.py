import asyncio
import json
import logging
import os
import time
import xml.etree.ElementTree as ET
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


class SendLogsRequest(BaseModel):
    region: str
    log_text: str


@app.post("/api/send-logs")
async def send_logs(req: SendLogsRequest):
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = tracker.last_telegram_chat_id
    if not token or not chat_id:
        return JSONResponse({"ok": False, "error": "Telegram not configured (no token or chat_id)"})
    filename = f"geointel_{req.region.replace(' ', '_').lower()}_{int(time.time())}.txt"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{token}/sendDocument",
                data={"chat_id": chat_id, "caption": f"GeoIntel logs — {req.region}"},
                files={"document": (filename, req.log_text.encode("utf-8"), "text/plain")},
            )
        result = resp.json()
        if result.get("ok"):
            tracker.record_telegram_message(chat_id=chat_id)
            logger.info(f"Log file sent to Telegram for {req.region}")
            return JSONResponse({"ok": True, "filename": filename})
        else:
            return JSONResponse({"ok": False, "error": result.get("description", "Unknown error")})
    except Exception as e:
        logger.warning(f"send-logs Telegram error: {e}")
        return JSONResponse({"ok": False, "error": str(e)})


@app.get("/api/limits")
async def limits():
    return tracker.snapshot()


@app.get("/api/server-logs")
async def server_logs(since: float = 0):
    return JSONResponse([l for l in _log_buffer if l["ts"] > since])


@app.get("/api/oil-price")
async def oil_price_endpoint():
    from tools import get_oil_prices
    result = await get_oil_prices()
    return JSONResponse(result.get("data", {}))


@app.get("/api/latest-video")
async def latest_video(ch: str = "alj"):
    channel_ids = {
        "alj": "UCNye-wNBqNL5ZzHSJdse9Bg",
        "bbc": "UC16niRr50-MSBwiO3YDb3RA",
    }
    cid = channel_ids.get(ch, channel_ids["alj"])
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
        root = ET.fromstring(r.text)
        atom = "{http://www.w3.org/2005/Atom}"
        yt = "{http://www.youtube.com/xml/schemas/2015}"
        entry = root.find(f"{atom}entry")
        if entry is not None:
            vid_id = entry.find(f"{yt}videoId")
            title_el = entry.find(f"{atom}title")
            if vid_id is not None:
                return JSONResponse({
                    "embed_url": f"https://www.youtube.com/embed/{vid_id.text}?autoplay=1&mute=1",
                    "video_id": vid_id.text,
                    "title": title_el.text if title_el is not None else "",
                })
    except Exception as e:
        logger.warning(f"latest-video fetch failed: {e}")
    return JSONResponse({"embed_url": None, "error": "Could not fetch latest video"})


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

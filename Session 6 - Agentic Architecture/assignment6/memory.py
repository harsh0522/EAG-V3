"""Memory service (keyword search, LLM classify) + ArtifactStore (content-addressable)."""
from __future__ import annotations
import hashlib
import json
import os
import re
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

import logger as log
from schemas import Artifact, MemoryItem, ToolCall

_STATE_DIR = Path(__file__).parent / "state"
_MEMORY_FILE = _STATE_DIR / "memory.json"
_ARTIFACTS_DIR = _STATE_DIR / "artifacts"

_STOPWORDS = {
    "a", "an", "the", "is", "it", "its", "in", "on", "at", "to", "of", "and",
    "or", "for", "with", "this", "that", "i", "me", "my", "we", "our", "you",
    "your", "he", "she", "they", "their", "be", "was", "are", "were", "has",
    "have", "had", "do", "did", "will", "would", "can", "could", "from",
}

GATEWAY_URL = os.getenv("LLM_GATEWAY_V3_URL", "http://localhost:8101")


def _tokenize(text: str) -> set[str]:
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return {t for t in tokens if t not in _STOPWORDS and len(t) > 1}


class ArtifactStore:
    def __init__(self):
        _ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    def put(self, blob: bytes, *, content_type: str, source: str, descriptor: str) -> str:
        sha = hashlib.sha256(blob).hexdigest()[:16]
        art_id = f"art:{sha}"
        bin_path = _ARTIFACTS_DIR / f"{sha}.bin"
        meta_path = _ARTIFACTS_DIR / f"{sha}.json"

        if not bin_path.exists():
            bin_path.write_bytes(blob)
            meta = Artifact(
                id=art_id,
                content_type=content_type,
                size_bytes=len(blob),
                source=source,
                descriptor=descriptor,
                created_at=datetime.now(timezone.utc),
            )
            _atomic_write(meta_path, meta.model_dump(mode="json"))
            log.artifact_put(art_id, len(blob), content_type, source, descriptor)

        return art_id

    def get_bytes(self, artifact_id: str) -> bytes:
        sha = artifact_id.removeprefix("art:")
        return (_ARTIFACTS_DIR / f"{sha}.bin").read_bytes()

    def get_meta(self, artifact_id: str) -> Artifact:
        sha = artifact_id.removeprefix("art:")
        data = json.loads((_ARTIFACTS_DIR / f"{sha}.json").read_text())
        return Artifact(**data)

    def exists(self, artifact_id: str) -> bool:
        sha = artifact_id.removeprefix("art:")
        return (_ARTIFACTS_DIR / f"{sha}.bin").exists()

    def list_all(self) -> list[Artifact]:
        items = []
        for p in _ARTIFACTS_DIR.glob("*.json"):
            try:
                items.append(Artifact(**json.loads(p.read_text())))
            except Exception:
                pass
        return sorted(items, key=lambda a: a.created_at)

    def count(self) -> int:
        return len(list(_ARTIFACTS_DIR.glob("*.bin")))


def _atomic_write(path: Path, data: Any):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, default=str, indent=2), encoding="utf-8")
    tmp.replace(path)


class Memory:
    def __init__(self):
        _STATE_DIR.mkdir(parents=True, exist_ok=True)
        self._items: list[MemoryItem] | None = None

    def _load(self) -> list[MemoryItem]:
        if self._items is None:
            if _MEMORY_FILE.exists():
                raw = json.loads(_MEMORY_FILE.read_text(encoding="utf-8"))
                self._items = [MemoryItem(**item) for item in raw]
            else:
                self._items = []
            print(f"[memory] loaded {_MEMORY_FILE} ({len(self._items)} items)", flush=True)
        return self._items

    def _save(self):
        _atomic_write(_MEMORY_FILE, [item.model_dump(mode="json") for item in self._items])

    def _persist(self, item: MemoryItem):
        self._load()
        self._items.append(item)
        self._save()

    def read(self, query: str, history: list[dict],
             kinds: list[str] | None = None, top_k: int = 8) -> list[MemoryItem]:
        items = self._load()
        if kinds:
            items = [i for i in items if i.kind in kinds]

        # Build query token set from query + recent history descriptors
        q_tokens = _tokenize(query)
        for h in history[-5:]:
            q_tokens |= _tokenize(str(h.get("result_descriptor", "")))
            q_tokens |= _tokenize(str(h.get("text", "")))

        scored = []
        for item in items:
            item_tokens = set(item.keywords) | _tokenize(item.descriptor)
            item_tokens = {t.lower() for t in item_tokens}
            overlap = len(q_tokens & item_tokens)
            if overlap > 0:
                scored.append((overlap, item))

        scored.sort(key=lambda x: -x[0])
        return [item for _, item in scored[:top_k]]

    def filter(self, kinds: list[str] | None = None,
               goal_id: str | None = None, recent: int | None = None) -> list[MemoryItem]:
        items = self._load()
        if kinds:
            items = [i for i in items if i.kind in kinds]
        if goal_id:
            items = [i for i in items if i.goal_id == goal_id]
        if recent:
            items = items[-recent:]
        return items

    async def relevant(self, query: str, kinds: list[str] | None = None,
                       top_k: int = 5) -> list[MemoryItem]:
        pool = self.filter(kinds=kinds)
        if not pool:
            return []
        pool_text = "\n".join(
            f"[{i}] {item.kind}: {item.descriptor}" for i, item in enumerate(pool)
        )
        prompt = (
            f"Query: {query}\n\nMemory items:\n{pool_text}\n\n"
            f"Return the indices (0-based, comma-separated) of the top {top_k} most relevant items. "
            f"Only indices, nothing else."
        )
        try:
            resp = await _gateway_call(
                messages=[{"role": "user", "content": prompt}],
                auto_route="memory",
                max_tokens=64,
                temperature=0.0,
            )
            text = resp.get("text", "")
            indices = [int(x.strip()) for x in text.split(",") if x.strip().isdigit()]
            return [pool[i] for i in indices if 0 <= i < len(pool)][:top_k]
        except Exception:
            return pool[:top_k]

    async def remember(self, raw_text: str, source: str, run_id: str,
                       goal_id: str | None = None) -> MemoryItem | None:
        prompt = (
            "You are a memory classifier. Given raw text from an agent run, extract any durable "
            "fact, preference, or scratchpad note worth remembering. "
            "Return JSON: {kind, keywords, descriptor, value} where:\n"
            "- kind: one of fact | preference | scratchpad (NOT tool_outcome)\n"
            "- keywords: list of 3-8 lowercase search tokens\n"
            "- descriptor: one concise sentence summarizing the memory\n"
            "- value: dict of structured data extracted (dates, names, etc.)\n"
            "If there is nothing durable to remember, return {}\n\n"
            f"Text: {raw_text}"
        )
        try:
            resp = await _gateway_call(
                messages=[{"role": "user", "content": prompt}],
                provider="g",
                max_tokens=256,
                temperature=0.3,
                response_format={"type": "json_object"},
            )
            text = resp.get("text", "").strip()
            parsed = resp.get("parsed") or {}
            if not parsed and text:
                try:
                    raw = json.loads(text)
                    parsed = raw if isinstance(raw, dict) else {}
                except json.JSONDecodeError:
                    pass

            if not parsed or not parsed.get("kind"):
                return None

            item = MemoryItem(
                id=uuid.uuid4().hex[:12],
                kind=parsed["kind"],
                keywords=parsed.get("keywords", []),
                descriptor=parsed.get("descriptor", raw_text[:100]),
                value=parsed.get("value", {}),
                source=source,
                run_id=run_id,
                goal_id=goal_id,
                created_at=datetime.now(timezone.utc),
            )
            self._persist(item)
            return item
        except Exception as e:
            print(f"[memory.remember] error: {e}", flush=True)
            return None

    def record_outcome(self, tool_call: ToolCall, result_text: str,
                       artifact_id: str | None, run_id: str, goal_id: str) -> MemoryItem:
        args_tokens = _tokenize(" ".join(str(v) for v in tool_call.arguments.values()))
        keywords = list({tool_call.name} | args_tokens)[:8]

        if artifact_id:
            descriptor = f"{tool_call.name}({_args_repr(tool_call.arguments)}) -> {artifact_id}"
        else:
            preview = result_text[:60].strip().replace("\n", " ")
            descriptor = f"{tool_call.name}({_args_repr(tool_call.arguments)}) -> {preview}"

        item = MemoryItem(
            id=uuid.uuid4().hex[:12],
            kind="tool_outcome",
            keywords=keywords,
            descriptor=descriptor,
            value={"tool": tool_call.name, "arguments": tool_call.arguments,
                   "artifact_id": artifact_id},
            artifact_id=artifact_id,
            source="action",
            run_id=run_id,
            goal_id=goal_id,
            created_at=datetime.now(timezone.utc),
        )
        self._persist(item)
        log.memory_record_outcome(log._CURRENT_ITER, item)
        return item

    def count(self) -> int:
        return len(self._load())


def _args_repr(args: dict) -> str:
    parts = []
    for k, v in list(args.items())[:2]:
        parts.append(f"{v!r}"[:40])
    return ", ".join(parts)


async def _gateway_call(messages: list, **kwargs) -> dict:
    body = {"messages": messages, **kwargs}
    body = {k: v for k, v in body.items() if v is not None}
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(f"{GATEWAY_URL}/v1/chat", json=body)
        r.raise_for_status()
        return r.json()

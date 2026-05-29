"""Memory service: keyword search + FAISS vector retrieval, LLM classify, ArtifactStore.

S7 changes vs S6:
- MemoryItem gains optional embedding: list[float] (768-dim)
- _persist_item() writes vectors to state/index.faiss + state/index_ids.json
- read() is vector-first with keyword fallback
- add_fact() is new — skips classifier, embeds directly (used by index_document MCP tool)
- _embed_sync() / _embed_async() call gateway V7 /v1/embed
- FAISS index is reloaded from disk on every read (cross-process consistency)
"""
from __future__ import annotations
import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

import logger as log
from schemas import Artifact, MemoryItem, ToolCall

_STATE_DIR = Path(__file__).parent / "state"
_MEMORY_FILE = _STATE_DIR / "memory.json"
_FAISS_FILE = _STATE_DIR / "index.faiss"
_IDS_FILE = _STATE_DIR / "index_ids.json"
_ARTIFACTS_DIR = _STATE_DIR / "artifacts"
_RUN_FILE = _STATE_DIR / "current_run.json"

_STOPWORDS = {
    "a", "an", "the", "is", "it", "its", "in", "on", "at", "to", "of", "and",
    "or", "for", "with", "this", "that", "i", "me", "my", "we", "our", "you",
    "your", "he", "she", "they", "their", "be", "was", "are", "were", "has",
    "have", "had", "do", "did", "will", "would", "can", "could", "from",
}

GATEWAY_URL = os.getenv("LLM_GATEWAY_V7_URL", "http://localhost:8107")
EMBED_DIM = 768


def _tokenize(text: str) -> set[str]:
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return {t for t in tokens if t not in _STOPWORDS and len(t) > 1}


def _atomic_write(path: Path, data: Any):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, default=str, indent=2), encoding="utf-8")
    tmp.replace(path)


# ─── Embed helpers ────────────────────────────────────────────────────────────

def _embed_sync(text: str, task_type: str = "retrieval_document") -> list[float] | None:
    """Synchronous embed via gateway V7. Returns None on error (embedding is optional)."""
    try:
        r = httpx.post(
            f"{GATEWAY_URL}/v1/embed",
            json={"text": text[:7000], "task_type": task_type},
            timeout=60,
        )
        r.raise_for_status()
        return r.json().get("embedding")
    except Exception as e:
        print(f"[memory._embed_sync] error: {e}", file=sys.stderr, flush=True)
        return None


async def _embed_async(text: str, task_type: str = "retrieval_document") -> list[float] | None:
    """Async embed via gateway V7."""
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                f"{GATEWAY_URL}/v1/embed",
                json={"text": text[:7000], "task_type": task_type},
            )
            r.raise_for_status()
            return r.json().get("embedding")
    except Exception as e:
        print(f"[memory._embed_async] error: {e}", file=sys.stderr, flush=True)
        return None


# ─── FAISS helpers ────────────────────────────────────────────────────────────

def _load_index():
    """Load FAISS index + parallel IDs from disk. Always reload for cross-process consistency."""
    try:
        import faiss
        import numpy as np
    except ImportError:
        return None, []

    index = faiss.IndexFlatIP(EMBED_DIM)
    ids: list[str] = []
    if _FAISS_FILE.exists():
        try:
            index = faiss.read_index(str(_FAISS_FILE))
        except Exception:
            index = faiss.IndexFlatIP(EMBED_DIM)
    if _IDS_FILE.exists():
        try:
            ids = json.loads(_IDS_FILE.read_text())
        except Exception:
            ids = []
    return index, ids


def _save_index(index, ids: list[str]):
    try:
        import faiss
        _STATE_DIR.mkdir(parents=True, exist_ok=True)
        faiss.write_index(index, str(_FAISS_FILE))
        _atomic_write(_IDS_FILE, ids)
    except Exception as e:
        print(f"[memory._save_index] error: {e}", file=sys.stderr, flush=True)


def _l2_normalize(vec):
    import numpy as np
    import faiss
    arr = np.array(vec, dtype="float32").reshape(1, -1)
    faiss.normalize_L2(arr)
    return arr


# ─── ArtifactStore ────────────────────────────────────────────────────────────

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


# ─── Memory ───────────────────────────────────────────────────────────────────

class Memory:
    def __init__(self):
        _STATE_DIR.mkdir(parents=True, exist_ok=True)

    # ── Private helpers ──

    def _load_items(self) -> list[MemoryItem]:
        if _MEMORY_FILE.exists():
            raw = json.loads(_MEMORY_FILE.read_text(encoding="utf-8"))
            return [MemoryItem(**item) for item in raw]
        return []

    def _save_items(self, items: list[MemoryItem]):
        _atomic_write(_MEMORY_FILE, [
            {k: v for k, v in item.model_dump(mode="json").items() if k != "score"}
            for item in items
        ])

    def _persist_item(self, item: MemoryItem):
        items = self._load_items()
        items.append(item)
        self._save_items(items)

        if item.embedding and len(item.embedding) == EMBED_DIM:
            index, ids = _load_index()
            if index is not None:
                vec = _l2_normalize(item.embedding)
                index.add(vec)
                ids.append(item.id)
                _save_index(index, ids)

    def _keyword_overlap(self, query: str, k: int, extra_tokens: set[str] | None = None) -> list[MemoryItem]:
        items = self._load_items()
        q_tokens = _tokenize(query)
        if extra_tokens:
            q_tokens |= extra_tokens
        scored = []
        for item in items:
            item_tokens = set(item.keywords) | _tokenize(item.descriptor)
            item_tokens = {t.lower() for t in item_tokens}
            overlap = len(q_tokens & item_tokens)
            if overlap > 0:
                item.score = float(overlap)
                scored.append((overlap, item))
        scored.sort(key=lambda x: -x[0])
        return [item for _, item in scored[:k]]

    # ── Public API ──

    def read(self, query: str, history: list[dict] | None = None, k: int = 8) -> list[MemoryItem]:
        """Vector-first read with keyword fallback. Reloads FAISS from disk every call."""
        index, ids = _load_index()
        method = "keyword"

        if index is not None and index.ntotal > 0:
            vec = _embed_sync(query, "retrieval_query")
            if vec and len(vec) == EMBED_DIM:
                try:
                    import numpy as np
                    qvec = _l2_normalize(vec)
                    scores, positions = index.search(qvec, min(k, index.ntotal))
                    all_items = self._load_items()
                    item_by_id = {item.id: item for item in all_items}
                    hits = []
                    for score, pos in zip(scores[0], positions[0]):
                        if pos < 0 or pos >= len(ids):
                            continue
                        item_id = ids[pos]
                        if item_id in item_by_id:
                            item = item_by_id[item_id]
                            item.score = float(score)
                            hits.append(item)
                    if hits:
                        method = "vector"
                        log.memory_read(log._CURRENT_ITER, hits, method=method)
                        return hits
                except Exception as e:
                    print(f"[memory.read] vector search failed: {e}", file=sys.stderr, flush=True)

        # Keyword fallback
        extra_tokens: set[str] = set()
        if history:
            for h in history[-5:]:
                extra_tokens |= _tokenize(str(h.get("result_descriptor", "")))
                extra_tokens |= _tokenize(str(h.get("text", "")))

        hits = self._keyword_overlap(query, k, extra_tokens)
        log.memory_read(log._CURRENT_ITER, hits, method=method)
        return hits

    def filter(self, kinds: list[str] | None = None,
               goal_id: str | None = None, recent: int | None = None) -> list[MemoryItem]:
        items = self._load_items()
        if kinds:
            items = [i for i in items if i.kind in kinds]
        if goal_id:
            items = [i for i in items if i.goal_id == goal_id]
        if recent:
            items = items[-recent:]
        return items

    async def relevant(self, query: str, kinds: list[str] | None = None, top_k: int = 5) -> list[MemoryItem]:
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
            "- value: dict of structured data extracted (dates, names, numbers, etc.)\n\n"
            "IMPORTANT classification rules:\n"
            "- Personal/family facts (birthdays, anniversaries, names, relationships) → kind='preference'\n"
            "- Dates the user explicitly states they want remembered → kind='preference'\n"
            "- 'Remember that', 'my X is Y', 'X's birthday is' → ALWAYS classify, never return {}\n"
            "- Only return {} if the text is purely an action request with NO factual content\n\n"
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

            descriptor = parsed.get("descriptor", raw_text[:100])
            # Embed the descriptor (skip for scratchpad)
            embedding = None
            if parsed["kind"] != "scratchpad":
                embedding = await _embed_async(descriptor, "retrieval_document")

            item = MemoryItem(
                id=uuid.uuid4().hex[:12],
                kind=parsed["kind"],
                keywords=parsed.get("keywords", []),
                descriptor=descriptor,
                value=parsed.get("value", {}),
                embedding=embedding,
                source=source,
                run_id=run_id,
                goal_id=goal_id,
                created_at=datetime.now(timezone.utc),
            )
            self._persist_item(item)
            return item
        except Exception as e:
            print(f"[memory.remember] error: {e}", file=sys.stderr, flush=True)
            return None

    def record_outcome(self, tool_call: ToolCall, result_text: str,
                       artifact_id: str | None, run_id: str, goal_id: str) -> MemoryItem:
        args_tokens = _tokenize(" ".join(str(v) for v in tool_call.arguments.values()))
        keywords = list({tool_call.name} | args_tokens)[:8]

        if artifact_id:
            descriptor = f"{tool_call.name}({_args_repr(tool_call.arguments)}) -> {artifact_id}"
        else:
            preview = result_text[:300].strip().replace("\n", " ")
            descriptor = f"{tool_call.name}({_args_repr(tool_call.arguments)}) -> {preview}"

        # Embed descriptor
        embedding = _embed_sync(descriptor, "retrieval_document")

        item = MemoryItem(
            id=uuid.uuid4().hex[:12],
            kind="tool_outcome",
            keywords=keywords,
            descriptor=descriptor,
            value={"tool": tool_call.name, "arguments": tool_call.arguments,
                   "artifact_id": artifact_id},
            artifact_id=artifact_id,
            embedding=embedding,
            source="action",
            run_id=run_id,
            goal_id=goal_id,
            created_at=datetime.now(timezone.utc),
        )
        self._persist_item(item)
        log.memory_record_outcome(log._CURRENT_ITER, item)
        return item

    def add_fact(self, descriptor: str, value: dict, keywords: list[str],
                 source: str, run_id: str, goal_id: str | None = None) -> MemoryItem:
        """Add a pre-typed fact, skipping the LLM classifier. Used by index_document."""
        embedding = _embed_sync(descriptor, "retrieval_document")
        item = MemoryItem(
            id=uuid.uuid4().hex[:12],
            kind="fact",
            keywords=keywords,
            descriptor=descriptor,
            value=value,
            embedding=embedding,
            source=source,
            run_id=run_id,
            goal_id=goal_id,
            created_at=datetime.now(timezone.utc),
        )
        self._persist_item(item)
        log.memory_add_fact(log._CURRENT_ITER, descriptor)
        return item

    def count(self) -> int:
        return len(self._load_items())

    def set_current_run(self, run_id: str):
        """Write current run_id to disk so MCP subprocess can read it."""
        _atomic_write(_RUN_FILE, {"run_id": run_id})

    @staticmethod
    def get_current_run() -> str:
        try:
            return json.loads(_RUN_FILE.read_text()).get("run_id", "unknown")
        except Exception:
            return "unknown"


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

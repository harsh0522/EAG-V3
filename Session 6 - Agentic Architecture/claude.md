# CLAUDE.md — EAGV3 Session 6 Agentic Architecture Assignment

You are building a working agentic system for the EAGV3 Session 6 assignment. The architecture decomposes a single LLM call into four cognitive roles (**Memory, Perception, Decision, Action**) connected by Pydantic v2 contracts, with a parallel Artifact store for raw bytes and the LLM Gateway V3 as the substrate for every LLM call.

This file is the complete specification. Build the project described below, in the order described, with the contracts and conventions described. Do not introduce LangChain, LangGraph, CrewAI, AutoGen, llama-index agents, or any other third-party agent framework. The architecture is the assignment.

---

## 0. What you are building

A single self-contained agent project named `assignment6/` that sits next to the shared `llm_gatewayV3/` folder. The agent:

- Reads the user's query interactively from stdin (`Enter query > ` prompt, blocks on Enter).
- Runs the four-role loop until Perception marks all goals done.
- Streams every LLM call, every Pydantic boundary, every iteration step, and every MCP tool input/output to a **live web dashboard** at `http://localhost:8102`.
- Persists memory and artifacts in `state/` so that durable-memory queries (Query C) work across runs without any special handling.
- Prints the final answer to the terminal and returns to the prompt for the next query.

The same agent must pass all four target queries when the user types them in:

| Query | What it tests | Expected iter | Hard cap (2×) |
|---|---|---|---|
| A — Shannon Wikipedia | artifact create → attach → extract | 3 | 6 |
| B — Tokyo + weather | multi-goal, weather as constraint | 6 | 12 |
| C — Mom's birthday (run 1 + run 2) | durable memory across runs | 4 + 2 | 8 + 4 |
| D — Asyncio research | multi-source synthesis, force-attach | 5–7 | 14 |

A query that exceeds twice its expected iteration count is not considered passing. Tune prompts and contracts until convergence is within bounds.

---

## 1. Repository layout (final state to produce)

```
Session 6 - Agentic Architecture/
├── llm_gatewayV3/                       # extracted from the teacher's zip; do not modify
│   └── (gateway internals)
└── assignment6/
    ├── pyproject.toml
    ├── .python-version                  # 3.11+
    ├── .env.example                     # TAVILY_API_KEY, GEMINI_API_KEY, ...
    ├── .gitignore                       # state/, logs/, .env, .venv/, __pycache__/
    ├── README.md                        # how to run + captured terminal outputs (the four reference queries)
    ├── schemas.py                       # Pydantic v2 models (MemoryItem, Artifact, Goal, ...)
    ├── memory.py                        # Memory service + ArtifactStore
    ├── perception.py                    # Perception.observe(...)
    ├── decision.py                      # Decision.next_step(...)
    ├── action.py                        # Action.execute(...)
    ├── agent6.py                        # orchestrator loop + interactive REPL
    ├── mcp_server.py                    # teacher's 9-tool MCP server (unchanged)
    ├── logger.py                        # structured event logger; emits to stdout, file, and dashboard
    ├── dashboard.py                     # FastAPI server at :8102; SSE stream to browser
    ├── validate.py                      # runs the four reference queries against validation.json
    ├── validation.json                  # PoP — expected iter counts and assertions per query
    ├── prompts/
    │   ├── perception_system.md         # Perception system prompt (Gemini-pinned)
    │   └── decision_system.md           # Decision system prompt (auto_route)
    ├── static/                          # served by dashboard.py
    │   ├── index.html
    │   ├── app.js
    │   └── style.css
    ├── state/                           # gitignored, persistent across runs
    │   ├── memory.json
    │   └── artifacts/
    │       ├── <sha>.bin
    │       └── <sha>.json
    └── logs/                            # gitignored
        └── run-<run_id>.jsonl           # one JSONL per run for replay/debugging
```

`.gitignore` must exclude `state/`, `logs/`, `.env`, `.venv/`, `__pycache__/`, `*.pyc`, `.uv/`, `dist/`, `build/`.

---

## 2. Run model (uv, no manual virtualenv, interactive REPL)

The agent is a long-running REPL. To run it from a clean state:

```bash
cd assignment6
rm -rf state/ logs/                              # clean
uv sync                                          # installs deps into a managed venv
cp .env.example .env && edit .env                # add real keys
uv run python agent6.py                          # starts dashboard server AND the REPL
```

Expected console output on launch:

```
[gateway] connecting to llm_gatewayV3 at http://localhost:8101 ... ok
[dashboard] serving at http://localhost:8102  (open in browser)
[mcp] spawning mcp_server.py over stdio ... ok (9 tools loaded)
[memory] loaded state/memory.json (N items)
[artifacts] state/artifacts/ contains N files

Enter query > _
```

The user types a query, presses Enter, and the agent runs the loop while the browser dashboard updates in real time. When the loop terminates the final answer prints to the terminal and the prompt returns:

```
Enter query > Fetch https://en.wikipedia.org/wiki/Claude_Shannon ...
... live iteration output mirrored in browser ...
FINAL: Birth date: April 30, 1916. Death date: February 24, 2001. ...
Enter query > _
```

`Ctrl-D` or `:quit` exits cleanly (shuts down MCP server, flushes logs).

**To validate (separate command):**

```bash
uv run python validate.py        # runs the four reference queries non-interactively
```

`validate.py` reads `validation.json`, runs each query against the agent (programmatically, not via the REPL), asserts the spec, and exits 0/1.

No `python -m venv`, no `source .venv/bin/activate`, no `pip install`. Use `uv add` for dependencies. Use `uv run` for execution. `pyproject.toml` declares `llm_gateway_v3` as a uv path dependency:

```toml
[project]
name = "assignment6"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "mcp>=1.0",
  "pydantic>=2.7",
  "httpx",
  "python-dotenv",
  "ddgs",
  "crawl4ai",
  "tavily-python",
  "fastapi",
  "uvicorn[standard]",
  "sse-starlette",
]

[tool.uv.sources]
llm_gateway_v3 = { path = "../llm_gatewayV3", editable = true }
```

### Environment variables and API keys — single global `.env`

A single `.env` file at `assignment6/.env` is read by every component. The MCP server reads it via `load_dotenv(Path(__file__).parent / ".env")` (already coded in the teacher's `mcp_server.py`). `agent6.py` loads it at startup so the LLM Gateway V3 (running in the same process via the uv path dependency) inherits all keys via `os.environ`. **Do not create separate `.env` files per role, per query, or anywhere else.** One file, one source of truth.

Put this at the very top of `agent6.py`, before any import that touches the gateway or any provider SDK:

```python
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).parent / ".env")
```

**Required keys** (the agent will not start without these):

| Var | Purpose | Where to get |
|---|---|---|
| `GEMINI_API_KEY` | Perception is pinned to Gemini via `provider="g"`. Without this, observe() cannot run. | https://aistudio.google.com — Google account, no card |
| `GOOGLE_API_KEY` | Alias for `GEMINI_API_KEY`. Some SDKs read this name. Set both to the same value. | (same key) |

**Strongly recommended** (Queries B and D depend on web search; without it they will fall back to DuckDuckGo, which is flaky):

| Var | Purpose | Where to get |
|---|---|---|
| `TAVILY_API_KEY` | Primary backend for MCP `web_search`. The teacher's `mcp_server.py` falls back to DDG if this is absent. | https://tavily.com — 1000 searches/month free, email signup |

**Router pool keys.** The Gateway V3 router selects a worker from a pool of small LLMs. Sign up for **at least two** of these so the router has a real choice; the more you have, the more meaningfully `auto_route` exercises the pool:

| Var | Provider | Free tier | Sign-up URL | Card required? |
|---|---|---|---|---|
| `GROQ_API_KEY` | Groq — Llama 3.3 70B, fastest free inference (~315 tok/s) | Yes, no expiry | https://console.groq.com | No |
| `CEREBRAS_API_KEY` | Cerebras — Llama 3.1 8B, ~1M tokens/day | Yes | https://cloud.cerebras.ai | No |
| `NVIDIA_API_KEY` | NVIDIA NIM — Nemotron-nano-8b, no daily token cap | Yes | https://build.nvidia.com | Phone verification |
| `GITHUB_TOKEN` | GitHub Models — Phi-4-mini, GPT-4.1, o4-mini (rate limits tied to Copilot tier) | Yes | https://github.com/marketplace/models — generate a classic PAT, no scopes needed | No (uses GitHub login) |

**Optional fallbacks** (useful when router pool members are rate-limited):

| Var | Provider | Notes |
|---|---|---|
| `OPENROUTER_API_KEY` | OpenRouter — single key, 30+ free models, OpenAI-compatible | https://openrouter.ai |
| `MISTRAL_API_KEY` | Mistral La Plateforme — ~1B tokens/month free across Mistral models | https://console.mistral.ai |

**Verify gateway names match before relying on the table above.** Open `llm_gatewayV3/` and find the file that lists the router pool (look for `routing`, `pool`, `providers`, or a YAML/JSON config). The env-var names *that file* expects are authoritative. The names above are the conventional ones each provider's official SDK reads — if the gateway uses non-standard names (for example `EAGV3_GROQ_KEY` instead of `GROQ_API_KEY`), duplicate the line in `.env` so both names hold the same value. Do not modify gateway code to fit your env names; the gateway is a black-box dependency.

**`.env.example` is part of the deliverable** and must list every key above with a one-line comment giving the provider, the free-tier note, and the sign-up URL. Students copying it to `.env` should be able to leave blanks for the keys they don't have; the gateway must gracefully skip pool members whose key is absent, and the agent must continue to function on the keys that are present (as long as `GEMINI_API_KEY` is set).

**Quick smoke test for env loading:**

```bash
uv run python -c "from dotenv import load_dotenv; load_dotenv(); import os; print([k for k in os.environ if k.endswith(('_API_KEY','_TOKEN'))])"
```

Should print a list including `GEMINI_API_KEY` and any others present.

---

## 3. Architectural recap (do not deviate)

The Session 6 agent has four roles, one orchestrator loop, and one parallel store. Each role has typed input, typed output, and one job.

**Memory** is a typed service that stores facts, preferences, tool outcomes, and scratchpad notes. It exposes pure-Python keyword `read`, a structured `filter`, and an optional LLM-scored `relevant`. Writes are `remember` (free-form, LLM-classified) and `record_outcome` (post-MCP, no LLM). Persistence is `state/memory.json`, loaded lazily and rewritten atomically after each mutation. **Keyword search is intentionally dumb in S6** — synonyms don't match, semantics don't match, you get back everything that shares surface tokens. The dashboard must show *all* hits, including noise, so the student can see the search behavior.

**Perception** is the orchestrator. It runs every iteration. It receives `query`, `hits`, `history`, `prior_goals`, `run_id` and emits an `Observation` with the current goal list. On the first iteration it decomposes the query into bounded goals. On every later iteration it preserves the goal list shape and updates only `done` flags and the `attach_artifact_id` field on the next unfinished goal. Perception subsumes the Verifier — a goal becomes `done` the moment history contains an action that satisfies it. Perception is pinned to Gemini via `provider="g"` with `temperature=1.0` (Gemini 3 loops at low temperatures).

**Decision** receives one goal, relevant memory hits, optionally attached artifact bytes, recent history, and the MCP tool list. It returns exactly one of: a plain-text answer, or a single `ToolCall`. Never both. Routed via `auto_route="decision"`.

**Action** dispatches one tool call over MCP stdio. No LLM. Collapses content blocks to one string. If the result exceeds `ARTIFACT_THRESHOLD_BYTES = 4096`, it persists to the ArtifactStore and returns a descriptor + `art:<sha>` handle. Otherwise it returns the text inline with `art_id=None`. Action also refuses any tool_call whose `arguments` contain a `path`/`url`/`file`/`location` value beginning with `art:` — that pattern is an artifact handle, not a tool argument.

**Artifacts** is a content-addressable store. Handles look like `art:<sha256-prefix>`. Two files per artifact under `state/artifacts/`: a `.bin` with raw bytes and a `.json` with metadata. Memory holds only the handle. Perception sees only the handle. Decision sees raw bytes *only* when Perception attaches them via `goal.attach_artifact_id`.

**Gateway V3** is the substrate. Every LLM call routes through it. Perception uses `provider="g"`. Decision uses `auto_route="decision"`. Memory.remember and Memory.relevant use `auto_route="memory"`. The gateway's response carries `router_decision`, `reasoning_applied`, `cache_read_input_tokens`, `cache_creation_input_tokens`, `fallback_used` — log all of these.

---

## 4. schemas.py — Pydantic v2 contracts

Every boundary between roles is a Pydantic model. Use Pydantic v2 syntax (`BaseModel`, `Field`, `Literal`, `ConfigDict`, `model_validator`).

```python
from __future__ import annotations
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, model_validator

class MemoryItem(BaseModel):
    id: str
    kind: Literal["fact", "preference", "tool_outcome", "scratchpad"]
    keywords: list[str] = Field(default_factory=list)
    descriptor: str
    value: dict = Field(default_factory=dict)
    artifact_id: str | None = None
    source: str
    run_id: str
    goal_id: str | None = None
    confidence: float = 1.0
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Artifact(BaseModel):
    id: str                       # "art:<sha256-prefix>"
    content_type: str
    size_bytes: int
    source: str
    descriptor: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Goal(BaseModel):
    id: str                       # assigned by outer loop as "g1", "g2", ...
    text: str
    done: bool = False
    attach_artifact_id: str | None = None

class Observation(BaseModel):
    goals: list[Goal]

class ToolCall(BaseModel):
    name: str
    arguments: dict

class DecisionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: str | None = None
    tool_call: ToolCall | None = None

    @model_validator(mode="after")
    def exactly_one(self) -> "DecisionOutput":
        if (self.answer is None) == (self.tool_call is None):
            raise ValueError("DecisionOutput must populate exactly one of answer / tool_call")
        return self
```

**Critical schema rules** (don't deviate):

- The Perception output schema you send to the LLM via `response_format` must use **positional identity** — *do not include a `goal.id` field in the schema sent to the model*. Ids are assigned by the outer loop using position (`g{i+1}`).
- Memory hits shown to Perception must include an **integer `artifact_index`** for entries that carry artifacts. The model emits `attach_artifact_index: <int>` rather than a string handle. The outer loop maps that index back to the real `art:` handle. Drop any out-of-range index silently.

Every Pydantic model construction must be logged through `logger.py` (see section 11) — input data shown, validation result shown. Validation errors must be caught and re-raised with the role name attached so the dashboard can highlight them.

---

## 5. memory.py — typed service + ArtifactStore

**`Memory`** owns `state/memory.json` and exposes:

- `read(query: str, history: list[dict], kinds: list[str] | None = None, top_k: int = 8) -> list[MemoryItem]`
  Pure Python. Lowercase, strip a small stopword set, intersect query+history tokens with each item's `keywords + tokens(descriptor)`, rank by overlap count, return top_k. Must run in milliseconds for hundreds of items. **No LLM call.** The dashboard must show *all hits* returned (often noisy) so the student sees the "dumb memory" behavior.

- `filter(kinds: list[str] | None = None, goal_id: str | None = None, recent: int | None = None) -> list[MemoryItem]`
  Structured filter, no LLM.

- `relevant(query: str, kinds: list[str] | None = None, top_k: int = 5) -> list[MemoryItem]`
  LLM-scored relevance over a kind-filtered pool, via gateway with `auto_route="memory"`. Used only when keyword recall is weak. Implement but expect rare use.

- `remember(raw_text: str, source: str, run_id: str, goal_id: str | None = None) -> MemoryItem | None`
  One gateway call with `auto_route="memory"`. Pinned to Gemini for reliability. The LLM returns a JSON object: `{kind, keywords, descriptor, value}`. The implementation wraps it in a MemoryItem, assigns an id, persists, returns. **Returns None if the classifier finds no durable content** (e.g., a query with no extractable fact/preference) — the caller does not error.

- `record_outcome(tool_call: ToolCall, result_text: str, artifact_id: str | None, run_id: str, goal_id: str) -> MemoryItem`
  Pure Python. `kind="tool_outcome"`. Keywords derived from tool name and argument tokens. Descriptor like `"fetch_url(<url>) -> art:abc..."` or `"web_search(<query>) -> 3 results"`. **No LLM call.**

**`ArtifactStore`** owns `state/artifacts/` and exposes:

- `put(blob: bytes, *, content_type: str, source: str, descriptor: str) -> str` — sha256 the blob, take first 16 chars as prefix, write `<prefix>.bin` and `<prefix>.json` under `state/artifacts/`, return `art:<prefix>`. Idempotent (same bytes → same handle).
- `get_bytes(artifact_id: str) -> bytes`
- `get_meta(artifact_id: str) -> Artifact`
- `exists(artifact_id: str) -> bool`

No eviction. The store is append-only for this assignment.

**Persistence**: lazy load on first read; atomic write (write to tempfile, fsync, rename) after each mutation. Use Pydantic's `model_dump(mode="json")` to serialize datetimes.

---

## 6. perception.py — the orchestrator

```python
class Perception:
    async def observe(
        self,
        query: str,
        hits: list[MemoryItem],
        history: list[dict],
        prior_goals: list[Goal],
        run_id: str,
    ) -> Observation: ...
```

Behavior:

1. Read `prompts/perception_system.md` as the system message.
2. Compose the user message: original query; hits rendered with `[i] kind=... descriptor=... [artifact_index=N if artifact_id else absent]`; recent history (last 8 events); prior_goals with current done flags.
3. Build a gateway call with `provider="g"` (Gemini), `temperature=1.0`, `response_format` = JSON schema of `{goals: [{text, done, attach_artifact_index|null}]}` (no `id` field).
4. Parse the JSON. Generate goal ids by position (`g{i+1}`). Map `attach_artifact_index` back to the real `art:` handle by indexing into the hits list as it was presented. **Drop any index that's out of range or points to a hit without `artifact_id`.**
5. Return `Observation(goals=[...])`.

**Perception's four obligations** (encoded in the system prompt, verbatim):

1. If prior_goals is empty, decompose the query into one or more bounded goals, each a short imperative.
2. For each prior goal, examine history. Mark `done: true` the moment history contains an action that satisfies it. Once done, the goal remains done in every subsequent iteration.
3. For the first unfinished goal, decide whether it needs raw bytes from a previously fetched artifact. If yes, set `attach_artifact_index` to one of the indices shown in MEMORY HITS.
4. Preserve goal order. Do not reorder, insert in the middle, or drop a goal.

Perception folds in the Verifier. There is no separate verify step in the loop.

**Force-attach safety net** (required for Query D): when the first unfinished goal's text contains any of `synthesise, synthesize, extract, list, compare, decide` (case-insensitive) AND at least one hit carries an `artifact_id`, the implementation must set `attach_artifact_index` to the *most recent* such hit, even if the model didn't. This guard reduces dependence on the model's reasoning about which artifact is relevant. Apply this guard *after* parsing the model's response, not in the prompt.

---

## 7. decision.py — single LLM call, two possible outputs

```python
class Decision:
    async def next_step(
        self,
        goal: Goal,
        hits: list[MemoryItem],
        attached: list[tuple[str, bytes]],
        history: list[dict],
        mcp_tools: list[dict],
    ) -> DecisionOutput: ...
```

Behavior:

1. Read `prompts/decision_system.md` as the system message.
2. Compose the user message: the goal text; relevant memory hits (handles + descriptors only); recent history (last 8 events); an `ATTACHED ARTIFACTS:` section if `attached` is non-empty, each entry rendered as

   ```
   --- art:<id> (<n> bytes) ---
   <utf-8 decode of bytes, truncated to ~32 KB>
   --- end ---
   ```

3. Build a gateway call with `auto_route="decision"`, `tools=mcp_tools`, `tool_choice="auto"`.
4. If response has `tool_calls[]`, wrap the first entry in a `ToolCall`, return `DecisionOutput(tool_call=...)`. Otherwise return `DecisionOutput(answer=response.text)`.

**Decision's three system-prompt rules** (verbatim):

1. **Respond with exactly one of two outputs.** Either an answer or a tool call. Never both.
2. **Strings beginning with `art:` are internal artifact handles.** They reference the artifact store. MCP tools accept real file paths and URLs. When the goal requires the bytes of an artifact, they appear in the prompt under `ATTACHED ARTIFACTS:`. Read them there. Do not pass an `art:` handle as a `path`, `url`, `file`, or `location` argument to any tool.
3. **Substantive answers.** When the goal asks for an extraction, a list, a comparison, or a selection, the answer must be substantive: at least three sentences or a list of items. Do not return meta-answers like "the page has been fetched, how would you like to proceed."

---

## 8. action.py — pure dispatch (no LLM)

```python
class Action:
    async def execute(
        self,
        session: ClientSession,
        tool_call: ToolCall,
    ) -> tuple[str, str | None]: ...
```

Behavior:

1. **Artifact-handle guard.** Walk `tool_call.arguments`. If any value associated with a key matching `(path|url|file|location)` is a string starting with `art:`, return `("error: artifact handles are not paths/urls — read attached bytes in the prompt instead", None)` *without* dispatching. Log this as an explicit "guarded" event so the dashboard surfaces it.
2. `result = await session.call_tool(tool_call.name, arguments=tool_call.arguments)`.
3. Collapse `result.content` blocks into one text string.
4. If `len(text.encode("utf-8")) > ARTIFACT_THRESHOLD_BYTES`, call `ArtifactStore.put(text.encode("utf-8"), content_type=..., source=tool_call.name, descriptor=f"{tool_call.name}({...})")`, and return `(f"[artifact {art_id}, {n} bytes] preview: {text[:300]}", art_id)`.
5. Otherwise return `(text, None)`.

About thirty lines of real logic. Zero LLM calls.

---

## 9. agent6.py — orchestrator loop + interactive REPL

The orchestrator loop, exactly as specified, plus an interactive REPL wrapper.

```python
MAX_ITERATIONS = 14    # global cap; per-query expectations enforced in validate.py

async def run(query: str) -> str:
    """One agent run for one query."""
    ensure_gateway()
    run_id = uuid.uuid4().hex[:8]
    log.run_start(run_id=run_id, query=query)
    history: list[dict] = []
    prior_goals: list[Goal] = []

    # 1) Durable-memory contract — classify the user query so any
    #    fact / preference inside it survives into future runs.
    classified = memory.remember(query, source="user_query", run_id=run_id)
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
            log.perception(it, observation=obs)

            if all(g.done for g in obs.goals):
                log.all_done(it, goals=obs.goals)
                break

            goal = next(g for g in obs.goals if not g.done)
            log.next_unfinished(it, goal=goal)

            attached: list[tuple[str, bytes]] = []
            if goal.attach_artifact_id and artifacts.exists(goal.attach_artifact_id):
                attached.append((goal.attach_artifact_id,
                                 artifacts.get_bytes(goal.attach_artifact_id)))
                log.attach(it, art_id=goal.attach_artifact_id,
                           size=len(attached[0][1]))
            elif goal.attach_artifact_id:
                log.attach_dropped(it, art_id=goal.attach_artifact_id,
                                   reason="artifact not found in store")

            out = await decision.next_step(goal, hits, attached, history, tools_for_decision)
            log.decision(it, output=out, goal_id=goal.id)

            if out.answer is not None:
                history.append({
                    "iter": it, "kind": "answer",
                    "goal_id": goal.id, "text": out.answer,
                })
                continue

            result_text, art_id = await action.execute(session, out.tool_call)
            log.action(it, tool_call=out.tool_call,
                       result_text=result_text, artifact_id=art_id)

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
```

**REPL wrapper** in the same file:

```python
async def main():
    await start_dashboard()        # FastAPI server on :8102 (non-blocking)
    print(BANNER)
    while True:
        try:
            query = input("\nEnter query > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nbye.")
            break
        if not query or query.lower() in {":quit", ":q", "exit"}:
            print("bye.")
            break
        try:
            final = await run(query)
        except Exception as e:
            log.error(e)
            print(f"ERROR: {e}")
            continue
        print("\nFINAL:", final)

if __name__ == "__main__":
    asyncio.run(main())
```

**Five observations the loop encodes** (these are contract, not optional):

1. The very first action after start is `memory.remember(query, ...)`. This is the durable-memory contract for Query C.
2. Memory is read at the top of every iteration. The agent asks what it already knows before doing anything else.
3. `prior_goals` is passed into Perception, giving stable identity across iterations.
4. Artifact attachment is gated on `artifacts.exists(...)`. If Perception emits an attachment handle that does not correspond to a real artifact, the loop silently drops it (logged as `attach_dropped`).
5. Decision selects actions; Perception declares goals done.

---

## 10. mcp_server.py — the 9-tool MCP server

Use the teacher's provided `mcp_server.py` **unchanged**. It exposes nine tools over stdio: `web_search`, `fetch_url`, `get_time`, `currency_convert`, `read_file`, `list_dir`, `create_file`, `update_file`, `edit_file`. It requires a `.env` file with `TAVILY_API_KEY` (DDG fallback if absent). It uses Tavily (advanced search, hard cap 5 results) and crawl4ai (headless Chromium → clean markdown). File tools are sandboxed under `./sandbox/`.

The agent opens the MCP server via `mcp.client.stdio.stdio_client(StdioServerParameters(command="python", args=["mcp_server.py"]))`. Run from the `assignment6/` directory so the sandbox lives there.

---

## 11. logger.py — structured event logger

`logger.py` is the **single source of truth for observability**. Every role calls into it. The logger has three sinks:

1. **stdout** — short human-readable trace in the format the lecture screenshots use:
   ```
   ── iter 1 ──
   [memory.read]    1 hits
   [perception]     [open] Fetch the Wikipedia page for Claude Shannon
                    [open] Extract birth date, death date, and three contributions
   [decision]       TOOL_CALL: fetch_url({"url": "https://en.wikipedia.org/wiki/Claude_Shannon"})
   [action]         → [artifact art:09ff0a67fe264eb9, 263065 bytes] preview: ...
   ```
2. **logs/run-`<run_id>`.jsonl** — one JSON object per event, line-delimited, for replay and grading.
3. **dashboard SSE channel** — same JSON events pushed to all connected browsers in real time.

**Event schema** (every event is one JSON object):

```json
{
  "ts": "2026-05-24T11:32:08.412Z",
  "run_id": "a1b2c3d4",
  "iter": 2,
  "role": "perception",
  "event": "observe",
  "input": { "query": "...", "hits_count": 2, "history_len": 1, "prior_goals_len": 2 },
  "output": { "goals": [ {"id":"g1","text":"...","done":true,"attach_artifact_id":null},
                          {"id":"g2","text":"...","done":false,"attach_artifact_id":"art:09ff..."} ] },
  "llm": {
    "provider": "g",
    "model": "gemini-3-pro",
    "tier": "LARGE",
    "router_decision": "perception → gemini-3-pro (provider override)",
    "messages_in_tokens": 1842,
    "tokens_out": 217,
    "temperature": 1.0,
    "reasoning_applied": true,
    "cache_read_input_tokens": 0,
    "cache_creation_input_tokens": 0,
    "fallback_used": false,
    "duration_ms": 1374,
    "messages": [ /* full prompt sent */ ],
    "response_raw": "..."
  },
  "pydantic": {
    "model": "Observation",
    "validated": true,
    "errors": []
  }
}
```

Not every event has every field. The shape is consistent: `ts, run_id, iter, role, event` always present; `input` and `output` always present; `llm` present only when an LLM call was made; `pydantic` present when a model was constructed at this boundary.

**Required event types**:

| role | event | when |
|---|---|---|
| `loop` | `run_start` | at the top of `run(query)` |
| `loop` | `iter_start` | at the top of each iteration |
| `loop` | `all_done` | when all goals are done |
| `loop` | `attach` | when an artifact is attached to Decision |
| `loop` | `attach_dropped` | when a hallucinated artifact id is dropped |
| `loop` | `run_end` | at the end of `run(query)` (with final answer) |
| `memory` | `remember` | the pre-loop classify call |
| `memory` | `read` | every iteration's keyword search (with **all** hits listed) |
| `memory` | `record_outcome` | after every Action call |
| `perception` | `observe` | every iteration |
| `decision` | `next_step` | every iteration with an unfinished goal |
| `action` | `execute` | every tool dispatch |
| `action` | `guarded` | when `art:` was passed as a path/url |
| `artifacts` | `put` | when a new artifact is stored |
| `gateway` | `call` | every LLM call (also embedded in role event's `llm` block) |
| `pydantic` | `construct` | every Pydantic model construction at a boundary |
| `pydantic` | `error` | every Pydantic ValidationError |

**Hooking Pydantic**: provide a small helper

```python
def log_construct(model_cls, **data):
    try:
        obj = model_cls(**data)
        log.pydantic_ok(model=model_cls.__name__, data=data, result=obj.model_dump(mode="json"))
        return obj
    except ValidationError as e:
        log.pydantic_err(model=model_cls.__name__, data=data, errors=e.errors())
        raise
```

…and use it everywhere a role boundary constructs a Pydantic model.

**Hooking the gateway**: wrap the gateway client so every call emits a `gateway.call` event before/after, capturing the full message list, the response text, all the honest signals (`reasoning_applied`, `cache_read_input_tokens`, `cache_creation_input_tokens`, `fallback_used`, `router_decision`), token counts, and duration.

---

## 12. dashboard.py — live web dashboard at :8102

A FastAPI app served by uvicorn, started in the background by `agent6.main()` before the REPL begins.

**Server**:

- `GET /` — serves `static/index.html`.
- `GET /static/*` — serves `app.js`, `style.css`.
- `GET /events` — Server-Sent Events stream. Every event the logger emits is pushed to all connected clients as `data: {...}\n\n`.
- `GET /api/state` — returns current `state/memory.json` and a listing of `state/artifacts/` (handles + metadata).
- `GET /api/runs` — lists `logs/*.jsonl` files for historical replay.
- `GET /api/runs/{run_id}` — returns the full JSONL of a past run for replay.

**`index.html` layout** (single-page, no framework — vanilla JS + clean CSS):

A header showing the current run id, query, and elapsed time. Below it, **four columns side-by-side** named **Memory**, **Perception**, **Decision**, **Action**, plus a fifth **Artifacts** strip across the bottom. Events stream into the right column. Each iteration gets its own bordered card with a clear "── iter N ──" header.

Inside each iteration card:

- **Memory column** shows the hits from `memory.read` — *all of them*, with each hit's `kind`, `descriptor`, `artifact_index` if present, and which keywords matched. This is the "dumb memory dump" visualization.
- **Perception column** shows the input summary, the full Pydantic-validated `Observation`, and which LLM tier handled it (`router_decision`). A collapsible "show prompt" reveals the full messages sent.
- **Decision column** shows the input summary, the Pydantic-validated `DecisionOutput`, with answer or tool_call highlighted. Collapsible "show prompt" reveals full messages including `ATTACHED ARTIFACTS:` section when present.
- **Action column** shows the tool name, arguments (formatted JSON), result descriptor, and artifact_id (if any). Guarded calls (artifact-handle leak) shown in red.
- **Artifacts strip** lists all artifacts created so far, with handle, size, content_type, source, descriptor.

Below the columns, three persistent panels:

- **Gateway calls** — log of every LLM call across the run, sortable: provider, tier, router_decision, tokens_in, tokens_out, duration_ms, reasoning_applied, fallback_used.
- **Memory state** — table of every `MemoryItem` currently in `state/memory.json`, with kind, keywords, descriptor, artifact_id, source, run_id. Refreshed when the logger emits a `memory` event.
- **Pydantic events** — table of every model construction at a role boundary, with the result of validation (✓/✗ and any errors).

A small "Replay run" dropdown lets the student select a past `run-<id>.jsonl` and re-stream it through the same UI without re-running the agent.

**Style**: monospace for log lines, sans-serif for headers. Dark theme to match the lecture screenshots. No external CSS frameworks — keep `style.css` under 200 lines. No build step.

---

## 13. Prompt files

Each is a short markdown file. Keep them declarative and bounded.

**`prompts/perception_system.md`** must encode:

- The four obligations from section 6, verbatim.
- The output schema description: a JSON object with one field `goals`, an array of `{text: str, done: bool, attach_artifact_index: int | null}`. No goal id field.
- A one-line note that this is iteration N of an agent loop and `prior_goals` (when non-empty) represents the goal list emitted on the previous iteration — *preserve it*.
- One worked example showing input/output for a query of the same shape (one of the four queries is fine).

**`prompts/decision_system.md`** must encode:

- The three rules from section 7, verbatim.
- A note that the `goal.text` is the entirety of the current task; do not work on other goals.
- A note that `ATTACHED ARTIFACTS:`, when present, contains the bytes to read from — not a metadata reference.

Both prompts are loaded with `Path(...).read_text(encoding="utf-8")` at startup; the dashboard's "show prompt" panel displays the assembled message verbatim.

---

## 14. The four target queries — specifications and expected traces

These four are the test cases `validate.py` runs. They are *not* hardcoded in `agent6.py`. The interactive REPL accepts any query; the four below are the queries the student types when demonstrating the assignment.

### Query A — Shannon Wikipedia (artifact attach test)

```
Fetch https://en.wikipedia.org/wiki/Claude_Shannon and tell me his birth date, death date, and three key contributions to information theory.
```

**Expected trace** (3 iterations):

```
── iter 1 ──
[memory.read]    1 hits      (or 0 on first ever run; tool_outcome from earlier runs may appear)
[perception]     [open] Fetch the Wikipedia page for Claude Shannon
                 [open] Extract birth date, death date, and three contributions
[decision]       TOOL_CALL: fetch_url({"url": "https://en.wikipedia.org/wiki/Claude_Shannon"})
[action]         → [artifact art:09ff... , 263065 bytes] preview: ...

── iter 2 ──
[memory.read]    2 hits
[perception]     [done] Fetch the Wikipedia page for Claude Shannon
                 [open] Extract birth date, death date, and three contributions
                     attach=art:09ff...
[attach]         art:09ff... (263065 bytes)
[decision]       ANSWER: Claude Shannon (1916–2001) was an American mathematician...

── iter 3 ──
[perception]     [done] Fetch the Wikipedia page for Claude Shannon
                 [done] Extract birth date, death date, and three contributions
[done] all 2 goals satisfied

FINAL: Birth date: April 30, 1916. Death date: February 24, 2001.
       Three key contributions: (1) A Mathematical Theory of Communication
       (1948), which established the mathematical foundations of digital
       communication; (2) introduction of the bit as the unit of information
       and the concept of entropy; (3) the Shannon limit, the theoretical
       maximum rate at which information can be transmitted over a noisy
       channel.
```

### Query B — Tokyo weekend + weather (multi-goal carryover)

```
Find family-friendly things to do in Tokyo this weekend, check the weather forecast, and recommend the best activity given the weather.
```

Expected ~6 iterations: search activities → fetch a page or two → search weather → reason → answer. Memory carries the activity list across goals. The recommendation must depend on the weather (indoor if rainy, outdoor if clear).

### Query C — Mom's birthday (durable memory across two runs)

**Run 1** (4 iterations including pre-loop classify):

```
My mom's birthday is 15 May 2026. Remember that and give me a calendar reminder for two weeks before and on the day.
```

Expected trace:

```
[memory.remember]   classified "Mom's birthday is 15 May 2026" as fact
                    keywords: ["mom", "birthday", "may", "2026"]

── iter 1 ──
[perception]     [open] Remember mom's birthday (15 May 2026)
                 [open] Create a reminder for 1 May 2026 (two weeks before)
                 [open] Create a reminder for 15 May 2026
[decision]       TOOL_CALL: create_file({"path": "reminders/mom_birthday_2026.txt", ...})
[action]         → ok

... two more iterations creating the reminders ...

FINAL: Reminders created. Mom's birthday on 15 May 2026 is recorded.
```

**Run 2** (2 iterations) — runs against the same `state/`:

```
When is mom's birthday?
```

Expected trace:

```
── iter 1 ──
[memory.read]    1 hits
                 fact: "Mom's birthday is on 15 May 2026"
[perception]     [open] Answer when mom's birthday is
[decision]       TOOL_CALL: list_dir({"path": "reminders/"})
[action]         → [file: mom_birthday_2026.txt]

── iter 2 ──
[memory.read]    2 hits
[perception]     [done] Answer when mom's birthday is
[decision]       ANSWER: Mom's birthday is on 15 May 2026.

[done] all 1 goals satisfied
```

The fact is carried across run boundaries by the persistent `state/memory.json` file. `validate.py` runs both runs sequentially without cleaning state between them.

### Query D — Asyncio research (multi-source synthesis)

```
Search for 'Python asyncio best practices', read the top 3 results, and give me a short numbered list of the advice they agree on.
```

Expected 5–7 iterations: one `web_search`, three `fetch_url` (each producing an artifact ~30–60 KB), one synthesis iteration where Perception's **force-attach safety net** picks the most recent synthesis-relevant artifact and Decision produces the numbered list.

Expected final answer shape:

```
1. Use asyncio.run() as the program entry point
2. Prefer asyncio.gather and asyncio.TaskGroup over manual awaits when
   running multiple coroutines concurrently
3. Avoid blocking calls in async code; use asyncio.to_thread() for
   CPU-bound or blocking I/O
4. Use timeouts on every external call to prevent hangs
5. Limit concurrency with semaphores when calling rate-limited
   external services
```

---

## 15. validation.json — PoP (Proof of Pass)

One file, four entries. The shape:

```json
{
  "queries": [
    {
      "id": "A",
      "name": "shannon_wikipedia",
      "query": "Fetch https://en.wikipedia.org/wiki/Claude_Shannon ...",
      "expected_iterations": 3,
      "max_iterations": 6,
      "clean_state_before": true,
      "must_contain": ["1916", "2001", "information theory"],
      "must_not_contain_any": ["I cannot", "as an AI"],
      "memory_assertions": [
        { "kind": "tool_outcome", "min_count": 1, "must_have_artifact_id": true }
      ],
      "artifact_assertions": [
        { "min_count": 1, "min_size_bytes": 50000 }
      ]
    },
    {
      "id": "B",
      "name": "tokyo_weekend",
      "query": "Find family-friendly things to do in Tokyo this weekend ...",
      "expected_iterations": 6,
      "max_iterations": 12,
      "clean_state_before": true,
      "must_contain_any_of": ["museum", "park", "aquarium", "garden", "indoor", "outdoor"],
      "must_contain": ["weather", "recommend"],
      "memory_assertions": [{ "kind": "tool_outcome", "min_count": 2 }]
    },
    {
      "id": "C",
      "name": "mom_birthday_durable",
      "query": "My mom's birthday is 15 May 2026. Remember that and give me a calendar reminder for two weeks before and on the day.",
      "expected_iterations": 4,
      "max_iterations": 8,
      "clean_state_before": true,
      "must_contain_any_of": ["created", "noted", "saved", "remember", "reminder"],
      "memory_assertions": [
        { "kind": "fact", "descriptor_contains": ["mom", "birthday"], "min_count": 1 }
      ],
      "follow_up": {
        "query": "When is mom's birthday?",
        "preserve_state": true,
        "expected_iterations": 2,
        "max_iterations": 4,
        "must_contain": ["15", "May", "2026"]
      }
    },
    {
      "id": "D",
      "name": "asyncio_synthesis",
      "query": "Search for 'Python asyncio best practices', read the top 3 results, and give me a short numbered list of the advice they agree on.",
      "expected_iterations": 6,
      "max_iterations": 14,
      "clean_state_before": true,
      "must_contain_any_of": ["1.", "2.", "3.", "•", "asyncio.run", "TaskGroup", "gather"],
      "must_contain": ["asyncio"],
      "memory_assertions": [{ "kind": "tool_outcome", "min_count": 4 }],
      "artifact_assertions": [{ "min_count": 3 }]
    }
  ]
}
```

`validate.py`:

```python
import asyncio, json, shutil, sys
from pathlib import Path
from agent6 import run

async def main():
    spec = json.loads(Path("validation.json").read_text())
    results = []
    for q in spec["queries"]:
        if q.get("clean_state_before"):
            shutil.rmtree("state", ignore_errors=True)
        final = await run(q["query"])
        failures = check(final, q)               # must_contain, iter cap, memory_assertions, ...
        if q.get("follow_up"):
            # do NOT clean state between primary and follow_up
            fup = q["follow_up"]
            final2 = await run(fup["query"])
            failures += check(final2, fup)
        results.append((q["id"], failures))
    for qid, fs in results:
        print(f"[{qid}] {'PASS' if not fs else 'FAIL'}")
        for f in fs: print("   -", f)
    sys.exit(0 if all(not fs for _, fs in results) else 1)

if __name__ == "__main__":
    asyncio.run(main())
```

`check(final, spec)` reads `state/memory.json` and `state/artifacts/` to evaluate the assertion blocks.

---

## 16. README.md (top of `assignment6/`)

The README has six sections, in this order:

1. **What this is** — one paragraph: the EAGV3 S6 four-role agent.
2. **Setup** — `cd assignment6 && uv sync && cp .env.example .env`.
3. **Run** — `uv run python agent6.py`, then open `http://localhost:8102` in browser, type queries at the terminal prompt.
4. **Validate** — `uv run python validate.py`; what passing looks like.
5. **The four target queries** — one paragraph each, with the exact text the user types.
6. **Captured terminal output** — four blocks, one per query. Captured from a clean state on the student's machine. For Query C, both runs shown, with no `state/` reset between them.

A YouTube link to a demonstration video goes at the very top, under the title.

---

## 17. Constraints (hard)

- **Pydantic v2** on every boundary. No raw dict passing between roles. Every model construction at a boundary goes through the `log_construct` helper.
- **uv** for everything. No `pip install`, no `python -m venv`, no `source venv/bin/activate`.
- **One global `.env`** at `assignment6/.env`. No per-role, per-query, or per-folder env files. The MCP server loads it from `Path(__file__).parent / ".env"`, and `agent6.py` loads it at startup so the gateway inherits all keys via `os.environ`. `.env` is gitignored; `.env.example` is committed.
- **MCP stdio** transport for tool dispatch. Do not reimplement tool calling.
- **Gateway V3** is the substrate for every LLM call. No direct provider SDK calls.
- **No regex on LLM output.** Use Pydantic + JSON `response_format`.
- **No third-party agent frameworks.** No LangChain, LangGraph, CrewAI, AutoGen, Haystack, llama-index agents, etc.
- **`state/` is gitignored**, cleanable manually with `rm -rf state/`. The validator cleans it where the spec says `"clean_state_before": true`. For Query C's follow-up, state is *preserved*.
- **Iteration cap is enforced**: a query that exceeds 2× expected is a failure. Tune prompts until convergence is within bounds.
- **Logging is mandatory.** Every LLM call, every Pydantic boundary, every iteration, every tool I/O is logged through `logger.py`. If an event happens and the dashboard does not see it, the implementation is incomplete.

---

## 18. Build order

Do it in this order. Do not skip ahead. Verify each step works before moving on.

0. **Acquire API keys before writing code.** Sign up for the providers in section 2's table — at minimum `GEMINI_API_KEY`, `TAVILY_API_KEY`, and two router-pool keys (recommended: Groq + Cerebras). Store all of them in `assignment6/.env`. Run the smoke test at the end of section 2 to confirm `os.environ` sees them after `load_dotenv`.
1. Repo skeleton: `.gitignore`, top-level `Session 6 - Agentic Architecture/` directory, place `llm_gatewayV3/` next to `assignment6/`.
2. `assignment6/pyproject.toml`, `.python-version`, `.env.example` (with all keys from section 2's tables, one comment per key). Run `uv sync`. Confirm `import llm_gateway_v3` works.
3. **Verify the gateway's env-var names match yours.** Open `llm_gatewayV3/` and locate where the router pool is configured. If a pool member uses a non-standard env name, mirror your value into that name inside `.env`. Run a one-line gateway probe (the gateway's own examples folder usually has one) to confirm it can reach at least one router-pool LLM.
4. `schemas.py` — all Pydantic models with the `model_validator` on `DecisionOutput`.
5. `logger.py` — stdout + jsonl sinks first; dashboard sink added later (it can be a no-op until the dashboard server is in place).
6. `memory.py` — `Memory` + `ArtifactStore`. Unit-test by hand: write a fact, read it back, check `state/memory.json` looks right.
7. `mcp_server.py` — copy unchanged from teacher's file. Run `uv run python mcp_server.py` and confirm it speaks stdio. Confirm `web_search` works against Tavily by calling the tool once from a small harness.
8. `action.py` — including the artifact-handle guard.
9. `prompts/perception_system.md`, `prompts/decision_system.md`.
10. `perception.py` and `decision.py`.
11. `agent6.py` — orchestrator loop only (no REPL yet, no dashboard yet). Test by calling `await run("hello")` from a small harness and watching stdout.
12. Test **Query A** end-to-end via the harness. Expect 3 iterations. Tune until it passes.
13. Test **Query C run 1** then **Query C run 2** with the same `state/` between them. Expect 4 + 2 iterations.
14. Test **Query B** and **Query D**. Tune. Query D requires the force-attach safety net in `perception.py`.
15. `dashboard.py` + `static/index.html` + `app.js` + `style.css`. Wire the SSE sink into `logger.py`. Confirm browser at `:8102` shows events in real time during a run.
16. Add the REPL wrapper in `agent6.py`. Confirm `Enter query > ` blocks, runs, returns to prompt.
17. `validation.json` and `validate.py`. Run `uv run python validate.py` and confirm all four queries PASS.
18. Capture clean-state terminal outputs into `README.md`. Record demonstration video. Commit.

---

## 19. Deliverables

- **GitHub repo** containing the code, with `state/` and `logs/` excluded via `.gitignore`, and a README documenting how to run and how to validate.
- **README's "Captured terminal output"** section showing the four reference queries run from a clean state on the student's own machine.
- **YouTube link** demonstrating runs of all four queries end-to-end with the dashboard visible.
- **Perception and Decision prompts** — the two files in `prompts/` are the deliverable.
- **Validation JSON of PoP** — `validation.json` is the deliverable.

---

## 20. What is excluded

This assignment is not a summariser, a stock or crypto analyser, a price-comparison toy, or any single-tool-call agent. The four target queries are the test suite. Do not replace them, do not simplify them, do not add a fifth toy. If a query cannot be made to pass within 2× its expected iteration count, the prompt or contract is wrong — fix that, not the query.

---

## 21. Failure modes to actively guard against

These are the common assignment mistakes from the lecture. Add explicit defenses for each, and surface each defense's activation on the dashboard.

1. **Decision returns a meta-answer** ("the page has been fetched, how would you like to proceed?") — Defended by Decision's substantive-answer rule and by Perception keeping the goal open until the answer is substantive.
2. **Perception drops a goal between iterations.** — Defended by positional identity and the explicit "preserve goal order" obligation.
3. **Perception hallucinates an artifact id.** — Defended by indexed artifact references in the prompt schema and the `artifacts.exists()` guard in the outer loop (logged as `attach_dropped`).
4. **Decision passes an `art:` handle as a tool argument.** — Defended by the explicit rule in the Decision system prompt and the runtime guard in `action.py` (logged as `guarded`).
5. **Query C run 2 returns nothing.** — Defended by `memory.remember` extracting a non-empty `keywords` list at write time, and by `memory.read` keyword-matching on both `keywords` and tokenized `descriptor`.
6. **Query D refuses to synthesize.** — Defended by Perception's force-attach safety net for synthesis-keyword goals.
7. **One change fixes Query A but breaks Query D.** — Defended by `validate.py` running all four queries on every prompt change. Treat the four queries as one test suite.
8. **`state/` accidentally committed.** — `.gitignore` includes `state/` and `logs/`; verify with `git check-ignore -v state/ logs/`.
9. **Dashboard misses events** — verify by closing the browser, running a query, then opening the browser and selecting the run from the replay dropdown — the same trace must appear.

---

End of spec. Build the project described in section 1, following the order in section 18, honoring the contracts in sections 3–9, the logging requirements in sections 11–12, and the hard constraints in section 17. Stop and ask only if a section here contradicts another section here. Otherwise, execute.
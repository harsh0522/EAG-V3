# CLAUDE.md — Session 8 Assignment: Multi-Agent DAG Orchestration

## Project Location

All code lives at:
```
/Users/harshagarwal/Documents/EAGv3/session8/assignment8/
```

The directory structure to create:
```
assignment8/
├── claude.md                      ← this file
├── readme.md                      ← run instructions, architecture notes, logs summary
├── .env                           ← all API keys (already exists, do not touch)
├── llm_gatewayV8/                 ← already exists, do NOT write any code inside
│   └── (gateway runs on port 8108, do not modify)
├── agent_config.yaml              ← skill registry (planner, researcher, retriever,
│                                     distiller, summariser, critic, formatter,
│                                     coder, sandbox_executor + 1 new custom skill)
├── flow.py                        ← DAG orchestrator (Executor + Graph over NetworkX)
├── skills.py                      ← Skill class: loads yaml, renders prompts
├── persistence.py                 ← SessionStore: atomic JSON writes, resume logic
├── recovery.py                    ← classify_failure: transient / validation_error / upstream_failure
├── schemas.py                     ← Pydantic v2: NodeSpec, NodeState, AgentResult, SessionLoadError
├── perception.py                  ← byte-identical to S7, do not modify
├── decision.py                    ← byte-identical to S7, do not modify
├── action.py                      ← byte-identical to S7, do not modify
├── memory.py                      ← byte-identical to S7, do not modify
├── mcp_server.py                  ← byte-identical to S7, do not modify
├── artifacts.py                   ← byte-identical to S7, do not modify
├── vector_index.py                ← byte-identical to S7, do not modify
├── sandbox.py                     ← subprocess runner for sandbox_executor skill
├── prompts/
│   ├── planner.md                 ← 39-line planner system prompt
│   ├── researcher.md              ← researcher system prompt
│   ├── retriever.md               ← retriever system prompt
│   ├── distiller.md               ← distiller system prompt
│   ├── summariser.md              ← summariser system prompt
│   ├── critic.md                  ← critic system prompt (pass/fail verdict)
│   ├── formatter.md               ← formatter system prompt
│   ├── coder.md                   ← ASSIGNMENT TASK 4: fill this in (not a stub)
│   └── <custom_skill>.md          ← ASSIGNMENT TASK 5: new skill prompt
├── tests/
│   └── test_recovery.py           ← 22 unit tests (18 classify_failure + 4 critic-splice)
├── state/
│   └── sessions/                  ← full JSON trace of every run saved here atomically
│       └── <session_id>/
│           ├── query.txt
│           ├── graph.json
│           └── nodes/
│               └── n_XXX.json
├── logs/                          ← ALL logs go here, created automatically at runtime
│   ├── agent_run_<timestamp>.log
│   ├── gateway_calls_<timestamp>.log
│   ├── node_trace_<timestamp>.log
│   └── cost_summary_<timestamp>.log
├── viewer/
│   └── index.html                 ← single-page DAG replay viewer (see UI section)
├── requirements.txt
└── run.py                         ← entry point: python run.py "<query>" [--resume <sid>]
```

---

## Environment Variables

All API keys are loaded from `.env` at `assignment8/.env`. Never hardcode any key
anywhere in the code. Reference every key exclusively via `os.getenv()`.

```
# assignment8/.env  (never commit this file)

# LLM Gateway V8 (already running on port 8108)
GATEWAY_URL=http://localhost:8108

# Primary LLM providers (pass through gateway — do not call provider APIs directly)
GEMINI_API_KEY=your_key_here
GROQ_API_KEY=your_key_here
CEREBRAS_API_KEY=your_key_here

# Embedding model (Nomic via Ollama, already set up from S7)
OLLAMA_BASE_URL=http://localhost:11434

# MCP server socket (already running from S7)
MCP_SERVER_PATH=./mcp_server.py
```

Load pattern — use at the top of every Python file that needs keys:
```python
from dotenv import load_dotenv
import os

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))
GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8108")
```

---

## Hard Constraints (violations = broken assignment)

1. **No API keys in code** — every key via `os.getenv()` from `.env`.
2. **No code inside `llm_gatewayV8/`** — gateway is already built; leave it untouched.
3. **S7 modules byte-identical** — `perception.py`, `decision.py`, `action.py`,
   `memory.py`, `mcp_server.py`, `artifacts.py`, `vector_index.py` must not be modified.
4. **No third-party agentic frameworks** — no LangChain, no CrewAI, no LangGraph.
   Use NetworkX directly. Build everything from scratch.
5. **All logs go to `logs/`** — every runtime log file must be created under `assignment8/logs/`.
6. **Adding a skill = yaml edit + prompt file only** — touching the Executor for
   anything but a new generic mechanism is a bug.
7. **Recovery classifier unit tests must pass** — `python -m pytest tests/test_recovery.py`
   must be green after any change.
8. **Skills are a triple** — prompt file + MCP tools list + temperature. No per-skill
   Python subclass. One `Skill` class parameterised by yaml.

---

## Architecture Overview

### What changed from S7 → S8

Session 7 had a single loop: Perception → Decision → Action → memory writes → repeat.
Decision emitted at most one tool call per iteration. Three independent web fetches ran
sequentially; by iteration 10 the context carried nine iterations of accumulated history
(token bill ~O(n²)).

Session 8 replaces the loop with a **Directed Acyclic Graph (DAG)**:

```
USER QUERY
    │
    ▼
n:1  planner          ← emits the graph
   ╱    │    ╲
n:2    n:3   n:4      ← researcher nodes, run concurrently via asyncio.gather
(London)(Paris)(Berlin)
    ╲    │    ╱
     ▼   ▼   ▼
    n:5  coder        ← waits for all three researchers (asyncio.gather barrier)
     ╱         ╲
n:6 formatter   n:7 sandbox_executor   ← run concurrently after coder
    │
    ▼
  ANSWER
```

Key properties:
- **Acyclic by construction** — planner cannot emit a back-edge.
- **Dynamic** — new nodes are added as nodes complete; the graph visible at t=0 is
  rarely the final graph.
- **Persisted** — every node state write is atomic (`write-tmp` + `os.replace`);
  the run can be killed and resumed from the last successful write.

### Executor loop (pseudocode)
```python
while incomplete_nodes_exist():
    ready = [n for n in graph if all_predecessors_complete_or_skipped(n)]
    results = await asyncio.gather(*[run_node(n) for n in ready])
    for node, result in zip(ready, results):
        node.status = "complete"
        graph.extend_from(node.emitted_successors)   # planner output → new nodes
        session_store.persist(graph, node)
```

### Skill definition
A skill is a **triple** (prompt_file, tools_allowed, temperature). Loaded from
`agent_config.yaml` at startup. One `Skill` class; no per-skill Python subclass.

```yaml
# agent_config.yaml  (excerpt)
skills:
  planner:
    prompt: prompts/planner.md
    tools_allowed: []
    temperature: 0.4
    max_tokens: 1024

  researcher:
    prompt: prompts/researcher.md
    tools_allowed: [web_search, fetch_url]
    temperature: 0.7
    max_tokens: 2048

  distiller:
    prompt: prompts/distiller.md
    tools_allowed: []
    temperature: 0.1
    max_tokens: 1024
    critic: true          # ← orchestrator auto-inserts critic on every outgoing edge

  critic:
    prompt: prompts/critic.md
    tools_allowed: []
    temperature: 0.0      # deterministic pass/fail
    max_tokens: 256

  coder:
    prompt: prompts/coder.md
    tools_allowed: []
    temperature: 0.2
    max_tokens: 2048
    internal_successors: [sandbox_executor]  # orchestrator auto-inserts after coder

  sandbox_executor:
    prompt: prompts/sandbox_executor.md
    tools_allowed: []
    temperature: 0.0
    max_tokens: 512

  formatter:
    prompt: prompts/formatter.md
    tools_allowed: []
    temperature: 0.3
    max_tokens: 2048

  retriever:
    prompt: prompts/retriever.md
    tools_allowed: [search_knowledge]
    temperature: 0.2
    max_tokens: 1024

  summariser:
    prompt: prompts/summariser.md
    tools_allowed: []
    temperature: 0.3
    max_tokens: 1024

  # TASK 5: add your new skill here
  # <your_skill_name>:
  #   prompt: prompts/<your_skill_name>.md
  #   tools_allowed: [<mcp_tools_if_any>]
  #   temperature: <0.0-1.0>
  #   max_tokens: <budget>
```

> **Note on temperature**: Gemini documentation recommends temperature=1.0 for all
> skills. The values above are the architecturally motivated choices (critic at 0.0 for
> determinism, distiller at 0.1 for extraction reliability). If you observe looping or
> degraded reasoning on Gemini-routed skills, reset all to 1.0 and constrain behaviour
> in the prompt instead. Temperature is expected to become obsolete in future Gemini
> versions.

---

## Planner Prompt (`prompts/planner.md`)

The planner prompt must be ~39 lines. It tells the model to emit a JSON object with
`rationale` and `nodes`. Exact required content:

```markdown
You are the Planner. Emit the next set of nodes for the orchestrator.

Available skills:
  retriever          search the agent's indexed knowledge base
  researcher         fetch fresh content from the web (URLs, search)
  distiller          extract structured fields from raw text
  summariser         condense long content
  critic             pass/fail evaluation of an upstream node
  formatter          render the final user-facing answer (TERMINAL)
  coder              emit Python (routes to sandbox_executor automatically)
  sandbox_executor   run Python from coder
  <custom_skill>     <one-line description>

Output (JSON, no markdown):
{
  "rationale": "<one sentence>",
  "nodes": [
    {"skill": "<name>",
     "inputs": ["USER_QUERY" or "n:<label>" or "art:<id>"],
     "metadata": {"label": "<short_id>", "question": "<optional hint>"}}
  ]
}

Reference upstream nodes as "n:<label>" where label matches a
sibling's metadata.label. The final node must be a formatter.

When the user asks to compare or process N concrete items
("compare A, B, C" / "top 3 results"), emit one node per item so
the orchestrator can run them in parallel. Do NOT consolidate.

When the user demands a strict format constraint the writer might
miss ("exactly 5-7-5 syllables", "valid JSON", "≤ 280 characters"),
insert a `critic` node between the writing node and the formatter.
Its input is the writing node id. Its metadata.question repeats
the constraint. If the critic fails, the orchestrator re-plans.

If FAILURE appears in the prompt, do not re-emit the failing step
on the same inputs.

Example:
{"rationale": "Look it up and answer.",
 "nodes": [
   {"skill":"researcher","inputs":["USER_QUERY"],
    "metadata":{"label":"r1","question":"What is..."}},
   {"skill":"formatter","inputs":["n:r1"],
    "metadata":{"label":"out"}}]
}
```

---

## Schemas (`schemas.py`)

```python
from pydantic import BaseModel, Field
from typing import Literal, Any
from enum import Enum

class NodeStatus(str, Enum):
    PENDING   = "pending"
    RUNNING   = "running"
    COMPLETE  = "complete"
    FAILED    = "failed"
    SKIPPED   = "skipped"

class NodeSpec(BaseModel):
    skill:    str
    inputs:   list[str]
    metadata: dict[str, Any] = Field(default_factory=dict)

class AgentResult(BaseModel):
    output:     str
    tool_calls: list[dict] = Field(default_factory=list)
    tokens_in:  int = 0
    tokens_out: int = 0

class NodeState(BaseModel):
    node_id:  str
    skill:    str
    inputs:   list[str]
    metadata: dict[str, Any] = Field(default_factory=dict)
    status:   NodeStatus = NodeStatus.PENDING
    result:   AgentResult | None = None
    error:    str | None = None

class SessionLoadError(Exception):
    """Raised when a persisted session file fails revival."""
    pass
```

---

## Persistence Layer (`persistence.py`)

```python
"""
SessionStore: atomic JSON persistence for graph + per-node state.

Write pattern: write to tmp file → os.replace (atomic swap).
A process kill between write and swap leaves the previous file intact.
A process kill after the swap leaves the new file intact.
No half-written files.

Resume contract: reads graph.json, resets status=running → pending,
continues from next ready_nodes() call. Completed nodes are not re-run.

NOTE: Resume is at node boundary, not tool-call boundary.
A researcher killed mid-tool-call resumes by re-running the full researcher.
This is a documented deferral (see DEFERRED.md).
"""
import os, json, pathlib
import networkx as nx
from schemas import NodeState, AgentResult, SessionLoadError

class SessionStore:
    def __init__(self, session_dir: str):
        self.root = pathlib.Path(session_dir)
        self.nodes_dir = self.root / "nodes"
        self.nodes_dir.mkdir(parents=True, exist_ok=True)

    def save_graph(self, graph: nx.DiGraph) -> None:
        data = nx.node_link_data(graph)
        self._atomic_write(self.root / "graph.json", json.dumps(data, default=str))

    def save_node(self, state: NodeState) -> None:
        payload = state.model_dump(mode="json")
        if state.result is not None:
            payload["_result_typed"] = True
        path = self.nodes_dir / f"{state.node_id}.json"
        self._atomic_write(path, json.dumps(payload))

    def load(self) -> nx.DiGraph:
        gpath = self.root / "graph.json"
        if not gpath.exists():
            raise SessionLoadError(f"graph.json not found at {gpath}")
        try:
            data = json.loads(gpath.read_text())
            graph = nx.node_link_graph(data)
        except Exception as e:
            raise SessionLoadError(f"Failed to load graph: {e}")
        # Reset running → pending for resume
        for node_id, attrs in graph.nodes(data=True):
            if attrs.get("status") == "running":
                attrs["status"] = "pending"
        return graph

    def _atomic_write(self, path: pathlib.Path, content: str) -> None:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(content)
        os.replace(tmp, path)
```

---

## Recovery Classifier (`recovery.py`)

```python
"""
classify_failure: keyword-based error classifier.

Returns one of three labels:
  transient         — 5xx, network noise; gateway retries already exhausted;
                      surface to user, do not re-plan
  validation_error  — malformed JSON / Pydantic failure; fix the prompt, not the graph
  upstream_failure  — everything else; queue one recovery Planner node

BRITTLE WARNING: keyword matching against actual gateway error strings.
Unit tests in tests/test_recovery.py pin the classifier against real error strings
from the gateway as of Session 8. A future gateway change that alters error format
will trip these tests — that is the intended behaviour.
"""

TRANSIENT_KEYWORDS = [
    "503", "502", "504", "timeout", "connection",
    "bad gateway", "gateway timeout", "ConnectionError",
    "HTTPStatusError", "service unavailable",
]
VALIDATION_KEYWORDS = [
    "malformed", "ValidationError", "validation error",
]

def classify_failure(error_text: str) -> str:
    lower = error_text.lower()
    if any(k.lower() in lower for k in TRANSIENT_KEYWORDS):
        return "transient"
    if any(k.lower() in lower for k in VALIDATION_KEYWORDS):
        return "validation_error"
    return "upstream_failure"
```

---

## Sandbox (`sandbox.py`)

```python
"""
SandboxExecutor: runs Python code from the Coder skill in an isolated subprocess.

SECURITY SCOPE: usability boundary, not a full security sandbox.
- Environment variables scrubbed to allowlist (PATH, HOME, LANG, LC_ALL, LC_CTYPE).
- Subprocess runs in a fresh temp directory (deleted on exit).
- stdout/stderr capped at 1 MB each.
- 30-second timeout.
- Does NOT restrict network access, filesystem reads outside tmp, or privilege.
- Appropriate for student code; NOT appropriate for untrusted sources.
- Production hardening: add seccomp, rlimit, network namespaces, non-privileged user.
"""
import subprocess, tempfile, os, textwrap

ALLOWED_ENV = {k: os.environ[k] for k in
               ["PATH", "HOME", "LANG", "LC_ALL", "LC_CTYPE"] if k in os.environ}

def run_in_sandbox(code: str, timeout: int = 30) -> dict:
    with tempfile.TemporaryDirectory() as tmpdir:
        script = os.path.join(tmpdir, "script.py")
        with open(script, "w") as f:
            f.write(textwrap.dedent(code))
        try:
            proc = subprocess.run(
                ["python", script],
                capture_output=True, text=True,
                timeout=timeout,
                env=ALLOWED_ENV,
                cwd=tmpdir,
            )
            return {
                "exit_code": proc.returncode,
                "stdout":    proc.stdout[:1_000_000],
                "stderr":    proc.stderr[:1_000_000],
                "success":   proc.returncode == 0,
            }
        except subprocess.TimeoutExpired:
            return {"exit_code": -1, "stdout": "", "stderr": "Timeout", "success": False}
        except Exception as e:
            return {"exit_code": -1, "stdout": "", "stderr": str(e), "success": False}
```

---

## Coder Skill Prompt — TASK 4 (`prompts/coder.md`)

**This is your assignment task.** The current file is a stub. Replace it with a prompt
that instructs the model to emit a JSON object suitable for the SandboxExecutor:

```json
{
  "code": "<python snippet that computes the answer>",
  "summary": "<one paragraph natural-language description of what the code does>"
}
```

Requirements for the coder prompt:
- Instructs the model to read its inputs (researcher outputs) and identify numeric values.
- Instructs the model to write Python that performs the actual computation (arithmetic,
  comparison, statistics — not just string manipulation).
- Instructs the model to emit valid JSON with exactly the two fields above, no markdown.
- The Python code must be runnable standalone (no imports not in stdlib or common packages).
- The summary must contain the computed answer explicitly so the Formatter can quote it.

Demonstrate the coder on at least one query where the Formatter alone could not reliably
produce the answer — e.g. "find populations of three cities and compute which two differ
by less than 5% of each other."

---

## Custom Skill — TASK 5

Add one new skill to `agent_config.yaml` that the existing catalogue does not cover.
Ideas (choose one or invent your own):

- `translator`  — translate text between languages
- `fact_checker` — verify a claim against attached source material
- `csv_analyst` — parse and summarise tabular data
- `timeline_builder` — extract dated events and sort chronologically
- `unit_converter` — perform unit conversion with shown working

Requirements:
- Entry in `agent_config.yaml` with `prompt`, `tools_allowed`, `temperature`, `max_tokens`.
- Prompt file at `prompts/<skill_name>.md`.
- One query in the demo that exercises this skill end-to-end.
- The Executor must not require modification. If it does, this is a reportable finding.
- Update `prompts/planner.md` to list the new skill under "Available skills".

---

## Gateway V8 — Usage Notes

The gateway runs on port 8108. Your code talks to it; you do not write inside it.

Key V8 features your code should use:
- `POST /v1/chat` — accepts `agent` (skill name) and `session` (session id) fields;
  these are logged per-call and visible in the dashboard.
- `GET /v1/cost/by_agent?session=<sid>` — returns per-agent token spend for a session.
- `POST /v1/chat/batch` — parallel LLM dispatch (optional; flow.py uses asyncio.gather
  at the Python level instead).
- `agent_routing.yaml` — pins skill names to specific providers (bypasses router pool).

Always pass `agent=<skill_name>` and `session=<session_id>` in every gateway call so
the `/v1/cost/by_agent` endpoint has data to return.

---

## Five Base Queries (must all pass)

### Query hello — Minimum DAG
```
Say hello.
```
Expected: 2 nodes (planner → formatter). Wall-clock < 3 seconds.
Verify: `graph.json` shows exactly 2 nodes both status=complete.

### Query A — Shannon Wikipedia (S7 carryover)
```
Fetch https://en.wikipedia.org/wiki/Claude_Shannon and tell me his birth
date, death date, and three key contributions to information theory.
```
Expected: 4 nodes (planner → researcher → distiller [+ auto-critic] → formatter).
The Critic auto-inserted between distiller and formatter must return `pass`.

### Query I — Three city populations (parallel fan-out)
```
Find the populations of London, Paris, Berlin and tell me which two are
closest in size.
```
Expected: 7 nodes. Three researchers run concurrently (asyncio.gather barrier).
All three finish at the same timestamp (within ~1 second).
Wall-clock ≈ 60–70 seconds. Token bill ≈ 17,000 input tokens.

**Verify the parallel speedup**: log must show
`wall_clock < sum_of_researcher_elapsed_times`.

### Query J — Graceful failure
```
Read /nonexistent/path.txt and tell me what's in it.
```
Expected: 2 nodes (planner → formatter with failure note). No tool dispatched.
The Planner must fail-fast by planning rather than attempting the read.

### Query K — Resumable execution
```
For Lagos, Cairo, and Kinshasa, find current populations and growth rates
and tell me which is growing fastest.
```
Run 1: start the query, kill the process (Ctrl+C or SIGKILL) while the parallel
researcher layer is in flight.
Run 2: `python run.py "" --resume <session_id>`

Verify: the two completed researchers are NOT re-run; only the killed one restarts.
Final answer: Lagos (~3.78% growth rate).

---

## Assignment Tasks

### Task 1 — Pass all five base queries
Run each query verbatim. Confirm node counts and wall-clock bounds above.
Log every run to `logs/agent_run_<timestamp>.log`.

### Task 2 — Custom parallel fan-out query
Design a query with **at least three independent sub-tasks** that the Planner emits
as concurrent nodes.

Verify: wall-clock of parallel layer ≤ max(branch elapsed times) + ~2s margin.
The log must explicitly show each researcher's start time, elapsed, and finish time.

Example (or invent your own):
```
Find the GDP, population, and capital city of Japan, Brazil, and Nigeria,
then compare which country has the highest GDP per capita.
```

### Task 3 — Critic verdict: pass and fail
Design a query where the Critic can actually verify a property with the tools available.

**Important**: the forcing query in the session notes (4-6-4 syllable haiku) demonstrated
that LLMs are rubber stamps for syllable counting. Do NOT use syllable counting as your
Critic property. Choose a property the model can actually verify:
- Structural completeness ("the JSON must have exactly these 4 fields")
- Presence of a required element ("the answer must mention a specific named entity")
- Length constraint verifiable by counting words/characters in a short output
- Factual ground-truth the model can check against provided source material

The Critic must produce **both a pass and a fail across two runs** of the query:
- Run A: craft the query so the Critic should return `pass` (well-formed input).
- Run B: craft the query or inject a deliberate flaw so the Critic returns `fail`
  and the recovery Planner splice fires, producing a corrected answer.

Log both runs. Capture the critic's verdict JSON for both in `logs/`.

### Task 4 — Fill the Coder skill
Complete `prompts/coder.md` (see Coder Skill Prompt section above).
Demonstrate on one query where the answer requires computation.

### Task 5 — New skill
Add one new skill (see Custom Skill section above).
Demonstrate on one query that exercises it.

---

## Logging Requirements

Every run must produce files under `assignment8/logs/`. Use Python's `logging` module
or plain file writes. Log rotation by timestamp is sufficient.

### `agent_run_<timestamp>.log`
```
[2026-06-07 10:00:00] SESSION s8-abc123
[2026-06-07 10:00:00] QUERY: Find the populations of London, Paris, Berlin...
[2026-06-07 10:00:02] NODE n:1 planner START
[2026-06-07 10:00:04] NODE n:1 planner COMPLETE (2.18s)
[2026-06-07 10:00:04] NODE n:2 researcher:london START
[2026-06-07 10:00:04] NODE n:3 researcher:paris START
[2026-06-07 10:00:04] NODE n:4 researcher:berlin START
[2026-06-07 10:00:45] NODE n:2 researcher:london COMPLETE (40.50s)
[2026-06-07 10:00:45] NODE n:3 researcher:paris COMPLETE (36.89s)
[2026-06-07 10:00:45] NODE n:4 researcher:berlin COMPLETE (32.43s)
[2026-06-07 10:00:45] PARALLEL BARRIER LIFTED — all 3 researchers complete
[2026-06-07 10:01:03] NODE n:5 coder COMPLETE (18.56s)
[2026-06-07 10:01:04] NODE n:6 formatter COMPLETE (1.14s)
[2026-06-07 10:01:04] NODE n:7 sandbox_executor COMPLETE (0.02s)
[2026-06-07 10:01:04] SESSION COMPLETE wall_clock=62.40s total_nodes=7
```

### `node_trace_<timestamp>.log`
One entry per node showing:
- Inputs received
- Prompt rendered (truncated to 500 chars)
- Tool calls made (name + args)
- Tool results (truncated to 500 chars)
- Output produced
- Token counts (in/out)

### `gateway_calls_<timestamp>.log`
One entry per gateway HTTP call:
- Timestamp, skill/agent label, session id
- Model routed to (from response headers)
- Tokens in / tokens out
- Latency (ms)
- HTTP status

### `cost_summary_<timestamp>.log`
At session end, append the output of `GET /v1/cost/by_agent?session=<sid>`.
Example:
```json
{
  "session": "s8-abc123",
  "by_agent": {
    "planner":    {"calls": 1,  "input_tokens":  814, "output_tokens":  176},
    "researcher": {"calls": 10, "input_tokens": 12318,"output_tokens": 1126},
    "coder":      {"calls": 1,  "input_tokens": 3284, "output_tokens":  340},
    "formatter":  {"calls": 1,  "input_tokens":  900, "output_tokens":   53}
  },
  "total_input_tokens": 17316,
  "total_output_tokens": 1695
}
```

---

## UI — `viewer/index.html`

A single self-contained HTML file. No build tools. No CDN calls. All CSS and JS inline.
Dark background. Load by opening the file in a browser after a run.

### Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│  HEADER: "S8 DAG Replay Viewer"  │  session id  │  [Load Session]  │
├──────────────────────┬──────────────────────────────────────────────┤
│                      │                                              │
│   DAG SIDEBAR        │    NODE DETAIL PANEL                        │
│   (left ~30%)        │    (right ~70%)                             │
│                      │                                             │
│  [n:1 planner ✓]     │  Node: n:2 researcher:london               │
│  [n:2 researcher ✓]  │  Status: complete  Elapsed: 40.50s         │
│  [n:3 researcher ✓]  │  Skill: researcher  Temperature: 0.7        │
│  [n:4 researcher ✓]  │  ─────────────────────────────────          │
│  [n:5 coder ✓]       │  INPUTS                                     │
│  [n:6 formatter ✓]   │    USER_QUERY: "Find the populations..."    │
│  [n:7 sandbox ✓]     │    question: "What is the population of..." │
│                      │  ─────────────────────────────────          │
│  Parallel layer:     │  TOOL CALLS                                 │
│  n2+n3+n4 concurrent │    web_search("London population 2024")     │
│                      │    fetch_url("https://...")                  │
│  Wall-clock: 62.40s  │  ─────────────────────────────────          │
│  Serial equiv: 131s  │  OUTPUT (first 800 chars)                   │
│  Speedup:  2.11x     │    "The population of Greater London is..." │
│                      │  ─────────────────────────────────          │
│  [Cost Summary]      │  TOKENS  in: 1232  out: 142                │
│                      │                                              │
├──────────────────────┴──────────────────────────────────────────────┤
│  COST BAR:  planner 814  │  researcher 12318  │  coder 3284  │ ...  │
└─────────────────────────────────────────────────────────────────────┘
```

### Behaviour
- On load: reads `state/sessions/` directory listing via a local fetch (or prompts user
  to paste `graph.json` path).
- Clicking a node in the sidebar loads its `NodeState` from `nodes/n_XXX.json` and
  populates the detail panel.
- Parallel nodes (nodes that started within 2 seconds of each other) are visually
  grouped with a bracket and labeled "concurrent".
- The cost bar at the bottom is a horizontal stacked bar chart drawn with CSS widths
  proportional to `input_tokens` per skill.
- Critic nodes show their verdict (PASS in green, FAIL in red) prominently.
- Failed/skipped nodes shown in red/grey in the sidebar.
- The [Load Session] button opens a file picker for `graph.json`; the viewer then
  auto-discovers the `nodes/` folder at the same path.

### Implementation notes
- All data is read from the persisted JSON files — no server needed.
- Use `<input type="file">` for loading `graph.json` and `nodes/*.json` files.
- Keep visual design clean: dark `#0d1117` background, monospace font for logs,
  coloured node-status badges (pending/grey, running/yellow, complete/green, failed/red,
  skipped/dimgrey).
- The DAG sidebar renders nodes in topological order (top = earliest, bottom = last).

---

## `run.py` — Entry Point

```python
#!/usr/bin/env python3
"""
Entry point for Session 8 DAG agent.

Usage:
  python run.py "<query>"
  python run.py "" --resume <session_id>

Logs are written to assignment8/logs/.
Session state is written to assignment8/state/sessions/<session_id>/.
After completion, prints the session ID and the path to the viewer.
"""
import argparse, asyncio, os, sys
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

from flow import Executor

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("query", nargs="?", default="")
    parser.add_argument("--resume", default=None)
    args = parser.parse_args()

    executor = Executor()
    result = asyncio.run(executor.run(query=args.query, resume_sid=args.resume))

    print(f"\nAnswer:\n{result.answer}")
    print(f"\nSession ID: {result.session_id}")
    print(f"Viewer:     file:///{os.path.abspath('viewer/index.html')}"
          f"?session={result.session_id}")

if __name__ == "__main__":
    main()
```

---

## Test Suite (`tests/test_recovery.py`)

Must contain 22 tests: 18 for `classify_failure`, 4 for the critic-fail splice mechanics.

```python
import pytest
from recovery import classify_failure

# ── 18 classify_failure tests ────────────────────────────────────────────────

@pytest.mark.parametrize("error_text", [
    "503 Service Unavailable",
    "502 Bad Gateway",
    "504 Gateway Timeout",
    "Connection timeout after 30s",
    "ConnectionError: failed to connect",
    "HTTPStatusError: 503",
    "service unavailable",
    "bad gateway returned by upstream",
    "gateway timeout",
    "Read timeout",
    "connect timeout",
    "Network connection failed",
    "upstream connect error or disconnect",
    "temporary network failure",
    "503: overloaded",
    "RemoteDisconnected: 502",
    "Retry-after: 502 backend",
    "backoff: 503 retry exhausted",
])
def test_transient(error_text):
    assert classify_failure(error_text) == "transient"

@pytest.mark.parametrize("error_text", [
    "malformed JSON in node output",
    "ValidationError: field 'skill' missing",
    "validation error on NodeSpec",
    "malformed response from planner",
])
def test_validation_error(error_text):
    assert classify_failure(error_text) == "validation_error"

@pytest.mark.parametrize("error_text", [
    "Researcher returned empty content",
    "Distiller failed to extract required fields",
    "Unexpected token in JSON at position 0",
    "Coder emitted no code field",
])
def test_upstream_failure(error_text):
    assert classify_failure(error_text) == "upstream_failure"

# ── 4 critic-splice mechanics tests ─────────────────────────────────────────
# These are integration-style tests verifying the orchestrator graph mutations.
# Implement as unit tests against a minimal in-memory graph.

def test_critic_auto_inserted_on_distiller_edge():
    """After extend_from with a distiller node, critic is inserted on every outgoing edge."""
    # Build minimal graph, call extend_from with a distiller node,
    # assert a critic node exists between distiller and its child.
    pass  # implement against your Graph class

def test_critic_fail_marks_child_skipped_and_queues_planner():
    """On critic fail, child is skipped and a recovery Planner node is queued."""
    pass  # implement against your Executor recovery path

def test_per_target_cap_prevents_loop():
    """Second critic fail on the same target does not queue a second recovery Planner."""
    pass  # implement — recovery_count[target] >= 1 must block re-plan

def test_critic_pass_leaves_graph_unchanged():
    """On critic pass, no graph modifications occur."""
    pass  # implement — graph node count before == after
```

---

## Build Order for Claude Code

Execute these steps in order. Do not skip steps. Do not proceed to the next step
until the current step is verified working.

**Step 0 — Verify prerequisites**
- `llm_gatewayV8/` exists and `python llm_gatewayV8/main.py` starts on port 8108.
- `.env` exists at `assignment8/.env` with all required keys.
- S7 files (`perception.py`, `memory.py`, `decision.py`, `action.py`,
  `mcp_server.py`, `artifacts.py`, `vector_index.py`) exist and are untouched.
- `pip install networkx pydantic python-dotenv pytest` succeeds.

**Step 1 — Schemas**
Create `schemas.py` exactly as specified. Run:
```bash
python -c "from schemas import NodeSpec, NodeState, AgentResult, SessionLoadError; print('OK')"
```

**Step 2 — Recovery classifier**
Create `recovery.py`. Run stub tests:
```bash
python -m pytest tests/test_recovery.py -k "test_transient or test_validation_error or test_upstream_failure" -v
```
All 22 keyword tests must pass before proceeding.

**Step 3 — Persistence layer**
Create `persistence.py`. Write a quick smoke test:
```bash
python -c "
from persistence import SessionStore
import networkx as nx, tempfile, os
g = nx.DiGraph()
g.add_node('n1', status='complete', skill='planner')
with tempfile.TemporaryDirectory() as d:
    s = SessionStore(d)
    s.save_graph(g)
    g2 = s.load()
    assert list(g2.nodes) == ['n1']
    print('persistence OK')
"
```

**Step 4 — Skill catalogue**
Create `agent_config.yaml` with all 10 skills (including your custom skill).
Create `skills.py` with the `Skill` class.

**Step 5 — Prompts**
Create all prompt files under `prompts/`. The `coder.md` must be fully written
(Task 4), not a stub. The custom skill prompt must be written (Task 5).

**Step 6 — Sandbox**
Create `sandbox.py`. Smoke test:
```bash
python -c "
from sandbox import run_in_sandbox
r = run_in_sandbox('print(2 + 2)')
assert r['stdout'].strip() == '4', r
print('sandbox OK')
"
```

**Step 7 — flow.py (orchestrator)**
Create `flow.py` with `Graph` (NetworkX DiGraph wrapper) and `Executor`.
Wire: planner fires first → extend_from → asyncio.gather on ready nodes →
persist → loop.
Include Critic auto-insertion on distiller edges.
Include SandboxExecutor auto-insertion after coder.
Include recovery classifier on node failure.

**Step 8 — run.py**
Create `run.py` as specified.

**Step 9 — Logging**
Wire all four log files (`agent_run`, `node_trace`, `gateway_calls`, `cost_summary`)
into the executor. Verify `logs/` directory is created and files appear after a run.

**Step 10 — Query hello (smoke test)**
```bash
python run.py "Say hello."
```
Verify: 2 nodes, both complete, wall-clock < 3s, `graph.json` written.

**Step 11 — Query A (Shannon)**
```bash
python run.py "Fetch https://en.wikipedia.org/wiki/Claude_Shannon and tell me his birth date, death date, and three key contributions to information theory."
```
Verify: 4 nodes, distiller present, critic auto-inserted, all complete.

**Step 12 — Query I (populations, parallel fan-out)**
```bash
python run.py "Find the populations of London, Paris, Berlin and tell me which two are closest in size."
```
Verify: 7 nodes, 3 researchers finish at same timestamp, parallel speedup logged.

**Step 13 — Query J (graceful failure)**
```bash
python run.py "Read /nonexistent/path.txt and tell me what's in it."
```
Verify: 2 nodes (planner + formatter), no tool dispatched.

**Step 14 — Query K (resume)**
```bash
python run.py "For Lagos, Cairo, and Kinshasa, find current populations and growth rates and tell me which is growing fastest."
# Kill after ~10 seconds (Ctrl+C)
python run.py "" --resume <session_id_from_logs>
```
Verify: completed researchers not re-run; final answer names Lagos.

**Step 15 — Task 2 (custom parallel fan-out query)**
Run your custom query. Verify ≥3 concurrent nodes, wall-clock ≤ max(branches) + 2s.

**Step 16 — Task 3 (Critic pass + fail)**
Run both critic runs. Verify PASS on run A, FAIL + recovery splice on run B.

**Step 17 — Task 4 (Coder)**
Run the computation query. Verify coder emits Python, sandbox runs it, formatter
quotes the computed result.

**Step 18 — Task 5 (custom skill)**
Run the custom skill query. Verify the new skill node appears in the graph.

**Step 19 — Viewer**
Create `viewer/index.html`. Load the populations session. Verify DAG sidebar,
node detail panel, parallel grouping, cost bar, and critic verdict display.

**Step 20 — README**
Create `readme.md` with:
- One-paragraph architecture summary (S7 → S8 change).
- Setup instructions (`.env`, `pip install`, gateway start).
- How to run each of the 5 base queries + 3 custom queries (Tasks 2, 3, 4, 5).
- Table of results: query | nodes | wall-clock | input tokens | status.
- Logs directory listing with one-line description of each log file.
- Known limitations (mid-tool-call resume, sandbox security scope, critic rubber-stamp).

**Step 21 — Full test suite**
```bash
python -m pytest tests/test_recovery.py -v
```
All 22 tests must pass.

---

## Expected Performance Benchmarks

| Query          | Nodes | Wall-clock   | Input tokens | Notes                         |
|----------------|-------|--------------|--------------|-------------------------------|
| hello          | 2     | < 3s         | ~200         | minimum DAG                   |
| A (Shannon)    | 4     | < 30s        | ~3,000       | critic auto-inserted          |
| I (populations)| 7     | ~60–75s      | ~17,000      | 3x parallel researcher        |
| J (graceful)   | 2     | < 3s         | ~200         | no tool dispatched            |
| K (resume)     | 7     | ~70s total   | ~18,000      | resume from mid-run           |

S8 vs S7 on Query I:
- Wall-clock: 62s vs 125s (2.1x speedup)
- Input tokens: 17k vs 54k (3.2x reduction)
- Gateway calls: 15 vs 60

---

## Known Limitations (document in README)

1. **Sandbox is not a security boundary** — network access and filesystem reads outside
   tmp are unrestricted. Add `seccomp`/`rlimit`/network namespaces for production.
2. **Mid-tool-call resume not supported** — a researcher killed mid-tool-call re-runs
   from the top (re-issues all tool calls). Fix: persist `partial_messages` in
   `NodeState`; ~60 lines in `mcp_runner.py`. Documented in `DEFERRED.md`.
3. **Critic is a generic LLM judge** — reliable for structural/factual properties the
   model can read; unreliable for precise arithmetic (syllable counts, exact character
   counts). Fix: give Critic targeted tools (count_words, count_chars, etc.).
4. **No Skill abstraction above yaml** — one `if skill.name == "sandbox_executor"`
   special case exists in the dispatcher. A second such special case should trigger a
   proper abstraction design.
5. **Agent-routing yaml not hot-reloaded** — changing a provider pin requires gateway
   restart (~15 seconds).
6. **Dense-only retrieval** — FAISS IndexFlatIP; no sparse/BM25 component. Hybrid
   retrieval (dense + sparse + RRF) deferred to Session 8 forward pointer.

---

## Diagnostic Rules (Rohan's invariant — do not break)

When something goes wrong, follow this trace before touching any code:

1. **Capture full trace** — read `logs/node_trace_<timestamp>.log` for the failing node.
2. **Identify role** — which skill produced the bad output?
3. **Reconstruct exact input** — what prompt did `render_prompt` actually send?
4. **Ask: was output rational given that input?**
   - YES → renderer bug (fix `render_prompt` or the log format). Do NOT patch the
     skill's SYSTEM prompt to mask a render bug.
   - NO  → skill SYSTEM prompt bug or model is too small for the task.
5. **For loops**: check if Decision/Planner is receiving stale memory hits with no
   `value.chunk` content — the synonym-recall loop pattern from S7 applies here too.
6. **For empty critic results**: check temperature (must be 0.0 for pass/fail determinism).
7. **For recovery loops**: check `classify_failure` — a transient that is misclassified
   as `upstream_failure` will re-plan on every retry.
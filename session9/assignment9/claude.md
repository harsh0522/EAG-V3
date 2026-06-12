# CLAUDE.md — Session 9 Assignment: Browser Comparison Agent + Replay Viewer

## Project Location

All code lives at:
```
/Users/harshagarwal/Documents/EAGv3/session9/assignment9/
```

The directory structure to create:
```
assignment9/
├── claude.md                  ← this file
├── readme.md                  ← run instructions, architecture note, logs summary
├── .env                       ← all API keys (already exists, do not touch)
├── llm_gatewayV9/             ← already exists, do not write any code inside
├── agent_config.yaml          ← skill registry
├── flow.py                    ← orchestrator, DO NOT MODIFY
├── schemas.py                 ← Pydantic models
├── skills.py                  ← dispatch branch for browser skill (small addition only)
├── browser/
│   ├── skill.py               ← cascade logic (~280 lines)
│   ├── client.py              ← V9 gateway calls
│   ├── dom.py                 ← clickable element enumeration, dedup, block detection
│   ├── highlight.py           ← set-of-marks box drawing (Pillow, DPR-aware)
│   └── driver.py              ← shared interaction loop for Layer 2b and Layer 3
├── prompts/
│   ├── browser.md             ← browser skill system prompt
│   └── planner.md             ← updated planner prompt with recovery section
├── logs/                      ← ALL logs go here, created automatically at runtime
│   ├── agent_run_<timestamp>.log
│   ├── browser_actions_<timestamp>.log
│   ├── gateway_calls_<timestamp>.log
│   └── cost_summary_<timestamp>.log
├── state/
│   └── sessions/              ← full JSON trace of each run saved here
├── viewer/
│   └── index.html             ← single-page replay viewer (see UI section below)
├── requirements.txt
└── run.py                     ← entry point: takes user goal as argument, runs agent
```

---

## Environment Variables

All API keys are loaded from `.env` at `assignment9/.env`. Never hardcode any key anywhere in the code. Always use:

```python
import os
from dotenv import load_dotenv
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY   = os.getenv("GROQ_API_KEY")
```

Expected keys in `.env` (these already exist — do not create or print them):
```
GEMINI_API_KEY=...
GROQ_API_KEY=...
CEREBRAS_API_KEY=...
GITHUB_TOKEN=...
```

Do not write any code inside `llm_gatewayV9/`. The gateway is already complete and runs on `localhost:8109`.

---

## What You Are Building

A browser-capable multi-agent system that performs a real comparison task on the web — one that Session 8's `web_search + fetch_url` tools cannot do. The agent interacts with live dynamic pages: clicking, filtering, sorting, navigating. It produces a structured comparison table, saves full logs, and renders everything in a single-page web UI.

---

## Comparison Task

Default task (use this unless you have a better one):
> **"Compare the top 3 Hugging Face text-generation models sorted by most likes — show model name, parameter count, likes count, and a one-line description."**

This requires: navigating to huggingface.co/models, filtering by text-generation, filtering by transformers library, sorting by most likes, and opening each model card — at least 5 browser actions. Session 8's `fetch_url` cannot do this because the filter and sort options only appear after clicks (they are not in the static HTML).

---

## Architecture: Agent DAG

```
User Goal (single prompt via run.py)
    ↓
Planner — produces the DAG
    ↓
Researcher — finds candidate URLs using web_search MCP tool
    ↓
Browser Skill — opens pages, interacts through cascade, extracts data
    ↓
Distiller — extracts structured fields from browser output
    ↓
Critic (auto-inserted by orchestrator on Distiller → Formatter edge)
    ↓
Formatter — renders final comparison table
    ↓
Trace + logs saved → viewer/index.html reads them
```

The Planner, Researcher, Distiller, Critic, and Formatter already exist from Session 8. You are building the **Browser Skill** and the **Replay Viewer UI**.

---

## The Browser Skill

### browser/skill.py — Cascade Logic

The skill always tries layers in order, cheapest first, and returns as soon as one succeeds. Every layer decision and action must be logged to `logs/browser_actions_<timestamp>.log`.

**Precondition (runs before all layers):**
Call `dom.detect_gateway_block(page_content)`. If CAPTCHA, login wall, geo block, or rate limit is detected, log the block reason and return `AgentResult` with `error_code="gateway_blocked"`. Do not attempt any layer.

**Layer 1 — Extract:**
Use `httpx` to download the page (timeout=10s). Use `trafilatura` to extract clean article text. No browser launched. No LLM called. Validate result: must be at least 200 characters and contain at least one keyword from the goal string. If valid, log `[Layer 1] extract succeeded` and return. If not, log `[Layer 1] extract failed — escalating` and proceed.

**Layer 2a — Deterministic:**
Launch Playwright headless Chromium. Set a real Chrome user-agent string, enable JavaScript, remove the `navigator.webdriver` marker (so sites like Amazon do not immediately show CAPTCHA). Use hand-written CSS selectors to find and extract target elements. No LLM called. If selectors match nothing useful, log `[Layer 2a] deterministic failed — escalating` and proceed.

**Layer 2b — Accessibility Tree (a11y):**
Use Playwright plus `page.accessibility.snapshot()`. Each turn: read a fresh a11y snapshot → send to cheap LLM via gateway at `localhost:8109` → receive one action → execute it → log the action → repeat. Apply the **dropdown-as-fence rule**: if the chosen action targets a dropdown trigger (name ends with `▾` or `:`, or starts with `Sort:`), it must be the only action of that turn. Max 2 actions per turn overall. Log every turn as `[Layer 2b] turn N: action=<action>`. If the LLM returns `done(success=false)` for 3+ consecutive turns with an empty summary, log `[Layer 2b] a11y exhausted — escalating` and proceed.

**Layer 3 — Vision (Set-of-Marks):**
Take a Playwright screenshot. Call `dom.py` to enumerate clickable elements and deduplicate (remove nested SVG decorations — an inner `<rect>` inside a button is not a separate clickable). Call `highlight.py` to draw numbered boxes on the screenshot using Pillow **after** capture (not as JS overlays). Read the page's device pixel ratio (DPR) and store it. Send the annotated screenshot as base64 to `POST /v1/vision` on the gateway. The model returns a box number. Convert the number back to a click coordinate using DPR scaling. Playwright dispatches the click. Log every vision call as `[Layer 3] turn N: chosen_box=<N>, coordinate=(<x>,<y>)`.

### browser/client.py

All gateway calls go through this module. Base URL must be read from `.env`:
```python
GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8109")
```
Exposes: `call_llm(prompt, system)` for text calls, `call_vision(image_b64, prompt)` for vision calls. Never hardcode port or URL.

### browser/dom.py

- `detect_gateway_block(html: str) -> bool` — checks for common CAPTCHA/block patterns
- `enumerate_clickables(page) -> list[dict]` — returns list of `{name, role, bbox}` for all clickable elements
- `deduplicate_clickables(elements: list[dict]) -> list[dict]` — removes nested duplicates; if bounding boxes overlap by >80%, keep the outermost one only

### browser/highlight.py

- `draw_marks(screenshot_bytes, elements, dpr) -> (annotated_bytes, index_map)` — draws numbered boxes on screenshot, returns annotated image and a dict mapping box number → element
- `coordinate_from_mark(mark_number, index_map, dpr) -> (x, y)` — converts box number to CSS pixel coordinate for Playwright

### browser/driver.py

- `A11yDriver` — runs the a11y turn loop; enforces dropdown-as-fence rule; calls `client.call_llm`
- `SetOfMarksDriver` — runs the vision turn loop; calls `highlight.draw_marks` and `client.call_vision`
- Both share `BaseDriver` with common turn counting and logging interface

### Output Schema (add to schemas.py)

```python
class BrowserOutput(BaseModel):
    url: str
    goal: str
    path: Literal["extract", "deterministic", "a11y", "vision"]
    turns: int
    content: str | None = None
    actions: list[dict] = []
    final_url: str | None = None

# Also add error_code to AgentResult:
class AgentResult(BaseModel):
    # ... existing fields ...
    error_code: Literal[
        "gateway_blocked", "extraction_failed",
        "interaction_failed", "timeout", "vlm_unavailable"
    ] | None = None
```

### agent_config.yaml entry

```yaml
browser:
  prompt: prompts/browser.md
  description: |
    Fetches and interacts with web pages through a four-layer cascade
    (extract, deterministic, a11y, vision). Input metadata accepts url
    (required) and goal (required). Returns BrowserOutput with the
    chosen layer surfaced as output.path. Use when the Researcher
    skill's fetch_url is insufficient: JavaScript-rendered content,
    interactive widgets, multi-page workflows.
  provider_pin: null
```

### skills.py change

Add a small dispatch branch for the browser skill. No other file in the orchestrator changes. Do not touch `flow.py`.

---

## Logging Requirements

Every log file goes into `logs/` with a timestamp suffix. Create the `logs/` directory at startup if it does not exist. Use Python's standard `logging` module configured to write to both file and stdout.

**`logs/agent_run_<timestamp>.log`** — top-level run log: goal received, DAG produced, each node start/end, errors.

**`logs/browser_actions_<timestamp>.log`** — one entry per browser action: layer, turn number, action taken, result, wall-clock time.

**`logs/gateway_calls_<timestamp>.log`** — one entry per LLM/vision call: endpoint, model, input tokens, output tokens, latency.

**`logs/cost_summary_<timestamp>.log`** — written at end of run: total turns per layer, total tokens, total cost (read from gateway SQLite ledger at `llm_gatewayV9/gateway_v9.db`).

Log format for every entry:
```
[2026-06-07 10:44:00] [LEVEL] [module] message
```

No API keys, no raw HTML dumps (truncate content to 500 chars in logs), no screenshots saved to logs (screenshots go to `state/sessions/<run_id>/screenshots/`).

---

## State / Trace Saving

After every run, save to `state/sessions/<run_id>/`:
```
state/sessions/<run_id>/
├── trace.json          ← full DAG execution trace (all node inputs/outputs)
├── browser_output.json ← BrowserOutput for the browser node
├── final_table.md      ← Formatter's comparison table in markdown
├── screenshots/        ← annotated screenshots from Layer 3 (if used)
│   └── turn_<N>_annotated.png
└── cost.json           ← {total_tokens, total_cost, turns_by_layer}
```

`run_id` format: `<YYYYMMDD_HHMMSS>_<first 6 chars of goal slug>`.

---

## UI: Replay Viewer (viewer/index.html)

Build a **single self-contained HTML file** at `viewer/index.html`. No external frameworks — vanilla HTML, CSS, JavaScript only. The page loads `state/sessions/` data by reading a `trace.json` path passed as a URL query parameter: `viewer/index.html?session=<run_id>`.

Since this runs locally (file:// or a simple Python http.server), use `fetch()` with a relative path to load the JSON files.

### What the UI must show

The page has two panels: a left sidebar (DAG navigator) and a right main panel (node detail).

**Left sidebar — DAG view:**
- Render the planner DAG as a vertical node list with arrows between them
- Each node shown as a card: node ID, skill name, status (✅ success / ❌ failed / ⚠️ recovered)
- Clicking a node loads its detail in the right panel

**Right main panel — Node detail:** switches content based on which node is selected.

When the **Browser node** is selected, show:
1. **Goal** — the goal string passed to the browser
2. **Layer chosen** — a badge: `extract` (green) / `deterministic` (blue) / `a11y` (yellow) / `vision` (red) / `blocked` (grey)
3. **Actions taken** — a numbered list of every action from `BrowserOutput.actions`, each showing: turn number, action type, target element, result
4. **Page state / a11y snapshots** — for Layer 2b: show the a11y summary text for each turn in a collapsible block. For Layer 3: show the annotated screenshot image inline (load from `screenshots/turn_N_annotated.png`)
5. **Extracted content** — the raw `BrowserOutput.content` in a scrollable code block (truncated to 2000 chars with a "show more" toggle)
6. **Final URL** — the URL after all navigation

When the **Formatter node** is selected, show:
7. **Final comparison table** — render the markdown table as an HTML table with proper styling

**Bottom bar (always visible):**
8. **Cost summary** — total turns, total input tokens, total output tokens, total cost, wall-clock time per node

### UI design requirements

- Dark background (`#0d1117`), light text (`#e6edf3`), matching the style of the course dashboard
- Node status badges use colour: green for success, red for failed, yellow for critic-recovered
- Layer badge for Browser node: colour-coded as above
- The comparison table must render as a real HTML table, not raw markdown
- Responsive enough to use at 1280px width minimum
- A "Load Session" button at the top that lets you type or paste a run_id to load a different session
- No external CDN calls — all CSS and JS inline in the file

### How to open the viewer

After a run completes, `run.py` should print:
```
Run complete. Open the replay viewer:
  cd /Users/harshagarwal/Documents/EAGv3/session9/assignment9
  python -m http.server 8200
  Then open: http://localhost:8200/viewer/index.html?session=<run_id>
```

---

## Entry Point: run.py

```
python run.py "Compare top 3 Hugging Face text-generation models sorted by likes"
```

`run.py` must:
1. Load `.env` from the `assignment9/` directory
2. Accept the goal as a positional command-line argument
3. Set up logging (create `logs/` if missing, open timestamped log files)
4. Run the agent via `flow.py`'s entry point
5. Save trace and outputs to `state/sessions/<run_id>/`
6. Print the viewer URL to stdout when done

---

## Prompts to Write

**`prompts/browser.md`** — system prompt for the browser agent. Tell it: your job is to fetch and interact with a web page to achieve a goal. You must report: which layer you used (extract/deterministic/a11y/vision), every action you took in order (action type, target, result), and the extracted content. Return a BrowserOutput JSON.

**`prompts/planner.md`** — update from S8 version. Add a recovery section at the bottom: when `FAILURE` appears in your prompt and inputs include node IDs of the form `n:*`, those nodes already succeeded — wire their outputs by ID into your new plan and only re-emit the failing branch. Never re-run a node whose ID appears in your inputs.

---

## Orchestrator Fixes Already in flow.py

Do not re-implement these. They are already present in the S9 `flow.py`.

**Recovery amnesia fix:** Failed node recovery now passes all completed node IDs (`prior_complete`) into the recovery Planner's inputs so it does not re-run finished work.

**Critic auto-insertion fix:** The orchestrator splices a Critic on every Distiller → next-node edge (not just dynamically-spawned children). The auto-inserted Critic receives `["USER_QUERY", src_nid]` as inputs.

---

## Gateway V9

Already running at `localhost:8109`. Do not write code inside `llm_gatewayV9/`. The two provider fixes (GitHub JSON keyword injection, Gemini→GitHub routing race) are already applied.

All code that calls the gateway must read the URL from `.env`:
```
GATEWAY_URL=http://localhost:8109
```

---

## Required Python Libraries (requirements.txt)

```
httpx
trafilatura
playwright
pillow
pydantic>=2.0
python-dotenv
networkx
faiss-cpu
```

After `pip install -r requirements.txt`, also run:
```
playwright install chromium
```

---

## Key Rules

- **Do not modify `flow.py`**
- **Do not write any code inside `llm_gatewayV9/`**
- **No hardcoded API keys** — always `os.getenv()`
- **No third-party agentic frameworks** (no LangChain, LlamaIndex, CrewAI, AutoGen)
- **All logs go to `logs/`** — never print sensitive data or raw HTML dumps
- **Minimum 3 visible browser actions** in the run
- **Viewer is a single HTML file** — no build step, no Node.js, no npm
- **Gateway port is 8109** — audit every gateway client instantiation

---

## Debugging Pattern (Rohan's Rule)

1. Check the full trace in `state/sessions/<run_id>/trace.json`
2. Find which node produced unexpected output
3. Reconstruct the exact input that node received
4. Ask: was the output rational given that input?
   - YES → fix the upstream node (input was wrong), not the SYSTEM prompt
   - NO → fix the SYSTEM prompt or escalate to a stronger model
5. Check the cost ledger: if token count doubles after a single failure, recovery amnesia is re-running completed nodes

If the gateway log shows Browser calls but no Planner/Distiller calls, the default gateway URL is pointing at the wrong port (the silent miswire bug from S9 integration).

---

## Cost Expectations

Runs should cost $0.00 on free-tier Gemini Flash-Lite. Layer 3 vision adds ~30s wall-clock per turn but no dollar cost. If cost is higher than expected, check `logs/gateway_calls_<timestamp>.log` to see which skills are hitting the gateway and how many times.
# Session 9 — Browser Comparison Agent + Replay Viewer

A browser-capable multi-agent system that performs a real comparison task on
the live web (clicking, filtering, sorting — things `web_search` + `fetch_url`
cannot do), produces a structured comparison table, saves full logs, and
replays the whole run in a single-page HTML viewer.

## Run instructions

1. **Install dependencies** (Python 3.11+):

   ```bash
   cd /Users/harshagarwal/Documents/EAGv3/session9/assignment9
   pip install -r requirements.txt
   playwright install chromium
   ```

2. **Fill in `.env`** (already present in this directory — add your keys,
   never commit them):

   ```
   GEMINI_API_KEY=...
   GROQ_API_KEY=...
   CEREBRAS_API_KEY=...
   GITHUB_TOKEN=...
   GATEWAY_URL=http://localhost:8109
   ```

3. **Start the gateway** (or just run `run.py` — `flow.py` calls
   `ensure_gateway()` and will auto-launch it from `llm_gatewayV9/` if it
   isn't already up on `:8109`):

   ```bash
   cd llm_gatewayV9 && uv run main.py
   ```

4. **Run the agent**:

   ```bash
   python run.py "Compare the top 3 Hugging Face text-generation models sorted by most likes — show model name, parameter count, likes count, and a one-line description."
   ```

5. **Open the replay viewer** (printed at the end of the run):

   ```bash
   python -m http.server 8200
   # then open:
   http://localhost:8200/viewer/index.html?session=<run_id>
   ```

## Architecture

```
User Goal (run.py)
    ↓
Planner — produces the DAG
    ↓
Researcher — finds candidate URLs (web_search MCP tool)
    ↓
Browser Skill — opens pages, interacts through a 4-layer cascade, extracts data
    ↓
Distiller — extracts structured fields
    ↓
Critic (auto-inserted on every Distiller → next-node edge)
    ↓
Formatter — renders the final comparison table
    ↓
Trace + logs saved → viewer/index.html replays the run
```

`flow.py` (the orchestrator), `schemas.py`, `skills.py`, `agent_config.yaml`,
`gateway.py`, `persistence.py`, `recovery.py`, `memory.py` and friends are the
Session 8 runtime, carried over unmodified in spirit (only `gateway.py`'s
path resolution and `.env`-driven `GATEWAY_URL` were adapted to this
directory's layout — `flow.py` itself was **not** touched). The new work for
this assignment is the **Browser skill** (`browser/`) and the **Replay
Viewer** (`viewer/index.html`).

### The Browser skill — four-layer cascade

Cheapest layer first; the skill returns as soon as one layer produces a
useful result. Every layer decision and action is logged to
`logs/browser_actions_<timestamp>.log`.

1. **Extract** (`httpx` + `trafilatura`) — no browser, no LLM. Works for
   static pages.
2. **Deterministic** (Playwright + hand-written CSS selectors, supplied via
   `metadata.selectors`) — no LLM.
3. **Accessibility tree (a11y)** — Playwright `page.accessibility.snapshot()`
   summarised as a text legend, sent to a cheap model on `/v1/chat`. Enforces
   the **dropdown-as-fence** rule (a click on an element whose name ends in
   `▾`/`:` or starts with `Sort:` must be the only action that turn — its
   popup options don't exist in the DOM until after the click) and a hard cap
   of 2 actions per turn (`browser/driver.py:_enforce_turn_rules`).
4. **Vision / set-of-marks** — Playwright screenshot, numbered boxes drawn
   with Pillow (DPR-aware, post-capture so the live DOM stays untouched), sent
   to `/v1/vision`. The model returns a box number; the driver converts it
   back to a CSS-pixel click coordinate.

A precondition (`dom.detect_gateway_block`) runs before every layer — CAPTCHA,
login walls, geo-blocks, or Cloudflare interstitials short-circuit the cascade
with `error_code="gateway_blocked"` and route the Planner to recovery.

## Logs

Every run writes four timestamped files under `logs/`, mirrored to stdout:

| file | contents |
|---|---|
| `agent_run_<ts>.log` | top-level run log: goal, DAG, each node start/end, errors |
| `browser_actions_<ts>.log` | one entry per browser action: layer, turn, action, result |
| `gateway_calls_<ts>.log` | one entry per LLM/vision call: endpoint(agent), model, tokens, latency — read back from the gateway's SQLite ledger after the run |
| `cost_summary_<ts>.log` | totals: turns per layer, tokens, dollars (from `/v1/cost/by_agent`) |

No API keys, no raw HTML dumps (content truncated to 500 chars), no
screenshots in logs — those go to `state/sessions/<run_id>/screenshots/`.

## Trace / replay data

Each run writes `state/sessions/<run_id>/`:

```
trace.json          full DAG execution trace (every node: status, inputs, output, prompt_sent, timings)
browser_output.json the BrowserOutput for the browser node
final_table.md      the Formatter's markdown comparison table
report.md           the 8-point run report (see below) — same text printed to stdout
screenshots/        annotated Layer-3 screenshots (turn_<N>_annotated.png)
cost.json           {total_tokens, total_cost, turns_by_layer}
```

`run_id` format: `<YYYYMMDD_HHMMSS>_<first 6 chars of the goal slug>`.

## Run report (8-point summary)

At the end of every run, `run.py` assembles an 8-point report from the trace,
the browser output, the formatter output, and the gateway's cost ledger. It is
printed to stdout (between `═` rules) and saved to
`state/sessions/<run_id>/report.md`:

1. **Original user goal** — the exact prompt passed to `run.py`
2. **Planner DAG** — every node (id, skill, status) and the edges between them
3. **Browser path chosen** — `extract` / `deterministic` / `a11y` / `vision` / `blocked`, per browser node
4. **Browser actions taken** — every turn's action(s) and outcome, in order
5. **Page state / screenshots** — a11y turn count, or annotated Layer-3 screenshots if vision was used
6. **Extracted data** — the raw content the browser node pulled off the page
7. **Final comparison table** — the Formatter's output
8. **Turn count and cost summary** — turns per layer, input/output tokens, total cost, wall-clock time

### Example: `python run.py "Compare top 3 Hugging Face text-generation models sorted by likes"`

This run (`state/sessions/20260613_101722_compar/`) drove the live
huggingface.co/models page through 3 real clicks (filter by "Text Generation",
then two sort-related clicks) before reporting `done`:

````text
# Run report — 20260613_101722_compar

## 1. Original user goal

> Compare top 3 Hugging Face text-generation models sorted by likes

## 2. Planner DAG

- `n:1` **planner** — success
- `n:2` **browser** — success
- `n:3` **distiller** — success
- `n:5` **critic** — success
- `n:4` **formatter** — success
  - n:1 → n:2
  - n:2 → n:3
  - n:3 → n:5
  - n:5 → n:4

## 3. Browser path chosen

- `n:2`: **a11y** (url: https://huggingface.co/models)

## 4. Browser actions taken

- turn 1: `[{'type': 'click', 'mark': 36}]` → ok
- turn 2: `[{'type': 'click', 'mark': 80}]` → ok
- turn 3: `[{'type': 'click', 'mark': 82}]` → ok
- turn 4: `[{'type': 'done', 'success': True, 'value': '1. deepseek-ai/DeepSeek-R1: 5.59M downloads, 685B parameters. 2. meta-llama/Meta-Llama-3-8B: 1.19M downloads, 8B parameters. 3. meta-llama/Llama-3.1-8B-Instruct: 9 downloads (data truncated), 8B parameters.'}]` → done(True)

## 5. Page state / screenshots

- `n:2`: 4 a11y turn(s) logged (see `logs/browser_actions_*.log` for per-turn snapshots)

## 6. Extracted data

`n:2`:
```
deepseek-ai/DeepSeek-R1
Text Generation • 685B • Updated • 5.59M • • 13.4k
Tasks
Parameters
Libraries
Inference Providers
373,192
Active filters: text-generation
Text Generation • 685B • Updated • 5.59M • • 13.4k
Text Generation • 8B • Updated • 1.19M • • 6.57k
Text Generation • 8B • Updated • 9.87M • • 6.07k
... [truncated]
```

## 7. Final comparison table

The top 3 text-generation models on Hugging Face, ranked by their number of likes, are as follows:

1. deepseek-ai/DeepSeek-R1: 13.4k likes (5.59M downloads)
2. meta-llama/Meta-Llama-3-8B: 6.57k likes (1.19M downloads)
3. meta-llama/Llama-3.1-8B-Instruct: 6.07k likes (9.87M downloads)

DeepSeek-R1 currently leads the list as the most liked model.

## 8. Turn count and cost summary

- layer `a11y`: 4 turn(s)
- input tokens: 14489
- output tokens: 1132
- estimated cost: $0.000174
- wall-clock: 60.5s
````

Full trace for this run: `state/sessions/20260613_101722_compar/trace.json` and
`report.md`. Replay it with:

```bash
python -m http.server 8200
# then open:
http://localhost:8200/viewer/index.html?session=20260613_101722_compar
```

## Replay viewer

`viewer/index.html` is a single self-contained file (no build step, no CDN).
It reads `?session=<run_id>` from the URL, fetches `trace.json`/`cost.json`
with relative paths, and renders:

- **Left** — the DAG as a vertical node list (id, skill, status badge).
- **Right** — node detail. The Browser node shows goal, a colour-coded layer
  badge (extract=green / deterministic=blue / a11y=yellow / vision=red /
  blocked=grey), the numbered action list, a11y-snapshot/screenshot view,
  truncated extracted content with "show more", and the final URL. The
  Formatter node renders the markdown comparison table as a real HTML table.
- **Bottom** — cost summary: total turns, input/output tokens, total cost,
  wall-clock time per node.

Serve it locally — `fetch()` needs `http://`, not `file://`:

```bash
python -m http.server 8200
```

## Debugging (Rohan's Rule)

1. Check `state/sessions/<run_id>/trace.json`.
2. Find the node with unexpected output.
3. Reconstruct exactly what it received (`prompt_sent` / `inputs`).
4. Was the output rational given that input?
   - **Yes** → fix the upstream node, not this node's system prompt.
   - **No** → fix the system prompt, or escalate to a stronger model.
5. If token count roughly doubles after a single failure, recovery amnesia
   is re-running completed nodes — check `prior_complete` wiring in the
   recovery Planner's inputs.

## Cost expectations

Runs should cost **$0.00** on free-tier Gemini Flash-Lite — confirmed via
`logs/cost_summary_<timestamp>.log` / `cost.json`. Layer 3 (vision) adds
roughly 30s of wall-clock per turn but no dollar cost.

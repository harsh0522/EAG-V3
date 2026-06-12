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
screenshots/        annotated Layer-3 screenshots (turn_<N>_annotated.png)
cost.json           {total_tokens, total_cost, turns_by_layer}
```

`run_id` format: `<YYYYMMDD_HHMMSS>_<first 6 chars of the goal slug>`.

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

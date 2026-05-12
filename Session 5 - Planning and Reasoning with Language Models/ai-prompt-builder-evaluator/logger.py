import json
import os
import time
from datetime import datetime
from pathlib import Path


class RunLogger:
    def __init__(self, idea: str):
        self.idea = idea
        self.started_at = datetime.now()
        self.steps: list[dict] = []
        self.pydantic_events: list[dict] = []
        self._step_start: float = 0.0

    def begin_step(self, number: int, name: str, system: str, user: str):
        self._step_start = time.time()
        self.steps.append({
            "number": number,
            "name": name,
            "system_prompt": system,
            "user_message": user,
            "raw_response": "",
            "parsed_output": {},
            "retried": False,
            "duration_ms": 0,
            "error": None,
        })

    def end_step(self, raw: str, parsed: dict, retried: bool = False):
        s = self.steps[-1]
        s["raw_response"] = raw
        s["parsed_output"] = parsed
        s["retried"] = retried
        s["duration_ms"] = int((time.time() - self._step_start) * 1000)

    def fail_step(self, error: str):
        s = self.steps[-1]
        s["error"] = error
        s["duration_ms"] = int((time.time() - self._step_start) * 1000)

    def log_pydantic(self, step_num: int, model_name: str, label: str,
                     raw_input: dict, validated_output: dict):
        coercions = []
        for k, v_out in validated_output.items():
            v_in = raw_input.get(k)
            if k not in raw_input:
                coercions.append({"field": k, "kind": "default",
                                  "detail": f"field missing → default applied: {repr(v_out)}"})
            elif type(v_in) != type(v_out):
                coercions.append({"field": k, "kind": "coercion",
                                  "detail": f"{type(v_in).__name__}({repr(v_in)[:50]}) → {type(v_out).__name__}({repr(v_out)[:50]})"})
        self.pydantic_events.append({
            "step_num": step_num,
            "model_name": model_name,
            "label": label,
            "raw_input": raw_input,
            "validated_output": validated_output,
            "coercions": coercions,
        })

    def write_html(self, final_json: str) -> str:
        logs_dir = Path(__file__).parent / "logs"
        logs_dir.mkdir(exist_ok=True)
        ts = self.started_at.strftime("%Y%m%d_%H%M%S")
        out_path = logs_dir / f"run_{ts}.html"
        latest_path = logs_dir / "latest.html"
        html = _render_html(self.idea, self.started_at, self.steps, self.pydantic_events, final_json)
        out_path.write_text(html, encoding="utf-8")
        latest_path.write_text(html, encoding="utf-8")
        return str(out_path)


_CRITERIA_DESCRIPTIONS = {
    "explicit_reasoning":      ("Think step by step", "Does the prompt tell the AI to reason out loud before answering?"),
    "structured_output":       ("Organized output", "Does the prompt ask for a formatted response — like JSON, numbered sections, or a table?"),
    "tool_separation":         ("Separate capabilities", "Are different tasks (search, compute, retrieve) broken into clearly named steps?"),
    "conversation_loop":       ("Ask if unclear", "Does the prompt tell the AI to ask clarifying questions before assuming?"),
    "instructional_framing":   ("Expert role assigned", "Does the prompt open with 'You are a [expert]...' to frame the AI's identity?"),
    "internal_self_checks":    ("Self-review before answering", "Does the prompt tell the AI to check its own output for errors before finishing?"),
    "reasoning_type_awareness":("Reasoning type named", "Does the prompt specify what kind of reasoning to use — deductive, causal, inductive?"),
    "fallbacks":               ("Handle failures gracefully", "Does the prompt tell the AI what to do if it can't complete part of the task?"),
}


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _criteria_rows(review: dict) -> str:
    rows = ""
    for c in _CRITERIA_DESCRIPTIONS:
        val = review.get(c)
        icon = "✓" if val else "✗"
        cls = "pass" if val else "fail"
        rows += f'<tr><td>{c}</td><td class="badge {cls}">{icon} {"Pass" if val else "Fail"}</td></tr>'
    return rows


def _criteria_badges(review: dict) -> str:
    html = '<div class="badge-grid">'
    for c, (short, _) in _CRITERIA_DESCRIPTIONS.items():
        val = review.get(c)
        cls = "pass" if val else "fail"
        icon = "✓" if val else "✗"
        html += f'<div class="crit-badge {cls}"><span class="crit-icon">{icon}</span><span class="crit-name">{c.replace("_", " ")}</span></div>'
    html += "</div>"
    return html


def _pydantic_card(event: dict) -> str:
    rows = ""
    for field, v_out in event["validated_output"].items():
        v_in = event["raw_input"].get(field, "⚠ not in input")
        type_out = type(v_out).__name__
        type_in  = type(v_in).__name__ if field in event["raw_input"] else "—"
        changed  = any(c["field"] == field for c in event["coercions"])

        def _fmt(v) -> str:
            if isinstance(v, dict):
                return "{...}"
            if isinstance(v, list) and len(v) > 0 and isinstance(v[0], dict):
                return f"[{len(v)} objects]"
            s = repr(v)
            return s if len(s) <= 70 else s[:67] + "..."

        row_cls = "pyd-changed" if changed else ""
        change_icon = " ⇒" if changed else ""
        rows += f"""<tr class="{row_cls}">
          <td class="pyd-field">{field}{change_icon}</td>
          <td class="pyd-type">{type_in} → {type_out}</td>
          <td class="pyd-val">{_esc(_fmt(v_in))}</td>
          <td class="pyd-val" style="color:#86efac">{_esc(_fmt(v_out))}</td>
        </tr>"""

    if event["coercions"]:
        coerce_html = "<div class='pyd-coerce-wrap'><strong>Type coercions / defaults applied:</strong><ul>"
        for c in event["coercions"]:
            tag_cls = "pyd-tag-coerce" if c["kind"] == "coercion" else "pyd-tag-default"
            coerce_html += f"<li><span class='pyd-tag {tag_cls}'>{c['kind']}</span> <code>{c['field']}</code>: {_esc(c['detail'])}</li>"
        coerce_html += "</ul></div>"
    else:
        coerce_html = "<div class='pyd-no-coerce'>✓ No type coercions — all fields matched expected types exactly.</div>"

    colors = {"0": "#6d28d9", "2": "#0891b2", "4": "#d97706", "5": "#059669"}
    color = colors.get(str(event["step_num"]), "#475569")

    return f"""
    <div class="pyd-card" style="--pyd-color:{color}">
      <div class="pyd-header">
        <div class="pyd-icon">&#10003;</div>
        <div>
          <div class="pyd-title">Pydantic Validation — <span style="color:{color}">{event["model_name"]}</span></div>
          <div class="pyd-sub">{event["label"]}</div>
        </div>
      </div>
      <table class="pyd-table">
        <thead>
          <tr>
            <th>Field</th>
            <th>Type (in → out)</th>
            <th>Raw Input Value</th>
            <th>Validated Output</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
      {coerce_html}
    </div>"""


def _step_card(s: dict) -> str:
    colors = ["#7c3aed", "#0891b2", "#059669", "#d97706"]
    color = colors[(s["number"] - 1) % 4]
    duration = f'{s["duration_ms"]:,} ms'
    retry_tag = '<span class="retry-tag">retried once</span>' if s["retried"] else ""
    error_block = f'<div class="error-box">{s["error"]}</div>' if s["error"] else ""

    parsed_str = json.dumps(s["parsed_output"], indent=2) if s["parsed_output"] else ""

    review_table = ""
    if s["number"] in (2, 4) and s["parsed_output"]:
        review_table = f"""
        <div class="sub-label">Scorecard</div>
        <table class="scorecard">
          <thead><tr><th>Criterion</th><th>Result</th></tr></thead>
          <tbody>{_criteria_rows(s["parsed_output"])}</tbody>
        </table>"""

    return f"""
    <div class="step-card" style="--accent:{color}">
      <div class="step-header">
        <div class="step-num" style="background:{color}">Step {s["number"]}</div>
        <div class="step-meta">
          <span class="step-name">{s["name"]}</span>
          <span class="step-time">{duration} {retry_tag}</span>
        </div>
      </div>
      {error_block}
      <div class="section-row">
        <div class="col">
          <div class="sub-label">System Prompt</div>
          <pre class="prompt-box sys">{_esc(s["system_prompt"])}</pre>
        </div>
        <div class="col">
          <div class="sub-label">User Message</div>
          <pre class="prompt-box usr">{_esc(s["user_message"])}</pre>
        </div>
      </div>
      <div class="sub-label">Raw LLM Response</div>
      <pre class="prompt-box raw">{_esc(s["raw_response"])}</pre>
      {review_table}
      {"<div class='sub-label'>Parsed Output</div><pre class='prompt-box parsed'>" + _esc(parsed_str) + "</pre>" if parsed_str and s["number"] not in (2,4) else ""}
    </div>"""


def _build_explainer(final: dict, steps: list[dict], ts_str: str, total_ms: int, confidence_pct: int) -> str:
    idea         = _esc(final.get("original_idea", ""))
    gen_prompt   = _esc(final.get("generated_prompt", ""))
    imp_prompt   = _esc(final.get("improved_prompt", ""))
    first_rev    = final.get("first_review", {})
    final_rev    = final.get("final_review", {})
    weaknesses   = final.get("weaknesses_found", [])
    reasoning    = _esc(final.get("reasoning", ""))
    self_check   = final.get("self_check", "")
    all_passed   = "passed" in self_check.lower()

    first_pass   = sum(1 for k in _CRITERIA_DESCRIPTIONS if first_rev.get(k))
    final_pass   = sum(1 for k in _CRITERIA_DESCRIPTIONS if final_rev.get(k))
    improved_by  = final_pass - first_pass

    step_durations = {s["number"]: s["duration_ms"] for s in steps}

    weaknesses_items = "".join(
        f'<div class="weakness-item"><span class="w-dot"></span>{_esc(w)}</div>'
        for w in weaknesses
    ) if weaknesses else "<div style='color:#64748b;font-size:0.85rem'>No weaknesses listed.</div>"

    criteria_table_rows = ""
    for c, (short, desc) in _CRITERIA_DESCRIPTIONS.items():
        v1 = first_rev.get(c)
        v2 = final_rev.get(c)
        b1 = f'<span class="badge {"pass" if v1 else "fail"}">{"✓" if v1 else "✗"}</span>'
        b2 = f'<span class="badge {"pass" if v2 else "fail"}">{"✓" if v2 else "✗"}</span>'
        criteria_table_rows += f"""
        <tr>
          <td><strong style="color:#c4b5fd">{c.replace("_"," ")}</strong><br>
              <span style="color:#64748b;font-size:0.78rem">{desc}</span></td>
          <td style="text-align:center">{b1}</td>
          <td style="text-align:center">{b2}</td>
        </tr>"""

    verdict_color = "#86efac" if all_passed else "#fca5a5"
    verdict_bg    = "#052e16" if all_passed else "#2d0a0a"
    verdict_bdr   = "#166534" if all_passed else "#7f1d1d"
    verdict_icon  = "✓" if all_passed else "✗"

    tools_rows = """
    <tr><td><strong style="color:#c4b5fd">Python</strong></td><td>The programming language — glue that connects all 4 agents together.</td></tr>
    <tr><td><strong style="color:#c4b5fd">Pydantic</strong></td><td>Data validation library. Every LLM response is validated against a strict schema — wrong fields crash early, not silently.</td></tr>
    <tr><td><strong style="color:#c4b5fd">httpx</strong></td><td>HTTP client. Makes the actual web request to call the LLM — like a browser, but in code.</td></tr>
    <tr><td><strong style="color:#c4b5fd">LLM Gateway V2</strong></td><td>A local server on port 8100. The only door to the AI — all 4 steps call it. Swap Gemini for GPT-4 by changing one line in .env.</td></tr>
    <tr><td><strong style="color:#c4b5fd">Gemini 3.1 Flash Lite</strong></td><td>Google's AI model. The brain behind all 4 agents — builder, evaluator, improver, re-evaluator.</td></tr>
    <tr><td><strong style="color:#c4b5fd">uv</strong></td><td>Modern Python package manager — faster alternative to pip for installing dependencies.</td></tr>
    """

    return f"""
<div class="yt-wrap">

  <!-- ─── HEADER ─── -->
  <div class="yt-hero-bar">
    <div class="yt-pill">YouTube Explainer</div>
    <h2 class="yt-title">Full Walkthrough — What Happened In This Run</h2>
    <p class="yt-subtitle">Everything from your raw idea to the final optimized prompt, step by step.</p>
    <div class="yt-stats-row">
      <div class="yt-stat"><span class="yt-stat-val">4</span><span class="yt-stat-lbl">AI Agents</span></div>
      <div class="yt-stat"><span class="yt-stat-val">{total_ms:,} ms</span><span class="yt-stat-lbl">Total Time</span></div>
      <div class="yt-stat"><span class="yt-stat-val">{first_pass}/8</span><span class="yt-stat-lbl">Criteria Before</span></div>
      <div class="yt-stat"><span class="yt-stat-val">{final_pass}/8</span><span class="yt-stat-lbl">Criteria After</span></div>
      <div class="yt-stat"><span class="yt-stat-val">{confidence_pct}%</span><span class="yt-stat-lbl">Confidence</span></div>
    </div>
  </div>

  <!-- ─── THE PITCH ─── -->
  <div class="yt-block">
    <div class="yt-num">WHAT IS THIS?</div>
    <h3 class="yt-block-title">An AI agent that turns vague ideas into professional prompts — and grades its own work</h3>
    <p class="yt-desc">When you type a rough idea into ChatGPT, you get mediocre results because the prompt is weak.
    This tool takes your rough idea and runs it through <strong>4 chained AI agents</strong> that write, score, fix, and re-score the prompt automatically.
    You get a professionally engineered prompt every single time — with a quality report showing exactly what improved.</p>
  </div>

  <!-- ─── STEP 0: INPUT ─── -->
  <div class="yt-block">
    <div class="yt-num">01 &mdash; THE INPUT</div>
    <h3 class="yt-block-title">You typed a rough idea. That's all it takes.</h3>
    <p class="yt-desc">No setup, no template to fill in. Just a raw thought. The system figures out the rest.</p>
    <div class="yt-input-bubble">
      <span style="color:#7c3aed;font-size:0.75rem;font-weight:700;display:block;margin-bottom:6px">YOUR INPUT</span>
      {idea}
    </div>
    <div class="yt-arrow">↓ Step 1: Prompt Builder Agent receives this</div>
  </div>

  <!-- ─── STEP 1: BUILDER ─── -->
  <div class="yt-block" style="border-left-color:#7c3aed">
    <div class="yt-num" style="color:#a78bfa">02 &mdash; STEP 1 · Prompt Builder Agent</div>
    <h3 class="yt-block-title">The Builder Agent rewrites your idea as a professional prompt</h3>
    <p class="yt-desc">The first AI agent acts as a <em>Senior Prompt Engineer</em>. It reads your raw idea and expands it into a
    full, structured, implementation-ready prompt — with expert framing, technical details, and clear output instructions.
    It took <strong>{step_durations.get(1, 0):,} ms</strong> to produce this:</p>
    <div class="sub-label" style="margin-top:16px">Generated Prompt (Step 1 Output)</div>
    <pre class="prompt-box sys" style="max-height:none">{gen_prompt}</pre>
    <div class="yt-arrow">↓ Step 2: Evaluator Agent receives this prompt</div>
  </div>

  <!-- ─── STEP 2: EVALUATOR ─── -->
  <div class="yt-block" style="border-left-color:#0891b2">
    <div class="yt-num" style="color:#38bdf8">03 &mdash; STEP 2 · Prompt Evaluator Agent</div>
    <h3 class="yt-block-title">The Evaluator Agent acts like a code reviewer — but for prompts</h3>
    <p class="yt-desc">The second AI agent scores the generated prompt on <strong>8 quality criteria</strong>.
    Each criterion is a known property that makes prompts produce better AI output.
    It scored <strong>{first_pass} out of 8</strong> on the first pass in <strong>{step_durations.get(2, 0):,} ms</strong>:</p>
    <div class="sub-label" style="margin-top:16px">First Review Scores</div>
    {_criteria_badges(first_rev)}
    <div class="yt-arrow">↓ Step 3: Improver Agent receives the prompt + these scores</div>
  </div>

  <!-- ─── STEP 3: IMPROVER ─── -->
  <div class="yt-block" style="border-left-color:#059669">
    <div class="yt-num" style="color:#34d399">04 &mdash; STEP 3 · Prompt Improver Agent</div>
    <h3 class="yt-block-title">The Improver Agent rewrites the prompt to fix every failing criterion</h3>
    <p class="yt-desc">The third agent receives both the original prompt and the Step 2 review scores.
    It rewrites the prompt so that every <em>false</em> criterion becomes <em>true</em>.
    It identified <strong>{len(weaknesses)} weakness{"es" if len(weaknesses) != 1 else ""}</strong> and fixed them in <strong>{step_durations.get(3, 0):,} ms</strong>.</p>
    <div class="sub-label" style="margin-top:16px">Weaknesses Found</div>
    <div class="weaknesses-list">{weaknesses_items}</div>
    <div class="sub-label" style="margin-top:16px">Improved Prompt (Step 3 Output)</div>
    <pre class="prompt-box parsed" style="max-height:none">{imp_prompt}</pre>
    <div class="sub-label" style="margin-top:12px">Improver's Reasoning</div>
    <div class="yt-reasoning-box">{reasoning}</div>
    <div class="yt-arrow">↓ Step 4: Re-Evaluator scores the improved prompt</div>
  </div>

  <!-- ─── STEP 4: RE-EVALUATOR ─── -->
  <div class="yt-block" style="border-left-color:#d97706">
    <div class="yt-num" style="color:#fbbf24">05 &mdash; STEP 4 · Re-Evaluator Agent</div>
    <h3 class="yt-block-title">The same Evaluator runs again on the improved prompt to confirm the fixes</h3>
    <p class="yt-desc">The exact same scoring agent from Step 2 now re-evaluates the improved prompt.
    This is the <strong>self-check</strong> — the system verifying its own work.
    It scored <strong>{final_pass} out of 8</strong> ({"+" if improved_by >= 0 else ""}{improved_by} from before) in <strong>{step_durations.get(4, 0):,} ms</strong>:</p>
    <div class="sub-label" style="margin-top:16px">Final Review Scores</div>
    {_criteria_badges(final_rev)}
  </div>

  <!-- ─── FULL CRITERIA COMPARISON ─── -->
  <div class="yt-block">
    <div class="yt-num">06 &mdash; BEFORE VS AFTER</div>
    <h3 class="yt-block-title">What each criterion means — and how it changed</h3>
    <p class="yt-desc">Here is every criterion explained in plain English, with both the before (Step 2) and after (Step 4) result:</p>
    <table class="scorecard" style="margin-top:14px">
      <thead>
        <tr>
          <th style="width:60%">Criterion &amp; What It Means</th>
          <th style="text-align:center;width:20%">Before (Step 2)</th>
          <th style="text-align:center;width:20%">After (Step 4)</th>
        </tr>
      </thead>
      <tbody>{criteria_table_rows}</tbody>
    </table>
  </div>

  <!-- ─── VERDICT ─── -->
  <div class="yt-block">
    <div class="yt-num">07 &mdash; THE VERDICT</div>
    <h3 class="yt-block-title">Self-Check Result — Did the pipeline succeed?</h3>
    <p class="yt-desc">After Step 4, the pipeline checks all 8 final scores. If all pass, the job is done.
    If any still fail, they are listed honestly. This is called the <strong>self-check</strong> —
    an agent auditing its own output rather than blindly claiming success.</p>
    <div style="background:{verdict_bg};border:1px solid {verdict_bdr};border-radius:10px;padding:18px 22px;margin-top:14px;font-size:1rem;font-weight:700;color:{verdict_color}">
      {verdict_icon} {_esc(self_check)}
    </div>
    <div style="margin-top:12px;background:#1e293b;border:1px solid #2d3748;border-radius:10px;padding:16px 20px">
      <div class="sub-label">Confidence Score</div>
      <div style="font-size:2rem;font-weight:800;color:#c4b5fd;margin-top:4px">{confidence_pct}%</div>
      <div style="font-size:0.82rem;color:#64748b;margin-top:2px">Reported by the Improver Agent based on how well the criteria were fixed</div>
    </div>
  </div>

  <!-- ─── TOOLS ─── -->
  <div class="yt-block">
    <div class="yt-num">08 &mdash; TOOLS &amp; TECH USED</div>
    <h3 class="yt-block-title">Every tool in the stack — what it is and why it's there</h3>
    <table class="scorecard" style="margin-top:14px">
      <thead><tr><th style="width:25%">Tool</th><th>What It Does In This Project</th></tr></thead>
      <tbody>{tools_rows}</tbody>
    </table>
  </div>

  <!-- ─── ARCHITECTURE ─── -->
  <div class="yt-block">
    <div class="yt-num">09 &mdash; THE KEY DESIGN DECISION</div>
    <h3 class="yt-block-title">All LLM calls go through one gateway — your app never touches the AI directly</h3>
    <p class="yt-desc">Every single LLM call in all 4 steps goes through <code style="background:#1e293b;padding:2px 6px;border-radius:4px;color:#c4b5fd">gateway_client.py</code> →
    <code style="background:#1e293b;padding:2px 6px;border-radius:4px;color:#c4b5fd">localhost:8100</code> → Gemini.
    This is a real production pattern: if you want to swap Gemini for OpenAI or Claude tomorrow, you change <strong>one line in .env</strong> and nothing else changes.
    The 4 agents don't know or care which AI model is running behind the gateway.</p>
    <div class="arch-flow">
      <div class="arch-box" style="border-color:#7c3aed">Your Idea (input)</div>
      <div class="arch-arrow">→</div>
      <div class="arch-box" style="border-color:#7c3aed">Prompt Builder</div>
      <div class="arch-arrow">→</div>
      <div class="arch-box" style="border-color:#0891b2">Evaluator</div>
      <div class="arch-arrow">→</div>
      <div class="arch-box" style="border-color:#059669">Improver</div>
      <div class="arch-arrow">→</div>
      <div class="arch-box" style="border-color:#d97706">Re-Evaluator</div>
      <div class="arch-arrow">→</div>
      <div class="arch-box" style="border-color:#86efac;color:#86efac">Final Prompt + Report</div>
    </div>
    <div style="text-align:center;color:#475569;font-size:0.8rem;margin-top:8px">All arrows pass through gateway_client.py → LLM Gateway V2 → Gemini 3.1 Flash Lite</div>
  </div>

</div>
"""


def _render_html(idea: str, started: datetime, steps: list[dict],
                 pydantic_events: list[dict], final_json: str) -> str:
    total_ms = sum(s["duration_ms"] for s in steps)
    pyd_by_step = {e["step_num"]: e for e in pydantic_events}

    def _step_with_pydantic(s: dict) -> str:
        card = _step_card(s)
        pyd = pyd_by_step.get(s["number"])
        return card + (_pydantic_card(pyd) if pyd else "")

    step_cards = "".join(_step_with_pydantic(s) for s in steps)
    pyd0_card = _pydantic_card(pyd_by_step[0]) if 0 in pyd_by_step else ""
    pyd5_card = _pydantic_card(pyd_by_step[5]) if 5 in pyd_by_step else ""
    ts_str = started.strftime("%Y-%m-%d %H:%M:%S")

    passed = sum(1 for s in steps if not s["error"])
    retried = sum(1 for s in steps if s["retried"])

    try:
        final = json.loads(final_json)
        confidence_pct = int(final.get("confidence", 0) * 100)
        self_check = final.get("self_check", "")
        self_check_cls = "pass" if "passed" in self_check.lower() else "fail"
        gen_prompt = _esc(final.get("generated_prompt", ""))
        imp_prompt = _esc(final.get("improved_prompt", ""))
        weaknesses = final.get("weaknesses_found", [])
    except Exception:
        confidence_pct = 0
        self_check = ""
        self_check_cls = "fail"
        gen_prompt = ""
        imp_prompt = ""
        weaknesses = []
        final = {}

    weaknesses_html = "".join(f"<li>{_esc(w)}</li>" for w in weaknesses)
    prompt_compare_block = f"""
    <div class="compare-grid" style="margin-bottom:0">
      <div class="compare-card before" style="border-color:#4b1e1e">
        <h4 style="margin-bottom:8px">Original Generated Prompt</h4>
        <pre class="prompt-box raw" style="max-height:340px">{gen_prompt}</pre>
      </div>
      <div class="compare-card after" style="border-color:#1e3a2f">
        <h4 style="margin-bottom:8px">Improved Prompt</h4>
        <pre class="prompt-box parsed" style="max-height:340px">{imp_prompt}</pre>
      </div>
    </div>
    {"<div style='margin-top:14px'><div class='sub-label'>Weaknesses Found</div><ul style='padding-left:20px;color:#94a3b8;font-size:0.85rem;margin-top:6px'>" + weaknesses_html + "</ul></div>" if weaknesses else ""}
    """

    explainer_block = _build_explainer(final, steps, ts_str, total_ms, confidence_pct)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>Run Log — {_esc(idea[:60])}</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:'Segoe UI',system-ui,sans-serif;background:#0f1117;color:#e2e8f0;line-height:1.6}}
    .hero{{background:linear-gradient(135deg,#1a1f35,#0f1117);border-bottom:1px solid #1e293b;padding:40px 32px 34px}}
    .hero h1{{font-size:1.7rem;font-weight:800;color:#c4b5fd;margin-bottom:8px}}
    .hero .idea-text{{background:#1e293b;border:1px solid #2d3748;border-radius:8px;padding:12px 16px;font-size:0.95rem;color:#94a3b8;margin-top:14px}}
    .meta-row{{display:flex;gap:20px;flex-wrap:wrap;margin-top:16px}}
    .meta-chip{{background:#1e293b;border:1px solid #2d3748;border-radius:999px;padding:4px 14px;font-size:0.78rem;color:#64748b}}
    .meta-chip span{{color:#c4b5fd;font-weight:700}}
    .container{{max-width:1100px;margin:0 auto;padding:36px 20px 80px}}
    .section-title{{font-size:1.1rem;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:.08em;margin:40px 0 16px;padding-bottom:8px;border-bottom:1px solid #1e293b}}
    /* Summary cards */
    .summary-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:32px}}
    @media(max-width:700px){{.summary-grid{{grid-template-columns:1fr 1fr}}}}
    .sum-card{{background:#1e293b;border:1px solid #2d3748;border-radius:12px;padding:18px 20px;text-align:center}}
    .sum-card .val{{font-size:1.9rem;font-weight:800;color:#c4b5fd}}
    .sum-card .lbl{{font-size:0.78rem;color:#64748b;margin-top:4px;text-transform:uppercase;letter-spacing:.05em}}
    /* Confidence bar */
    .conf-bar-wrap{{background:#1e293b;border:1px solid #2d3748;border-radius:12px;padding:20px 24px;margin-bottom:16px}}
    .conf-bar-track{{background:#0f172a;border-radius:999px;height:14px;overflow:hidden;margin:10px 0 6px}}
    .conf-bar-fill{{height:100%;border-radius:999px;background:linear-gradient(90deg,#7c3aed,#06b6d4);transition:width .4s}}
    .conf-label{{font-size:0.85rem;color:#64748b}}
    /* Self check */
    .self-check{{border-radius:10px;padding:14px 18px;font-size:0.92rem;font-weight:600;margin-bottom:24px}}
    .self-check.pass{{background:#052e16;border:1px solid #166534;color:#86efac}}
    .self-check.fail{{background:#2d0a0a;border:1px solid #7f1d1d;color:#fca5a5}}
    /* Step cards */
    .step-card{{background:#1e293b;border:1px solid #2d3748;border-left:3px solid var(--accent);border-radius:12px;padding:22px 24px;margin-bottom:20px}}
    .step-header{{display:flex;align-items:center;gap:14px;margin-bottom:18px}}
    .step-num{{color:#fff;font-size:0.8rem;font-weight:800;border-radius:6px;padding:4px 12px;white-space:nowrap}}
    .step-name{{font-size:1rem;font-weight:700;color:#e2e8f0}}
    .step-time{{font-size:0.78rem;color:#64748b;margin-left:8px}}
    .retry-tag{{background:#451a03;color:#fb923c;border:1px solid #92400e;border-radius:999px;padding:1px 8px;font-size:0.7rem;margin-left:6px}}
    .section-row{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px}}
    @media(max-width:650px){{.section-row{{grid-template-columns:1fr}}}}
    .sub-label{{font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:#475569;margin:10px 0 5px}}
    .prompt-box{{background:#0f172a;border:1px solid #1e293b;border-radius:8px;padding:14px;font-family:'Courier New',monospace;font-size:0.78rem;color:#cbd5e1;white-space:pre-wrap;word-break:break-word;max-height:280px;overflow-y:auto}}
    .prompt-box.sys{{border-color:#7c3aed33}}
    .prompt-box.usr{{border-color:#0891b233}}
    .prompt-box.raw{{border-color:#334155;color:#94a3b8}}
    .prompt-box.parsed{{border-color:#05966933;color:#86efac}}
    /* Scorecard */
    .scorecard{{width:100%;border-collapse:collapse;margin-top:6px;font-size:0.83rem}}
    .scorecard th{{text-align:left;padding:6px 10px;color:#475569;font-weight:600;border-bottom:1px solid #1e293b}}
    .scorecard td{{padding:7px 10px;border-bottom:1px solid #1e293b;color:#94a3b8}}
    .badge{{font-weight:700;font-size:0.75rem;border-radius:6px;padding:2px 10px;text-align:center}}
    .badge.pass{{background:#052e16;color:#86efac;border:1px solid #166534}}
    .badge.fail{{background:#2d0a0a;color:#fca5a5;border:1px solid #7f1d1d}}
    /* Before/after */
    .compare-grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:24px}}
    @media(max-width:650px){{.compare-grid{{grid-template-columns:1fr}}}}
    .compare-card{{background:#0f172a;border:1px solid #1e293b;border-radius:10px;padding:16px 18px}}
    .compare-card h4{{font-size:0.85rem;font-weight:700;margin-bottom:10px}}
    .compare-card.before h4{{color:#f87171}}
    .compare-card.after h4{{color:#86efac}}
    /* Final JSON */
    .final-json{{background:#0f172a;border:1px solid #1e293b;border-radius:10px;padding:20px;font-family:'Courier New',monospace;font-size:0.8rem;color:#86efac;white-space:pre-wrap;word-break:break-word;overflow-x:auto}}
    .error-box{{background:#2d0a0a;border:1px solid #7f1d1d;border-radius:8px;padding:12px;color:#fca5a5;font-size:0.85rem;margin-bottom:14px}}
    footer{{text-align:center;padding:24px;color:#334155;font-size:0.75rem;border-top:1px solid #1e293b}}
    /* ── Pydantic Cards ── */
    .pyd-card{{background:#0d1b2a;border:1px solid #1e3a5f;border-left:4px solid var(--pyd-color,#6d28d9);border-radius:10px;padding:18px 20px;margin-bottom:16px;margin-top:6px}}
    .pyd-header{{display:flex;align-items:flex-start;gap:12px;margin-bottom:14px}}
    .pyd-icon{{width:28px;height:28px;border-radius:50%;background:var(--pyd-color,#6d28d9);color:#fff;font-size:1rem;display:flex;align-items:center;justify-content:center;flex-shrink:0;font-weight:900}}
    .pyd-title{{font-size:0.95rem;font-weight:700;color:#e2e8f0}}
    .pyd-sub{{font-size:0.72rem;color:#475569;margin-top:2px;text-transform:uppercase;letter-spacing:.06em}}
    .pyd-table{{width:100%;border-collapse:collapse;font-size:0.79rem;margin-bottom:12px}}
    .pyd-table th{{text-align:left;padding:6px 10px;color:#334155;font-weight:600;border-bottom:1px solid #1e293b;background:#0a1628}}
    .pyd-table td{{padding:6px 10px;border-bottom:1px solid #0f172a;vertical-align:top}}
    .pyd-field{{color:#94a3b8;font-family:'Courier New',monospace;white-space:nowrap}}
    .pyd-type{{color:#475569;font-size:0.72rem;white-space:nowrap}}
    .pyd-val{{color:#64748b;font-family:'Courier New',monospace;word-break:break-all}}
    .pyd-changed{{background:#1a1205}}
    .pyd-changed .pyd-field{{color:#fbbf24}}
    .pyd-coerce-wrap{{background:#1a1205;border:1px solid #78350f44;border-radius:8px;padding:10px 14px;font-size:0.8rem;color:#d97706}}
    .pyd-coerce-wrap ul{{padding-left:16px;margin-top:6px}}
    .pyd-coerce-wrap li{{margin-bottom:4px;color:#94a3b8}}
    .pyd-coerce-wrap code{{background:#0f172a;padding:1px 5px;border-radius:3px;color:#fbbf24;font-size:0.75rem}}
    .pyd-tag{{display:inline-block;border-radius:4px;padding:1px 7px;font-size:0.68rem;font-weight:700;margin-right:6px;text-transform:uppercase}}
    .pyd-tag-coerce{{background:#451a03;color:#fb923c;border:1px solid #92400e}}
    .pyd-tag-default{{background:#1e1b4b;color:#a5b4fc;border:1px solid #3730a3}}
    .pyd-no-coerce{{color:#166534;font-size:0.8rem;padding:8px 12px;background:#052e16;border-radius:6px;border:1px solid #166534}}

    /* ── YouTube Explainer styles ── */
    .yt-wrap{{margin-top:0;margin-bottom:0}}
    .yt-hero-bar{{background:linear-gradient(135deg,#1e1040,#0d1f35);border:1px solid #2d3748;border-radius:16px;padding:36px 36px 28px;margin-bottom:8px}}
    .yt-pill{{display:inline-block;background:#7c3aed;color:#fff;font-size:0.7rem;font-weight:800;letter-spacing:.1em;text-transform:uppercase;border-radius:999px;padding:4px 14px;margin-bottom:12px}}
    .yt-title{{font-size:1.55rem;font-weight:800;color:#e2e8f0;margin-bottom:8px}}
    .yt-subtitle{{color:#64748b;font-size:0.9rem;margin-bottom:20px}}
    .yt-stats-row{{display:flex;gap:16px;flex-wrap:wrap}}
    .yt-stat{{background:#0f172a;border:1px solid #1e293b;border-radius:10px;padding:10px 18px;text-align:center;min-width:90px}}
    .yt-stat-val{{display:block;font-size:1.3rem;font-weight:800;color:#c4b5fd}}
    .yt-stat-lbl{{display:block;font-size:0.68rem;color:#475569;text-transform:uppercase;letter-spacing:.05em;margin-top:2px}}
    .yt-block{{background:#1e293b;border:1px solid #2d3748;border-left:4px solid #334155;border-radius:12px;padding:28px 30px;margin-bottom:16px}}
    .yt-num{{font-size:0.68rem;font-weight:800;text-transform:uppercase;letter-spacing:.12em;color:#475569;margin-bottom:8px}}
    .yt-block-title{{font-size:1.1rem;font-weight:700;color:#e2e8f0;margin-bottom:10px}}
    .yt-desc{{color:#94a3b8;font-size:0.88rem;line-height:1.7;margin-bottom:0}}
    .yt-input-bubble{{background:#0f172a;border:1px solid #7c3aed44;border-radius:10px;padding:16px 20px;font-size:0.95rem;color:#c4b5fd;margin-top:14px;font-style:italic}}
    .yt-arrow{{text-align:center;color:#334155;font-size:1.2rem;font-weight:700;margin:14px 0 0}}
    .badge-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:12px}}
    @media(max-width:700px){{.badge-grid{{grid-template-columns:1fr 1fr}}}}
    .crit-badge{{border-radius:8px;padding:10px 12px;display:flex;align-items:center;gap:8px;font-size:0.78rem}}
    .crit-badge.pass{{background:#052e16;border:1px solid #166534}}
    .crit-badge.fail{{background:#2d0a0a;border:1px solid #7f1d1d}}
    .crit-icon{{font-size:1rem;font-weight:900}}
    .crit-badge.pass .crit-icon{{color:#86efac}}
    .crit-badge.fail .crit-icon{{color:#fca5a5}}
    .crit-name{{color:#94a3b8;line-height:1.3}}
    .weaknesses-list{{display:flex;flex-direction:column;gap:8px;margin-top:10px}}
    .weakness-item{{background:#2d0a0a;border:1px solid #7f1d1d33;border-radius:8px;padding:10px 14px;color:#fca5a5;font-size:0.83rem;display:flex;align-items:flex-start;gap:10px}}
    .w-dot{{width:6px;height:6px;border-radius:50%;background:#ef4444;flex-shrink:0;margin-top:6px}}
    .yt-reasoning-box{{background:#0f172a;border:1px solid #1e293b;border-radius:8px;padding:14px 16px;color:#94a3b8;font-size:0.85rem;line-height:1.7;margin-top:6px}}
    .arch-flow{{display:flex;align-items:center;gap:0;flex-wrap:wrap;margin-top:20px;justify-content:center}}
    .arch-box{{background:#0f172a;border:2px solid #334155;border-radius:8px;padding:8px 14px;font-size:0.78rem;font-weight:700;color:#94a3b8;white-space:nowrap}}
    .arch-arrow{{color:#334155;font-size:1.2rem;padding:0 6px;font-weight:700}}
  </style>
</head>
<body>

<div class="hero">
  <div style="font-size:0.75rem;color:#475569;margin-bottom:6px;letter-spacing:.06em;text-transform:uppercase">AI Prompt Builder Evaluator · Run Log</div>
  <h1>Pipeline Execution Report</h1>
  <div class="idea-text"><strong style="color:#7c3aed">Idea:</strong> {_esc(idea)}</div>
  <div class="meta-row">
    <div class="meta-chip">Run at <span>{ts_str}</span></div>
    <div class="meta-chip">Total time <span>{total_ms:,} ms</span></div>
    <div class="meta-chip">Steps completed <span>{passed}/4</span></div>
    <div class="meta-chip">Retries <span>{retried}</span></div>
  </div>
</div>

<div class="container">

  <div class="section-title">YouTube Explainer — Full Walkthrough</div>
  {explainer_block}

  <div class="section-title">Run Summary</div>

  <div class="summary-grid">
    <div class="sum-card"><div class="val">{passed}</div><div class="lbl">Steps Done</div></div>
    <div class="sum-card"><div class="val">{retried}</div><div class="lbl">JSON Retries</div></div>
    <div class="sum-card"><div class="val">{confidence_pct}%</div><div class="lbl">Confidence</div></div>
    <div class="sum-card"><div class="val">{total_ms:,}</div><div class="lbl">Total ms</div></div>
  </div>

  <div class="conf-bar-wrap">
    <div class="sub-label">Final Confidence Score</div>
    <div class="conf-bar-track"><div class="conf-bar-fill" style="width:{confidence_pct}%"></div></div>
    <div class="conf-label">{confidence_pct}% — reported by the Prompt Improver agent</div>
  </div>

  <div class="self-check {self_check_cls}">Self Check: {_esc(self_check)}</div>

  <div class="section-title">Generated Prompt vs Improved Prompt</div>
  {prompt_compare_block}

  <div class="section-title">Before vs After — Criteria Comparison</div>
  <div class="compare-grid">
    <div class="compare-card before">
      <h4>First Review (after Step 2)</h4>
      <table class="scorecard">
        <thead><tr><th>Criterion</th><th>Result</th></tr></thead>
        <tbody>{_criteria_rows(steps[1]["parsed_output"] if len(steps) > 1 else {{}})}</tbody>
      </table>
    </div>
    <div class="compare-card after">
      <h4>Final Review (after Step 4)</h4>
      <table class="scorecard">
        <thead><tr><th>Criterion</th><th>Result</th></tr></thead>
        <tbody>{_criteria_rows(steps[3]["parsed_output"] if len(steps) > 3 else {{}})}</tbody>
      </table>
    </div>
  </div>

  <div class="section-title">Step-by-Step LLM Calls &amp; Pydantic Validations</div>
  <div style="font-size:0.8rem;color:#475569;margin-bottom:16px">
    Purple cards = LLM step &nbsp;|&nbsp;
    <span style="color:#6d28d9">&#10003;</span> <span style="color:#6d28d9">Teal/Blue cards</span> = Pydantic validation (what went in, what came out, any type coercions)
  </div>
  <div class="sub-label" style="margin-bottom:8px">Before Step 1 — Input Validation</div>
  {pyd0_card}
  {step_cards}
  <div class="sub-label" style="margin-bottom:8px">After All Steps — Final Output Assembly</div>
  {pyd5_card}

  <div class="section-title">Final JSON Output</div>
  <pre class="final-json">{_esc(final_json)}</pre>

</div>

<footer>Generated by ai-prompt-builder-evaluator · {ts_str}</footer>
</body>
</html>"""

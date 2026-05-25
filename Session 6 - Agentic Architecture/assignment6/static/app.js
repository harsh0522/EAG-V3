/* EAGV3 S6 Dashboard — vanilla JS, no framework */
"use strict";

// ── State ──────────────────────────────────────────────────────────────────
let currentRunId = null;
let startTime = null;
let elapsedTimer = null;
const iterCards = { memory: {}, perception: {}, decision: {}, action: {} };

// ── Run Log helpers ────────────────────────────────────────────────────────
function appendLog(text, cls = "ll-act") {
  const body = document.getElementById("log-body");
  if (!body) return;
  const div = document.createElement("div");
  div.className = cls;
  div.textContent = text;
  body.appendChild(div);
  body.scrollTop = body.scrollHeight;
}

function clearLog() {
  const body = document.getElementById("log-body");
  if (body) body.innerHTML = "";
}

function handleEventLog(ev) {
  const { role, event, iter } = ev;
  if (role === "loop") {
    if (event === "run_start") {
      clearLog();
      const q = (ev.input?.query || "").slice(0, 90);
      appendLog(`[run_start]  run_id=${ev.run_id}`, "ll-run");
      appendLog(`             query: "${q}${q.length >= 90 ? "…" : ""}"`, "ll-run");
    } else if (event === "iter_start") {
      appendLog(`── iter ${iter} ──`, "ll-iter");
    } else if (event === "attach") {
      const o = ev.output || {};
      appendLog(`[attach]     ${o.art_id}  (${o.size_bytes} bytes)  — artifact bytes sent to Decision`, "ll-attach");
    } else if (event === "attach_dropped") {
      const o = ev.output || {};
      appendLog(`[attach_dropped]  ${o.art_id}  — ${o.reason}`, "ll-guard");
    } else if (event === "all_done") {
      const n = (ev.output?.goals || []).length;
      appendLog(`[done]  all ${n} goal${n !== 1 ? "s" : ""} satisfied — loop exits`, "ll-done");
    } else if (event === "run_end") {
      const final = (ev.output?.final || "").slice(0, 400);
      appendLog(`\nFINAL ANSWER:\n${final}${(ev.output?.final || "").length > 400 ? "\n[…truncated]" : ""}`, "ll-final");
    }
  } else if (role === "memory") {
    if (event === "read") {
      const n = ev.output?.hits_count ?? (ev.output?.hits || []).length;
      appendLog(`[memory.read]     ${n} hit${n !== 1 ? "s" : ""}  — keyword search over state/memory.json`, "ll-mem");
    } else if (event === "remember") {
      const item = ev.output?.item;
      if (item) {
        appendLog(`[memory.remember] classified → ${item.kind}: ${(item.descriptor || "").slice(0, 70)}`, "ll-mem");
      } else {
        appendLog(`[memory.remember] no durable content extracted from query`, "ll-mem");
      }
    } else if (event === "record_outcome") {
      const item = ev.output?.item || {};
      appendLog(`[memory.outcome]  ${(item.descriptor || "").slice(0, 90)}  — persisted to state/memory.json`, "ll-mem");
    }
  } else if (role === "perception" && event === "observe") {
    const goals = ev.output?.goals || [];
    goals.forEach(g => {
      const mark = g.done ? "[done]" : "[open]";
      const att = g.attach_artifact_id ? `  attach=${g.attach_artifact_id.slice(0, 18)}` : "";
      appendLog(`[perception]  ${mark} ${(g.text || "").slice(0, 85)}${att}`, g.done ? "ll-pdone" : "ll-popen");
    });
    const rd = ev.llm?.router_decision;
    if (rd) {
      const prov = rd.chosen_worker_provider || rd.router_provider || "?";
      const tier = rd.tier || "?";
      appendLog(`              via ${prov}/${tier}`, "ll-act");
    }
  } else if (role === "decision" && event === "next_step") {
    const out = ev.output?.output || {};
    if (out.tool_call) {
      const tc = out.tool_call;
      const args = JSON.stringify(tc.arguments || {}).slice(0, 90);
      appendLog(`[decision]    TOOL_CALL: ${tc.name}(${args})`, "ll-dtool");
    } else if (out.answer) {
      const ans = out.answer.slice(0, 140);
      appendLog(`[decision]    ANSWER: ${ans}${out.answer.length > 140 ? "…" : ""}`, "ll-dans");
    }
    const rd = ev.llm?.router_decision;
    if (rd) {
      const prov = rd.chosen_worker_provider || rd.router_provider || "?";
      appendLog(`              via ${prov}`, "ll-act");
    }
  } else if (role === "action") {
    if (event === "execute") {
      const res = (ev.output?.result_text || "").slice(0, 130);
      const art = ev.output?.artifact_id;
      const artStr = art ? `  → ${art}` : "";
      appendLog(`[action]      → ${res}${res.length >= 130 ? "…" : ""}${artStr}`, "ll-act");
    } else if (event === "guarded") {
      const tc = ev.input?.tool_call || {};
      appendLog(`[action.guarded]  ⚠ art: handle passed to ${tc.name || "?"}(${tc.arguments?.path || tc.arguments?.url || ""}) — blocked`, "ll-guard");
    }
  } else if (role === "artifacts" && event === "put") {
    const art_id = ev.output?.art_id || "";
    const size = ev.output?.size_bytes || 0;
    const ct = ev.input?.content_type || "";
    const desc = (ev.input?.descriptor || "").slice(0, 60);
    appendLog(`[artifacts.put]   ${art_id}  (${size} bytes, ${ct})  ← ${desc}`, "ll-art");
  }
}

// ── SSE Connection ─────────────────────────────────────────────────────────
function connectSSE() {
  const es = new EventSource("/events");
  const dot = document.getElementById("status-dot");
  es.onopen = () => { dot.className = "running"; dot.title = "Live"; };
  es.onerror = () => { dot.className = ""; dot.title = "Disconnected"; setTimeout(connectSSE, 3000); es.close(); };
  es.onmessage = (e) => {
    try {
      const ev = JSON.parse(e.data);
      if (ev.event === "ping") return;
      handleEvent(ev);
    } catch {}
  };
}

// ── Event routing ──────────────────────────────────────────────────────────
function handleEvent(ev) {
  handleEventLog(ev);   // mirror every event to the Run Log panel
  const { role, event, iter } = ev;

  if (role === "loop") {
    if (event === "run_start") onRunStart(ev);
    else if (event === "iter_start") onIterStart(ev);
    else if (event === "all_done") onAllDone(ev);
    else if (event === "run_end") onRunEnd(ev);
    else if (event === "attach") appendToCol("action", iter, renderAttach(ev), ev);
    else if (event === "attach_dropped") appendToCol("action", iter, renderAttachDropped(ev), ev);
  } else if (role === "memory") {
    if (event === "read") appendToCol("memory", iter, renderMemoryRead(ev), ev);
    else if (event === "remember" || event === "record_outcome") refreshMemoryState();
  } else if (role === "perception" && event === "observe") {
    appendToCol("perception", iter, renderPerception(ev), ev);
    if (ev.llm) appendGatewayRow(ev.llm, "perception");
  } else if (role === "decision" && event === "next_step") {
    appendToCol("decision", iter, renderDecision(ev), ev);
    if (ev.llm) appendGatewayRow(ev.llm, "decision");
  } else if (role === "action") {
    if (event === "execute") appendToCol("action", iter, renderAction(ev), ev);
    else if (event === "guarded") appendToCol("action", iter, renderGuarded(ev), ev);
  } else if (role === "artifacts" && event === "put") {
    // Merge input (content_type, descriptor) + output (art_id, size_bytes)
    addArtifact({ ...ev.output, ...ev.input });
  } else if (role === "pydantic") {
    appendPydanticRow(ev);
  } else if (role === "gateway" && event === "call") {
    appendGatewayRow(ev.output, ev.input?.role || "");
  }
}

// ── Run lifecycle ──────────────────────────────────────────────────────────
function onRunStart(ev) {
  currentRunId = ev.run_id;
  startTime = Date.now();
  document.getElementById("run-id").textContent = ev.run_id;
  document.getElementById("query-display").textContent = ev.input?.query || "";
  document.getElementById("status-dot").className = "running";
  if (elapsedTimer) clearInterval(elapsedTimer);
  elapsedTimer = setInterval(() => {
    document.getElementById("elapsed").textContent = ((Date.now() - startTime) / 1000).toFixed(1) + "s";
  }, 200);
  // Clear iter cards
  Object.keys(iterCards).forEach(k => { iterCards[k] = {}; });
  ["col-memory","col-perception","col-decision","col-action"].forEach(id => {
    document.getElementById(id).innerHTML = "";
  });
}

function onIterStart(ev) {
  const it = ev.iter;
  ["memory","perception","decision","action"].forEach(col => {
    if (!iterCards[col][it]) {
      const card = document.createElement("div");
      card.className = "iter-card";
      card.id = `iter-${col}-${it}`;
      card.innerHTML = `<div class="iter-header">── iter ${it} ──</div><div class="iter-content" id="iter-${col}-${it}-body"></div>`;
      document.getElementById(`col-${col}`).appendChild(card);
      iterCards[col][it] = card;
    }
  });
}

function onAllDone(ev) {
  document.getElementById("status-dot").className = "";
  if (elapsedTimer) { clearInterval(elapsedTimer); elapsedTimer = null; }
}

function onRunEnd(ev) {
  document.getElementById("status-dot").className = "";
  if (elapsedTimer) { clearInterval(elapsedTimer); elapsedTimer = null; }
  refreshMemoryState();
}

// ── Column helpers ─────────────────────────────────────────────────────────
function appendToCol(colName, iter, html, ev) {
  const bodyId = `iter-${colName}-${iter}-body`;
  let body = document.getElementById(bodyId);
  if (!body) {
    // Create card on demand
    onIterStart({ iter });
    body = document.getElementById(bodyId);
  }
  if (body) {
    const div = document.createElement("div");
    div.className = "ev";
    div.innerHTML = html;
    body.appendChild(div);
    body.scrollTop = body.scrollHeight;
    const colEl = document.getElementById(`col-${colName}`);
    if (colEl) colEl.scrollTop = colEl.scrollHeight;
  }
}

// ── Renderers ─────────────────────────────────────────────────────────────
function renderMemoryRead(ev) {
  const hits = ev.output?.hits || [];
  if (!hits.length) return `<span class="ev-kind">0 hits</span>`;
  const rows = hits.map((h, i) => {
    const art = h.artifact_id ? ` <span class="ev-artifact">[art:${h.artifact_id.slice(4,10)}…]</span>` : "";
    const desc = h.descriptor ? esc(h.descriptor.slice(0,70)) + (h.descriptor.length > 70 ? "…" : "") : "";
    return `<div class="ev-kind">[${i}] ${esc(h.kind)}: ${desc}${art}</div>`;
  });
  return rows.join("");
}

function renderPerception(ev) {
  const goals = ev.output?.goals || [];
  const llm = ev.llm || {};
  const rd = llm.router_decision;
  const rdStr = rd ? ` <span class="ev-kind">[${rd.chosen_worker_provider || rd.router_provider || "?"}/${rd.tier || "?"}]</span>` : "";
  const goalRows = goals.map(g => {
    const cls = g.done ? "ev-done" : "ev-open";
    const mark = g.done ? "[done]" : "[open]";
    const att = g.attach_artifact_id ? ` <span class="ev-artifact">attach=${g.attach_artifact_id.slice(0,12)}</span>` : "";
    return `<div class="${cls}">${mark} ${esc(g.text?.slice(0,70))}${att}</div>`;
  });
  const promptDetails = ev.llm?.messages
    ? `<details><summary>show prompt</summary><div class="prompt-box">${esc(JSON.stringify(ev.llm.messages, null, 2))}</div></details>` : "";
  return goalRows.join("") + rdStr + promptDetails;
}

function renderDecision(ev) {
  const out = ev.output?.output || {};
  const llm = ev.llm || {};
  const rd = llm.router_decision;
  const rdStr = rd ? ` <span class="ev-kind">[${rd.chosen_worker_provider || rd.router_provider || "?"}/${rd.tier || "?"}]</span>` : "";
  if (out.tool_call) {
    const tc = out.tool_call;
    const args = JSON.stringify(tc.arguments || {}).slice(0, 100);
    return `<div class="ev-tool">TOOL: ${esc(tc.name)}(${esc(args)})</div>${rdStr}`;
  }
  if (out.answer) {
    return `<div class="ev-answer">ANSWER: ${esc(out.answer.slice(0, 200))}</div>${rdStr}`;
  }
  return `<span class="ev-kind">(no output)</span>`;
}

function renderAction(ev) {
  const res = ev.output?.result_text || "";
  const art = ev.output?.artifact_id;
  if (art) {
    return `<div class="ev-artifact">→ [artifact ${art}]</div><div class="ev-kind">${esc(res.slice(0, 200))}</div>`;
  }
  return `<div>→ ${esc(res.slice(0, 200))}</div>`;
}

function renderGuarded(ev) {
  const tc = ev.input?.tool_call || {};
  return `<div class="ev-guarded">⚠ GUARDED: art: handle passed to ${esc(tc.name || "?")} as path/url</div>`;
}

function renderAttach(ev) {
  const out = ev.output || {};
  return `<div class="ev-artifact">📎 attached ${out.art_id || ""} (${out.size_bytes || 0} bytes)</div>`;
}

function renderAttachDropped(ev) {
  const out = ev.output || {};
  return `<div class="ev-guarded">⚠ attach_dropped: ${out.art_id} — ${out.reason}</div>`;
}

// ── Artifacts strip ────────────────────────────────────────────────────────
function addArtifact(art) {
  const list = document.getElementById("artifact-list");
  const card = document.createElement("div");
  card.className = "artifact-card";
  card.innerHTML = `
    <div class="art-id">${esc(art.art_id || art.id || "")}</div>
    <div class="art-meta">${esc(art.size_bytes)} bytes · ${esc(art.content_type || "")}</div>
    <div class="art-meta">${esc((art.descriptor || "").slice(0, 60))}</div>`;
  list.appendChild(card);
  const count = list.children.length;
  document.getElementById("art-count").textContent = `(${count})`;
}

// ── Gateway table ──────────────────────────────────────────────────────────
function appendGatewayRow(llm, role) {
  if (!llm) return;
  const tbody = document.getElementById("gateway-tbody");
  const rd = llm.router_decision;
  const provider = rd?.chosen_worker_provider || llm.provider || "?";
  const model = (rd?.chosen_worker_model || llm.model || "?").slice(0, 30);
  const tier = rd?.tier || "—";
  const tokIn = llm.messages_in_tokens || llm.input_tokens || 0;
  const tokOut = llm.tokens_out || llm.output_tokens || 0;
  const ms = llm.duration_ms || 0;
  const reason = llm.reasoning_applied ? "✓" : "";
  const tr = document.createElement("tr");
  tr.innerHTML = `<td>${esc(provider)}</td><td style="color:var(--accent)">${esc(model)}</td>
    <td>${esc(tier)}</td><td>${tokIn}</td><td>${tokOut}</td><td>${ms}</td><td>${reason}</td>`;
  tbody.insertBefore(tr, tbody.firstChild);
}

// ── Memory state table ─────────────────────────────────────────────────────
function refreshMemoryState() {
  fetch("/api/state").then(r => r.json()).then(data => {
    const tbody = document.getElementById("memory-tbody");
    tbody.innerHTML = "";
    (data.memory || []).forEach(item => {
      const tr = document.createElement("tr");
      const artCell = item.artifact_id
        ? `<span class="ev-artifact">${esc(item.artifact_id.slice(0, 12))}</span>` : "—";
      tr.innerHTML = `<td style="color:var(--yellow)">${esc(item.kind)}</td>
        <td>${esc((item.descriptor || "").slice(0, 80))}</td>
        <td class="ev-kind">${esc((item.keywords || []).join(", ").slice(0, 50))}</td>
        <td>${artCell}</td>`;
      tbody.appendChild(tr);
    });
    // Update artifact strip
    const list = document.getElementById("artifact-list");
    list.innerHTML = "";
    (data.artifacts || []).forEach(art => addArtifact(art));
  }).catch(() => {});
}

// ── Pydantic events ────────────────────────────────────────────────────────
function appendPydanticRow(ev) {
  const tbody = document.getElementById("pydantic-tbody");
  const model = ev.input?.model || "?";
  const ok = ev.output?.validated !== false;
  const errors = (ev.output?.errors || []).map(e => e.msg || JSON.stringify(e)).join("; ");
  const tr = document.createElement("tr");
  tr.innerHTML = `<td style="color:var(--accent)">${esc(model)}</td>
    <td class="${ok ? 'tag-ok' : 'tag-err'}">${ok ? "✓" : "✗"}</td>
    <td class="tag-err">${esc(errors.slice(0, 100))}</td>`;
  tbody.insertBefore(tr, tbody.firstChild);
}

// ── Replay ─────────────────────────────────────────────────────────────────
async function loadReplays() {
  try {
    const data = await fetch("/api/runs").then(r => r.json());
    const sel = document.getElementById("replay-select");
    const runs = (data.runs || []).reverse(); // most recent first
    runs.forEach(id => {
      const opt = document.createElement("option");
      opt.value = id; opt.textContent = id;
      sel.appendChild(opt);
    });
    // Auto-select the most recent run so the user can just click Replay
    if (runs.length > 0) sel.value = runs[0];
  } catch (e) { console.warn("loadReplays failed:", e); }
}

document.getElementById("replay-btn").addEventListener("click", async () => {
  const sel = document.getElementById("replay-select");
  const runId = sel.value;
  if (!runId) return;
  try {
    const data = await fetch(`/api/runs/${runId}`).then(r => r.json());
    if (data.error) { alert("Run not found: " + runId); return; }
    const events = data.events || [];

    // Clear display
    Object.keys(iterCards).forEach(k => { iterCards[k] = {}; });
    ["col-memory","col-perception","col-decision","col-action"].forEach(id => {
      document.getElementById(id).innerHTML = "";
    });
    document.getElementById("artifact-list").innerHTML = "";
    document.getElementById("art-count").textContent = "(0)";
    document.getElementById("gateway-tbody").innerHTML = "";
    document.getElementById("pydantic-tbody").innerHTML = "";
    clearLog();
    document.getElementById("run-id").textContent = runId;
    document.getElementById("query-display").textContent = "Replaying…";

    for (const ev of events) {
      await new Promise(r => setTimeout(r, 20));
      try { handleEvent(ev); } catch (err) { console.error("handleEvent error", err, ev); }
    }
    document.getElementById("query-display").textContent =
      events.find(e => e.event === "run_start")?.input?.query || "(replayed)";
  } catch (e) {
    console.error("Replay failed:", e);
    alert("Replay failed: " + e);
  }
});

document.getElementById("clear-btn").addEventListener("click", () => {
  Object.keys(iterCards).forEach(k => { iterCards[k] = {}; });
  ["col-memory","col-perception","col-decision","col-action"].forEach(id => {
    document.getElementById(id).innerHTML = "";
  });
  document.getElementById("artifact-list").innerHTML = "";
  document.getElementById("art-count").textContent = "(0)";
  document.getElementById("gateway-tbody").innerHTML = "";
  document.getElementById("memory-tbody").innerHTML = "";
  document.getElementById("pydantic-tbody").innerHTML = "";
  clearLog();
});

document.getElementById("log-clear-btn").addEventListener("click", clearLog);

// ── Utility ────────────────────────────────────────────────────────────────
function esc(s) {
  if (s == null) return "";
  return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}

// ── Init ───────────────────────────────────────────────────────────────────
connectSSE();
loadReplays();
refreshMemoryState();

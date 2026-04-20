/* ── State ────────────────────────────────────────────── */
const state = {
  selectedRegion: null,
  running: false,
  totalTokens: 0,
  analyzedRegions: {},   // region -> { lat, lng, data }
  geoLayer: null,
  selectedLayer: null,
};

/* ── Log Storage (shared with logs.html via localStorage) ── */
let _logEntries = [];
let _toolLog = [];   // { iter, name, args, result, error, ms }

function _syncLogs() {
  try {
    localStorage.setItem('geointel_logs', JSON.stringify({
      entries: _logEntries,
      running: state.running,
      totalTokens: state.totalTokens,
    }));
  } catch {}
}

function openLogsPage() {
  window.open('/logs.html', 'geointel-logs',
    'width=1100,height=800,menubar=no,toolbar=no,location=no');
}

/* ── Map Init ─────────────────────────────────────────── */
const map = L.map('map', {
  center: [20, 0],
  zoom: 2,
  zoomControl: true,
  attributionControl: false,
});

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 18,
  attribution: '© OpenStreetMap'
}).addTo(map);

// Load world countries GeoJSON
fetch('https://raw.githubusercontent.com/datasets/geo-countries/master/data/countries.geojson')
  .then(r => r.json())
  .then(data => {
    state.geoLayer = L.geoJSON(data, {
      style: defaultStyle,
      onEachFeature(feature, layer) {
        layer.on({
          mouseover: onHover,
          mouseout: onLeave,
          click: onCountryClick,
        });
        layer._regionName = feature.properties.ADMIN || feature.properties.name || 'Unknown';
      }
    }).addTo(map);
  })
  .catch(() => {
    // Fallback: click anywhere on map → reverse geocode
    map.on('click', async (e) => {
      const name = await reverseGeocode(e.latlng.lat, e.latlng.lng);
      if (name) startAnalysis(name, e.latlng.lat, e.latlng.lng);
    });
  });

function defaultStyle() {
  return { fillColor: '#0d1f35', weight: 0.8, color: '#1e3a5f', fillOpacity: 0.9 };
}
function hoverStyle() {
  return { fillColor: '#1a3a5c', weight: 1.2, color: '#2a5aaf', fillOpacity: 1 };
}
function selectedStyle() {
  return { fillColor: '#0e3460', weight: 2, color: '#00d4ff', fillOpacity: 1 };
}

function onHover(e) {
  if (e.target !== state.selectedLayer) e.target.setStyle(hoverStyle());
  const name = e.target._regionName;
  document.getElementById('map-hint').textContent = `Click to analyze: ${name}`;
}
function onLeave(e) {
  if (e.target !== state.selectedLayer) e.target.setStyle(defaultStyle());
  document.getElementById('map-hint').textContent = 'Click any country or region to begin analysis';
}
function onCountryClick(e) {
  L.DomEvent.stopPropagation(e);
  if (state.running) return;
  const layer = e.target;
  const name = layer._regionName;
  const center = layer.getBounds().getCenter();

  // Reset previous selection
  if (state.selectedLayer && state.selectedLayer !== layer) {
    state.selectedLayer.setStyle(defaultStyle());
  }
  state.selectedLayer = layer;
  layer.setStyle(selectedStyle());

  startAnalysis(name, center.lat, center.lng);
}

async function reverseGeocode(lat, lng) {
  try {
    const r = await fetch(`https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lng}&format=json`);
    const d = await r.json();
    return d.address?.country || d.display_name?.split(',').pop()?.trim() || null;
  } catch { return null; }
}

/* ── Start Analysis ───────────────────────────────────── */
function startAnalysis(region, lat, lng) {
  if (state.running) return;

  state.selectedRegion = region;
  state.running = true;

  // UI reset
  setStatus('running');
  setEl('region-name', region);
  setEl('analysis-status', 'Analyzing…');
  setEl('trend-direction', '—');
  setEl('trend-confidence', '—');
  const trendCard = document.getElementById('card-trend');
  if (trendCard) trendCard.style.borderColor = '';
  document.getElementById('map-hint').classList.add('hidden');

  document.getElementById('report-panel').style.display = 'none';
  document.getElementById('report-content').innerHTML = '';
  document.getElementById('news-list').innerHTML = '<li class="placeholder">Loading…</li>';

  // Reset video card
  const iframe = document.getElementById('live-iframe');
  const placeholder = document.getElementById('video-placeholder');
  const label = document.getElementById('video-region-label');
  const badge = document.getElementById('video-live-badge');
  if (iframe) { iframe.src = ''; iframe.style.display = 'none'; }
  if (placeholder) placeholder.style.display = 'flex';
  if (label) label.textContent = 'Loading news video…';
  if (badge) badge.style.display = 'none';

  _toolLog = [];
  clearLog();
  appendLog('start', null, `Starting analysis for: <span class="log-highlight">${region}</span>`);

  startSSE(region, lat, lng);
}

/* ── SSE Client ───────────────────────────────────────── */
function startSSE(region, lat, lng) {
  fetch('/api/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ region }),
  }).then(async (response) => {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop();
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const event = JSON.parse(line.slice(6));
            handleEvent(event, region, lat, lng);
          } catch {}
        }
      }
    }
  }).catch(err => {
    appendLog('error', null, `Connection error: ${err.message}`);
    setStatus('error');
    state.running = false;
  });
}

/* ── Event Handler ────────────────────────────────────── */
function handleEvent(ev, region, lat, lng) {
  switch (ev.type) {

    case 'agent_start':
      appendLog('start', null, ev.message || 'Agent started');
      break;

    case 'token_update':
      state.totalTokens = ev.total_tokens;
      _syncLogs();
      setEl('token-display', ev.total_tokens.toLocaleString());
      setEl('token-call-display', ev.call_tokens?.toLocaleString() || '0');
      appendLog('tokens', ev.iteration,
        `Tokens this call: <span class="log-highlight">${ev.call_tokens}</span>  |  Total: <span class="log-highlight">${ev.total_tokens}</span>`
      );
      break;

    case 'llm_response': {
      const calls = ev.raw?.function_calls || [];
      const text = ev.raw?.text;
      let body = `Finish: ${ev.raw?.finish_reason || '?'}`;
      if (calls.length) body += `\nFunction calls: ${calls.map(c => c.name).join(', ')}`;
      if (text) body += `\n\n${text.substring(0, 200)}${text.length > 200 ? '…' : ''}`;
      appendLog('llm', ev.iteration, body);
      break;
    }

    case 'tool_call':
      appendLog('tool-call', ev.iteration,
        `<span class="log-highlight">${ev.function}</span>(<span class="log-body json">${JSON.stringify(ev.args)}</span>)`
      );
      _toolLog.push({ iter: ev.iteration, name: ev.function, args: ev.args, result: null, error: null, ms: null });
      break;

    case 'tool_result': {
      const d = ev.data || {};
      let lines = [
        `<span class="log-body url">URL: ${ev.url || '?'}</span>`,
        `<span class="log-body time">Method: ${ev.method || 'GET'}  |  Time: ${ev.response_time_ms}ms</span>`,
      ];
      if (ev.error) lines.push(`Error: ${ev.error}`);

      appendLog('tool-result', ev.iteration,
        `<span class="log-highlight">${ev.function}</span> → ${lines.join('  |  ')}`
      );

      // Merge result into _toolLog entry
      const tlEntry = [..._toolLog].reverse().find(t => t.name === ev.function);
      if (tlEntry) {
        tlEntry.result = ev.data || {};
        tlEntry.error = ev.error || null;
        tlEntry.ms = ev.response_time_ms;
      }

      // Update UI panels from tool results
      if (ev.function === 'get_fear_greed_index' && d.data?.[0]) {
        updateFNG(d.data[0]);
      }
      if (ev.function === 'get_geopolitical_news' && d.articles) {
        updateNews(d.articles);
      }
      if (ev.function === 'get_oil_prices' && d.price_usd) {
        updateOil(d);
      }
      if (ev.function === 'get_youtube_videos' && d.videos) {
        updateYT(d.videos);
      }
      if (ev.function === 'predict_oil_trend' && d.analysis) {
        updateOilTrend(d);
      }
      break;
    }

    case 'final_answer':
      appendLog('final', ev.iteration, 'Agent produced final intelligence report');
      showReport(ev.content);
      setEl('analysis-status', 'Complete ✓');
      addMapPin(region, lat, lng);
      state.analyzedRegions[region] = { lat, lng, content: ev.content };
      break;

    case 'session_summary': {
      const s = ev;
      appendLog('summary', null,
        `Session complete — Iterations: ${s.total_iterations}  |  API calls: ${s.total_api_calls}  |  ` +
        `Total tokens: ${s.total_tokens}  |  Time: ${(s.total_time_ms/1000).toFixed(1)}s\n` +
        `URLs visited:\n${(s.all_urls || []).map(u => '  • ' + u).join('\n')}`
      );
      appendToolTable(_toolLog);
      sendLogsToTelegram(region);
      setStatus('done');
      state.running = false;
      document.getElementById('map-hint').classList.remove('hidden');
      document.getElementById('map-hint').textContent = 'Click any country or region to begin analysis';
      break;
    }

    case 'error':
      appendLog('error', null, ev.message);
      setStatus('error');
      setEl('analysis-status', 'Error');
      state.running = false;
      break;

    case 'stream_end':
      if (state.running) {
        setStatus('done');
        state.running = false;
      }
      break;
  }
}

/* ── UI Updaters ──────────────────────────────────────── */
function updateFNG(data) {
  const val = parseInt(data.value, 10);
  setEl('fng-value', val);
  setEl('fng-label', data.value_classification || '');

  const card = document.getElementById('card-fng');
  const sub = document.getElementById('fng-label');
  if (val >= 60) { card.style.borderColor = 'var(--green)'; sub.className = 'live-card-sub up'; }
  else if (val <= 40) { card.style.borderColor = 'var(--red)'; sub.className = 'live-card-sub down'; }
  else { sub.className = 'live-card-sub neutral'; }
}

function updateOil(d) {
  setEl('oil-price', `$${d.price_usd}`);
  const pct = d.change_pct;
  const sign = pct >= 0 ? '+' : '';
  const sub = document.getElementById('oil-change');
  sub.textContent = `${sign}${pct}%`;
  sub.className = `live-card-sub ${pct >= 0 ? 'up' : 'down'}`;
  document.getElementById('card-oil').style.borderColor = pct >= 0 ? 'var(--green)' : 'var(--red)';
}

function updateOilTrend(d) {
  const text = d.analysis || '';
  const dirMatch = text.match(/TREND DIRECTION[^:]*:\s*\**\s*(BULLISH|BEARISH|NEUTRAL)/i);
  const confMatch = text.match(/CONFIDENCE[^:]*:\s*\**\s*(HIGH|MEDIUM|LOW)/i);
  const rangeMatch = text.match(/48.HOUR PRICE RANGE[^:]*:\s*\**\s*(\$[\d.,]+ ?[-–] ?\$[\d.,]+)/i);

  const dir = dirMatch ? dirMatch[1].toUpperCase() : '—';
  const conf = confMatch ? confMatch[1] : '';
  const range = rangeMatch ? rangeMatch[1] : '';

  setEl('trend-direction', dir);
  const sub = document.getElementById('trend-confidence');
  sub.textContent = [conf, range].filter(Boolean).join('  ');

  const card = document.getElementById('card-trend');
  if (dir === 'BULLISH') {
    card.style.borderColor = 'var(--green)';
    sub.className = 'live-card-sub up';
  } else if (dir === 'BEARISH') {
    card.style.borderColor = 'var(--red)';
    sub.className = 'live-card-sub down';
  } else {
    card.style.borderColor = '';
    sub.className = 'live-card-sub neutral';
  }
}

function updateNews(articles) {
  const ul = document.getElementById('news-list');
  if (!articles.length) {
    ul.innerHTML = '<li class="placeholder">No headlines found.</li>';
    return;
  }
  ul.innerHTML = articles.slice(0, 8).map(a => `
    <li>
      <a href="${a.link}" target="_blank" rel="noopener">${a.title}</a>
      ${a.published ? `<div class="news-date">${a.published.substring(0, 22)}</div>` : ''}
    </li>
  `).join('');
}

function updateYT(videos) {
  if (!videos.length) return;
  const first = videos[0];
  const iframe = document.getElementById('live-iframe');
  const placeholder = document.getElementById('video-placeholder');
  const label = document.getElementById('video-region-label');
  const badge = document.getElementById('video-live-badge');
  if (iframe && first.embed_url) {
    let src = first.embed_url;
    if (!src.includes('autoplay')) src += (src.includes('?') ? '&' : '?') + 'autoplay=1&mute=1';
    iframe.src = src;
    iframe.style.display = 'block';
    if (placeholder) placeholder.style.display = 'none';
    if (label) label.textContent = first.title ? first.title.substring(0, 50) + (first.title.length > 50 ? '…' : '') : state.selectedRegion;
    if (badge) badge.style.display = 'inline';
  }
}

function showReport(markdown) {
  const panel = document.getElementById('report-panel');
  const content = document.getElementById('report-content');
  panel.style.display = 'flex';
  content.innerHTML = marked.parse(markdown || '');
  panel.scrollIntoView({ behavior: 'smooth' });
}

/* ── Map Pins ─────────────────────────────────────────── */
function addMapPin(region, lat, lng) {
  if (!lat || !lng) return;
  const icon = L.divIcon({
    html: `<div class="region-pin" title="${region}" onclick="showPinPopup('${region.replace(/'/g, "\\'")}')">${region.charAt(0)}</div>`,
    className: '',
    iconSize: [28, 28],
    iconAnchor: [14, 14],
  });
  L.marker([lat, lng], { icon }).addTo(map);
}

function showPinPopup(region) {
  const data = state.analyzedRegions[region];
  if (data?.content) showReport(data.content);
}

/* ── Tool Summary Table ───────────────────────────────── */
const TOOL_REASONING = {
  get_geopolitical_news:  'Gather latest regional news headlines to understand active conflicts, political shifts, and economic events driving geopolitical risk.',
  get_fear_greed_index:   'Measure global market sentiment to determine whether investors are panic-selling (fear) or over-buying (greed), which amplifies or dampens oil price moves.',
  get_oil_prices:         'Fetch the current WTI crude benchmark price and prior-close to establish the exact price level and recent momentum before making a trend prediction.',
  predict_oil_trend:      'Synthesise news, sentiment, and price data through an LLM to produce a structured 48-hour directional forecast with confidence level and risk factors.',
  get_youtube_videos:     'Surface the most recent video coverage for the region so the analyst can quickly watch primary-source reporting that may not yet appear in text feeds.',
};

function _summariseResult(name, result, error) {
  if (error) return `<span style="color:var(--red)">Error: ${error}</span>`;
  if (!result) return '—';
  switch (name) {
    case 'get_geopolitical_news':
      return `${result.count ?? 0} articles fetched for <em>${result.region || ''}</em>`;
    case 'get_fear_greed_index': {
      const d = result.data?.[0] || {};
      return d.value ? `Score ${d.value} — <em>${d.value_classification}</em>` : 'Data received';
    }
    case 'get_oil_prices':
      return result.price_usd
        ? `WTI $${result.price_usd} (${result.change_pct >= 0 ? '+' : ''}${result.change_pct}%)`
        : 'Price data received';
    case 'predict_oil_trend': {
      const a = (result.analysis || '').substring(0, 120);
      return a ? a + (result.analysis.length > 120 ? '…' : '') : 'Analysis generated';
    }
    case 'get_youtube_videos':
      return result.videos?.length
        ? `${result.videos.length} video(s) — "${result.videos[0].title?.substring(0, 60)}…"`
        : 'No videos returned';
    default:
      return JSON.stringify(result).substring(0, 100);
  }
}

function appendToolTable(toolLog) {
  if (!toolLog.length) return;
  const log = document.getElementById('agent-log');

  const rows = toolLog.map((t, i) => {
    const argsStr = Object.keys(t.args || {}).length
      ? Object.entries(t.args).map(([k, v]) => `<span style="color:var(--text-dim)">${k}=</span><em>${String(v).substring(0, 40)}</em>`).join(', ')
      : '<span style="color:var(--text-dim)">no args</span>';
    const summary = _summariseResult(t.name, t.result, t.error);
    const reasoning = TOOL_REASONING[t.name] || '—';
    const ms = t.ms != null ? `<span style="color:var(--text-dim);font-size:0.68rem">${t.ms}ms</span>` : '';
    return `<tr>
      <td><span class="log-tag tool-call" style="display:inline-block;margin-bottom:3px">${t.name}</span><br>${argsStr} ${ms}</td>
      <td>${summary}</td>
      <td style="color:var(--text-dim);font-size:0.78rem">${reasoning}</td>
    </tr>`;
  }).join('');

  const wrap = document.createElement('div');
  wrap.className = 'log-entry';
  wrap.innerHTML = `
    <span class="log-tag summary">tool table</span>
    <div class="log-body" style="overflow-x:auto;margin-top:6px">
      <table class="tool-summary-table">
        <thead><tr><th>Tool Called</th><th>What It Did</th><th>Reasoning</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
  log.appendChild(wrap);
  log.scrollTop = log.scrollHeight;
}

/* ── Log Helpers ──────────────────────────────────────── */
function appendLog(type, iteration, html) {
  const log = document.getElementById('agent-log');
  const placeholder = log.querySelector('.log-placeholder');
  if (placeholder) placeholder.remove();

  const entry = document.createElement('div');
  entry.className = 'log-entry';

  const tag = `<span class="log-tag ${type}">${type.replace('-', ' ')}</span>`;
  const iter = iteration ? `<span class="log-iter">[iter ${iteration}]</span>` : '';
  entry.innerHTML = `${tag}${iter}<div class="log-body">${html}</div>`;
  log.appendChild(entry);
  log.scrollTop = log.scrollHeight;

  // Sync to localStorage for logs.html
  _logEntries.push({ type, iteration, html, ts: Date.now(), region: state.selectedRegion });
  _syncLogs();
}

function clearLog() {
  document.getElementById('agent-log').innerHTML = '<div class="log-placeholder">Agent reasoning will stream here in real time…</div>';
  _logEntries = [];
  _syncLogs();
}

/* ── API Limits ───────────────────────────────────────── */
async function fetchLimits() {
  try {
    const r = await fetch('/api/limits');
    const d = await r.json();

    // YouTube
    const yt = d.youtube;
    setEl('yt-limit-detail', `YT: ${yt.searches_today}/${yt.limit_day}`);
    setEl('yt-limit-pct', `${yt.pct}%`);
    setEl('yt-units', yt.units_used.toLocaleString());
    const ytBar = document.getElementById('yt-limit-bar');
    ytBar.style.width = `${Math.min(yt.pct, 100)}%`;
    ytBar.className = `limit-bar${yt.pct >= 90 ? ' crit' : yt.pct >= 70 ? ' warn' : ''}`;

    // Gemini
    const gem = d.gemini;
    setEl('gem-limit-detail', `Gem: ${gem.requests_today}/${gem.limit_day}`);
    setEl('gem-limit-pct', `${gem.pct}%`);
    setEl('gem-tokens-today', gem.tokens_today.toLocaleString());
    setEl('gem-tokens-session', gem.tokens_session.toLocaleString());
    const gemBar = document.getElementById('gem-limit-bar');
    gemBar.style.width = `${Math.min(gem.pct, 100)}%`;
    gemBar.className = `limit-bar${gem.pct >= 90 ? ' crit' : gem.pct >= 70 ? ' warn' : ''}`;

    // Telegram
    const tg = d.telegram;
    setEl('tg-limit-detail', `TG: ${tg.messages_today} today • ${tg.messages_session} session`);
    setEl('tg-limit-pct', `${tg.messages_today}`);
    document.getElementById('tg-limit-bar').style.width = `${Math.min(tg.messages_today, 100)}%`;

  } catch {}
}

// Poll limits every 10 seconds
fetchLimits();
setInterval(fetchLimits, 10000);



/* ── Send Logs to Telegram ────────────────────────────────── */
async function sendLogsToTelegram(region) {
  try {
    // Build plain-text log from _logEntries
    const lines = _logEntries.map(e => {
      const t = new Date(e.ts).toTimeString().substring(0, 8);
      const iter = e.iteration ? `[iter ${e.iteration}] ` : '';
      const plain = (e.html || '').replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim();
      return `[${t}] [${(e.type || '').toUpperCase()}] ${iter}${plain}`;
    });

    // Append tool summary table as plain text
    if (_toolLog.length) {
      lines.push('');
      lines.push('=== TOOL SUMMARY ===');
      lines.push(['Tool', 'What It Did', 'Reasoning'].join(' | '));
      lines.push('-'.repeat(90));
      _toolLog.forEach(t => {
        const argsStr = Object.entries(t.args || {}).map(([k,v]) => `${k}=${v}`).join(', ') || 'no args';
        const summary = (t.error ? `Error: ${t.error}` : JSON.stringify(t.result || {}).substring(0, 80)).replace(/"/g, '');
        const reasoning = (TOOL_REASONING[t.name] || '').substring(0, 80);
        lines.push(`${t.name}(${argsStr}) | ${summary} | ${reasoning}`);
      });
    }

    const log_text = lines.join('\n');
    const resp = await fetch('/api/send-logs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ region, log_text }),
    });
    const d = await resp.json();
    if (d.ok) {
      appendLog('summary', null, `Log file <span class="log-highlight">${d.filename}</span> sent to Telegram`);
    } else {
      appendLog('summary', null, `Telegram log send skipped: ${d.error}`);
    }
  } catch (e) {
    appendLog('summary', null, `Telegram log send failed: ${e.message}`);
  }
}

/* ── Server Logs ──────────────────────────────────────────── */
let _lastLogTs = 0;

async function fetchServerLogs() {
  try {
    const r = await fetch(`/api/server-logs?since=${_lastLogTs}`);
    const lines = await r.json();
    if (!lines.length) return;
    const box = document.getElementById('server-log-box');
    lines.forEach(l => {
      _lastLogTs = Math.max(_lastLogTs, l.ts);
      const div = document.createElement('div');
      div.className = `slog-line slog-${l.level.toLowerCase()}`;
      const t = new Date(l.ts).toTimeString().substring(0, 8);
      div.textContent = `[${t}] ${l.msg}`;
      box.appendChild(div);
    });
    box.scrollTop = box.scrollHeight;
  } catch {}
}

fetchServerLogs();
setInterval(fetchServerLogs, 2000);

/* ── Status ───────────────────────────────────────────── */
function setStatus(s) {
  const dot = document.getElementById('status-dot');
  dot.className = `status-dot ${s}`;
  dot.title = { running: 'Analyzing…', done: 'Complete', error: 'Error', idle: 'Idle' }[s] || s;
}

function setEl(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

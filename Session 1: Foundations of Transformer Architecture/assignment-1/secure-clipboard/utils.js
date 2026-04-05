// ─── Crypto ──────────────────────────────────────────────────────────────────

async function hashString(str) {
  const data = new TextEncoder().encode(str);
  const buf  = await crypto.subtle.digest('SHA-256', data);
  return Array.from(new Uint8Array(buf)).map(b => b.toString(16).padStart(2, '0')).join('');
}

// ─── ID / Time ────────────────────────────────────────────────────────────────

function generateId() {
  return `${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

function formatTimestamp(ts) {
  const diff = Date.now() - ts;
  if (diff < 60_000)        return 'Just now';
  if (diff < 3_600_000)     return `${Math.floor(diff / 60_000)}m ago`;
  if (diff < 86_400_000)    return `${Math.floor(diff / 3_600_000)}h ago`;
  if (diff < 604_800_000)   return `${Math.floor(diff / 86_400_000)}d ago`;
  return new Date(ts).toLocaleDateString();
}

function getTimeFilterMs(filter) {
  const day = 86_400_000;
  const map = { '24h': day, '2d': 2*day, '7d': 7*day, '30d': 30*day, '1y': 365*day };
  return map[filter] ? Date.now() - map[filter] : 0;
}

// ─── Filtering ────────────────────────────────────────────────────────────────

function filterItems(items, { search = '', timeFilter = 'all' } = {}) {
  let out = [...items];

  if (timeFilter !== 'all') {
    const minTs = getTimeFilterMs(timeFilter);
    out = out.filter(i => i.pinned || i.timestamp >= minTs);
  }

  if (search.trim()) {
    const q = search.trim().toLowerCase();
    out = out.filter(i => (i.type === 'text' || i.type === 'note') && i.content.toLowerCase().includes(q));
  }

  out.sort((a, b) => {
    if (a.pinned !== b.pinned) return a.pinned ? -1 : 1;
    return b.timestamp - a.timestamp;
  });

  return out;
}

function truncate(text, max = 120) {
  return text.length <= max ? text : text.slice(0, max) + '…';
}

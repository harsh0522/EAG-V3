const MAX_ITEMS = 500;

// ─── Sequential write queue (prevents race condition) ─────────────────────────
// Without this, concurrent saveEntry calls both read the old array and overwrite each other.
let writeQueue = Promise.resolve();

function saveEntry(content, type = 'text') {
  writeQueue = writeQueue.then(() => _doSave(content, type)).catch(() => {});
}

async function _doSave(content, type) {
  if (!content) return;
  if (type === 'text' && !content.trim()) return;

  const { clipboardItems = [] } = await chrome.storage.local.get('clipboardItems');

  // Skip if identical to the most recent entry
  if (clipboardItems[0]?.content === content) return;

  const entry = {
    id:        `${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
    content,
    type,
    timestamp: Date.now(),
    pinned:    false
  };

  const updated = [entry, ...clipboardItems].slice(0, MAX_ITEMS);
  await chrome.storage.local.set({ clipboardItems: updated });
}

// ─── Offscreen document ───────────────────────────────────────────────────────

async function ensureOffscreen() {
  try {
    if (await chrome.offscreen.hasDocument()) return true;
    await chrome.offscreen.createDocument({
      url:           'offscreen.html',
      reasons:       ['CLIPBOARD'],
      justification: 'Reading clipboard to detect changes for secure storage'
    });
    return true;
  } catch (_) {
    return false;
  }
}

// ─── Messages ─────────────────────────────────────────────────────────────────

chrome.runtime.onMessage.addListener(msg => {
  if (msg.type === 'NEW_CLIPBOARD' || msg.type === 'CLIPBOARD_RESULT') {
    saveEntry(msg.content, msg.contentType || 'text');
  }
});

// ─── Polling alarm ────────────────────────────────────────────────────────────

chrome.alarms.create('poll', { periodInMinutes: 0.05 });

chrome.alarms.onAlarm.addListener(async alarm => {
  if (alarm.name !== 'poll') return;
  const ok = await ensureOffscreen();
  if (ok) chrome.runtime.sendMessage({ type: 'DO_READ' }).catch(() => {});
});

// ─── Init ─────────────────────────────────────────────────────────────────────

chrome.runtime.onInstalled.addListener(async () => {
  const { clipboardItems } = await chrome.storage.local.get('clipboardItems');
  if (!clipboardItems) await chrome.storage.local.set({ clipboardItems: [] });
  ensureOffscreen();
});

ensureOffscreen();

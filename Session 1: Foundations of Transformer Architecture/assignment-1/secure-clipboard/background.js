// ─── background.js (Service Worker) ──────────────────────────────────────────
// Manages clipboard polling, offscreen document lifecycle, and storage helpers.
// ─────────────────────────────────────────────────────────────────────────────

'use strict';

const OFFSCREEN_URL = chrome.runtime.getURL('offscreen.html');
const POLL_ALARM    = 'clipboard-poll';
const POLL_PERIOD   = 0.5; // minutes — minimum Chrome allows is ~0.5

// ── Offscreen document lifecycle ─────────────────────────────────────────────

let offscreenCreating = false;

async function ensureOffscreen() {
  const existing = await chrome.offscreen.hasDocument?.().catch(() => false);
  if (existing) return;
  if (offscreenCreating) return;
  offscreenCreating = true;
  try {
    await chrome.offscreen.createDocument({
      url: OFFSCREEN_URL,
      reasons: ['CLIPBOARD'],
      justification: 'Read clipboard contents for clipboard history'
    });
  } finally {
    offscreenCreating = false;
  }
}

// ── Alarm setup ───────────────────────────────────────────────────────────────

chrome.runtime.onInstalled.addListener(() => {
  chrome.alarms.create(POLL_ALARM, { periodInMinutes: POLL_PERIOD });
});

chrome.alarms.onAlarm.addListener(alarm => {
  if (alarm.name === POLL_ALARM) pollClipboard();
});

// ── Clipboard poll ────────────────────────────────────────────────────────────

async function pollClipboard() {
  // Only poll when a user session is active (logged in)
  const { session } = await chrome.storage.local.get('session');
  if (!session || !session.loggedIn) return;

  await ensureOffscreen();
  chrome.runtime.sendMessage({ type: 'READ_CLIPBOARD' }).catch(() => {
    // Offscreen not yet ready — will retry on next alarm tick
  });
}

// ── Message handler ───────────────────────────────────────────────────────────

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.type === 'CLIPBOARD_DATA') {
    handleClipboardData(msg.payload).then(() => sendResponse({ ok: true }));
    return true; // keep channel open for async response
  }
  if (msg.type === 'SAVE_ITEM') {
    saveItem(msg.item).then(() => sendResponse({ ok: true }));
    return true;
  }
  if (msg.type === 'DELETE_ITEM') {
    deleteItem(msg.id).then(() => sendResponse({ ok: true }));
    return true;
  }
});

// ── Data handlers ─────────────────────────────────────────────────────────────

async function handleClipboardData({ type, content }) {
  if (!content) return;

  const { clipboardItems = [], lastContent = '' } = await chrome.storage.local.get([
    'clipboardItems',
    'lastContent'
  ]);

  // De-duplicate: skip if identical to previous clipboard content
  if (type === 'text' && content === lastContent) return;

  const newItem = {
    id:        Date.now().toString(36) + Math.random().toString(36).slice(2, 6),
    type,
    content,
    timestamp: Date.now(),
    pinned:    false,
    locked:    false
  };

  const updated = [newItem, ...clipboardItems].slice(0, 500); // cap at 500 items
  await chrome.storage.local.set({
    clipboardItems: updated,
    lastContent:    type === 'text' ? content : lastContent
  });
}

async function saveItem(item) {
  const { clipboardItems = [] } = await chrome.storage.local.get('clipboardItems');
  const existing = clipboardItems.findIndex(i => i.id === item.id);
  let updated;
  if (existing >= 0) {
    updated = clipboardItems.map(i => i.id === item.id ? item : i);
  } else {
    updated = [item, ...clipboardItems];
  }
  await chrome.storage.local.set({ clipboardItems: updated });
}

async function deleteItem(id) {
  const { clipboardItems = [] } = await chrome.storage.local.get('clipboardItems');
  const updated = clipboardItems.filter(i => i.id !== id);
  await chrome.storage.local.set({ clipboardItems: updated });
}

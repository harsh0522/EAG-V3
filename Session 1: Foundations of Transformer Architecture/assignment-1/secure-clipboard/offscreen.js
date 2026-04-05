// ─── offscreen.js ────────────────────────────────────────────────────────────
// Runs inside offscreen.html. Reads the system clipboard (text + images) and
// forwards the data to the background service worker.
// ─────────────────────────────────────────────────────────────────────────────

'use strict';

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.type === 'READ_CLIPBOARD') {
    readClipboard().then(() => sendResponse({ ok: true })).catch(console.warn);
    return true;
  }
});

async function readClipboard() {
  try {
    const items = await navigator.clipboard.read();
    for (const item of items) {
      // ── Image ──
      if (item.types.includes('image/png') || item.types.includes('image/jpeg')) {
        const mimeType = item.types.find(t => t.startsWith('image/'));
        const blob = await item.getType(mimeType);
        const dataUrl = await blobToDataUrl(blob);
        chrome.runtime.sendMessage({
          type: 'CLIPBOARD_DATA',
          payload: { type: 'image', content: dataUrl }
        });
        return; // only handle one item per poll
      }
      // ── Text ──
      if (item.types.includes('text/plain')) {
        const blob = await item.getType('text/plain');
        const text = await blob.text();
        if (text.trim()) {
          chrome.runtime.sendMessage({
            type: 'CLIPBOARD_DATA',
            payload: { type: 'text', content: text }
          });
        }
        return;
      }
    }
  } catch {
    // Clipboard permission not granted or no content — ignore silently
  }
}

function blobToDataUrl(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload  = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}

// ─── content.js ──────────────────────────────────────────────────────────────
// Injected into all pages. Listens for copy/cut events and forwards the
// captured text to the background service worker via chrome.runtime.sendMessage.
// ─────────────────────────────────────────────────────────────────────────────

'use strict';

document.addEventListener('copy',  handleCopy);
document.addEventListener('cut',   handleCopy);

function handleCopy(e) {
  // Use the DataTransfer object when available (most reliable)
  const dt = e.clipboardData;
  if (!dt) return;

  const text = dt.getData('text/plain');
  if (text && text.trim()) {
    chrome.runtime.sendMessage({
      type: 'CLIPBOARD_DATA',
      payload: { type: 'text', content: text }
    }).catch(() => {
      // Extension context may be invalidated after extension update — safe to ignore
    });
  }
}

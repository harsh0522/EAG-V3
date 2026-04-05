// Read clipboard data (text + images) and send to background
async function captureClipboard() {
  try {
    // Use clipboard.read() so we get images too
    const items = await navigator.clipboard.read();
    for (const item of items) {
      // Image types take priority
      const imageType = item.types.find(t => t.startsWith('image/'));
      if (imageType) {
        const blob   = await item.getType(imageType);
        const reader = new FileReader();
        reader.onloadend = () => {
          chrome.runtime.sendMessage({
            type: 'NEW_CLIPBOARD',
            content: reader.result,   // data URL
            contentType: 'image'
          }).catch(() => {});
        };
        reader.readAsDataURL(blob);
        return;
      }
      // Plain text
      if (item.types.includes('text/plain')) {
        const blob = await item.getType('text/plain');
        const text = await blob.text();
        if (text.trim()) {
          chrome.runtime.sendMessage({ type: 'NEW_CLIPBOARD', content: text, contentType: 'text' }).catch(() => {});
        }
        return;
      }
    }
  } catch (_) {
    // Fallback: readText (no image support, but works when read() is blocked)
    try {
      const text = await navigator.clipboard.readText();
      if (text.trim()) {
        chrome.runtime.sendMessage({ type: 'NEW_CLIPBOARD', content: text, contentType: 'text' }).catch(() => {});
      }
    } catch (_2) {}
  }
}

// Use clipboardData from the event itself for text — no setTimeout, no gesture issue.
// For images we still need the async API (copy event clipboardData rarely has images).
document.addEventListener('copy', e => {
  const text = e.clipboardData?.getData('text/plain');
  if (text?.trim()) {
    chrome.runtime.sendMessage({ type: 'NEW_CLIPBOARD', content: text, contentType: 'text' }).catch(() => {});
  } else {
    // Might be an image — try async read (gesture is still valid immediately)
    captureClipboard();
  }
});

document.addEventListener('cut', e => {
  const text = e.clipboardData?.getData('text/plain');
  if (text?.trim()) {
    chrome.runtime.sendMessage({ type: 'NEW_CLIPBOARD', content: text, contentType: 'text' }).catch(() => {});
  }
});

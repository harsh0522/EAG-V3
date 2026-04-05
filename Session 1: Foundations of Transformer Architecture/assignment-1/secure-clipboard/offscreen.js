// Read clipboard including images and send result to background
async function readAndSend() {
  try {
    const items = await navigator.clipboard.read();
    for (const item of items) {
      const imageType = item.types.find(t => t.startsWith('image/'));
      if (imageType) {
        const blob   = await item.getType(imageType);
        const reader = new FileReader();
        reader.onloadend = () => {
          chrome.runtime.sendMessage({ type: 'CLIPBOARD_RESULT', content: reader.result, contentType: 'image' }).catch(() => {});
        };
        reader.readAsDataURL(blob);
        return;
      }
      if (item.types.includes('text/plain')) {
        const blob = await item.getType('text/plain');
        const text = await blob.text();
        if (text.trim()) {
          chrome.runtime.sendMessage({ type: 'CLIPBOARD_RESULT', content: text, contentType: 'text' }).catch(() => {});
        }
        return;
      }
    }
  } catch (_) {
    // Fallback: readText
    try {
      const text = await navigator.clipboard.readText();
      if (text.trim()) {
        chrome.runtime.sendMessage({ type: 'CLIPBOARD_RESULT', content: text, contentType: 'text' }).catch(() => {});
      }
    } catch (_2) {}
  }
}

chrome.runtime.onMessage.addListener(msg => {
  if (msg.type === 'DO_READ') readAndSend();
});

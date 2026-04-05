# Secure Clipboard Vault

**Version:** 1.1.0  
**Type:** Chrome Extension (Manifest V3)  
**Platform:** macOS / Windows / Linux (Chrome 109+)

---

## What is this?

A privacy-first, fully local clipboard manager built as a Chrome Extension. All data stays on your device — no backend, no external APIs, no cloud sync.

---

## Features

### v1.0.0
- **Clipboard capture** — automatically saves everything you copy (text + images)
- **Authentication** — username + password (SHA-256 hashed), with security question for password reset
- **Session management** — auto-locks when browser restarts
- **Search** — real-time case-insensitive search across all items
- **Time filter** — filter by last 24h, 2 days, 7 days, 30 days, 1 year, or all time
- **Pin / Copy / Delete** — per-card actions
- **Dark mode** — persisted preference
- **Paste zone** — right-click → Paste or ⌘V/Ctrl+V to capture screenshots and images
- **Note cards** — manually add notes with "+ New note"
- **Resizable window** — open in standalone window (⤢ button)
- **Keyboard shortcut** — ⌘⇧V (Mac) / Ctrl+Shift+V (Windows)

### v1.1.0
- **Secure cards (PIN lock)** — lock any card with a 4-digit PIN; content is AES-256-GCM encrypted at rest
- **Tab directory** — navigate by category: Recent (7 days), Images, Texts, Passwords, Favourites
- **Inline autosave** — double-click a note card to edit; changes save automatically after 800ms
- **Extension icon** — custom clipboard+lock icon in all required sizes

---

## File Structure

```
secure-clipboard/
├── manifest.json       # Extension config (MV3)
├── background.js       # Service worker — storage management, clipboard polling
├── content.js          # Injected in all pages — captures copy/cut events
├── offscreen.html      # Offscreen document host
├── offscreen.js        # Clipboard reader (text + images via Clipboard API)
├── popup.html          # Full extension UI (auth + dashboard)
├── popup.js            # Auth, dashboard, tabs, lock, note composer
├── popup.css           # Light + dark theme, all component styles
├── utils.js            # SHA-256, AES-GCM, filtering, formatting helpers
└── icons/
    ├── generate.html   # Open in Chrome to generate PNG icons
    ├── icon16.png      # Generated icon — 16×16
    ├── icon32.png      # Generated icon — 32×32
    ├── icon48.png      # Generated icon — 48×48
    └── icon128.png     # Generated icon — 128×128
```

---

## Installation

1. Clone / download this folder
2. Open **`icons/generate.html`** in Chrome → 4 PNG icons are auto-downloaded → move them to the `icons/` folder
3. Go to `chrome://extensions`
4. Enable **Developer Mode** (top-right toggle)
5. Click **Load unpacked** → select the `secure-clipboard/` folder
6. Click the extension icon in the toolbar → create your account

---

## Usage

### First run
1. Open the extension → you'll see the **Create Account** screen
2. Set username, password, security question & answer

### Capturing clipboard
- **Copy anything** (text, images) → it's automatically saved as a card
- **Screenshots** → press ⌘⌃⇧4 (Mac) to copy to clipboard → open extension → ⌘V in the paste zone

### Tabs
| Tab | Shows |
|-----|-------|
| 🕐 Recent | Last 7 days |
| 🖼 Images | Image/screenshot cards |
| 📝 Texts | Text + note cards |
| 🔐 Passwords | PIN-locked cards |
| ⭐ Favs | Pinned cards |

### Locking a card
1. Click **🔒 Lock** on any card
2. Enter a 4-digit PIN → content is AES-256-GCM encrypted
3. Card moves to the **Passwords** tab
4. Click **🔓 Unlock** → enter PIN → content revealed temporarily (never stored decrypted)

### Editing notes
- Double-click the text of a **note** card → edit inline
- Changes auto-save after 800ms (no button needed)
- Press **Escape** to cancel

---

## Security Model

| Layer | Method |
|-------|--------|
| Vault login | SHA-256 password hash |
| Security Q&A | SHA-256 answer hash |
| Card PIN lock | AES-256-GCM (key derived via SHA-256 from PIN) |
| Storage | `chrome.storage.local` — device only |

> Note: `chrome.storage.local` is not encrypted at the OS level. The card PIN lock provides AES encryption so individual card content is unreadable without the PIN, even if storage is accessed directly.

---

## Permissions

| Permission | Reason |
|-----------|--------|
| `storage` | Save clipboard history, settings, auth |
| `clipboardRead` | Read clipboard for monitoring |
| `clipboardWrite` | Copy items back to clipboard |
| `offscreen` | Background clipboard access |
| `alarms` | Periodic clipboard polling |
| `host_permissions: <all_urls>` | Inject content script for copy event capture |

---

## Keyboard Shortcuts

| Action | Mac | Windows |
|--------|-----|---------|
| Open extension | ⌘⇧V | Ctrl+Shift+V |
| Save note | ⌘↵ | Ctrl+Enter |
| Cancel edit | Esc | Esc |
| Paste to capture | ⌘V | Ctrl+V |
| Screenshot to clipboard | ⌘⌃⇧4 | Win+⇧S |

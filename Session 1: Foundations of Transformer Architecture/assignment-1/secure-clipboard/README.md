# Keeper

**Version:** 1.2.0  
**Type:** Chrome Extension (Manifest V3)  
**Platform:** macOS / Windows / Linux (Chrome 109+)

---

## What is this?

A privacy-first, fully local clipboard manager built as a Chrome Extension. All data stays on your device — no backend, no external APIs, no cloud sync.

---

## 🎥 Demo Video

[![Keeper Demo](https://img.youtube.com/vi/Xn106D1aYPU/0.jpg)](https://www.youtube.com/watch?v=Xn106D1aYPU)

## Features

### v1.0.0
- **Clipboard capture** — automatically saves everything you copy (text + images)
- **Authentication** — username + password (SHA-256 hashed), with security question for password reset
- **Session management** — auto-locks when browser restarts
- **Search** — real-time case-insensitive search across all items
- **Time filter** — filter by last 24h, 2 days, 7 days, 30 days, 1 year, or all time
- **Pin / Copy / Delete** — per-card actions
- **Dark mode** — persisted preference
- **Paste zone** — ⌘V/Ctrl+V to capture screenshots and images
- **Note cards** — manually add notes with "+ New note"
- **Resizable window** — open in standalone window (⤢ button)
- **Keyboard shortcut** — ⌘⇧V (Mac) / Ctrl+Shift+V (Windows)

### v1.1.0
- **Secure cards (PIN lock)** — lock any card with a 4-digit PIN; content is AES-256-GCM encrypted at rest
- **Tab directory** — navigate by category: Recent (7 days), Images, Texts, Passwords, Favourites
- **Inline autosave** — double-click any text card to edit; changes save automatically after 800ms
- **Extension icon** — custom clipboard icon

### v1.2.0
- **Renamed to Keeper** — cleaner branding throughout
- **User-controlled categories** — tabs show only cards you explicitly assign there via the 📁 Move button; the extension never auto-categorises your cards
- **Move menu** — every card has a 📁 Move button that lets you assign it to Images, Texts, Passwords, Favourites, or back to Recent only
- **Right-click context menu** — right-click any card to Copy, Paste into card, Move, Pin, Lock, or Delete without scrolling to the action buttons
- **Paste into card** — click 📋 Paste on any card (or right-click → Paste into card) to replace its content with your current clipboard (text or image)
- **All text cards editable** — double-click to edit works on every unlocked text card, not just notes
- **Screenshot auto-capture** — Cmd+V anywhere in the popup (when no text input is focused) creates a new card from clipboard; screenshots land in Recent and can be moved from there
- **Paste zone auto-focus** — paste zone is focused on dashboard load so ⌘V works immediately
- **Scrolling fixed** — cards scroll correctly; full card content including images is accessible
- **Larger image previews** — images show up to 200px tall with no cropping (`object-fit: contain`)
- **Taller popup** — popup is 700px to fit more cards without cutting them off

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
├── popup.js            # Auth, dashboard, tabs, lock, move menu, context menu
├── popup.css           # Light + dark theme, all component styles
├── utils.js            # SHA-256, AES-GCM, filtering, formatting helpers
└── icons/
    ├── icon.png        # Extension icon
    └── generate.html  # Open in Chrome to regenerate PNG icons if needed
```

---

## Installation

1. Clone / download this folder
2. Go to `chrome://extensions`
3. Enable **Developer Mode** (top-right toggle)
4. Click **Load unpacked** → select the `secure-clipboard/` folder
5. Click the extension icon in the toolbar → create your account

---

## Usage

### First run
1. Open the extension → you'll see the **Create Account** screen
2. Set username, password, security question & answer

### Capturing clipboard
- **Copy anything** (text, images) → it's automatically saved as a card in Recent
- **Screenshots** → press ⌘⌃⇧4 (Mac) to copy to clipboard → open extension → ⌘V to create a card

### Managing cards

| Action | How |
|--------|-----|
| Edit content | Double-click the card text |
| Move to a tab | Click 📁 Move on the card, pick a category |
| Right-click menu | Copy · Paste into card · Move · Pin · Lock · Delete |
| Paste clipboard into card | Click 📋 Paste on the card, or right-click → Paste into card |
| Copy to clipboard | Click 📋 Copy, or click the card |
| Pin / favourite | Click 📌 Pin (pinned cards always appear in Recent) |

### Tabs
| Tab | Shows |
|-----|-------|
| 🕐 Recent | All items from last 7 days + pinned items |
| 🖼 Images | Cards you moved to Images |
| 📝 Texts | Cards you moved to Texts |
| 🔐 Passwords | Cards you moved to Passwords |
| ⭐ Favs | Cards you moved to Favourites + pinned cards |

> Cards start in **Recent**. Use 📁 Move to assign them to a tab — your choice, not the extension's.

### Locking a card
1. Click **🔒 Lock** on any card (or right-click → Lock)
2. Enter a 4-digit PIN → content is AES-256-GCM encrypted
3. Click **🔓 Unlock** → enter PIN → content is revealed temporarily (never stored decrypted)

### Editing text cards
- Double-click the text of any unlocked card → edit inline
- Changes auto-save after 800ms
- Press **Escape** to cancel, **⌘↵** to save immediately

---

## Security Model

| Layer | Method |
|-------|--------|
| Vault login | SHA-256 password hash |
| Security Q&A | SHA-256 answer hash |
| Card PIN lock | AES-256-GCM (key derived via SHA-256 from PIN) |
| Storage | `chrome.storage.local` — device only, no network |

> `chrome.storage.local` is not OS-level encrypted. The card PIN lock provides AES encryption so individual card content is unreadable without the PIN, even if storage is inspected directly.

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
| Paste to capture / paste into card | ⌘V | Ctrl+V |
| Save note (inline edit) | ⌘↵ | Ctrl+Enter |
| Cancel edit | Esc | Esc |
| Screenshot to clipboard | ⌘⌃⇧4 | Win+⇧S |

# DevOps Sentinel AI — Chrome Extension

A browser extension that acts as an AI-powered DevOps assistant. Paste your YAML or Terraform code directly into the popup and get instant expert analysis, corrections, and optimizations — powered by Google Gemini.

---

## What It Does

### Tab 1 — YAML Debugger
Paste any YAML — Kubernetes manifests, Docker Compose files, CI/CD pipeline configs — and choose one of two actions:
- **Explain** — the AI identifies syntax errors, indentation issues, schema violations, deprecated API versions, and security gaps, with line-level detail
- **Correct & Optimize** — the AI returns a fully fixed, production-ready YAML block with a summary of every change made

### Tab 2 — Terraform Analyzer
Paste any HCL (HashiCorp Configuration Language) snippet and choose:
- **Logic Check** — the AI explains the full infrastructure impact: what gets created/modified/destroyed, IAM implications, cost considerations, and drift risks
- **Fix Deprecations** — the AI rewrites the block using current provider syntax, showing a before → after diff for every deprecated attribute

Both tabs preserve your input when switching between them (state is never cleared), include a Copy to Clipboard button on every output block, and show a loading indicator while the AI is working.

---

## AI Configuration

**Model:** `gemini-3-flash-preview`

**System Prompt:**
> "You are a Senior Staff DevOps Engineer with 15 years of experience in Infrastructure as Code and Kubernetes internals."

Every request to Gemini is sent with this system context, ensuring responses are expert-level and focused on real-world DevOps concerns — not generic programming advice.

---

## How the API Key Works

The API key **never lives in source code**. Here is the full flow:

```
.env                          ← single source of truth (you create this)
  │
  ├── build-config.js reads it and generates config.js
  │         (run once: node build-config.js)
  │
  └── popup.js reads it at runtime via three fallback paths:
        1. chrome.storage.sync  ← user-saved key via Settings UI
        2. window.DEVOPS_SENTINEL_CONFIG  ← from generated config.js
        3. fetch('.env') directly  ← Chrome extension fetches its own
                                      bundled .env at runtime
```

**The .env file format:**
```
GEMINI_API_KEY=AIzaSy...your_key_here
```

The extension popup uses `chrome.runtime.getURL('.env')` to fetch the `.env` file directly from its own package — so even if `config.js` was never generated, the key is always resolved. The key is never sent anywhere except the Gemini API endpoint.

---

## How This Was Built

This extension was built entirely by **Claude** (Anthropic's AI) from a spec written in this README.

The workflow was:
1. A `README.md` (this file) was written describing the full specification — tabs, actions, AI model, prompt engineering guidelines, and tech stack
2. A `.env` file was created with the Gemini API key
3. Claude Code was pointed at this folder and told: *"read the README and build everything as described, API key is in .env"*
4. Claude read both files, planned the architecture, and generated all four extension files:
   - `manifest.json` — Chrome Manifest V3 with required permissions
   - `popup.html` — 2-tab interface with Settings modal
   - `styles.css` — dark professional DevOps theme (no external CDN)
   - `popup.js` — all logic: API calls, syntax highlighting, state management, key loading
5. Iterative fixes were made through conversation — API key resolution, host permissions, endpoint selection — all handled by Claude without touching any code manually

---

## Tech Stack

| Layer | Choice |
|---|---|
| Frontend | HTML5, CSS3 (custom dark theme), JavaScript ES6+ |
| AI Backend | Google Gemini (`gemini-3-flash-preview`) via REST API |
| Syntax Highlighting | Custom lightweight highlighter (no external libs) |
| Key Storage | `.env` file + `chrome.storage.sync` for user overrides |
| Extension Standard | Chrome Manifest V3 |

---

## Project Structure

```
devops-sentinel/
├── .env                  ← API key (never commit this)
├── manifest.json         ← Chrome extension manifest (MV3)
├── popup.html            ← Extension UI
├── popup.js              ← All JavaScript logic
├── styles.css            ← Dark theme styles
├── config.js             ← Auto-generated from .env (never commit)
├── build-config.js       ← Build script: reads .env → writes config.js
└── README.md             ← This file
```

---

## Installation

### Prerequisites
- Google Chrome (or any Chromium browser)
- Node.js (only needed if you want to run `build-config.js`)
- A Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey)

### Steps

**1. Clone or download this folder**
```bash
git clone <repo-url>
cd devops-sentinel
```

**2. Add your API key**

Create a `.env` file in the `devops-sentinel/` folder:
```
GEMINI_API_KEY=AIzaSy...your_key_here
```

**3. (Optional) Generate config.js**

This step is optional — the extension can read `.env` directly at runtime. But generating `config.js` makes the key load faster:
```bash
node build-config.js
```

**4. Load the extension in Chrome**

- Open Chrome and go to `chrome://extensions`
- Toggle **Developer mode** ON (top-right switch)
- Click **Load unpacked**
- Select the `devops-sentinel/` folder
- The extension icon appears in your toolbar

**5. Use it**

- Click the extension icon
- Paste YAML or Terraform code into the relevant tab
- Hit **Explain**, **Correct**, **Logic Check**, or **Fix Deprecations**
- Copy the output with the **Copy** button

### Changing the API Key

Click the **⚙ Settings** icon inside the popup. Paste a new key and save. The key is stored in `chrome.storage.sync` and takes priority over `.env` on next load. To revert to the `.env` key, clear the field in Settings and save.

---

## Security Notes

- The API key is loaded at runtime — it is never hardcoded in `popup.js`
- `config.js` and `.env` should both be added to `.gitignore` before committing
- The key is only ever sent to `https://generativelanguage.googleapis.com` — no other destination
- `chrome.storage.sync` encrypts data at rest on the user's device

---

## Demo

<!-- YouTube video -->


<!-- Twitter / X post link -->


<!-- GIF demo -->


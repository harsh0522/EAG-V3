// ─── utils.js ────────────────────────────────────────────────────────────────
// Shared helper utilities for Secure Clipboard Vault v1.1.0
// ─────────────────────────────────────────────────────────────────────────────

'use strict';

// ── Storage wrappers ──────────────────────────────────────────────────────────

/** Read one or more keys from chrome.storage.local. */
function getStorage(keys) {
  return new Promise((resolve, reject) => {
    chrome.storage.local.get(keys, result => {
      if (chrome.runtime.lastError) reject(chrome.runtime.lastError);
      else resolve(result);
    });
  });
}

/** Write an object of key/value pairs to chrome.storage.local. */
function setStorage(obj) {
  return new Promise((resolve, reject) => {
    chrome.storage.local.set(obj, () => {
      if (chrome.runtime.lastError) reject(chrome.runtime.lastError);
      else resolve();
    });
  });
}

/** Remove one or more keys from chrome.storage.local. */
function removeStorage(keys) {
  return new Promise((resolve, reject) => {
    chrome.storage.local.remove(keys, () => {
      if (chrome.runtime.lastError) reject(chrome.runtime.lastError);
      else resolve();
    });
  });
}

// ── Hashing ───────────────────────────────────────────────────────────────────

/**
 * SHA-256 hash a string and return a lowercase hex digest.
 * Used for password and security-answer storage.
 */
async function sha256(str) {
  const buf = await crypto.subtle.digest(
    'SHA-256',
    new TextEncoder().encode(str)
  );
  return Array.from(new Uint8Array(buf))
    .map(b => b.toString(16).padStart(2, '0'))
    .join('');
}

// ── AES-GCM PIN encryption helpers ───────────────────────────────────────────

/**
 * Derive a non-extractable AES-GCM key from a 4-digit PIN string
 * by hashing the PIN with SHA-256 and importing the result.
 * @param {string} pin  The raw PIN string (e.g. "1234")
 * @returns {Promise<CryptoKey>}
 */
async function deriveAesKey(pin) {
  const pinBuf = new TextEncoder().encode(pin);
  const hash = await crypto.subtle.digest('SHA-256', pinBuf);
  return crypto.subtle.importKey(
    'raw',
    hash,
    { name: 'AES-GCM' },
    false,
    ['encrypt', 'decrypt']
  );
}

/**
 * Encrypt a plaintext string with AES-GCM using a key derived from `pin`.
 * @param {string} text  Plaintext to encrypt
 * @param {string} pin   4-digit PIN
 * @returns {Promise<{encryptedContent: string, iv: string}>}
 *          Both values are base-64 encoded.
 */
async function encryptText(text, pin) {
  const key = await deriveAesKey(pin);
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const enc = await crypto.subtle.encrypt(
    { name: 'AES-GCM', iv },
    key,
    new TextEncoder().encode(text)
  );
  const toB64 = buf => btoa(String.fromCharCode(...new Uint8Array(buf)));
  return { encryptedContent: toB64(enc), iv: toB64(iv) };
}

/**
 * Decrypt a base-64-encoded AES-GCM ciphertext using a key derived from `pin`.
 * Throws a DOMException if the PIN is wrong (authentication tag mismatch).
 * @param {string} encryptedBase64  Base-64 ciphertext
 * @param {string} ivBase64         Base-64 IV
 * @param {string} pin              4-digit PIN
 * @returns {Promise<string>}  Plaintext
 */
async function decryptText(encryptedBase64, ivBase64, pin) {
  const key = await deriveAesKey(pin);
  const fromB64 = s => Uint8Array.from(atob(s), c => c.charCodeAt(0));
  const dec = await crypto.subtle.decrypt(
    { name: 'AES-GCM', iv: fromB64(ivBase64) },
    key,
    fromB64(encryptedBase64)
  );
  return new TextDecoder().decode(dec);
}

// ── Filtering helpers ─────────────────────────────────────────────────────────

/**
 * Filter an array of clipboard items by a time window (ms from now).
 * Pass Infinity to return all items.
 * Pinned items always pass the time filter.
 */
function filterByTime(items, windowMs) {
  if (!isFinite(windowMs)) return items;
  const cutoff = Date.now() - windowMs;
  return items.filter(i => i.pinned || (i.timestamp && i.timestamp >= cutoff));
}

/**
 * Case-insensitive search across content and note text.
 * For image items the search checks any stored caption / alt text.
 */
function filterBySearch(items, query) {
  if (!query || !query.trim()) return items;
  const q = query.trim().toLowerCase();
  return items.filter(i => {
    if (i.type === 'image') return false; // images have no searchable text
    return (i.content || '').toLowerCase().includes(q);
  });
}

// ── Formatting helpers ────────────────────────────────────────────────────────

/**
 * Return a human-readable relative timestamp (e.g. "just now", "3 min ago").
 */
function relativeTime(ts) {
  const diff = Date.now() - ts;
  const s = Math.floor(diff / 1000);
  if (s < 60) return 'just now';
  const m = Math.floor(s / 60);
  if (m < 60) return `${m} min ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  if (d < 7) return `${d}d ago`;
  return new Date(ts).toLocaleDateString();
}

/**
 * Truncate a string to `max` characters and append "…" if truncated.
 */
function truncate(str, max = 120) {
  if (!str) return '';
  return str.length > max ? str.slice(0, max) + '…' : str;
}

/**
 * Escape HTML special characters to prevent XSS when inserting into innerHTML.
 */
function escapeHtml(str) {
  if (!str) return '';
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/**
 * Generate a short random ID (not cryptographic — just for UI keys).
 */
function generateId() {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
}

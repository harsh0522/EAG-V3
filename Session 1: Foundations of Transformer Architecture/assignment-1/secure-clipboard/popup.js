// ─── popup.js ─────────────────────────────────────────────────────────────────
// Secure Clipboard Vault v1.1.0
// Handles auth, dashboard rendering, tabs, PIN-lock cards, inline note editing.
// Depends on utils.js being loaded first (getStorage, setStorage, sha256,
// encryptText, decryptText, filterBySearch, relativeTime, truncate, escapeHtml,
// generateId).
// ──────────────────────────────────────────────────────────────────────────────

'use strict';

// ── State ─────────────────────────────────────────────────────────────────────

let allItems    = [];        // full list loaded from storage
let currentTab  = 'recent'; // active tab in the tab bar
let pinCallback = null;      // async fn(pin) to call when PIN modal confirms

// ── DOM helpers ───────────────────────────────────────────────────────────────

const $  = id  => document.getElementById(id);
const $$ = sel => document.querySelectorAll(sel);

// ── Init ──────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', async () => {
  applyTheme();
  await checkSession();
  bindAuthEvents();
  bindDashboardEvents();
  bindPinModalEvents();
  bindSettingsEvents();
  bindPasteZone();
  bindTabBar();
});

// ─────────────────────────────────────────────────────────────────────────────
// THEME
// ─────────────────────────────────────────────────────────────────────────────

function applyTheme() {
  getStorage('darkMode').then(({ darkMode }) => {
    if (darkMode) {
      document.body.classList.add('dark');
      $('theme-toggle').textContent = '☀️';
    }
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// SESSION CHECK
// ─────────────────────────────────────────────────────────────────────────────

async function checkSession() {
  const { accounts, session } = await getStorage(['accounts', 'session']);

  if (!accounts || accounts.length === 0) {
    // First run — show registration
    showView('register-view');
    showScreen('auth-screen');
    return;
  }

  if (session && session.loggedIn) {
    await loadAndShowDashboard();
  } else {
    showView('login-view');
    showScreen('auth-screen');
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// HELPERS — show/hide screens & views
// ─────────────────────────────────────────────────────────────────────────────

function showScreen(id) {
  $$('.screen').forEach(s => s.classList.add('hidden'));
  $(id).classList.remove('hidden');
}

function showView(id) {
  $$('#auth-screen > div').forEach(v => v.classList.add('hidden'));
  $(id).classList.remove('hidden');
}

// ─────────────────────────────────────────────────────────────────────────────
// AUTH — BIND EVENTS
// ─────────────────────────────────────────────────────────────────────────────

function bindAuthEvents() {
  // Navigation
  $('go-register').addEventListener('click', () => showView('register-view'));
  $('go-login').addEventListener('click',    () => showView('login-view'));
  $('go-forgot').addEventListener('click',   () => showView('forgot-view'));
  $('forgot-back').addEventListener('click', () => showView('login-view'));

  // Login
  $('login-btn').addEventListener('click', handleLogin);
  $('login-pass').addEventListener('keydown', e => { if (e.key === 'Enter') handleLogin(); });

  // Register
  $('register-btn').addEventListener('click', handleRegister);

  // Forgot password
  $('forgot-submit').addEventListener('click', handleForgotPassword);
}

// ── Login ─────────────────────────────────────────────────────────────────────

async function handleLogin() {
  const user = $('login-user').value.trim();
  const pass = $('login-pass').value;
  if (!user || !pass) return;

  const { accounts = [] } = await getStorage('accounts');
  const hash = await sha256(pass);
  const account = accounts.find(a => a.username === user && a.passwordHash === hash);

  if (!account) {
    $('login-error').classList.remove('hidden');
    return;
  }
  $('login-error').classList.add('hidden');
  await setStorage({ session: { loggedIn: true, username: user } });
  await loadAndShowDashboard();
}

// ── Register ──────────────────────────────────────────────────────────────────

async function handleRegister() {
  const user = $('reg-user').value.trim();
  const pass = $('reg-pass').value;
  const q    = $('reg-q').value.trim();
  const a    = $('reg-a').value.trim();

  if (!user || !pass || !q || !a) {
    showRegError('All fields are required.');
    return;
  }

  const { accounts = [] } = await getStorage('accounts');
  if (accounts.find(ac => ac.username === user)) {
    showRegError('Username already exists.');
    return;
  }

  const passwordHash = await sha256(pass);
  const answerHash   = await sha256(a.toLowerCase());
  accounts.push({ username: user, passwordHash, securityQuestion: q, answerHash });
  await setStorage({ accounts, session: { loggedIn: true, username: user } });
  await loadAndShowDashboard();
}

function showRegError(msg) {
  const el = $('reg-error');
  el.textContent = msg;
  el.classList.remove('hidden');
}

// ── Forgot password ───────────────────────────────────────────────────────────

async function handleForgotPassword() {
  const user    = $('forgot-user').value.trim();
  const answer  = $('forgot-a').value.trim();
  const newPass = $('forgot-newpass').value;

  const { accounts = [] } = await getStorage('accounts');
  const idx = accounts.findIndex(a => a.username === user);
  if (idx < 0) {
    showForgotError('Username not found.');
    return;
  }

  const account = accounts[idx];

  // First step: show question
  const qWrap = $('forgot-q-wrap');
  if (qWrap.classList.contains('hidden')) {
    $('forgot-q-text').textContent = `Q: ${account.securityQuestion}`;
    qWrap.classList.remove('hidden');
    return;
  }

  // Second step: verify answer + reset
  if (!answer || !newPass) {
    showForgotError('Please fill in all fields.');
    return;
  }
  const answerHash = await sha256(answer.toLowerCase());
  if (answerHash !== account.answerHash) {
    showForgotError('Incorrect answer.');
    return;
  }
  accounts[idx].passwordHash = await sha256(newPass);
  await setStorage({ accounts });
  $('forgot-error').classList.add('hidden');
  $('forgot-success').classList.remove('hidden');
}

function showForgotError(msg) {
  const el = $('forgot-error');
  el.textContent = msg;
  el.classList.remove('hidden');
}

// ─────────────────────────────────────────────────────────────────────────────
// DASHBOARD
// ─────────────────────────────────────────────────────────────────────────────

async function loadAndShowDashboard() {
  const { clipboardItems = [] } = await getStorage('clipboardItems');
  allItems = clipboardItems;
  showScreen('dashboard-screen');
  renderDashboard();
  // Focus paste zone so Cmd+V works immediately without clicking first
  setTimeout(() => $('paste-zone')?.focus(), 100);

  // Poll for new items every 2 seconds while popup is open
  setInterval(async () => {
    const { clipboardItems: fresh = [] } = await getStorage('clipboardItems');
    if (fresh.length !== allItems.length) {
      allItems = fresh;
      renderDashboard();
    }
  }, 2000);
}

// ── Tab filtering — tabs reflect user-assigned categories, not auto-detected types ───

function getTabItems() {
  const sevenDaysAgo = Date.now() - 7 * 24 * 60 * 60 * 1000;
  switch (currentTab) {
    case 'recent':
      // All items from the last 7 days, plus any pinned items
      return allItems.filter(i => i.timestamp >= sevenDaysAgo || i.pinned);
    case 'images':
      return allItems.filter(i => i.category === 'images');
    case 'texts':
      return allItems.filter(i => i.category === 'texts');
    case 'passwords':
      return allItems.filter(i => i.category === 'passwords');
    case 'favourites':
      return allItems.filter(i => i.category === 'favourites' || i.pinned);
    default:
      return allItems;
  }
}

// ── Render ────────────────────────────────────────────────────────────────────

function renderDashboard() {
  const query      = $('search-input').value;
  const windowMs   = parseFloat($('time-filter').value);

  // 1. Filter by active tab
  let items = getTabItems();

  // 2. Apply time window filter (pinned items are immune)
  if (isFinite(windowMs)) {
    const cutoff = Date.now() - windowMs;
    items = items.filter(i => i.pinned || i.timestamp >= cutoff);
  }

  // 3. Apply search filter
  items = filterBySearch(items, query);

  // Sort: pinned first, then most-recent
  items = [
    ...items.filter(i => i.pinned),
    ...items.filter(i => !i.pinned)
  ];

  const list       = $('item-list');
  const emptyState = $('empty-state');
  list.innerHTML   = '';

  $('item-count').textContent = `${items.length} item${items.length !== 1 ? 's' : ''}`;

  if (items.length === 0) {
    emptyState.classList.remove('hidden');
    return;
  }
  emptyState.classList.add('hidden');

  items.forEach(item => {
    const el = buildItemEl(item);
    list.appendChild(el);
  });
}

// ── Build a single card element ───────────────────────────────────────────────

function buildItemEl(item) {
  const el = document.createElement('div');
  el.className = `clip-item${item.pinned ? ' pinned' : ''}${item.locked ? ' locked' : ''}`;
  el.dataset.id = item.id;

  // ── Header ────────────────────────────────────────────────────────────────
  const header = document.createElement('div');
  header.className = 'item-header';

  const badge = document.createElement('span');
  const catLabel = item.locked ? '🔒 locked'
    : (item.category && item.category !== 'none') ? item.category : item.type;
  badge.className = `item-type-badge ${item.type}`;
  badge.textContent = catLabel;

  const timeEl = document.createElement('span');
  timeEl.className = 'item-time';
  timeEl.textContent = relativeTime(item.timestamp);

  header.append(badge, timeEl);
  el.appendChild(header);

  // ── Preview ───────────────────────────────────────────────────────────────
  if (item.locked) {
    // Locked card shows a placeholder (Feature 2)
    const lp = document.createElement('div');
    lp.className = 'locked-preview item-preview';
    lp.innerHTML = '<span>🔒</span><span>Secured — click <em>Unlock</em> to reveal</span>';
    el.appendChild(lp);
  } else if (item.type === 'image') {
    const preview = document.createElement('div');
    preview.className = 'item-preview';
    const img = document.createElement('img');
    img.src = item.content;
    img.alt = 'Clipboard image';
    preview.appendChild(img);
    el.appendChild(preview);
  } else {
    const preview = document.createElement('div');
    preview.className = 'item-preview';
    preview.textContent = truncate(item.content, 140);
    el.appendChild(preview);

    // ── Inline edit for ALL unlocked text/note cards ─────────────────────
    {
      preview.title  = 'Double-click to edit';
      preview.style.cursor = 'text';
      let saveTimer;

      preview.addEventListener('dblclick', () => {
        // Replace preview with a textarea
        const textarea = document.createElement('textarea');
        textarea.className = 'edit-textarea';
        textarea.value = item.content;

        const indicator = document.createElement('div');
        indicator.className = 'autosave-indicator';

        preview.replaceWith(textarea);
        textarea.after(indicator);
        textarea.focus();
        // Move cursor to end
        textarea.selectionStart = textarea.selectionEnd = textarea.value.length;

        // Debounced auto-save
        textarea.addEventListener('input', () => {
          clearTimeout(saveTimer);
          indicator.textContent = 'Saving…';
          saveTimer = setTimeout(async () => {
            const newContent = textarea.value;
            item.content = newContent;
            allItems = allItems.map(i =>
              i.id === item.id ? { ...i, content: newContent } : i
            );
            await setStorage({ clipboardItems: allItems });
            indicator.textContent = 'Saved ✓';
            setTimeout(() => { indicator.textContent = ''; }, 1500);
          }, 800);
        });

        // Escape cancels edit
        textarea.addEventListener('keydown', e => {
          if (e.key === 'Escape') {
            clearTimeout(saveTimer);
            renderDashboard();
          }
          // Ctrl/Cmd+Enter also saves immediately
          if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
            clearTimeout(saveTimer);
            const newContent = textarea.value;
            item.content = newContent;
            allItems = allItems.map(i =>
              i.id === item.id ? { ...i, content: newContent } : i
            );
            setStorage({ clipboardItems: allItems }).then(() => {
              indicator.textContent = 'Saved ✓';
              setTimeout(() => renderDashboard(), 800);
            });
          }
        });
      });
    }
  }

  // ── Actions row ───────────────────────────────────────────────────────────
  const actions = document.createElement('div');
  actions.className = 'item-actions';

  // Copy button
  if (!item.locked) {
    const copyBtn = document.createElement('button');
    copyBtn.className = 'action-btn';
    copyBtn.textContent = item.type === 'image' ? '📋 Copy image' : '📋 Copy';
    copyBtn.addEventListener('click', e => {
      e.stopPropagation();
      copyItemToClipboard(item);
    });
    actions.appendChild(copyBtn);
  }

  // Paste button — pastes current clipboard content into this card
  if (!item.locked) {
    const pasteBtn = document.createElement('button');
    pasteBtn.className = 'action-btn';
    pasteBtn.textContent = '📋 Paste';
    pasteBtn.title = 'Paste clipboard content into this card (right-click also works)';
    pasteBtn.addEventListener('click', e => {
      e.stopPropagation();
      pasteIntoCard(item);
    });
    actions.appendChild(pasteBtn);
  }

  // Move to category
  const moveBtn = document.createElement('button');
  moveBtn.className = 'action-btn';
  moveBtn.textContent = '📁 Move';
  moveBtn.title = 'Move this card to a category tab';
  moveBtn.addEventListener('click', e => {
    e.stopPropagation();
    showMoveMenu(item, moveBtn);
  });
  actions.appendChild(moveBtn);

  // Pin / Unpin
  const pinBtn = document.createElement('button');
  pinBtn.className = 'action-btn';
  pinBtn.textContent = item.pinned ? '📌 Unpin' : '📌 Pin';
  pinBtn.addEventListener('click', async e => {
    e.stopPropagation();
    allItems = allItems.map(i =>
      i.id === item.id ? { ...i, pinned: !i.pinned } : i
    );
    await setStorage({ clipboardItems: allItems });
    renderDashboard();
    toast(item.pinned ? 'Unpinned' : 'Pinned ✓');
  });
  actions.appendChild(pinBtn);

  // Lock / Unlock (Feature 2)
  const lockBtn = document.createElement('button');
  lockBtn.className = 'action-btn lock-btn';
  lockBtn.textContent = item.locked ? '🔓 Unlock' : '🔒 Lock';
  lockBtn.addEventListener('click', e => {
    e.stopPropagation();
    handleLockToggle(item, el);
  });
  actions.appendChild(lockBtn);

  // Delete
  const delBtn = document.createElement('button');
  delBtn.className = 'action-btn danger';
  delBtn.textContent = '🗑 Delete';
  delBtn.addEventListener('click', async e => {
    e.stopPropagation();
    allItems = allItems.filter(i => i.id !== item.id);
    await setStorage({ clipboardItems: allItems });
    renderDashboard();
    toast('Deleted');
  });
  actions.appendChild(delBtn);

  el.appendChild(actions);

  // Right-click → custom context menu (Copy / Paste / Delete)
  el.addEventListener('contextmenu', e => {
    e.preventDefault();
    showCardContextMenu(item, e.clientX, e.clientY);
  });

  // Click on card copies to clipboard (unless auto-copy is off)
  el.addEventListener('click', async () => {
    const { autoCopy } = await getStorage('autoCopy');
    if (autoCopy !== false && !item.locked) {
      copyItemToClipboard(item);
    }
  });

  return el;
}

// ── Copy helpers ──────────────────────────────────────────────────────────────

async function copyItemToClipboard(item) {
  try {
    if (item.type === 'image') {
      const resp = await fetch(item.content);
      const blob = await resp.blob();
      await navigator.clipboard.write([
        new ClipboardItem({ [blob.type]: blob })
      ]);
    } else {
      await navigator.clipboard.writeText(item.content);
    }
    toast('Copied ✓');
  } catch {
    toast('Could not copy');
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// LOCK / UNLOCK — Feature 2
// ─────────────────────────────────────────────────────────────────────────────

function handleLockToggle(item, cardEl) {
  if (item.locked) {
    // ── Unlock mode ────────────────────────────────────────────────────────
    openPinModal('unlock', async pin => {
      try {
        const text = await decryptText(item.encryptedContent, item.iv, pin);

        // Reveal decrypted content temporarily — do NOT persist it
        const preview = cardEl.querySelector('.locked-preview');
        if (preview) {
          preview.innerHTML =
            `<span style="background:var(--item-pin);padding:4px 6px;border-radius:4px;font-size:12px;word-break:break-word;">${escapeHtml(text)}</span>` +
            `<span style="font-size:10px;color:var(--text-sub);margin-left:6px;white-space:nowrap;">(unlocked temporarily)</span>`;
        }
        return true; // close modal
      } catch {
        shakePinInputs();
        showPinError('Incorrect PIN. Try again.');
        return false; // keep modal open
      }
    });
  } else {
    // ── Lock mode ───────────────────────────────────────────────────────────
    openPinModal('lock', async pin => {
      const { encryptedContent, iv } = await encryptText(item.content, pin);
      allItems = allItems.map(i =>
        i.id === item.id
          ? { ...i, content: '', encryptedContent, iv, locked: true }
          : i
      );
      await setStorage({ clipboardItems: allItems });
      renderDashboard();
      toast('Card locked 🔒');
      return true;
    });
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// PIN MODAL — Feature 2
// ─────────────────────────────────────────────────────────────────────────────

function openPinModal(mode, callback) {
  pinCallback = callback;

  $('pin-modal-title').textContent = mode === 'lock' ? '🔒 Lock Card' : '🔓 Unlock Card';
  $('pin-modal-hint').textContent  = mode === 'lock'
    ? 'Set a 4-digit PIN to encrypt this card'
    : 'Enter the 4-digit PIN to reveal content';

  $('pin-error').classList.add('hidden');
  $$('.pin-digit').forEach(d => { d.value = ''; });
  $('pin-modal').classList.remove('hidden');
  $$('.pin-digit')[0].focus();
}

function bindPinModalEvents() {
  // Auto-advance digits
  $$('.pin-digit').forEach((inp, i, all) => {
    inp.addEventListener('input', () => {
      // Keep only last digit, ensure it's numeric
      inp.value = inp.value.replace(/\D/g, '').slice(-1);
      if (inp.value && i < all.length - 1) all[i + 1].focus();
      // If all 4 filled, auto-confirm
      if (i === all.length - 1 && inp.value) {
        // Small delay so user sees the filled state
        setTimeout(() => confirmPin(), 80);
      }
    });
    inp.addEventListener('keydown', e => {
      if (e.key === 'Backspace' && !inp.value && i > 0) all[i - 1].focus();
      if (e.key === 'Enter') confirmPin();
      if (e.key === 'Escape') closePinModal();
    });
    // Paste support — distribute pasted digits across boxes
    inp.addEventListener('paste', e => {
      e.preventDefault();
      const pasted = (e.clipboardData.getData('text') || '').replace(/\D/g, '').slice(0, 4);
      const allDigits = $$('.pin-digit');
      pasted.split('').forEach((ch, idx) => {
        if (allDigits[i + idx]) allDigits[i + idx].value = ch;
      });
      const nextIdx = Math.min(i + pasted.length, allDigits.length - 1);
      allDigits[nextIdx].focus();
    });
  });

  $('pin-modal-close').addEventListener('click', closePinModal);

  $('pin-confirm').addEventListener('click', confirmPin);
}

async function confirmPin() {
  const digits = $$('.pin-digit');
  const pin = Array.from(digits).map(d => d.value).join('');
  if (pin.length !== 4) {
    shakePinInputs();
    return;
  }
  if (pinCallback) {
    const ok = await pinCallback(pin);
    if (ok !== false) {
      closePinModal();
    }
  }
}

function closePinModal() {
  $('pin-modal').classList.add('hidden');
  pinCallback = null;
  $$('.pin-digit').forEach(d => { d.value = ''; });
  $('pin-error').classList.add('hidden');
}

function shakePinInputs() {
  const container = $('pin-inputs');
  container.classList.remove('shake');
  // Force reflow so the animation re-triggers if already shaking
  void container.offsetWidth;
  container.classList.add('shake');
  container.addEventListener('animationend', () => container.classList.remove('shake'), { once: true });
}

function showPinError(msg) {
  const el = $('pin-error');
  el.textContent = msg;
  el.classList.remove('hidden');
}

// ─────────────────────────────────────────────────────────────────────────────
// TAB BAR — Feature 4
// ─────────────────────────────────────────────────────────────────────────────

function bindTabBar() {
  $$('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      $$('.tab-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentTab = btn.dataset.tab;
      renderDashboard();
    });
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// DASHBOARD EVENTS
// ─────────────────────────────────────────────────────────────────────────────

function bindDashboardEvents() {
  // Search & filter
  $('search-input').addEventListener('input',  () => renderDashboard());
  $('time-filter').addEventListener('change',  () => renderDashboard());

  // Theme toggle
  $('theme-toggle').addEventListener('click', async () => {
    const isDark = document.body.classList.toggle('dark');
    $('theme-toggle').textContent = isDark ? '☀️' : '🌙';
    await setStorage({ darkMode: isDark });
  });

  // New note
  $('new-note-btn').addEventListener('click', () => createNewNote());

  // Expand to window
  $('expand-btn').addEventListener('click', () => {
    chrome.windows.create({
      url: chrome.runtime.getURL('popup.html'),
      type: 'popup',
      width: 700,
      height: 700
    });
  });

  // Logout
  $('logout-btn').addEventListener('click', async () => {
    await setStorage({ session: { loggedIn: false } });
    showView('login-view');
    showScreen('auth-screen');
  });

  // Settings button
  $('settings-btn').addEventListener('click', () => {
    $('settings-modal').classList.remove('hidden');
  });
}

// ── New note card ─────────────────────────────────────────────────────────────

async function createNewNote() {
  const note = {
    id:        generateId(),
    type:      'note',
    content:   '',
    timestamp: Date.now(),
    pinned:    false,
    locked:    false,
    category:  'none'
  };
  allItems = [note, ...allItems];
  await setStorage({ clipboardItems: allItems });

  // Switch to Recent tab so the new note is always visible
  if (currentTab !== 'recent') {
    $$('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelector('.tab-btn[data-tab="recent"]').classList.add('active');
    currentTab = 'recent';
  }

  renderDashboard();

  // Immediately enter edit mode on the new note
  const firstCard = document.querySelector('.clip-item[data-id="' + note.id + '"]');
  if (firstCard) {
    const preview = firstCard.querySelector('.item-preview');
    if (preview) {
      // Trigger the double-click listener programmatically
      preview.dispatchEvent(new MouseEvent('dblclick'));
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// PASTE ZONE
// ─────────────────────────────────────────────────────────────────────────────

function bindPasteZone() {
  const zone = $('paste-zone');

  // Click paste zone → focus it so next Cmd+V is caught by the document paste handler
  zone.addEventListener('click', () => zone.focus());

  // Global paste (Cmd/Ctrl+V) — captures screenshots and images anywhere in the popup
  document.addEventListener('paste', async e => {
    const target = e.target;
    // Let normal text inputs / textareas handle their own paste
    if (target.matches('input:not(#search-input), textarea, [contenteditable]')) return;
    // Also skip the PIN modal inputs
    if (target.closest('#pin-modal') || target.closest('#change-pass-modal')) return;

    const items = Array.from(e.clipboardData?.items || []);

    // Image first (screenshots)
    for (const item of items) {
      if (item.type.startsWith('image/')) {
        e.preventDefault();
        const blob    = item.getAsFile();
        const dataUrl = await blobToDataUrl(blob);
        await saveManualItem({ type: 'image', content: dataUrl });
        return;
      }
    }

    // Plain text — create a new card
    for (const item of items) {
      if (item.type === 'text/plain') {
        item.getAsString(async text => {
          if (text && text.trim()) {
            e.preventDefault();
            await saveManualItem({ type: 'text', content: text });
          }
        });
        return;
      }
    }
  });

  // Drag-and-drop
  zone.addEventListener('dragover', e => {
    e.preventDefault();
    zone.classList.add('drag-over');
  });
  zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
  zone.addEventListener('drop', async e => {
    e.preventDefault();
    zone.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (file && file.type.startsWith('image/')) {
      const dataUrl = await blobToDataUrl(file);
      await saveManualItem({ type: 'image', content: dataUrl });
    }
  });
}

async function saveManualItem(partial) {
  const item = {
    id:        generateId(),
    timestamp: Date.now(),
    pinned:    false,
    locked:    false,
    category:  'none',
    ...partial
  };
  allItems = [item, ...allItems];
  await setStorage({ clipboardItems: allItems });
  renderDashboard();
  toast('Saved ✓');
}

function blobToDataUrl(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload  = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// SETTINGS
// ─────────────────────────────────────────────────────────────────────────────

function bindSettingsEvents() {
  // Settings modal open/close
  $('settings-close').addEventListener('click', () => {
    $('settings-modal').classList.add('hidden');
  });

  // Auto-copy toggle
  $('auto-copy-toggle').addEventListener('change', async e => {
    await setStorage({ autoCopy: e.target.checked });
  });
  getStorage('autoCopy').then(({ autoCopy }) => {
    $('auto-copy-toggle').checked = autoCopy !== false;
  });

  // Max items
  $('max-items-select').addEventListener('change', async e => {
    await setStorage({ maxItems: parseInt(e.target.value) });
  });

  // Change password
  $('change-pass-btn').addEventListener('click', () => {
    $('settings-modal').classList.add('hidden');
    $('change-pass-modal').classList.remove('hidden');
  });
  $('change-pass-close').addEventListener('click', () => {
    $('change-pass-modal').classList.add('hidden');
  });
  $('cp-submit').addEventListener('click', handleChangePassword);

  // Clear all
  $('clear-all-btn').addEventListener('click', async () => {
    if (!confirm('Delete ALL clipboard items? This cannot be undone.')) return;
    allItems = [];
    await setStorage({ clipboardItems: [] });
    renderDashboard();
    $('settings-modal').classList.add('hidden');
    toast('All items cleared');
  });
}

async function handleChangePassword() {
  const current = $('cp-current').value;
  const newPass  = $('cp-new').value;
  if (!current || !newPass) return;

  const { accounts = [], session } = await getStorage(['accounts', 'session']);
  const currentHash = await sha256(current);
  const idx = accounts.findIndex(
    a => a.username === session.username && a.passwordHash === currentHash
  );

  if (idx < 0) {
    const e = $('cp-error');
    e.textContent = 'Current password is incorrect.';
    e.classList.remove('hidden');
    return;
  }

  accounts[idx].passwordHash = await sha256(newPass);
  await setStorage({ accounts });
  $('cp-error').classList.add('hidden');
  $('cp-success').classList.remove('hidden');
  setTimeout(() => {
    $('cp-success').classList.add('hidden');
    $('change-pass-modal').classList.add('hidden');
  }, 1800);
}

// ─────────────────────────────────────────────────────────────────────────────
// TOAST
// ─────────────────────────────────────────────────────────────────────────────

let toastTimer;
function toast(msg, durationMs = 2000) {
  const el = $('toast');
  el.textContent = msg;
  el.classList.remove('hidden');
  el.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    el.classList.remove('show');
    setTimeout(() => el.classList.add('hidden'), 220);
  }, durationMs);
}

// ─────────────────────────────────────────────────────────────────────────────
// CARD RIGHT-CLICK CONTEXT MENU
// ─────────────────────────────────────────────────────────────────────────────

function showCardContextMenu(item, x, y) {
  // Close any open menus first
  document.querySelectorAll('.card-ctx-menu, .move-menu').forEach(m => m.remove());

  const menu = document.createElement('div');
  menu.className = 'card-ctx-menu';

  function addOpt(label, cls, handler) {
    const btn = document.createElement('button');
    btn.className = 'card-ctx-opt' + (cls ? ' ' + cls : '');
    btn.textContent = label;
    btn.addEventListener('click', e => {
      e.stopPropagation();
      menu.remove();
      handler();
    });
    menu.appendChild(btn);
  }

  if (!item.locked) {
    addOpt(item.type === 'image' ? '📋 Copy image' : '📋 Copy', '', () => copyItemToClipboard(item));
    addOpt('📋 Paste into card', '', () => pasteIntoCard(item));
    addOpt('📁 Move to…', '', () => showMoveMenu(item, menu));
  }

  addOpt(item.pinned ? '📌 Unpin' : '📌 Pin', '', async () => {
    allItems = allItems.map(i => i.id === item.id ? { ...i, pinned: !i.pinned } : i);
    await setStorage({ clipboardItems: allItems });
    renderDashboard();
    toast(item.pinned ? 'Unpinned' : 'Pinned ✓');
  });

  addOpt(item.locked ? '🔓 Unlock' : '🔒 Lock', '', () => handleLockToggle(item, document.querySelector(`.clip-item[data-id="${item.id}"]`)));

  addOpt('🗑 Delete', 'danger', async () => {
    allItems = allItems.filter(i => i.id !== item.id);
    await setStorage({ clipboardItems: allItems });
    renderDashboard();
    toast('Deleted');
  });

  document.body.appendChild(menu);

  // Position: keep within popup bounds
  const mw = 170;
  const mh = menu.children.length * 33 + 8;
  menu.style.left = `${Math.min(x, window.innerWidth  - mw - 4)}px`;
  menu.style.top  = `${Math.min(y, window.innerHeight - mh - 4)}px`;

  setTimeout(() => {
    document.addEventListener('click', () => menu.remove(), { once: true });
  }, 0);
}

// ─────────────────────────────────────────────────────────────────────────────
// MOVE MENU — user picks which tab/category a card belongs to
// ─────────────────────────────────────────────────────────────────────────────

function showMoveMenu(item, anchorEl) {
  document.querySelectorAll('.move-menu').forEach(m => m.remove());

  const menu = document.createElement('div');
  menu.className = 'move-menu';

  const categories = [
    { id: 'none',       label: '🕐 Recent only' },
    { id: 'images',     label: '🖼 Images' },
    { id: 'texts',      label: '📝 Texts' },
    { id: 'passwords',  label: '🔐 Passwords' },
    { id: 'favourites', label: '⭐ Favourites' },
  ];

  categories.forEach(cat => {
    const opt = document.createElement('button');
    opt.className = 'move-option' + ((item.category || 'none') === cat.id ? ' active' : '');
    opt.textContent = cat.label;
    opt.addEventListener('click', async e => {
      e.stopPropagation();
      allItems = allItems.map(i => i.id === item.id ? { ...i, category: cat.id } : i);
      await setStorage({ clipboardItems: allItems });
      menu.remove();
      renderDashboard();
      toast(`Moved to ${cat.label} ✓`);
    });
    menu.appendChild(opt);
  });

  document.body.appendChild(menu);

  const rect     = anchorEl.getBoundingClientRect();
  const menuH    = categories.length * 34 + 8;
  const spaceBelow = window.innerHeight - rect.bottom;
  menu.style.top  = (spaceBelow >= menuH || spaceBelow >= 80)
    ? `${rect.bottom + 2}px`
    : `${rect.top - menuH - 2}px`;
  menu.style.left = `${Math.min(rect.left, window.innerWidth - 160)}px`;

  setTimeout(() => {
    document.addEventListener('click', () => menu.remove(), { once: true });
  }, 0);
}

// ─────────────────────────────────────────────────────────────────────────────
// PASTE INTO CARD — reads clipboard and updates the card's content
// ─────────────────────────────────────────────────────────────────────────────

async function pasteIntoCard(item) {
  try {
    const clipItems = await navigator.clipboard.read();
    for (const clipItem of clipItems) {
      const imgType = clipItem.types.find(t => t.startsWith('image/'));
      if (imgType) {
        const blob    = await clipItem.getType(imgType);
        const dataUrl = await blobToDataUrl(blob);
        allItems = allItems.map(i =>
          i.id === item.id ? { ...i, type: 'image', content: dataUrl } : i
        );
        await setStorage({ clipboardItems: allItems });
        renderDashboard();
        toast('Image pasted ✓');
        return;
      }
      if (clipItem.types.includes('text/plain')) {
        const blob = await clipItem.getType('text/plain');
        const text = await blob.text();
        if (text.trim()) {
          allItems = allItems.map(i =>
            i.id === item.id ? { ...i, content: text } : i
          );
          await setStorage({ clipboardItems: allItems });
          renderDashboard();
          toast('Text pasted ✓');
          return;
        }
      }
    }
    toast('Nothing to paste');
  } catch {
    toast('Use ⌘V / Ctrl+V to paste here');
  }
}

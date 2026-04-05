// ─── State ────────────────────────────────────────────────────────────────────
let allItems  = [];
let darkMode  = false;
let toastTimer = null;

// ─── Screen helpers ───────────────────────────────────────────────────────────
function show(id) {
  ['setup-screen','login-screen','reset-screen','dashboard-screen'].forEach(s => {
    document.getElementById(s).classList.add('hidden');
  });
  document.getElementById(id).classList.remove('hidden');
  if (id === 'dashboard-screen') focusPasteZone();
}

// Defined early so show() can reference it; body filled in PASTE ZONE section below
function focusPasteZone() {
  setTimeout(() => document.getElementById('paste-zone')?.focus(), 50);
}

function showErr(id, msg) {
  const el = document.getElementById(id);
  el.textContent = msg;
  el.classList.remove('hidden');
}
function hideErr(id) { document.getElementById(id).classList.add('hidden'); }

// ─── Toast ────────────────────────────────────────────────────────────────────
function toast(msg, duration = 1800) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.classList.remove('hidden');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.add('hidden'), duration);
}

// ─── Dark mode ────────────────────────────────────────────────────────────────
function applyDark(on) {
  darkMode = on;
  document.body.classList.toggle('dark', on);
  document.getElementById('dark-toggle').textContent = on ? '☀️' : '🌙';
}

// ─── Storage wrappers ─────────────────────────────────────────────────────────
function getStorage(keys) {
  return new Promise(r => chrome.storage.local.get(keys, r));
}
function setStorage(obj) {
  return new Promise(r => chrome.storage.local.set(obj, r));
}

// ─── Init ─────────────────────────────────────────────────────────────────────
async function init() {
  const data = await getStorage(['authUser', 'session', 'darkMode', 'clipboardItems']);

  // Apply saved theme
  applyDark(!!data.darkMode);

  if (!data.authUser) {
    show('setup-screen');
    return;
  }

  // Session persists until browser restart (session flag cleared on extension unload)
  if (data.session) {
    allItems = data.clipboardItems || [];
    show('dashboard-screen');
    renderDashboard();
  } else {
    show('login-screen');
  }
}

// ─── SETUP ────────────────────────────────────────────────────────────────────
document.getElementById('su-btn').addEventListener('click', async () => {
  hideErr('su-error');
  const username = document.getElementById('su-username').value.trim();
  const password = document.getElementById('su-password').value;
  const confirm  = document.getElementById('su-confirm').value;
  const question = document.getElementById('su-question').value;
  const answer   = document.getElementById('su-answer').value.trim();

  if (!username)              return showErr('su-error', 'Username is required.');
  if (password.length < 4)   return showErr('su-error', 'Password must be at least 4 characters.');
  if (password !== confirm)   return showErr('su-error', 'Passwords do not match.');
  if (!question)              return showErr('su-error', 'Please select a security question.');
  if (!answer)                return showErr('su-error', 'Security answer is required.');

  const [pwdHash, ansHash] = await Promise.all([hashString(password), hashString(answer.toLowerCase())]);

  await setStorage({
    authUser: { username, passwordHash: pwdHash, question, answerHash: ansHash },
    clipboardItems: [],
    session: true
  });

  allItems = [];
  show('dashboard-screen');
  renderDashboard();
  toast('Account created! Welcome 🎉');
});

// ─── LOGIN ────────────────────────────────────────────────────────────────────
document.getElementById('li-btn').addEventListener('click', async () => {
  hideErr('li-error');
  const username = document.getElementById('li-username').value.trim();
  const password = document.getElementById('li-password').value;

  if (!username || !password) return showErr('li-error', 'Please fill in all fields.');

  const { authUser, clipboardItems = [] } = await getStorage(['authUser', 'clipboardItems']);
  if (!authUser) return showErr('li-error', 'No account found. Please set up first.');

  if (authUser.username !== username) return showErr('li-error', 'Incorrect username or password.');

  const pwdHash = await hashString(password);
  if (pwdHash !== authUser.passwordHash) return showErr('li-error', 'Incorrect username or password.');

  await setStorage({ session: true });
  allItems = clipboardItems;
  show('dashboard-screen');
  renderDashboard();
});

// Enter key on login
document.getElementById('li-password').addEventListener('keydown', e => {
  if (e.key === 'Enter') document.getElementById('li-btn').click();
});

// ─── FORGOT PASSWORD ──────────────────────────────────────────────────────────
document.getElementById('li-forgot').addEventListener('click', () => {
  document.getElementById('rs-step1').classList.remove('hidden');
  document.getElementById('rs-step2').classList.add('hidden');
  document.getElementById('rs-username').value = '';
  document.getElementById('rs-answer').value = '';
  document.getElementById('rs-new-pwd').value = '';
  document.getElementById('rs-confirm-pwd').value = '';
  hideErr('rs-err1'); hideErr('rs-err2');
  show('reset-screen');
});

document.getElementById('rs-back').addEventListener('click', () => show('login-screen'));

// Step 1: find account
document.getElementById('rs-find-btn').addEventListener('click', async () => {
  hideErr('rs-err1');
  const username = document.getElementById('rs-username').value.trim();
  if (!username) return showErr('rs-err1', 'Please enter your username.');

  const { authUser } = await getStorage(['authUser']);
  if (!authUser || authUser.username !== username) return showErr('rs-err1', 'Account not found.');

  document.getElementById('rs-question-text').textContent = `"${authUser.question}"`;
  document.getElementById('rs-step1').classList.add('hidden');
  document.getElementById('rs-step2').classList.remove('hidden');
});

// Step 2: verify answer + set new password
document.getElementById('rs-submit-btn').addEventListener('click', async () => {
  hideErr('rs-err2');
  const answer   = document.getElementById('rs-answer').value.trim();
  const newPwd   = document.getElementById('rs-new-pwd').value;
  const confirm  = document.getElementById('rs-confirm-pwd').value;
  const username = document.getElementById('rs-username').value.trim();

  if (!answer)             return showErr('rs-err2', 'Please enter your security answer.');
  if (newPwd.length < 4)  return showErr('rs-err2', 'New password must be at least 4 characters.');
  if (newPwd !== confirm)  return showErr('rs-err2', 'Passwords do not match.');

  const { authUser } = await getStorage(['authUser']);
  const ansHash = await hashString(answer.toLowerCase());

  if (ansHash !== authUser.answerHash) return showErr('rs-err2', 'Incorrect security answer.');

  const newHash = await hashString(newPwd);
  authUser.passwordHash = newHash;
  await setStorage({ authUser });

  show('login-screen');
  toast('Password reset! Please log in.', 2500);
});

// ─── LOGOUT ───────────────────────────────────────────────────────────────────
document.getElementById('logout-btn').addEventListener('click', async () => {
  await setStorage({ session: false });
  show('login-screen');
  document.getElementById('li-username').value = '';
  document.getElementById('li-password').value = '';
});

// ─── DARK MODE TOGGLE ─────────────────────────────────────────────────────────
document.getElementById('dark-toggle').addEventListener('click', async () => {
  applyDark(!darkMode);
  await setStorage({ darkMode });
});

// ─── CHANGE PASSWORD MODAL ────────────────────────────────────────────────────
document.getElementById('chpwd-open').addEventListener('click', () => {
  ['cp-current','cp-new','cp-confirm'].forEach(id => document.getElementById(id).value = '');
  hideErr('cp-error');
  document.getElementById('chpwd-modal').classList.remove('hidden');
});
document.getElementById('chpwd-close').addEventListener('click', () => {
  document.getElementById('chpwd-modal').classList.add('hidden');
});

document.getElementById('cp-save').addEventListener('click', async () => {
  hideErr('cp-error');
  const current = document.getElementById('cp-current').value;
  const newPwd  = document.getElementById('cp-new').value;
  const confirm = document.getElementById('cp-confirm').value;

  if (!current || !newPwd) return showErr('cp-error', 'Please fill in all fields.');
  if (newPwd.length < 4)   return showErr('cp-error', 'New password must be at least 4 characters.');
  if (newPwd !== confirm)   return showErr('cp-error', 'New passwords do not match.');

  const { authUser } = await getStorage(['authUser']);
  const curHash = await hashString(current);
  if (curHash !== authUser.passwordHash) return showErr('cp-error', 'Current password is incorrect.');

  authUser.passwordHash = await hashString(newPwd);
  await setStorage({ authUser });
  document.getElementById('chpwd-modal').classList.add('hidden');
  toast('Password updated ✓');
});

// ─── PASTE ZONE ───────────────────────────────────────────────────────────────

const isMac = /Mac/.test(navigator.userAgent);
const shortcutKey = isMac ? '⌘V' : 'Ctrl+V';
const screenshotTip = isMac ? '  •  Screenshot to clipboard: ⌘⌃⇧4' : '';

// Set placeholder dynamically so it reflects the OS shortcut
document.getElementById('paste-zone').placeholder =
  `📋  Right-click → Paste  or  press ${shortcutKey} here${screenshotTip}`;

/**
 * Single global paste handler — catches ALL paste actions in the popup:
 *   • ⌘V / Ctrl+V anywhere (when paste zone or body is focused)
 *   • Right-click → Paste on the paste zone textarea
 *
 * Skips pastes inside the search bar, modal inputs, and auth screens.
 */
document.addEventListener('paste', async e => {
  const target = e.target;

  // Ignore pastes inside search, password fields, or modal
  if (
    target.id === 'search'           ||
    target.closest('#chpwd-modal')   ||
    target.closest('#change-pwd-modal') ||
    (target.tagName === 'INPUT' && target.type === 'password') ||
    document.getElementById('dashboard-screen').classList.contains('hidden')
  ) return;

  e.preventDefault();

  const items = e.clipboardData?.items;
  if (!items || items.length === 0) return;

  // ── Images (screenshots, copied images) ──────────────────────────────
  for (const item of items) {
    if (item.type.startsWith('image/')) {
      const blob = item.getAsFile();
      if (!blob) continue;
      const reader = new FileReader();
      reader.onloadend = async () => {
        await addItemToStorage(reader.result, 'image');
        flashPasteZone();
        toast('Screenshot saved ✓');
      };
      reader.readAsDataURL(blob);
      return;
    }
  }

  // ── Plain text ────────────────────────────────────────────────────────
  for (const item of items) {
    if (item.type === 'text/plain') {
      item.getAsString(async text => {
        if (!text.trim()) return;
        await addItemToStorage(text, 'text');
        flashPasteZone();
        toast('Pasted & saved ✓');
      });
      return;
    }
  }
});

function flashPasteZone() {
  const el = document.getElementById('paste-zone');
  el.value = '';
  el.classList.add('flash');
  setTimeout(() => el.classList.remove('flash'), 700);
}


// Save directly to storage + update local list (bypasses background service worker)
async function addItemToStorage(content, type) {
  const { clipboardItems = [] } = await getStorage(['clipboardItems']);
  if (clipboardItems[0]?.content === content) return; // deduplicate

  const entry = {
    id:        `${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
    content,
    type,
    timestamp: Date.now(),
    pinned:    false
  };

  const updated = [entry, ...clipboardItems].slice(0, 500);
  await setStorage({ clipboardItems: updated });
  allItems = updated;
  renderDashboard();
}

// ─── NOTE COMPOSER ────────────────────────────────────────────────────────────

const noteComposer = document.getElementById('note-composer');
const noteText     = document.getElementById('note-text');
const noteCount    = document.getElementById('note-char-count');

function openComposer() {
  noteComposer.classList.remove('hidden');
  noteText.value = '';
  noteCount.textContent = '0 chars';
  noteText.focus();
}

function closeComposer() {
  noteComposer.classList.add('hidden');
  noteText.value = '';
  focusPasteZone();
}

document.getElementById('add-note-btn').addEventListener('click', () => {
  const isOpen = !noteComposer.classList.contains('hidden');
  isOpen ? closeComposer() : openComposer();
});

document.getElementById('note-cancel').addEventListener('click', closeComposer);

// Live char count
noteText.addEventListener('input', () => {
  const len = noteText.value.length;
  noteCount.textContent = `${len.toLocaleString()} char${len !== 1 ? 's' : ''}`;
});

// Save note
document.getElementById('note-save').addEventListener('click', saveNote);

// ⌘↵ / Ctrl+↵ to save while composer is open
noteText.addEventListener('keydown', e => {
  if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
    e.preventDefault();
    saveNote();
  }
  // Escape to cancel
  if (e.key === 'Escape') closeComposer();
});

async function saveNote() {
  const text = noteText.value.trim();
  if (!text) { noteText.focus(); return; }
  await addItemToStorage(text, 'note');
  closeComposer();
  toast('Note saved ✓');
}

// ─── SEARCH + FILTER ──────────────────────────────────────────────────────────
document.getElementById('search').addEventListener('input', renderDashboard);
document.getElementById('time-filter').addEventListener('change', renderDashboard);

// ─── CLEAR ALL ────────────────────────────────────────────────────────────────
document.getElementById('clear-all').addEventListener('click', async () => {
  if (!confirm('Delete all clipboard history?')) return;
  allItems = [];
  await setStorage({ clipboardItems: [] });
  renderDashboard();
  toast('Cleared all items');
});

// ─── RENDER ───────────────────────────────────────────────────────────────────
function renderDashboard() {
  const search     = document.getElementById('search').value;
  const timeFilter = document.getElementById('time-filter').value;
  const visible    = filterItems(allItems, { search, timeFilter });

  document.getElementById('item-count').textContent =
    `${visible.length} item${visible.length !== 1 ? 's' : ''}`;

  const list  = document.getElementById('clip-list');
  const empty = document.getElementById('empty-state');

  // Remove existing item cards (keep #empty-state)
  list.querySelectorAll('.clip-item').forEach(el => el.remove());

  if (visible.length === 0) {
    empty.classList.remove('hidden');
    return;
  }
  empty.classList.add('hidden');

  visible.forEach(item => list.appendChild(buildItemEl(item)));
}

function buildItemEl(item) {
  const el = document.createElement('div');
  el.className = `clip-item${item.pinned ? ' pinned' : ''}`;
  el.dataset.id = item.id;

  const preview = item.type === 'image'
    ? `<img src="${item.content}" alt="clipboard image" style="max-width:100%;max-height:120px;border-radius:4px;object-fit:contain;">`
    : escapeHtml(truncate(item.content, 150));

  const badgeClass = item.type === 'note' ? 'item-badge note-badge' : 'item-badge';

  el.innerHTML = `
    <div class="item-meta">
      <span class="item-time">${formatTimestamp(item.timestamp)}</span>
      <span class="${badgeClass}">${item.type === 'note' ? '📝 note' : item.type}</span>
    </div>
    <div class="item-preview">${preview}</div>
    <div class="item-actions">
      <button class="copy-btn">📋 Copy</button>
      <button class="pin-btn ${item.pinned ? 'active' : ''}">${item.pinned ? '📌 Unpin' : '📌 Pin'}</button>
      <button class="del-btn">🗑 Delete</button>
    </div>`;

  el.querySelector('.copy-btn').addEventListener('click', () => copyItem(item));
  el.querySelector('.pin-btn').addEventListener('click', () => togglePin(item.id));
  el.querySelector('.del-btn').addEventListener('click', () => deleteItem(item.id));

  return el;
}

// ─── Item actions ─────────────────────────────────────────────────────────────
async function copyItem(item) {
  try {
    if (item.type === 'image') {
      // For base64 images, copy as text (data URL)
      await navigator.clipboard.writeText(item.content);
    } else {
      await navigator.clipboard.writeText(item.content);
    }
    toast('Copied to clipboard ✓');
  } catch (e) {
    toast('Failed to copy');
  }
}

async function deleteItem(id) {
  allItems = allItems.filter(i => i.id !== id);
  await setStorage({ clipboardItems: allItems });
  renderDashboard();
}

async function togglePin(id) {
  allItems = allItems.map(i => i.id === id ? { ...i, pinned: !i.pinned } : i);
  await setStorage({ clipboardItems: allItems });
  renderDashboard();
}

// ─── Live update from background ─────────────────────────────────────────────
chrome.storage.onChanged.addListener((changes) => {
  if (changes.clipboardItems && !document.getElementById('dashboard-screen').classList.contains('hidden')) {
    allItems = changes.clipboardItems.newValue || [];
    renderDashboard();
  }
});

// ─── Helpers ──────────────────────────────────────────────────────────────────
function escapeHtml(str) {
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// ─── Open in resizable window ─────────────────────────────────────────────────
document.getElementById('open-window-btn').addEventListener('click', () => {
  chrome.windows.create({
    url:    chrome.runtime.getURL('popup.html?mode=window'),
    type:   'popup',
    width:  500,
    height: 680
  });
  window.close();
});

// ─── Boot ─────────────────────────────────────────────────────────────────────
if (new URLSearchParams(location.search).get('mode') === 'window') {
  document.body.classList.add('window-mode');
  // Hide the expand button when already in a window
  document.getElementById('open-window-btn').style.display = 'none';
}

init();

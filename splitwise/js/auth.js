// js/auth.js — Local authentication using chrome.storage.local + SubtleCrypto
window.Auth = (() => {
  let _locked = true;
  let _autoLockTimer = null;
  let _autoLockMinutes = 5;

  async function hash(str) {
    const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(str));
    return Array.from(new Uint8Array(buf)).map(b => b.toString(16).padStart(2, '0')).join('');
  }

  function storageGet(keys) {
    return new Promise((resolve) => chrome.storage.local.get(keys, resolve));
  }

  function storageSet(data) {
    return new Promise((resolve) => chrome.storage.local.set(data, resolve));
  }

  async function isSetup() {
    const data = await storageGet(['fs_setup']);
    return !!data.fs_setup;
  }

  async function setup(username, password, pin, question, answer) {
    const [pwHash, pinHash, ansHash] = await Promise.all([
      hash(password),
      hash(pin),
      hash(answer.toLowerCase().trim())
    ]);
    await storageSet({
      fs_setup: true,
      fs_username: username,
      fs_passwordHash: pwHash,
      fs_pinHash: pinHash,
      fs_securityQuestion: question,
      fs_securityAnswerHash: ansHash
    });
    _locked = false;
  }

  async function verifyPassword(password) {
    const [data, h] = await Promise.all([
      storageGet(['fs_passwordHash']),
      hash(password)
    ]);
    return data.fs_passwordHash === h;
  }

  async function verifyPin(pin) {
    const [data, h] = await Promise.all([
      storageGet(['fs_pinHash']),
      hash(pin)
    ]);
    return data.fs_pinHash === h;
  }

  async function verifySecurityAnswer(answer) {
    const [data, h] = await Promise.all([
      storageGet(['fs_securityAnswerHash']),
      hash(answer.toLowerCase().trim())
    ]);
    return data.fs_securityAnswerHash === h;
  }

  async function getUsername() {
    const data = await storageGet(['fs_username']);
    return data.fs_username || 'User';
  }

  async function getSecurityQuestion() {
    const data = await storageGet(['fs_securityQuestion']);
    return data.fs_securityQuestion || '';
  }

  async function updatePin(newPin) {
    const h = await hash(newPin);
    await storageSet({ fs_pinHash: h });
  }

  function isLocked() {
    return _locked;
  }

  function lock() {
    _locked = true;
    if (_autoLockTimer) { clearTimeout(_autoLockTimer); _autoLockTimer = null; }
  }

  function unlock() {
    _locked = false;
  }

  function startAutoLock(minutes) {
    _autoLockMinutes = minutes;
    if (_autoLockTimer) clearTimeout(_autoLockTimer);
    if (!minutes || minutes === 0) return;
    _autoLockTimer = setTimeout(() => {
      Auth.lock();
      if (window.App) App.navigate('lock');
    }, minutes * 60 * 1000);
  }

  function resetTimer() {
    if (!_locked && _autoLockMinutes && _autoLockMinutes > 0) {
      startAutoLock(_autoLockMinutes);
    }
  }

  async function getSettings() {
    const data = await storageGet(['fs_settings']);
    return data.fs_settings || { theme: 'light', autoLockMinutes: 5, currency: 'INR' };
  }

  async function saveSettings(settings) {
    await storageSet({ fs_settings: settings });
  }

  return {
    hash,
    isSetup,
    setup,
    verifyPassword,
    verifyPin,
    verifySecurityAnswer,
    getUsername,
    getSecurityQuestion,
    updatePin,
    isLocked,
    lock,
    unlock,
    startAutoLock,
    resetTimer,
    getSettings,
    saveSettings
  };
})();

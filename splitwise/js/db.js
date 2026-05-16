// js/db.js — IndexedDB wrapper for FairSplit Local
window.DB = (() => {
  const DB_NAME = 'fairsplit';
  const DB_VERSION = 1;
  let _db = null;

  function open() {
    return new Promise((resolve, reject) => {
      if (_db) { resolve(_db); return; }
      const req = indexedDB.open(DB_NAME, DB_VERSION);

      req.onupgradeneeded = (e) => {
        const db = e.target.result;

        // groups
        if (!db.objectStoreNames.contains('groups')) {
          db.createObjectStore('groups', { keyPath: 'id' });
        }

        // members
        if (!db.objectStoreNames.contains('members')) {
          const ms = db.createObjectStore('members', { keyPath: 'id' });
          ms.createIndex('groupId', 'groupId', { unique: false });
        }

        // expenses
        if (!db.objectStoreNames.contains('expenses')) {
          const es = db.createObjectStore('expenses', { keyPath: 'id' });
          es.createIndex('groupId', 'groupId', { unique: false });
        }

        // expense_splits
        if (!db.objectStoreNames.contains('expense_splits')) {
          const ss = db.createObjectStore('expense_splits', { keyPath: 'id' });
          ss.createIndex('expenseId', 'expenseId', { unique: false });
        }

        // settlements
        if (!db.objectStoreNames.contains('settlements')) {
          const st = db.createObjectStore('settlements', { keyPath: 'id' });
          st.createIndex('groupId', 'groupId', { unique: false });
        }

        // activity_log
        if (!db.objectStoreNames.contains('activity_log')) {
          db.createObjectStore('activity_log', { keyPath: 'id' });
        }
      };

      req.onsuccess = (e) => {
        _db = e.target.result;
        resolve(_db);
      };

      req.onerror = (e) => reject(e.target.error);
    });
  }

  function getAll(store, indexName, key) {
    return new Promise((resolve, reject) => {
      const tx = _db.transaction(store, 'readonly');
      const os = tx.objectStore(store);
      let req;
      if (indexName && key !== undefined) {
        const idx = os.index(indexName);
        req = idx.getAll(key);
      } else {
        req = os.getAll();
      }
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  }

  function get(store, id) {
    return new Promise((resolve, reject) => {
      const tx = _db.transaction(store, 'readonly');
      const os = tx.objectStore(store);
      const req = os.get(id);
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  }

  function put(store, data) {
    return new Promise((resolve, reject) => {
      const tx = _db.transaction(store, 'readwrite');
      const os = tx.objectStore(store);
      const req = os.put(data);
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  }

  function del(store, id) {
    return new Promise((resolve, reject) => {
      const tx = _db.transaction(store, 'readwrite');
      const os = tx.objectStore(store);
      const req = os.delete(id);
      req.onsuccess = () => resolve();
      req.onerror = () => reject(req.error);
    });
  }

  function clear(store) {
    return new Promise((resolve, reject) => {
      const tx = _db.transaction(store, 'readwrite');
      const os = tx.objectStore(store);
      const req = os.clear();
      req.onsuccess = () => resolve();
      req.onerror = () => reject(req.error);
    });
  }

  function uuid() {
    return crypto.randomUUID();
  }

  function now() {
    return new Date().toISOString();
  }

  async function exportAll() {
    const [groups, members, expenses, splits, settlements, activity] = await Promise.all([
      getAll('groups'),
      getAll('members'),
      getAll('expenses'),
      getAll('expense_splits'),
      getAll('settlements'),
      getAll('activity_log')
    ]);
    return { groups, members, expenses, splits, settlements, activity };
  }

  async function importAll(data) {
    const stores = ['groups', 'members', 'expenses', 'expense_splits', 'settlements', 'activity_log'];
    const keys = ['groups', 'members', 'expenses', 'splits', 'settlements', 'activity'];
    for (let i = 0; i < stores.length; i++) {
      await clear(stores[i]);
      const items = data[keys[i]] || [];
      for (const item of items) {
        await put(stores[i], item);
      }
    }
  }

  async function clearAllData() {
    const stores = ['groups', 'members', 'expenses', 'expense_splits', 'settlements', 'activity_log'];
    for (const store of stores) {
      await clear(store);
    }
  }

  return { open, getAll, get, put, del, clear, uuid, now, exportAll, importAll, clearAllData };
})();

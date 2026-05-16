// js/app.js — Main application controller for FairSplit Local
window.App = (() => {
  let _currentScreen = null;
  let _currentParams = {};

  const GROUP_CATEGORIES = [
    { key: 'trip', label: 'Trip', icon: '🧳' },
    { key: 'home', label: 'Home', icon: '🏠' },
    { key: 'friends', label: 'Friends', icon: '👫' },
    { key: 'office', label: 'Office', icon: '💼' },
    { key: 'family', label: 'Family', icon: '👨‍👩‍👧' },
    { key: 'other', label: 'Other', icon: '📦' }
  ];

  const EXPENSE_CATEGORIES = [
    { key: 'food', label: 'Food', icon: '🍕' },
    { key: 'travel', label: 'Travel', icon: '✈️' },
    { key: 'housing', label: 'Housing', icon: '🏠' },
    { key: 'entertainment', label: 'Entertainment', icon: '🎬' },
    { key: 'shopping', label: 'Shopping', icon: '🛍️' },
    { key: 'other', label: 'Other', icon: '📦' }
  ];

  const SECURITY_QUESTIONS = [
    "Mother's maiden name",
    "First pet name",
    "Childhood nickname",
    "Favorite teacher"
  ];

  function $(sel, ctx) { return (ctx || document).querySelector(sel); }
  function $$(sel, ctx) { return Array.from((ctx || document).querySelectorAll(sel)); }

  function el(tag, attrs, ...children) {
    const e = document.createElement(tag);
    if (attrs) {
      for (const [k, v] of Object.entries(attrs)) {
        if (k === 'className') e.className = v;
        else if (k === 'style') Object.assign(e.style, v);
        else if (k.startsWith('on')) e.addEventListener(k.slice(2).toLowerCase(), v);
        else e.setAttribute(k, v);
      }
    }
    for (const child of children) {
      if (child === null || child === undefined) continue;
      if (typeof child === 'string') e.appendChild(document.createTextNode(child));
      else e.appendChild(child);
    }
    return e;
  }

  function html(str) {
    const d = document.createElement('div');
    d.innerHTML = str;
    return d;
  }

  function showToast(msg, type = 'info') {
    const existing = $('.toast');
    if (existing) existing.remove();
    const t = el('div', { className: `toast toast-${type}` }, msg);
    document.body.appendChild(t);
    setTimeout(() => t.classList.add('show'), 10);
    setTimeout(() => { t.classList.remove('show'); setTimeout(() => t.remove(), 300); }, 3000);
  }

  function showConfirm(msg) {
    return new Promise((resolve) => {
      const overlay = el('div', { className: 'modal-overlay' });
      const box = el('div', { className: 'modal-box' },
        el('p', { className: 'modal-msg' }, msg),
        el('div', { className: 'modal-actions' },
          el('button', { className: 'btn btn-secondary', onClick: () => { overlay.remove(); resolve(false); } }, 'Cancel'),
          el('button', { className: 'btn btn-danger', onClick: () => { overlay.remove(); resolve(true); } }, 'Confirm')
        )
      );
      overlay.appendChild(box);
      document.body.appendChild(overlay);
    });
  }

  async function logActivity(type, message, extras = {}) {
    await DB.put('activity_log', {
      id: DB.uuid(),
      type,
      message,
      groupId: extras.groupId || null,
      expenseId: extras.expenseId || null,
      settlementId: extras.settlementId || null,
      createdAt: DB.now()
    });
  }

  function navigate(screen, params = {}) {
    _currentScreen = screen;
    _currentParams = params;
    render();
  }

  function render() {
    const app = $('#app');
    app.innerHTML = '';
    const screens = {
      setup: renderSetup,
      lock: renderLock,
      dashboard: renderDashboard,
      groups: renderGroups,
      'group-detail': renderGroupDetail,
      'add-expense': renderAddExpense,
      'expense-detail': renderExpenseDetail,
      'settle-up': renderSettleUp,
      'person-view': renderPersonView,
      'simplify-global': renderSimplifyGlobal,
      activity: renderActivity,
      settings: renderSettings,
      'add-group': renderAddGroup,
      'add-member': renderAddMember
    };
    const fn = screens[_currentScreen];
    if (fn) fn(_currentParams);
    else app.textContent = 'Unknown screen: ' + _currentScreen;
  }

  // ───────────────────────────────────────────────────────────
  // BOTTOM NAV
  // ───────────────────────────────────────────────────────────
  function renderBottomNav(active) {
    const tabs = [
      { key: 'dashboard', icon: '🏠', label: 'Home' },
      { key: 'groups', icon: '👥', label: 'Groups' },
      { key: 'activity', icon: '📋', label: 'Activity' },
      { key: 'settings', icon: '⚙️', label: 'Settings' }
    ];
    const nav = el('nav', { className: 'bottom-nav' });
    for (const tab of tabs) {
      const btn = el('button', {
        className: 'nav-tab' + (active === tab.key ? ' active' : ''),
        onClick: () => navigate(tab.key)
      },
        el('span', { className: 'nav-icon' }, tab.icon),
        el('span', { className: 'nav-label' }, tab.label)
      );
      nav.appendChild(btn);
    }
    return nav;
  }

  function renderBackHeader(title, backScreen, backParams) {
    return el('div', { className: 'screen-header' },
      el('button', { className: 'back-btn', onClick: () => navigate(backScreen, backParams) }, '←'),
      el('h2', { className: 'screen-title' }, title)
    );
  }

  // ───────────────────────────────────────────────────────────
  // SETUP SCREEN
  // ───────────────────────────────────────────────────────────
  function renderSetup() {
    const app = $('#app');
    app.className = 'screen-setup';

    const form = el('div', { className: 'setup-form' });

    const logoArea = el('div', { className: 'setup-logo' },
      el('div', { className: 'logo-icon' }, '💸'),
      el('h1', {}, 'FairSplit Local'),
      el('p', { className: 'text-muted' }, 'Set up your local account')
    );

    const usernameInput = el('input', { type: 'text', placeholder: 'Username', className: 'form-input', id: 'su-username' });
    const passwordInput = el('input', { type: 'password', placeholder: 'Password', className: 'form-input', id: 'su-password' });
    const confirmPwInput = el('input', { type: 'password', placeholder: 'Confirm Password', className: 'form-input' });
    const pinInput = el('input', { type: 'password', placeholder: '4-digit PIN', className: 'form-input', maxlength: '4', pattern: '[0-9]{4}' });
    const confirmPinInput = el('input', { type: 'password', placeholder: 'Confirm PIN', className: 'form-input', maxlength: '4' });

    const questionSel = el('select', { className: 'form-input' });
    questionSel.appendChild(el('option', { value: '' }, 'Select security question…'));
    for (const q of SECURITY_QUESTIONS) {
      questionSel.appendChild(el('option', { value: q }, q));
    }

    const answerInput = el('input', { type: 'text', placeholder: 'Security answer', className: 'form-input' });
    const errDiv = el('div', { className: 'form-error hidden' });

    const submitBtn = el('button', { className: 'btn btn-primary btn-full', onClick: async () => {
      const username = usernameInput.value.trim();
      const password = passwordInput.value;
      const confirmPw = confirmPwInput.value;
      const pin = pinInput.value.trim();
      const confirmPin = confirmPinInput.value.trim();
      const question = questionSel.value;
      const answer = answerInput.value.trim();

      const errors = [];
      if (!username) errors.push('Username is required.');
      if (password.length < 6) errors.push('Password must be at least 6 characters.');
      if (password !== confirmPw) errors.push('Passwords do not match.');
      if (!/^\d{4}$/.test(pin)) errors.push('PIN must be exactly 4 digits.');
      if (pin !== confirmPin) errors.push('PINs do not match.');
      if (!question) errors.push('Please select a security question.');
      if (!answer) errors.push('Security answer is required.');

      if (errors.length) {
        errDiv.textContent = errors.join(' ');
        errDiv.classList.remove('hidden');
        return;
      }

      errDiv.classList.add('hidden');
      await Auth.setup(username, password, pin, question, answer);
      await logActivity('setup', 'Account set up successfully');
      navigate('dashboard');
    }}, 'Create Account');

    form.append(logoArea,
      el('div', { className: 'form-group' }, el('label', {}, 'Username'), usernameInput),
      el('div', { className: 'form-group' }, el('label', {}, 'Password'), passwordInput),
      el('div', { className: 'form-group' }, el('label', {}, 'Confirm Password'), confirmPwInput),
      el('div', { className: 'form-group' }, el('label', {}, 'PIN (4 digits)'), pinInput),
      el('div', { className: 'form-group' }, el('label', {}, 'Confirm PIN'), confirmPinInput),
      el('div', { className: 'form-group' }, el('label', {}, 'Security Question'), questionSel),
      el('div', { className: 'form-group' }, el('label', {}, 'Security Answer'), answerInput),
      errDiv,
      submitBtn
    );

    const wrapper = el('div', { className: 'setup-wrapper' }, form);
    app.appendChild(wrapper);
  }

  // ───────────────────────────────────────────────────────────
  // LOCK SCREEN
  // ───────────────────────────────────────────────────────────
  function renderLock() {
    const app = $('#app');
    app.className = 'screen-lock';

    let pinDigits = '';
    let activeTab = 'pin';

    const container = el('div', { className: 'lock-container' });

    const logoArea = el('div', { className: 'lock-logo' },
      el('div', { className: 'logo-icon' }, '🔒'),
      el('h2', {}, 'FairSplit Local'),
      el('p', { className: 'text-muted' }, 'Unlock your data')
    );

    // Tabs
    const tabBar = el('div', { className: 'lock-tabs' },
      el('button', { className: 'lock-tab active', id: 'tab-pin', onClick: () => switchTab('pin') }, 'Enter PIN'),
      el('button', { className: 'lock-tab', id: 'tab-pw', onClick: () => switchTab('password') }, 'Password Login')
    );

    // PIN panel
    const pinDots = el('div', { className: 'pin-dots' },
      el('div', { className: 'pin-dot', id: 'pd0' }),
      el('div', { className: 'pin-dot', id: 'pd1' }),
      el('div', { className: 'pin-dot', id: 'pd2' }),
      el('div', { className: 'pin-dot', id: 'pd3' })
    );

    const pinErrDiv = el('div', { className: 'pin-error hidden' }, 'Incorrect PIN');

    const pinPad = el('div', { className: 'pin-pad' });
    const digits = [1,2,3,4,5,6,7,8,9,'',0,'⌫'];
    for (const d of digits) {
      if (d === '') {
        pinPad.appendChild(el('div', { className: 'pin-key pin-empty' }));
      } else if (d === '⌫') {
        const k = el('button', { className: 'pin-key pin-back', onClick: () => {
          pinDigits = pinDigits.slice(0, -1);
          updatePinDots();
        }}, '⌫');
        pinPad.appendChild(k);
      } else {
        const k = el('button', { className: 'pin-key', onClick: () => pressPin(String(d)) }, String(d));
        pinPad.appendChild(k);
      }
    }

    function updatePinDots() {
      for (let i = 0; i < 4; i++) {
        const dot = $(`#pd${i}`, container);
        if (dot) dot.className = 'pin-dot' + (i < pinDigits.length ? ' filled' : '');
      }
    }

    async function pressPin(d) {
      if (pinDigits.length >= 4) return;
      pinDigits += d;
      updatePinDots();
      pinErrDiv.classList.add('hidden');
      if (pinDigits.length === 4) {
        const ok = await Auth.verifyPin(pinDigits);
        if (ok) {
          Auth.unlock();
          const settings = await Auth.getSettings();
          Auth.startAutoLock(settings.autoLockMinutes || 5);
          await logActivity('unlock', 'App unlocked with PIN');
          navigate('dashboard');
        } else {
          pinErrDiv.classList.remove('hidden');
          pinErrDiv.classList.add('shake');
          setTimeout(() => pinErrDiv.classList.remove('shake'), 500);
          pinDigits = '';
          updatePinDots();
        }
      }
    }

    const forgotLink = el('button', { className: 'link-btn', onClick: () => showForgotPin() }, 'Forgot PIN?');

    const pinPanel = el('div', { className: 'lock-panel', id: 'panel-pin' },
      pinDots,
      pinErrDiv,
      pinPad,
      forgotLink
    );

    // Password panel
    const pwUserInput = el('input', { type: 'text', className: 'form-input', placeholder: 'Username' });
    const pwPassInput = el('input', { type: 'password', className: 'form-input', placeholder: 'Password' });
    const pwErrDiv = el('div', { className: 'form-error hidden' });

    const pwSubmit = el('button', { className: 'btn btn-primary btn-full', onClick: async () => {
      const ok = await Auth.verifyPassword(pwPassInput.value);
      if (ok) {
        Auth.unlock();
        const settings = await Auth.getSettings();
        Auth.startAutoLock(settings.autoLockMinutes || 5);
        await logActivity('unlock', 'App unlocked with password');
        navigate('dashboard');
      } else {
        pwErrDiv.textContent = 'Incorrect password.';
        pwErrDiv.classList.remove('hidden');
      }
    }}, 'Unlock');

    const pwPanel = el('div', { className: 'lock-panel hidden', id: 'panel-pw' },
      el('div', { className: 'form-group' }, el('label', {}, 'Username'), pwUserInput),
      el('div', { className: 'form-group' }, el('label', {}, 'Password'), pwPassInput),
      pwErrDiv,
      pwSubmit
    );

    function switchTab(tab) {
      activeTab = tab;
      const pinTab = $('#tab-pin', container);
      const pwTab = $('#tab-pw', container);
      const pinPanel2 = $('#panel-pin', container);
      const pwPanel2 = $('#panel-pw', container);
      if (tab === 'pin') {
        pinTab.className = 'lock-tab active';
        pwTab.className = 'lock-tab';
        pinPanel2.classList.remove('hidden');
        pwPanel2.classList.add('hidden');
      } else {
        pwTab.className = 'lock-tab active';
        pinTab.className = 'lock-tab';
        pwPanel2.classList.remove('hidden');
        pinPanel2.classList.add('hidden');
      }
    }

    // Forgot PIN modal
    async function showForgotPin() {
      const question = await Auth.getSecurityQuestion();
      const overlay = el('div', { className: 'modal-overlay' });
      const ansInput = el('input', { type: 'text', className: 'form-input', placeholder: 'Your answer' });
      const newPinInput = el('input', { type: 'password', className: 'form-input', placeholder: 'New 4-digit PIN', maxlength: '4' });
      const errD = el('div', { className: 'form-error hidden' });

      const box = el('div', { className: 'modal-box' },
        el('h3', {}, 'Reset PIN'),
        el('p', { className: 'text-muted' }, question),
        el('div', { className: 'form-group' }, el('label', {}, 'Answer'), ansInput),
        el('div', { className: 'form-group' }, el('label', {}, 'New PIN'), newPinInput),
        errD,
        el('div', { className: 'modal-actions' },
          el('button', { className: 'btn btn-secondary', onClick: () => overlay.remove() }, 'Cancel'),
          el('button', { className: 'btn btn-primary', onClick: async () => {
            const ans = ansInput.value.trim();
            const newPin = newPinInput.value.trim();
            if (!ans) { errD.textContent = 'Please enter your answer.'; errD.classList.remove('hidden'); return; }
            if (!/^\d{4}$/.test(newPin)) { errD.textContent = 'PIN must be 4 digits.'; errD.classList.remove('hidden'); return; }
            const ok = await Auth.verifySecurityAnswer(ans);
            if (!ok) { errD.textContent = 'Incorrect answer.'; errD.classList.remove('hidden'); return; }
            await Auth.updatePin(newPin);
            overlay.remove();
            showToast('PIN updated successfully!', 'success');
          }}, 'Reset PIN')
        )
      );
      overlay.appendChild(box);
      document.body.appendChild(overlay);
    }

    container.append(logoArea, tabBar, pinPanel, pwPanel);
    app.appendChild(container);
  }

  // ───────────────────────────────────────────────────────────
  // DASHBOARD
  // ───────────────────────────────────────────────────────────
  async function renderDashboard() {
    const app = $('#app');
    app.className = 'screen-main';

    const content = el('div', { className: 'screen-content' });

    // Header
    const header = el('div', { className: 'main-header' },
      el('div', { className: 'header-left' },
        el('h2', { className: 'app-title' }, '💸 FairSplit'),
        el('p', { className: 'header-sub text-muted' }, 'Local')
      ),
      el('button', { className: 'icon-btn', title: 'Lock app', onClick: async () => {
        await logActivity('lock', 'App locked manually');
        Auth.lock();
        navigate('lock');
      }}, '🔒')
    );

    // Summary cards
    const { totalOwed, totalOwe } = await Balance.calcAll();

    const summaryRow = el('div', { className: 'summary-row' },
      el('div', { className: 'summary-card card-green' },
        el('div', { className: 'summary-label' }, 'Total Owed to You'),
        el('div', { className: 'summary-amount' }, Balance.formatAmount(totalOwed))
      ),
      el('div', { className: 'summary-card card-orange' },
        el('div', { className: 'summary-label' }, 'You Owe'),
        el('div', { className: 'summary-amount' }, Balance.formatAmount(totalOwe))
      )
    );

    // Groups list
    const groups = await DB.getAll('groups');
    const groupsSection = el('div', { className: 'section' },
      el('div', { className: 'section-header' },
        el('h3', { className: 'section-title' }, 'Your Groups'),
        el('button', { className: 'link-btn', onClick: () => navigate('groups') }, 'View all')
      )
    );

    if (groups.length === 0) {
      groupsSection.appendChild(el('div', { className: 'empty-state' },
        el('div', { className: 'empty-icon' }, '👥'),
        el('p', {}, 'No groups yet'),
        el('button', { className: 'btn btn-primary btn-sm', onClick: () => navigate('add-group') }, '+ Create Group')
      ));
    } else {
      const groupList = el('div', { className: 'group-list' });
      for (const group of groups.slice(0, 4)) {
        const cat = GROUP_CATEGORIES.find(c => c.key === group.category) || GROUP_CATEGORIES[5];
        const netMap = await Balance.calcGroup(group.id);
        const members = await DB.getAll('members', 'groupId', group.id);
        let netTotal = 0;
        for (const v of netMap.values()) netTotal += v;

        const balanceClass = netTotal > 0 ? 'balance-positive' : netTotal < 0 ? 'balance-negative' : 'balance-zero';
        const balanceText = netTotal === 0 ? 'Settled' : Balance.formatAmount(Math.abs(netTotal));

        const item = el('div', { className: 'group-item', onClick: () => navigate('group-detail', { groupId: group.id }) },
          el('div', { className: 'group-icon' }, cat.icon),
          el('div', { className: 'group-info' },
            el('div', { className: 'group-name' }, group.name),
            el('div', { className: 'group-meta text-muted' }, `${members.length} member${members.length !== 1 ? 's' : ''}`)
          ),
          el('div', { className: `group-balance ${balanceClass}` }, balanceText)
        );
        groupList.appendChild(item);
      }
      groupsSection.appendChild(groupList);
    }

    // Recent expenses
    const allExpenses = await DB.getAll('expenses');
    allExpenses.sort((a, b) => b.createdAt.localeCompare(a.createdAt));
    const recentExpenses = allExpenses.slice(0, 5);

    const expSection = el('div', { className: 'section' },
      el('div', { className: 'section-header' },
        el('h3', { className: 'section-title' }, 'Recent Expenses')
      )
    );

    if (recentExpenses.length === 0) {
      expSection.appendChild(el('div', { className: 'empty-state small' },
        el('p', { className: 'text-muted' }, 'No expenses yet')
      ));
    } else {
      const expList = el('div', { className: 'expense-list' });
      for (const exp of recentExpenses) {
        const cat = EXPENSE_CATEGORIES.find(c => c.key === exp.category) || EXPENSE_CATEGORIES[5];
        const group = await DB.get('groups', exp.groupId);
        const payer = await DB.get('members', exp.paidByMemberId);
        const item = el('div', { className: 'expense-item', onClick: () => navigate('expense-detail', { expenseId: exp.id }) },
          el('div', { className: 'expense-icon' }, cat.icon),
          el('div', { className: 'expense-info' },
            el('div', { className: 'expense-title' }, exp.title),
            el('div', { className: 'expense-meta text-muted' }, `${group ? group.name : '?'} · ${payer ? payer.name : '?'} paid`)
          ),
          el('div', { className: 'expense-amount' }, Balance.formatAmount(exp.amount))
        );
        expList.appendChild(item);
      }
      expSection.appendChild(expList);
    }

    // FAB
    const fab = el('button', { className: 'fab', title: 'Add Expense', onClick: () => {
      if (groups.length === 0) {
        showToast('Create a group first!', 'warn');
        return;
      }
      navigate('add-expense', { groupId: groups[0].id });
    }}, '+');

    content.append(header, summaryRow, groupsSection, expSection);
    app.append(content, renderBottomNav('dashboard'), fab);
  }

  // ───────────────────────────────────────────────────────────
  // GROUPS SCREEN
  // ───────────────────────────────────────────────────────────
  async function renderGroups() {
    const app = $('#app');
    app.className = 'screen-main';

    const content = el('div', { className: 'screen-content' });
    const header = el('div', { className: 'main-header' },
      el('h2', { className: 'app-title' }, 'Groups'),
      el('div', { className: 'header-actions' },
        el('button', { className: 'btn btn-secondary btn-sm', onClick: () => navigate('person-view') }, '👤 Friends'),
        el('button', { className: 'btn btn-primary btn-sm', onClick: () => navigate('add-group') }, '+ New')
      )
    );

    const groups = await DB.getAll('groups');
    const list = el('div', { className: 'group-list-full' });

    if (groups.length === 0) {
      list.appendChild(el('div', { className: 'empty-state' },
        el('div', { className: 'empty-icon' }, '👥'),
        el('p', {}, 'No groups yet. Create one to start splitting expenses!'),
        el('button', { className: 'btn btn-primary', onClick: () => navigate('add-group') }, '+ Create Group')
      ));
    } else {
      for (const group of groups) {
        const cat = GROUP_CATEGORIES.find(c => c.key === group.category) || GROUP_CATEGORIES[5];
        const members = await DB.getAll('members', 'groupId', group.id);
        const netMap = await Balance.calcGroup(group.id);
        let netTotal = 0;
        for (const v of netMap.values()) netTotal += v;
        const balClass = netTotal > 0 ? 'balance-positive' : netTotal < 0 ? 'balance-negative' : 'balance-zero';

        const item = el('div', { className: 'group-card', onClick: () => navigate('group-detail', { groupId: group.id }) },
          el('div', { className: 'group-card-left' },
            el('div', { className: 'group-icon-lg' }, cat.icon),
            el('div', {},
              el('div', { className: 'group-name' }, group.name),
              el('div', { className: 'group-meta text-muted' }, `${cat.label} · ${members.length} member${members.length !== 1 ? 's' : ''}`)
            )
          ),
          el('div', { className: `group-balance ${balClass}` },
            netTotal === 0 ? 'Settled' : Balance.formatAmount(Math.abs(netTotal))
          )
        );
        list.appendChild(item);
      }
    }

    content.append(header, list);
    app.append(content, renderBottomNav('groups'));
  }

  // ───────────────────────────────────────────────────────────
  // ADD GROUP SCREEN
  // ───────────────────────────────────────────────────────────
  function renderAddGroup({ groupId } = {}) {
    const app = $('#app');
    app.className = 'screen-main';

    const isEdit = !!groupId;
    const content = el('div', { className: 'screen-content' });
    const header = renderBackHeader(isEdit ? 'Edit Group' : 'New Group', 'groups');

    const nameInput = el('input', { type: 'text', className: 'form-input', placeholder: 'Group name (e.g. Goa Trip)' });
    let selectedCat = 'other';

    const catGrid = el('div', { className: 'cat-grid' });
    function buildCatGrid() {
      catGrid.innerHTML = '';
      for (const cat of GROUP_CATEGORIES) {
        const btn = el('button', {
          className: 'cat-btn' + (selectedCat === cat.key ? ' selected' : ''),
          onClick: () => { selectedCat = cat.key; buildCatGrid(); }
        },
          el('span', { className: 'cat-icon' }, cat.icon),
          el('span', { className: 'cat-label' }, cat.label)
        );
        catGrid.appendChild(btn);
      }
    }
    buildCatGrid();

    const errDiv = el('div', { className: 'form-error hidden' });

    if (isEdit) {
      DB.get('groups', groupId).then(group => {
        if (group) {
          nameInput.value = group.name;
          selectedCat = group.category || 'other';
          buildCatGrid();
        }
      });
    }

    const saveBtn = el('button', { className: 'btn btn-primary btn-full', onClick: async () => {
      const name = nameInput.value.trim();
      if (!name) { errDiv.textContent = 'Group name is required.'; errDiv.classList.remove('hidden'); return; }

      const now = DB.now();
      if (isEdit) {
        const existing = await DB.get('groups', groupId);
        await DB.put('groups', { ...existing, name, category: selectedCat, updatedAt: now });
        await logActivity('group_edit', `Group "${name}" updated`, { groupId });
        showToast('Group updated!', 'success');
        navigate('group-detail', { groupId });
      } else {
        const id = DB.uuid();
        await DB.put('groups', { id, name, category: selectedCat, createdAt: now, updatedAt: now });
        await logActivity('group_create', `Group "${name}" created`, { groupId: id });
        showToast('Group created!', 'success');
        navigate('group-detail', { groupId: id });
      }
    }}, isEdit ? 'Save Changes' : 'Create Group');

    content.append(header,
      el('div', { className: 'form-group' }, el('label', {}, 'Group Name'), nameInput),
      el('div', { className: 'form-group' }, el('label', {}, 'Category'), catGrid),
      errDiv,
      saveBtn
    );
    app.appendChild(content);
  }

  // ───────────────────────────────────────────────────────────
  // GROUP DETAIL SCREEN
  // ───────────────────────────────────────────────────────────
  async function renderGroupDetail({ groupId }) {
    const app = $('#app');
    app.className = 'screen-main';

    const group = await DB.get('groups', groupId);
    if (!group) { navigate('groups'); return; }

    const cat = GROUP_CATEGORIES.find(c => c.key === group.category) || GROUP_CATEGORIES[5];
    let activeTab = 'expenses';

    const content = el('div', { className: 'screen-content' });
    const header = el('div', { className: 'screen-header' },
      el('button', { className: 'back-btn', onClick: () => navigate('groups') }, '←'),
      el('div', { className: 'group-detail-title' },
        el('span', {}, cat.icon + ' ' + group.name)
      ),
      el('button', { className: 'icon-btn', onClick: () => navigate('add-group', { groupId }) }, '✏️')
    );

    const tabs = ['expenses', 'members', 'balances', 'settle'];
    const tabLabels = { expenses: 'Expenses', members: 'Members', balances: 'Balances', settle: 'Settle' };
    const tabBar = el('div', { className: 'detail-tabs' });
    const tabContent = el('div', { className: 'tab-content' });

    async function renderTabContent() {
      tabContent.innerHTML = '';
      // rebuild tab bar
      tabBar.innerHTML = '';
      for (const t of tabs) {
        const btn = el('button', {
          className: 'detail-tab' + (activeTab === t ? ' active' : ''),
          onClick: () => { activeTab = t; renderTabContent(); }
        }, tabLabels[t]);
        tabBar.appendChild(btn);
      }

      if (activeTab === 'expenses') {
        await renderExpensesTab(tabContent, groupId);
      } else if (activeTab === 'members') {
        await renderMembersTab(tabContent, groupId);
      } else if (activeTab === 'balances') {
        await renderBalancesTab(tabContent, groupId);
      } else if (activeTab === 'settle') {
        await renderSettleTab(tabContent, groupId);
      }
    }

    await renderTabContent();

    // Delete group button
    const deleteBtn = el('button', { className: 'btn btn-danger btn-sm', onClick: async () => {
      const ok = await showConfirm(`Delete group "${group.name}"? All expenses and members will be removed.`);
      if (!ok) return;
      const members = await DB.getAll('members', 'groupId', groupId);
      const expenses = await DB.getAll('expenses', 'groupId', groupId);
      const settlements = await DB.getAll('settlements', 'groupId', groupId);

      for (const m of members) await DB.del('members', m.id);
      for (const e of expenses) {
        const splits = await DB.getAll('expense_splits', 'expenseId', e.id);
        for (const s of splits) await DB.del('expense_splits', s.id);
        await DB.del('expenses', e.id);
      }
      for (const s of settlements) await DB.del('settlements', s.id);
      await DB.del('groups', groupId);
      await logActivity('group_delete', `Group "${group.name}" deleted`);
      showToast('Group deleted', 'info');
      navigate('groups');
    }}, '🗑️ Delete Group');

    content.append(header, tabBar, tabContent, el('div', { className: 'delete-section' }, deleteBtn));
    app.appendChild(content);
  }

  async function renderExpensesTab(container, groupId) {
    const expenses = await DB.getAll('expenses', 'groupId', groupId);
    expenses.sort((a, b) => b.date.localeCompare(a.date));

    const addBtn = el('button', { className: 'btn btn-primary btn-full', onClick: () => navigate('add-expense', { groupId }) }, '+ Add Expense');

    if (expenses.length === 0) {
      container.append(addBtn, el('div', { className: 'empty-state' },
        el('div', { className: 'empty-icon' }, '💰'),
        el('p', {}, 'No expenses yet')
      ));
      return;
    }

    const list = el('div', { className: 'expense-list' });
    for (const exp of expenses) {
      const cat = EXPENSE_CATEGORIES.find(c => c.key === exp.category) || EXPENSE_CATEGORIES[5];
      const payer = await DB.get('members', exp.paidByMemberId);
      const item = el('div', { className: 'expense-item', onClick: () => navigate('expense-detail', { expenseId: exp.id, fromGroupId: groupId }) },
        el('div', { className: 'expense-icon' }, cat.icon),
        el('div', { className: 'expense-info' },
          el('div', { className: 'expense-title' }, exp.title),
          el('div', { className: 'expense-meta text-muted' }, `${payer ? payer.name : '?'} paid · ${formatDate(exp.date)}`)
        ),
        el('div', { className: 'expense-amount' }, Balance.formatAmount(exp.amount))
      );
      list.appendChild(item);
    }

    container.append(addBtn, list);
  }

  async function renderMembersTab(container, groupId) {
    const members = await DB.getAll('members', 'groupId', groupId);
    const netMap = await Balance.calcGroup(groupId);

    const addBtn = el('button', { className: 'btn btn-primary btn-full', onClick: () => navigate('add-member', { groupId }) }, '+ Add Member');

    if (members.length === 0) {
      container.append(addBtn, el('div', { className: 'empty-state' },
        el('div', { className: 'empty-icon' }, '👤'),
        el('p', {}, 'No members yet')
      ));
      return;
    }

    const list = el('div', { className: 'member-list' });
    for (const member of members) {
      const net = netMap.get(member.id) || 0;
      const balClass = net > 0 ? 'balance-positive' : net < 0 ? 'balance-negative' : 'balance-zero';
      const balText = net === 0 ? 'Settled' : (net > 0 ? 'Gets back ' : 'Owes ') + Balance.formatAmount(Math.abs(net));

      const deleteBtn = el('button', { className: 'icon-btn text-danger', title: 'Remove member', onClick: async (e) => {
        e.stopPropagation();
        if (Math.abs(net) > 1) {
          showToast('Cannot remove member with pending balance.', 'warn');
          return;
        }
        const ok = await showConfirm(`Remove ${member.name} from the group?`);
        if (!ok) return;
        await DB.del('members', member.id);
        await logActivity('member_remove', `Member "${member.name}" removed`, { groupId });
        showToast('Member removed', 'info');
        navigate('group-detail', { groupId });
      }}, '✕');

      const item = el('div', { className: 'member-item' },
        el('div', { className: 'member-avatar' }, member.name.charAt(0).toUpperCase()),
        el('div', { className: 'member-info' },
          el('div', { className: 'member-name' }, member.name),
          el('div', { className: `member-balance ${balClass}` }, balText)
        ),
        deleteBtn
      );
      list.appendChild(item);
    }

    container.append(addBtn, list);
  }

  async function renderBalancesTab(container, groupId) {
    const netMap = await Balance.calcGroup(groupId);
    const members = await DB.getAll('members', 'groupId', groupId);
    const memberMap = {};
    for (const m of members) memberMap[m.id] = m;

    const transactions = Balance.simplify(netMap);

    if (transactions.length === 0) {
      container.appendChild(el('div', { className: 'empty-state' },
        el('div', { className: 'empty-icon' }, '✅'),
        el('p', {}, 'All settled up!')
      ));
      return;
    }

    const list = el('div', { className: 'balance-list' });
    for (const tx of transactions) {
      const fromM = memberMap[tx.from];
      const toM = memberMap[tx.to];
      const item = el('div', { className: 'balance-row' },
        el('div', { className: 'balance-from' },
          el('div', { className: 'member-avatar sm' }, fromM ? fromM.name.charAt(0) : '?'),
          el('span', {}, fromM ? fromM.name : '?')
        ),
        el('div', { className: 'balance-arrow' },
          el('span', { className: 'balance-amt text-danger' }, '→ ' + Balance.formatAmount(tx.amount))
        ),
        el('div', { className: 'balance-to' },
          el('div', { className: 'member-avatar sm' }, toM ? toM.name.charAt(0) : '?'),
          el('span', {}, toM ? toM.name : '?')
        )
      );
      list.appendChild(item);
    }
    container.appendChild(list);
  }

  async function renderSettleTab(container, groupId) {
    const [netMap, members, settlements] = await Promise.all([
      Balance.calcGroup(groupId),
      DB.getAll('members', 'groupId', groupId),
      DB.getAll('settlements', 'groupId', groupId)
    ]);
    const memberMap = {};
    for (const m of members) memberMap[m.id] = m;

    const pairwiseDebts = await Balance.calcPairwise(groupId);
    const simplified    = Balance.simplify(netMap);
    const origCount     = pairwiseDebts.length;
    const simpCount     = simplified.length;
    const saved         = origCount - simpCount;

    settlements.sort((a, b) => b.createdAt.localeCompare(a.createdAt));

    const recordBtn = el('button', { className: 'btn btn-primary btn-full', onClick: () => navigate('settle-up', { groupId }) }, '+ Record Payment');

    // ── Summary card ──
    let summaryCard;
    if (origCount === 0) {
      summaryCard = el('div', { className: 'settle-all-good' },
        el('div', { className: 'empty-icon' }, '✅'),
        el('p', {}, 'All settled up!')
      );
    } else {
      const badge = saved > 0
        ? el('span', { className: 'simplify-badge' }, `✨ ${saved} fewer payment${saved !== 1 ? 's' : ''}`)
        : el('span', { className: 'simplify-badge badge-neutral' }, 'Already optimal');

      summaryCard = el('div', { className: 'simplify-header-card' },
        el('div', { className: 'simplify-title-row' },
          el('span', { className: 'simplify-title' }, '🔀 Simplify Debts'),
          badge
        ),
        el('div', { className: 'simplify-count-row' },
          el('span', { className: 'text-muted' }, 'Original: '),
          el('span', { className: 'count-num' }, String(origCount)),
          el('span', { className: 'text-muted' }, ' payments → Simplified: '),
          el('span', { className: 'count-num accent' }, String(simpCount))
        )
      );
    }

    // ── View toggle ──
    const tabsRow    = el('div', { className: 'simplify-tabs' });
    const simpTab    = el('button', { className: 'simplify-tab active' }, `Simplified (${simpCount})`);
    const origTab    = el('button', { className: 'simplify-tab' }, `Original (${origCount})`);
    tabsRow.append(simpTab, origTab);

    const paymentsList = el('div', { className: 'payments-list' });

    function makePaymentRow(tx, isSimplified) {
      const fromM    = memberMap[tx.from];
      const toM      = memberMap[tx.to];
      const fromName = fromM ? fromM.name : (tx.from || '?');
      const toName   = toM  ? toM.name   : (tx.to   || '?');

      const recordBtn = (fromM && toM)
        ? el('button', {
            className: 'btn-record',
            onClick: () => navigate('settle-up', {
              groupId,
              prefill: {
                payerId: tx.from,
                receiverId: tx.to,
                amountPaise: tx.amount,
                notes: isSimplified && saved > 0 ? 'Simplified settlement' : ''
              }
            })
          }, '⚡ Record')
        : null;

      return el('div', { className: 'suggestion-row' },
        el('div', { className: 'suggestion-left' },
          el('span', { className: 'suggestion-text' }, `${fromName} → ${toName}`),
          isSimplified && saved > 0
            ? el('span', { className: 'suggestion-label' }, 'simplified')
            : null
        ),
        el('div', { className: 'suggestion-right' },
          el('span', { className: 'suggestion-amt text-danger' }, Balance.formatAmount(tx.amount)),
          recordBtn
        )
      );
    }

    function switchView(isSimplified) {
      paymentsList.innerHTML = '';
      simpTab.classList.toggle('active', isSimplified);
      origTab.classList.toggle('active', !isSimplified);
      const list = isSimplified ? simplified : pairwiseDebts;
      if (list.length === 0) {
        paymentsList.appendChild(el('div', { className: 'settle-all-good' },
          el('div', { className: 'empty-icon' }, '✅'), el('p', {}, 'All settled up!')
        ));
      } else {
        for (const tx of list) paymentsList.appendChild(makePaymentRow(tx, isSimplified));
      }
    }

    simpTab.addEventListener('click', () => switchView(true));
    origTab.addEventListener('click', () => switchView(false));
    switchView(true);

    // ── Past settlements ──
    const pastSection = el('div');
    if (settlements.length > 0) {
      pastSection.appendChild(el('h4', { className: 'sub-title' }, 'Past Settlements'));
      for (const s of settlements) {
        const payer    = memberMap[s.payerMemberId];
        const receiver = memberMap[s.receiverMemberId];
        const delBtn   = el('button', { className: 'icon-btn text-danger', onClick: async (e) => {
          e.stopPropagation();
          if (!await showConfirm('Delete this settlement?')) return;
          await DB.del('settlements', s.id);
          await logActivity('settlement_delete', `Settlement of ${Balance.formatAmount(s.amount)} deleted`, { groupId, settlementId: s.id });
          showToast('Settlement deleted', 'info');
          navigate('group-detail', { groupId });
        }}, '✕');

        pastSection.appendChild(el('div', { className: 'settlement-item' },
          el('div', { className: 'settlement-info' },
            el('div', { className: 'settlement-text' }, `${payer ? payer.name : '?'} paid ${receiver ? receiver.name : '?'}`),
            el('div', { className: 'settlement-meta text-muted' }, `${formatDate(s.date)}${s.notes ? ' · ' + s.notes : ''}`)
          ),
          el('div', { className: 'settlement-right' },
            el('div', { className: 'settlement-amt balance-positive' }, Balance.formatAmount(s.amount)),
            delBtn
          )
        ));
      }
    }

    container.append(recordBtn, summaryCard, tabsRow, paymentsList, pastSection);
  }

  // ───────────────────────────────────────────────────────────
  // ADD MEMBER SCREEN
  // ───────────────────────────────────────────────────────────
  function renderAddMember({ groupId }) {
    const app = $('#app');
    app.className = 'screen-main';
    const content = el('div', { className: 'screen-content' });
    const header = renderBackHeader('Add Member', 'group-detail', { groupId });

    const nameInput = el('input', { type: 'text', className: 'form-input', placeholder: 'Member name' });
    const errDiv = el('div', { className: 'form-error hidden' });

    const saveBtn = el('button', { className: 'btn btn-primary btn-full', onClick: async () => {
      const name = nameInput.value.trim();
      if (!name) { errDiv.textContent = 'Name is required.'; errDiv.classList.remove('hidden'); return; }
      const now = DB.now();
      const id = DB.uuid();
      await DB.put('members', { id, groupId, name, createdAt: now, updatedAt: now });
      await logActivity('member_add', `Member "${name}" added`, { groupId });
      showToast('Member added!', 'success');
      navigate('group-detail', { groupId });
    }}, 'Add Member');

    content.append(header,
      el('div', { className: 'form-group' }, el('label', {}, 'Name'), nameInput),
      errDiv,
      saveBtn
    );
    app.appendChild(content);
  }

  // ───────────────────────────────────────────────────────────
  // ADD / EDIT EXPENSE SCREEN
  // ───────────────────────────────────────────────────────────
  async function renderAddExpense({ groupId, expenseId } = {}) {
    const app = $('#app');
    app.className = 'screen-main';

    const isEdit = !!expenseId;
    let existingExpense = null;
    let existingSplits = [];

    if (isEdit) {
      existingExpense = await DB.get('expenses', expenseId);
      if (existingExpense) groupId = existingExpense.groupId;
      existingSplits = await DB.getAll('expense_splits', 'expenseId', expenseId);
    }

    const members = await DB.getAll('members', 'groupId', groupId);
    if (members.length === 0) {
      showToast('Add members to the group first!', 'warn');
      navigate('group-detail', { groupId });
      return;
    }

    const content = el('div', { className: 'screen-content' });
    const header = renderBackHeader(isEdit ? 'Edit Expense' : 'Add Expense', 'group-detail', { groupId });

    const titleInput = el('input', { type: 'text', className: 'form-input', placeholder: 'What was this for?' });
    const amountInput = el('input', { type: 'number', className: 'form-input', placeholder: '0.00', min: '0', step: '0.01' });

    const paidBySel = el('select', { className: 'form-input' });
    for (const m of members) {
      paidBySel.appendChild(el('option', { value: m.id }, m.name));
    }

    const dateInput = el('input', { type: 'date', className: 'form-input', value: todayISO() });

    const categorySel = el('select', { className: 'form-input' });
    for (const cat of EXPENSE_CATEGORIES) {
      categorySel.appendChild(el('option', { value: cat.key }, cat.icon + ' ' + cat.label));
    }

    const notesInput = el('textarea', { className: 'form-input form-textarea', placeholder: 'Notes (optional)', rows: '2' });

    // Split type
    let splitType = 'equal';
    const splitTypeRow = el('div', { className: 'split-type-row' });
    const splitTypes = [
      { key: 'equal', label: 'Equal' },
      { key: 'exact', label: 'Exact' },
      { key: 'percentage', label: '%' },
      { key: 'shares', label: 'Shares' }
    ];

    function buildSplitTypeRow() {
      splitTypeRow.innerHTML = '';
      for (const st of splitTypes) {
        const btn = el('button', {
          className: 'split-type-btn' + (splitType === st.key ? ' active' : ''),
          onClick: () => { splitType = st.key; buildSplitTypeRow(); buildSplitFields(); }
        }, st.label);
        splitTypeRow.appendChild(btn);
      }
    }
    buildSplitTypeRow();

    // Member checkboxes & split fields
    let checkedMembers = new Set(members.map(m => m.id));
    const splitFieldsContainer = el('div', { className: 'split-fields' });

    function buildSplitFields() {
      splitFieldsContainer.innerHTML = '';
      const totalPaise = Math.round((parseFloat(amountInput.value) || 0) * 100);

      for (const m of members) {
        const checked = checkedMembers.has(m.id);
        const row = el('div', { className: 'split-member-row' });

        const chk = el('input', { type: 'checkbox', className: 'split-check', id: `chk-${m.id}` });
        chk.checked = checked;
        chk.addEventListener('change', () => {
          if (chk.checked) checkedMembers.add(m.id);
          else checkedMembers.delete(m.id);
          buildSplitFields();
        });

        const nameLabel = el('label', { for: `chk-${m.id}`, className: 'split-member-name' }, m.name);
        row.append(chk, nameLabel);

        if (checked) {
          if (splitType === 'equal') {
            const n = checkedMembers.size;
            const share = n > 0 ? Math.floor(totalPaise / n) : 0;
            const disp = el('span', { className: 'split-amount text-muted' }, Balance.formatAmount(share));
            row.appendChild(disp);
          } else if (splitType === 'exact') {
            const inp = el('input', { type: 'number', className: 'form-input split-inp', placeholder: '0.00', min: '0', step: '0.01', 'data-mid': m.id });
            const existing = existingSplits.find(s => s.memberId === m.id);
            if (existing) inp.value = (existing.amount / 100).toFixed(2);
            row.appendChild(inp);
          } else if (splitType === 'percentage') {
            const inp = el('input', { type: 'number', className: 'form-input split-inp', placeholder: '0', min: '0', max: '100', step: '0.01', 'data-mid': m.id });
            const existing = existingSplits.find(s => s.memberId === m.id);
            if (existing && existing.percentage !== undefined) inp.value = existing.percentage;
            else if (checkedMembers.size > 0) inp.value = (100 / checkedMembers.size).toFixed(2);
            row.appendChild(inp);
          } else if (splitType === 'shares') {
            const inp = el('input', { type: 'number', className: 'form-input split-inp', placeholder: '1', min: '1', step: '1', 'data-mid': m.id });
            const existing = existingSplits.find(s => s.memberId === m.id);
            if (existing && existing.shares !== undefined) inp.value = existing.shares;
            else inp.value = '1';
            row.appendChild(inp);
          }
        }

        splitFieldsContainer.appendChild(row);
      }
    }

    amountInput.addEventListener('input', buildSplitFields);
    buildSplitFields();

    // Pre-fill for edit
    if (existingExpense) {
      titleInput.value = existingExpense.title;
      amountInput.value = (existingExpense.amount / 100).toFixed(2);
      paidBySel.value = existingExpense.paidByMemberId;
      dateInput.value = existingExpense.date;
      categorySel.value = existingExpense.category || 'other';
      notesInput.value = existingExpense.notes || '';
      splitType = existingExpense.splitType || 'equal';
      checkedMembers = new Set(existingSplits.map(s => s.memberId));
      buildSplitTypeRow();
      buildSplitFields();
      // restore split inputs
      setTimeout(() => {
        for (const s of existingSplits) {
          const inp = splitFieldsContainer.querySelector(`[data-mid="${s.memberId}"]`);
          if (inp) {
            if (splitType === 'exact') inp.value = (s.amount / 100).toFixed(2);
            else if (splitType === 'percentage') inp.value = s.percentage !== undefined ? s.percentage : '';
            else if (splitType === 'shares') inp.value = s.shares !== undefined ? s.shares : '1';
          }
        }
      }, 50);
    }

    const errDiv = el('div', { className: 'form-error hidden' });

    const saveBtn = el('button', { className: 'btn btn-primary btn-full', onClick: async () => {
      const title = titleInput.value.trim();
      const amountRupees = parseFloat(amountInput.value);
      const paidBy = paidBySel.value;
      const date = dateInput.value;
      const category = categorySel.value;
      const notes = notesInput.value.trim();

      const errs = [];
      if (!title) errs.push('Title is required.');
      if (!amountRupees || amountRupees <= 0) errs.push('Amount must be positive.');
      if (!date) errs.push('Date is required.');
      if (checkedMembers.size === 0) errs.push('Select at least one member for the split.');

      if (errs.length) { errDiv.textContent = errs.join(' '); errDiv.classList.remove('hidden'); return; }

      const totalPaise = Math.round(amountRupees * 100);
      let splits = [];

      if (splitType === 'equal') {
        const n = checkedMembers.size;
        const share = Math.floor(totalPaise / n);
        const remainder = totalPaise - share * n;
        let first = true;
        for (const mid of checkedMembers) {
          splits.push({ memberId: mid, amount: share + (first ? remainder : 0) });
          first = false;
        }
      } else if (splitType === 'exact') {
        let sum = 0;
        for (const mid of checkedMembers) {
          const inp = splitFieldsContainer.querySelector(`[data-mid="${mid}"]`);
          const amt = Math.round(parseFloat(inp ? inp.value : 0) * 100) || 0;
          splits.push({ memberId: mid, amount: amt });
          sum += amt;
        }
        if (sum !== totalPaise) {
          errDiv.textContent = `Exact amounts must sum to ${Balance.formatAmount(totalPaise)} (currently ${Balance.formatAmount(sum)}).`;
          errDiv.classList.remove('hidden');
          return;
        }
      } else if (splitType === 'percentage') {
        let totalPct = 0;
        const rawPcts = [];
        for (const mid of checkedMembers) {
          const inp = splitFieldsContainer.querySelector(`[data-mid="${mid}"]`);
          const pct = parseFloat(inp ? inp.value : 0) || 0;
          rawPcts.push({ memberId: mid, pct });
          totalPct += pct;
        }
        if (Math.abs(totalPct - 100) > 0.1) {
          errDiv.textContent = `Percentages must sum to 100% (currently ${totalPct.toFixed(2)}%).`;
          errDiv.classList.remove('hidden');
          return;
        }
        let assigned = 0;
        for (let i = 0; i < rawPcts.length; i++) {
          const { memberId, pct } = rawPcts[i];
          let amt;
          if (i === rawPcts.length - 1) {
            amt = totalPaise - assigned;
          } else {
            amt = Math.round(totalPaise * pct / 100);
          }
          splits.push({ memberId, amount: amt, percentage: pct });
          assigned += amt;
        }
      } else if (splitType === 'shares') {
        let totalShares = 0;
        const rawShares = [];
        for (const mid of checkedMembers) {
          const inp = splitFieldsContainer.querySelector(`[data-mid="${mid}"]`);
          const sh = parseInt(inp ? inp.value : 1) || 1;
          rawShares.push({ memberId: mid, shares: sh });
          totalShares += sh;
        }
        let assigned = 0;
        for (let i = 0; i < rawShares.length; i++) {
          const { memberId, shares } = rawShares[i];
          let amt;
          if (i === rawShares.length - 1) {
            amt = totalPaise - assigned;
          } else {
            amt = Math.round(totalPaise * shares / totalShares);
          }
          splits.push({ memberId, amount: amt, shares });
          assigned += amt;
        }
      }

      const now = DB.now();
      let savedExpenseId = expenseId;

      if (isEdit) {
        await DB.put('expenses', {
          ...existingExpense,
          title, amount: totalPaise, paidByMemberId: paidBy,
          date, category, notes, splitType, updatedAt: now
        });
        // delete old splits
        for (const s of existingSplits) await DB.del('expense_splits', s.id);
        await logActivity('expense_edit', `Expense "${title}" updated`, { groupId, expenseId });
      } else {
        savedExpenseId = DB.uuid();
        await DB.put('expenses', {
          id: savedExpenseId, groupId, title, amount: totalPaise,
          paidByMemberId: paidBy, date, category, notes, splitType,
          createdAt: now, updatedAt: now
        });
        await logActivity('expense_add', `Expense "${title}" (${Balance.formatAmount(totalPaise)}) added`, { groupId, expenseId: savedExpenseId });
      }

      // save splits
      for (const sp of splits) {
        await DB.put('expense_splits', {
          id: DB.uuid(),
          expenseId: savedExpenseId,
          memberId: sp.memberId,
          amount: sp.amount,
          percentage: sp.percentage,
          shares: sp.shares,
          createdAt: now,
          updatedAt: now
        });
      }

      showToast(isEdit ? 'Expense updated!' : 'Expense added!', 'success');
      navigate('expense-detail', { expenseId: savedExpenseId, fromGroupId: groupId });
    }}, isEdit ? 'Save Changes' : 'Add Expense');

    content.append(header,
      el('div', { className: 'form-group' }, el('label', {}, 'Title'), titleInput),
      el('div', { className: 'form-group' }, el('label', {}, 'Amount (₹)'), amountInput),
      el('div', { className: 'form-group' }, el('label', {}, 'Paid by'), paidBySel),
      el('div', { className: 'form-group' }, el('label', {}, 'Date'), dateInput),
      el('div', { className: 'form-group' }, el('label', {}, 'Category'), categorySel),
      el('div', { className: 'form-group' }, el('label', {}, 'Notes'), notesInput),
      el('div', { className: 'form-group' },
        el('label', {}, 'Split type'),
        splitTypeRow
      ),
      el('div', { className: 'form-group' },
        el('label', {}, 'Split among'),
        splitFieldsContainer
      ),
      errDiv,
      saveBtn
    );
    app.appendChild(content);
  }

  // ───────────────────────────────────────────────────────────
  // EXPENSE DETAIL SCREEN
  // ───────────────────────────────────────────────────────────
  async function renderExpenseDetail({ expenseId, fromGroupId } = {}) {
    const app = $('#app');
    app.className = 'screen-main';

    const expense = await DB.get('expenses', expenseId);
    if (!expense) { navigate('dashboard'); return; }

    const backGroupId = fromGroupId || expense.groupId;
    const splits = await DB.getAll('expense_splits', 'expenseId', expenseId);
    const members = await DB.getAll('members', 'groupId', expense.groupId);
    const memberMap = {};
    for (const m of members) memberMap[m.id] = m;
    const payer = memberMap[expense.paidByMemberId];
    const group = await DB.get('groups', expense.groupId);
    const cat = EXPENSE_CATEGORIES.find(c => c.key === expense.category) || EXPENSE_CATEGORIES[5];

    const content = el('div', { className: 'screen-content' });
    const header = renderBackHeader('Expense Details', 'group-detail', { groupId: backGroupId });

    const card = el('div', { className: 'expense-detail-card' },
      el('div', { className: 'expense-detail-icon' }, cat.icon),
      el('h2', { className: 'expense-detail-title' }, expense.title),
      el('div', { className: 'expense-detail-amount' }, Balance.formatAmount(expense.amount)),
      el('div', { className: 'expense-detail-meta' },
        el('span', { className: 'badge' }, group ? group.name : 'Unknown group'),
        el('span', { className: 'badge badge-accent' }, cat.label),
        el('span', { className: 'badge' }, formatDate(expense.date))
      )
    );

    const payerRow = el('div', { className: 'detail-row' },
      el('span', { className: 'detail-label' }, 'Paid by'),
      el('span', { className: 'detail-value highlight' }, payer ? payer.name : '?')
    );

    const splitTitle = el('h4', { className: 'sub-title' }, 'Split breakdown');
    const splitTable = el('div', { className: 'split-table' });
    for (const s of splits) {
      const m = memberMap[s.memberId];
      splitTable.appendChild(el('div', { className: 'split-row' },
        el('div', { className: 'split-row-left' },
          el('div', { className: 'member-avatar sm' }, m ? m.name.charAt(0) : '?'),
          el('span', {}, m ? m.name : '?')
        ),
        el('div', { className: 'split-row-right' },
          el('span', { className: expense.paidByMemberId === s.memberId ? 'balance-positive' : '' },
            Balance.formatAmount(s.amount)
          )
        )
      ));
    }

    let notesEl = null;
    if (expense.notes) {
      notesEl = el('div', { className: 'detail-row' },
        el('span', { className: 'detail-label' }, 'Notes'),
        el('span', { className: 'detail-value' }, expense.notes)
      );
    }

    const actions = el('div', { className: 'expense-actions' },
      el('button', { className: 'btn btn-secondary', onClick: () => navigate('add-expense', { groupId: expense.groupId, expenseId }) }, '✏️ Edit'),
      el('button', { className: 'btn btn-danger', onClick: async () => {
        const ok = await showConfirm('Delete this expense?');
        if (!ok) return;
        const existingSplits = await DB.getAll('expense_splits', 'expenseId', expenseId);
        for (const s of existingSplits) await DB.del('expense_splits', s.id);
        await DB.del('expenses', expenseId);
        await logActivity('expense_delete', `Expense "${expense.title}" deleted`, { groupId: expense.groupId });
        showToast('Expense deleted', 'info');
        navigate('group-detail', { groupId: expense.groupId });
      }}, '🗑️ Delete')
    );

    content.append(header, card, payerRow, notesEl, splitTitle, splitTable, actions);
    app.appendChild(content);
  }

  // ───────────────────────────────────────────────────────────
  // SETTLE UP SCREEN
  // ───────────────────────────────────────────────────────────
  async function renderSettleUp({ groupId, prefill = {} } = {}) {
    const app = $('#app');
    app.className = 'screen-main';

    const groups = await DB.getAll('groups');
    let targetGroupId = groupId || (groups.length > 0 ? groups[0].id : null);

    if (!targetGroupId) {
      navigate('groups');
      return;
    }

    const content = el('div', { className: 'screen-content' });
    const header = renderBackHeader('Record Payment', 'group-detail', { groupId: targetGroupId });

    const members = await DB.getAll('members', 'groupId', targetGroupId);
    if (members.length < 2) {
      content.append(header, el('div', { className: 'empty-state' },
        el('p', {}, 'Need at least 2 members to record a settlement.')
      ));
      app.appendChild(content);
      return;
    }

    const payerSel = el('select', { className: 'form-input' });
    const receiverSel = el('select', { className: 'form-input' });
    for (const m of members) {
      payerSel.appendChild(el('option', { value: m.id }, m.name));
      receiverSel.appendChild(el('option', { value: m.id }, m.name));
    }
    // Apply pre-fill or defaults
    if (prefill.payerId) payerSel.value = prefill.payerId;
    if (prefill.receiverId) receiverSel.value = prefill.receiverId;
    else if (members.length > 1) receiverSel.value = members[1].id;

    const amountInput = el('input', { type: 'number', className: 'form-input', placeholder: '0.00', min: '0', step: '0.01' });
    if (prefill.amountPaise) amountInput.value = (prefill.amountPaise / 100).toFixed(2);

    const dateInput = el('input', { type: 'date', className: 'form-input', value: todayISO() });
    const notesInput = el('input', { type: 'text', className: 'form-input', placeholder: 'Notes (optional)' });
    if (prefill.notes) notesInput.value = prefill.notes;

    if (prefill.amountPaise || prefill.payerId) {
      const prefillBanner = el('div', { className: 'prefill-banner' }, '⚡ Pre-filled from simplified debt suggestion');
      content.appendChild(prefillBanner);
    }
    const errDiv = el('div', { className: 'form-error hidden' });

    const saveBtn = el('button', { className: 'btn btn-primary btn-full', onClick: async () => {
      const payerId = payerSel.value;
      const receiverId = receiverSel.value;
      const amt = parseFloat(amountInput.value);
      const date = dateInput.value;
      const notes = notesInput.value.trim();

      if (payerId === receiverId) { errDiv.textContent = 'Payer and receiver must be different.'; errDiv.classList.remove('hidden'); return; }
      if (!amt || amt <= 0) { errDiv.textContent = 'Amount must be positive.'; errDiv.classList.remove('hidden'); return; }
      if (!date) { errDiv.textContent = 'Date is required.'; errDiv.classList.remove('hidden'); return; }

      const paise = Math.round(amt * 100);
      const now = DB.now();
      const sId = DB.uuid();
      await DB.put('settlements', {
        id: sId, groupId: targetGroupId,
        payerMemberId: payerId, receiverMemberId: receiverId,
        amount: paise, date, notes, createdAt: now, updatedAt: now
      });

      const payer = members.find(m => m.id === payerId);
      const receiver = members.find(m => m.id === receiverId);
      await logActivity('settlement_add', `${payer ? payer.name : '?'} paid ${receiver ? receiver.name : '?'} ${Balance.formatAmount(paise)}`, { groupId: targetGroupId, settlementId: sId });
      showToast('Payment recorded!', 'success');
      navigate('group-detail', { groupId: targetGroupId });
    }}, 'Record Payment');

    content.append(header,
      el('div', { className: 'form-group' }, el('label', {}, 'Who paid?'), payerSel),
      el('div', { className: 'form-group' }, el('label', {}, 'Paid to'), receiverSel),
      el('div', { className: 'form-group' }, el('label', {}, 'Amount (₹)'), amountInput),
      el('div', { className: 'form-group' }, el('label', {}, 'Date'), dateInput),
      el('div', { className: 'form-group' }, el('label', {}, 'Notes'), notesInput),
      errDiv,
      saveBtn
    );
    app.appendChild(content);
  }

  // ───────────────────────────────────────────────────────────
  // ACTIVITY SCREEN
  // ───────────────────────────────────────────────────────────
  async function renderActivity() {
    const app = $('#app');
    app.className = 'screen-main';

    const content = el('div', { className: 'screen-content' });
    const header = el('div', { className: 'main-header' },
      el('h2', { className: 'app-title' }, 'Activity')
    );

    const logs = await DB.getAll('activity_log');
    logs.sort((a, b) => b.createdAt.localeCompare(a.createdAt));

    const typeIcons = {
      setup: '🔧', group_create: '➕', group_edit: '✏️', group_delete: '🗑️',
      member_add: '👤', member_remove: '❌', expense_add: '💰', expense_edit: '📝',
      expense_delete: '🗑️', settlement_add: '💳', settlement_delete: '↩️',
      lock: '🔒', unlock: '🔓', theme: '🎨', settings: '⚙️'
    };

    const list = el('div', { className: 'activity-list' });

    if (logs.length === 0) {
      list.appendChild(el('div', { className: 'empty-state' },
        el('div', { className: 'empty-icon' }, '📋'),
        el('p', {}, 'No activity yet')
      ));
    } else {
      for (const log of logs) {
        const icon = typeIcons[log.type] || '📌';
        list.appendChild(el('div', { className: 'activity-item' },
          el('div', { className: 'activity-icon' }, icon),
          el('div', { className: 'activity-info' },
            el('div', { className: 'activity-msg' }, log.message),
            el('div', { className: 'activity-time text-muted' }, formatDateTime(log.createdAt))
          )
        ));
      }
    }

    content.append(header, list);
    app.append(content, renderBottomNav('activity'));
  }

  // ───────────────────────────────────────────────────────────
  // SETTINGS SCREEN
  // ───────────────────────────────────────────────────────────
  async function renderSettings() {
    const app = $('#app');
    app.className = 'screen-main';

    const content = el('div', { className: 'screen-content' });
    const header = el('div', { className: 'main-header' },
      el('h2', { className: 'app-title' }, 'Settings')
    );

    const settings = await Auth.getSettings();
    const username = await Auth.getUsername();

    // Profile card
    const profileCard = el('div', { className: 'settings-card' },
      el('div', { className: 'profile-row' },
        el('div', { className: 'profile-avatar' }, username.charAt(0).toUpperCase()),
        el('div', {},
          el('div', { className: 'profile-name' }, username),
          el('div', { className: 'text-muted' }, 'Local account')
        )
      )
    );

    // Theme toggle
    const themeToggle = el('div', { className: 'settings-card' },
      el('div', { className: 'setting-row' },
        el('div', {},
          el('div', { className: 'setting-label' }, 'Theme'),
          el('div', { className: 'text-muted' }, settings.theme === 'dark' ? 'Dark mode' : 'Light mode')
        ),
        el('button', {
          className: 'toggle-btn' + (settings.theme === 'dark' ? ' active' : ''),
          onClick: async (e) => {
            const newTheme = settings.theme === 'dark' ? 'light' : 'dark';
            settings.theme = newTheme;
            await Auth.saveSettings(settings);
            document.documentElement.setAttribute('data-theme', newTheme);
            await logActivity('theme', `Theme changed to ${newTheme}`);
            navigate('settings');
          }
        }, settings.theme === 'dark' ? '🌙 Dark' : '☀️ Light')
      )
    );

    // Auto-lock
    const lockOptions = [
      { value: 0, label: 'Never' },
      { value: 1, label: '1 minute' },
      { value: 5, label: '5 minutes' },
      { value: 15, label: '15 minutes' },
      { value: 30, label: '30 minutes' }
    ];
    const lockSel = el('select', { className: 'form-input' });
    for (const opt of lockOptions) {
      const o = el('option', { value: String(opt.value) }, opt.label);
      if (settings.autoLockMinutes === opt.value) o.selected = true;
      lockSel.appendChild(o);
    }
    lockSel.addEventListener('change', async () => {
      settings.autoLockMinutes = parseInt(lockSel.value);
      await Auth.saveSettings(settings);
      Auth.startAutoLock(settings.autoLockMinutes);
      showToast('Auto-lock updated', 'success');
    });

    const lockCard = el('div', { className: 'settings-card' },
      el('div', { className: 'setting-label' }, 'Auto-lock'),
      lockSel
    );

    // Backup section
    const backupCard = el('div', { className: 'settings-card' },
      el('h4', { className: 'settings-section-title' }, 'Backup & Restore'),
      el('div', { className: 'backup-row' },
        el('button', { className: 'btn btn-secondary', onClick: async () => {
          const data = await DB.exportAll();
          const authData = await new Promise(resolve => chrome.storage.local.get(null, resolve));
          const fullExport = { _version: '1.0', _date: DB.now(), data, auth: authData };
          const blob = new Blob([JSON.stringify(fullExport, null, 2)], { type: 'application/json' });
          const url = URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = `fairsplit-backup-${todayISO()}.json`;
          a.click();
          URL.revokeObjectURL(url);
          showToast('Backup downloaded!', 'success');
        }}, '📤 Export Data'),

        el('label', { className: 'btn btn-secondary file-label' },
          '📥 Import Data',
          (() => {
            const fileInput = el('input', { type: 'file', accept: '.json', className: 'hidden-file-input' });
            fileInput.addEventListener('change', async () => {
              const file = fileInput.files[0];
              if (!file) return;
              try {
                const text = await file.text();
                const fullExport = JSON.parse(text);
                const importData = fullExport.data || fullExport;
                await DB.importAll(importData);
                showToast('Data imported successfully!', 'success');
                navigate('dashboard');
              } catch (err) {
                showToast('Import failed: ' + err.message, 'error');
              }
            });
            return fileInput;
          })()
        )
      ),
      el('button', { className: 'btn btn-danger btn-full', onClick: async () => {
        const ok = await showConfirm('Clear ALL data? This cannot be undone. You will need to set up the app again.');
        if (!ok) return;
        await DB.clearAllData();
        await new Promise(r => chrome.storage.local.clear(r));
        showToast('All data cleared. Reloading…', 'info');
        setTimeout(() => location.reload(), 1500);
      }}, '🗑️ Clear All Data')
    );

    // Security info
    const infoCard = el('div', { className: 'settings-card info-card' },
      el('h4', { className: 'settings-section-title' }, '🔐 Security Info'),
      el('ul', { className: 'info-list' },
        el('li', {}, 'Data is stored only on this device/browser.'),
        el('li', {}, 'This is NOT a cloud account — data is NOT synced.'),
        el('li', {}, 'If you clear browser data, your expense data will be lost.'),
        el('li', {}, 'Export a backup regularly to avoid data loss.')
      )
    );

    // Simplify All Debts
    const simplifyAllCard = el('div', { className: 'settings-card' },
      el('h4', { className: 'settings-section-title' }, '🔀 Simplify All Debts'),
      el('p', { className: 'text-muted', style: { fontSize: '13px', margin: '4px 0 10px' } },
        'Find the minimum payments to settle all debts across every group at once.'),
      el('button', { className: 'btn btn-primary btn-full', onClick: () => navigate('simplify-global') },
        'View Simplified Payments')
    );

    content.append(header, profileCard, themeToggle, lockCard, simplifyAllCard, backupCard, infoCard);
    app.append(content, renderBottomNav('settings'));
  }

  // ───────────────────────────────────────────────────────────
  // FRIEND VIEW SCREEN
  // ───────────────────────────────────────────────────────────
  async function renderPersonView({ personName } = {}) {
    const app = $('#app');
    app.className = 'screen-main';
    const content = el('div', { className: 'screen-content' });
    const header = renderBackHeader('Friend View', 'groups');

    const allGroups = await DB.getAll('groups');
    const nameSet = new Set();
    for (const group of allGroups) {
      const members = await DB.getAll('members', 'groupId', group.id);
      for (const m of members) nameSet.add(m.name);
    }
    const allNames = [...nameSet].sort();

    if (allNames.length === 0) {
      content.append(header, el('div', { className: 'empty-state' },
        el('div', { className: 'empty-icon' }, '👤'),
        el('p', {}, 'No members found. Add members to groups first.')
      ));
      app.appendChild(content);
      return;
    }

    const nameSel = el('select', { className: 'form-input' });
    for (const name of allNames) {
      const opt = el('option', { value: name }, name);
      if (name === personName) opt.selected = true;
      nameSel.appendChild(opt);
    }

    const resultsDiv = el('div', { className: 'person-view-results' });

    async function loadPersonData(name) {
      resultsDiv.innerHTML = '<div class="loading-text text-muted">Calculating…</div>';
      const { groupResults, nameNet } = await Balance.calcPersonView(name);
      resultsDiv.innerHTML = '';

      if (groupResults.length === 0 && [...nameNet.values()].every(v => Math.abs(v) < 2)) {
        resultsDiv.appendChild(el('div', { className: 'settle-all-good' },
          el('div', { className: 'empty-icon' }, '✅'),
          el('p', {}, `${name} is all settled up!`)
        ));
        return;
      }

      if (groupResults.length > 0) {
        resultsDiv.appendChild(el('h4', { className: 'sub-title' }, 'Balance by Group'));
        for (const gr of groupResults) {
          const pos = gr.netPaise > 0;
          resultsDiv.appendChild(el('div', { className: 'person-group-row' },
            el('span', { className: 'person-group-name' }, gr.groupName),
            el('span', { className: pos ? 'balance-positive' : 'balance-negative' },
              pos ? `gets ${Balance.formatAmount(gr.netPaise)}` : `owes ${Balance.formatAmount(Math.abs(gr.netPaise))}`)
          ));
        }
      }

      const netEntries = [...nameNet.entries()].filter(([, v]) => Math.abs(v) >= 2);
      if (netEntries.length > 0) {
        resultsDiv.appendChild(el('h4', { className: 'sub-title' }, 'Net Balance with Each Person'));
        for (const [other, net] of netEntries) {
          const pos = net > 0;
          resultsDiv.appendChild(el('div', { className: 'person-net-row' },
            el('div', { className: 'person-net-label' },
              pos ? `${other} owes ${name}` : `${name} owes ${other}`
            ),
            el('div', { className: `person-net-amt ${pos ? 'balance-positive' : 'balance-negative'}` },
              Balance.formatAmount(Math.abs(net))
            )
          ));
        }
      }

      resultsDiv.appendChild(el('div', { className: 'simplify-info-card' },
        el('p', { className: 'text-muted' }, '💡 To record a payment, open the relevant group → Settle tab → ⚡ Record.')
      ));
    }

    const selectedName = personName || allNames[0];
    nameSel.value = selectedName;
    nameSel.addEventListener('change', () => loadPersonData(nameSel.value));

    content.append(
      header,
      el('div', { className: 'form-group' }, el('label', {}, 'Select Person'), nameSel),
      resultsDiv
    );
    app.appendChild(content);
    await loadPersonData(selectedName);
  }

  // ───────────────────────────────────────────────────────────
  // SIMPLIFY ALL DEBTS SCREEN
  // ───────────────────────────────────────────────────────────
  async function renderSimplifyGlobal() {
    const app = $('#app');
    app.className = 'screen-main';
    const content = el('div', { className: 'screen-content' });
    const header = renderBackHeader('Simplify All Debts', 'settings');

    const { transactions } = await Balance.simplifyGlobal();

    const infoCard = el('div', { className: 'simplify-info-card' },
      el('p', {}, '🔀 Minimum payments to settle all debts across every group.'),
      el('p', { className: 'text-muted' }, 'Members with the same name across groups are treated as one person.')
    );

    const section = el('div', { className: 'settle-section' });

    if (transactions.length === 0) {
      section.appendChild(el('div', { className: 'settle-all-good' },
        el('div', { className: 'empty-icon' }, '✅'),
        el('p', {}, 'Everyone is settled up across all groups!')
      ));
    } else {
      section.appendChild(el('h4', { className: 'sub-title' },
        `${transactions.length} Payment${transactions.length !== 1 ? 's' : ''} to Settle Everything`
      ));
      for (const tx of transactions) {
        section.appendChild(el('div', { className: 'suggestion-row' },
          el('div', { className: 'suggestion-left' },
            el('span', { className: 'suggestion-text' }, `${tx.from} → ${tx.to}`),
            el('span', { className: 'suggestion-label' }, 'across all groups')
          ),
          el('span', { className: 'suggestion-amt text-danger' }, Balance.formatAmount(tx.amount))
        ));
      }
      section.appendChild(el('div', { className: 'simplify-info-card' },
        el('p', { className: 'text-muted' }, '💡 Open the relevant group → Settle tab → ⚡ Record to save each payment.')
      ));
    }

    content.append(header, infoCard, section);
    app.appendChild(content);
  }

  // ───────────────────────────────────────────────────────────
  // HELPERS
  // ───────────────────────────────────────────────────────────
  function todayISO() {
    return new Date().toISOString().split('T')[0];
  }

  function formatDate(iso) {
    if (!iso) return '';
    const d = new Date(iso + 'T00:00:00');
    return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
  }

  function formatDateTime(iso) {
    if (!iso) return '';
    const d = new Date(iso);
    return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' }) + ' ' +
      d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
  }

  return { navigate, render };
})();

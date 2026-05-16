// js/balance.js — Balance calculation engine (all amounts in integer paise)
window.Balance = (() => {

  // Calculate net balance map for a group
  // positive = this member is owed (creditor)
  // negative = this member owes (debtor)
  async function calcGroup(groupId) {
    const [expenses, splits, settlements] = await Promise.all([
      DB.getAll('expenses', 'groupId', groupId),
      DB.getAll('expense_splits'),
      DB.getAll('settlements', 'groupId', groupId)
    ]);

    const netMap = new Map();

    function ensure(id) {
      if (!netMap.has(id)) netMap.set(id, 0);
    }

    for (const expense of expenses) {
      // payer gets credited the full amount
      ensure(expense.paidByMemberId);
      netMap.set(expense.paidByMemberId, netMap.get(expense.paidByMemberId) + expense.amount);

      // each split member gets debited their share
      const expSplits = splits.filter(s => s.expenseId === expense.id);
      for (const split of expSplits) {
        ensure(split.memberId);
        netMap.set(split.memberId, netMap.get(split.memberId) - split.amount);
      }
    }

    for (const settlement of settlements) {
      // payer reduces their debt (or increases credit)
      ensure(settlement.payerMemberId);
      ensure(settlement.receiverMemberId);
      netMap.set(settlement.payerMemberId, netMap.get(settlement.payerMemberId) + settlement.amount);
      netMap.set(settlement.receiverMemberId, netMap.get(settlement.receiverMemberId) - settlement.amount);
    }

    return netMap;
  }

  // Calculate totals across all groups
  async function calcAll() {
    const groups = await DB.getAll('groups');
    let totalOwed = 0;  // sum of positive balances
    let totalOwe = 0;   // sum of negative balances (absolute)

    for (const group of groups) {
      const netMap = await calcGroup(group.id);
      for (const val of netMap.values()) {
        if (val > 0) totalOwed += val;
        else if (val < 0) totalOwe += Math.abs(val);
      }
    }

    return { totalOwed, totalOwe };
  }

  // Debt simplification using greedy algorithm
  // Returns [{from: memberId, to: memberId, amount: paise}]
  function simplify(netMap) {
    const debtors = [];   // negative balance (they owe)
    const creditors = []; // positive balance (they are owed)

    for (const [id, amount] of netMap.entries()) {
      if (amount < -1) debtors.push({ id, amount: -amount });
      else if (amount > 1) creditors.push({ id, amount });
    }

    // Sort descending by amount
    debtors.sort((a, b) => b.amount - a.amount);
    creditors.sort((a, b) => b.amount - a.amount);

    const transactions = [];
    let di = 0, ci = 0;

    while (di < debtors.length && ci < creditors.length) {
      const d = debtors[di];
      const c = creditors[ci];
      const settled = Math.min(d.amount, c.amount);

      if (settled > 0) {
        transactions.push({ from: d.id, to: c.id, amount: settled });
      }

      d.amount -= settled;
      c.amount -= settled;

      if (d.amount <= 1) di++;
      if (c.amount <= 1) ci++;
    }

    return transactions;
  }

  function formatAmount(paise) {
    const rupees = paise / 100;
    return '₹' + rupees.toFixed(2);
  }

  // Pairwise debts: direct per-pair balances before simplification
  // Returns [{from, to, amount}] — "from owes to" this amount
  async function calcPairwise(groupId) {
    const [expenses, allSplits, settlements] = await Promise.all([
      DB.getAll('expenses', 'groupId', groupId),
      DB.getAll('expense_splits'),
      DB.getAll('settlements', 'groupId', groupId)
    ]);

    const pm = {}; // pm[from][to] = net amount from owes to
    function add(from, to, amount) {
      if (!pm[from]) pm[from] = {};
      pm[from][to] = (pm[from][to] || 0) + amount;
    }

    for (const expense of expenses) {
      const expSplits = allSplits.filter(s => s.expenseId === expense.id);
      for (const split of expSplits) {
        if (split.memberId !== expense.paidByMemberId) {
          add(split.memberId, expense.paidByMemberId, split.amount);
        }
      }
    }
    for (const s of settlements) {
      add(s.payerMemberId, s.receiverMemberId, -s.amount);
    }

    const allIds = new Set([
      ...Object.keys(pm),
      ...Object.values(pm).flatMap(v => Object.keys(v))
    ]);
    const result = [];
    const seen = new Set();
    for (const a of allIds) {
      for (const b of allIds) {
        if (a === b) continue;
        const key = [a, b].sort().join('|');
        if (seen.has(key)) continue;
        seen.add(key);
        const net = (pm[a]?.[b] || 0) - (pm[b]?.[a] || 0);
        if (net > 1) result.push({ from: a, to: b, amount: net });
        else if (net < -1) result.push({ from: b, to: a, amount: -net });
      }
    }
    return result;
  }

  // Global simplification: matches members by name across all groups
  async function simplifyGlobal() {
    const groups = await DB.getAll('groups');
    const nameNet = new Map(); // name → net paise across all groups

    for (const group of groups) {
      const netMap = await calcGroup(group.id);
      const members = await DB.getAll('members', 'groupId', group.id);
      const memberMap = {};
      for (const m of members) memberMap[m.id] = m.name;
      for (const [id, amount] of netMap.entries()) {
        const name = memberMap[id];
        if (!name) continue;
        nameNet.set(name, (nameNet.get(name) || 0) + amount);
      }
    }

    // Build a name-keyed map then run simplify
    const namedTransactions = simplify(nameNet);
    return { transactions: namedTransactions, nameNet };
  }

  // Per-person cross-group view: how much does personName owe/is owed by each other person
  async function calcPersonView(personName) {
    const groups = await DB.getAll('groups');
    const nameLower = personName.toLowerCase();
    const groupResults = [];
    const nameNet = new Map(); // otherName → net (positive = other owes person)

    for (const group of groups) {
      const members = await DB.getAll('members', 'groupId', group.id);
      const person = members.find(m => m.name.toLowerCase() === nameLower);
      if (!person) continue;

      const netMap = await calcGroup(group.id);
      const personNet = netMap.get(person.id) || 0;
      if (personNet !== 0) groupResults.push({ groupId: group.id, groupName: group.name, netPaise: personNet });

      const pairwise = await calcPairwise(group.id);
      const memberMap = {};
      for (const m of members) memberMap[m.id] = m.name;

      for (const tx of pairwise) {
        if (tx.from === person.id) {
          const other = memberMap[tx.to] || '?';
          nameNet.set(other, (nameNet.get(other) || 0) - tx.amount); // person owes other
        } else if (tx.to === person.id) {
          const other = memberMap[tx.from] || '?';
          nameNet.set(other, (nameNet.get(other) || 0) + tx.amount); // other owes person
        }
      }
    }
    return { groupResults, nameNet };
  }

  return { calcGroup, calcAll, simplify, calcPairwise, simplifyGlobal, calcPersonView, formatAmount };
})();

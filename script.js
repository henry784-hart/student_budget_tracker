// Load browser data first so it remains available if the API is offline.
function loadLocalTransactions() {
  try {
    const saved = JSON.parse(localStorage.getItem("transactions"));
    return Array.isArray(saved) ? saved : [];
  } catch (error) {
    return [];
  }
}

let transactions = loadLocalTransactions();
let storageMode = "local";
let monthlyBudget = 0;
try {
  monthlyBudget = parseFloat(localStorage.getItem("monthlyBudget")) || 0;
} catch (error) {
  monthlyBudget = 0;
}

// Set window.BUDGET_API_URL before script.js to use a separately hosted API.
const API_BASE_URL = window.BUDGET_API_URL || "http://127.0.0.1:5000/api";
let editingId = null;

const amountInput = document.getElementById("amount");
const typeInput = document.getElementById("type");
const categoryInput = document.getElementById("category");
const dateInput = document.getElementById("date");
const noteInput = document.getElementById("note");
const transactionForm = document.getElementById("transaction-form");
const addBtn = document.getElementById("add-btn");
const cancelBtn = document.getElementById("cancel-btn");
const categoryList = document.getElementById("category-list");
const list = document.getElementById("list");
const incomeEl = document.getElementById("income");
const expensesEl = document.getElementById("expenses");
const balanceEl = document.getElementById("balance");
const monthlyIncomeEl = document.getElementById("monthly-income");
const monthlyExpensesEl = document.getElementById("monthly-expenses");
const monthlyBalanceEl = document.getElementById("monthly-balance");
const monthLabelEl = document.getElementById("month-label");
const breakdownList = document.getElementById("breakdown-list");
const budgetInput = document.getElementById("budget-input");
const budgetBtn = document.getElementById("budget-btn");
const budgetStatus = document.getElementById("budget-status");
const budgetFill = document.getElementById("budget-fill");
const appStatus = document.getElementById("app-status");

async function apiRequest(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...options.headers,
    },
  });

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || `API request failed (${response.status}).`);
  }
  return data;
}

function showStatus(message, mode) {
  appStatus.textContent = message;
  appStatus.className = `app-status ${mode}`;
}

async function initializeApp() {
  try {
    let remoteTransactions = await apiRequest("/transactions");
    const localTransactions = loadLocalTransactions();

    // Preserve existing browser-only data by importing it once into a fresh DB.
    if (remoteTransactions.length === 0 && localTransactions.length > 0) {
      remoteTransactions = await apiRequest("/transactions/import", {
        method: "POST",
        body: JSON.stringify({ transactions: localTransactions }),
      });
      localStorage.removeItem("transactions");
      showStatus("Connected to the Flask API. Existing browser transactions were imported.", "connected");
    } else {
      showStatus("Connected to the Flask API. Transactions are saved in SQLite.", "connected");
    }

    transactions = remoteTransactions;
    storageMode = "api";
  } catch (error) {
    transactions = loadLocalTransactions();
    storageMode = "local";
    showStatus("Flask API unavailable; using this browser’s saved data. Start the backend to use SQLite.", "offline");
  }

  render();
}

function getTodayISODate() {
  const now = new Date();
  const localDate = new Date(now.getTime() - now.getTimezoneOffset() * 60000);
  return localDate.toISOString().slice(0, 10);
}

function getCurrentMonthKey() {
  const now = new Date();
  return now.getFullYear() + "-" + String(now.getMonth() + 1).padStart(2, "0");
}

function getMonthLabel(date = new Date()) {
  return new Intl.DateTimeFormat("en-US", { month: "long", year: "numeric" }).format(date);
}

function formatNumber(number) {
  return Number(number || 0).toLocaleString("en-US", { maximumFractionDigits: 2 });
}

function formatCurrency(number) {
  return `KES ${formatNumber(number)}`;
}

function saveLocal() {
  localStorage.setItem("transactions", JSON.stringify(transactions));
}

function clearForm() {
  amountInput.value = "";
  categoryInput.value = "";
  noteInput.value = "";
  dateInput.value = getTodayISODate();
}

function exitEditMode() {
  editingId = null;
  addBtn.textContent = "Add";
  cancelBtn.style.display = "none";
  typeInput.value = "expense";
  clearForm();
}

async function addTransaction() {
  const amount = Number(amountInput.value);
  const category = categoryInput.value.trim();
  if (!Number.isFinite(amount) || amount <= 0 || !category || !dateInput.value) {
    alert("Please enter a valid amount, category and date.");
    return;
  }

  const transaction = {
    amount,
    type: typeInput.value,
    category,
    note: noteInput.value.trim(),
    date: dateInput.value,
  };

  try {
    if (storageMode === "api") {
      if (editingId !== null) {
        const updated = await apiRequest(`/transactions/${editingId}`, {
          method: "PUT",
          body: JSON.stringify(transaction),
        });
        transactions = transactions.map((item) => item.id === editingId ? updated : item);
        exitEditMode();
      } else {
        const created = await apiRequest("/transactions", {
          method: "POST",
          body: JSON.stringify(transaction),
        });
        transactions.push(created);
        clearForm();
      }
    } else if (editingId !== null) {
      transactions = transactions.map((item) => item.id === editingId ? { ...item, ...transaction } : item);
      exitEditMode();
      saveLocal();
    } else {
      transactions.push({ id: Date.now(), ...transaction });
      clearForm();
      saveLocal();
    }

    render();
  } catch (error) {
    alert(`Could not save the transaction: ${error.message}`);
  }
}

function startEdit(id) {
  const transaction = transactions.find((item) => item.id === id);
  if (!transaction) return;

  editingId = id;
  amountInput.value = transaction.amount;
  typeInput.value = transaction.type;
  categoryInput.value = transaction.category;
  noteInput.value = transaction.note || "";
  dateInput.value = transaction.date;
  addBtn.textContent = "Save changes";
  cancelBtn.style.display = "block";

  render();
  amountInput.scrollIntoView({ behavior: "smooth", block: "center" });
  amountInput.focus();
}

async function deleteTransaction(id) {
  try {
    if (storageMode === "api") {
      await apiRequest(`/transactions/${id}`, { method: "DELETE" });
    }
    if (editingId === id) exitEditMode();
    transactions = transactions.filter((transaction) => transaction.id !== id);
    if (storageMode === "local") saveLocal();
    render();
  } catch (error) {
    alert(`Could not delete the transaction: ${error.message}`);
  }
}

function setBudget() {
  const value = Number(budgetInput.value);
  if (!Number.isFinite(value) || value <= 0) {
    alert("Please enter a monthly limit greater than 0.");
    return;
  }
  monthlyBudget = value;
  try {
    localStorage.setItem("monthlyBudget", String(value));
  } catch (error) {
    alert("The budget could not be saved in this browser.");
  }
  render();
}

function renderMonthlySummary() {
  const monthKey = getCurrentMonthKey();
  monthLabelEl.textContent = getMonthLabel();
  let income = 0;
  let expenses = 0;

  transactions.forEach((transaction) => {
    if (!transaction.date || !transaction.date.startsWith(monthKey)) return;
    if (transaction.type === "income") income += Number(transaction.amount) || 0;
    if (transaction.type === "expense") expenses += Number(transaction.amount) || 0;
  });

  const balance = income - expenses;
  monthlyIncomeEl.textContent = formatCurrency(income);
  monthlyExpensesEl.textContent = formatCurrency(expenses);
  monthlyBalanceEl.textContent = formatCurrency(balance);
  monthlyBalanceEl.parentElement.classList.toggle("positive", balance >= 0);
  monthlyBalanceEl.parentElement.classList.toggle("negative", balance < 0);
}

function renderBudget() {
  if (monthlyBudget <= 0) {
    budgetStatus.textContent = "No limit set yet. Enter one above.";
    budgetStatus.className = "";
    budgetFill.style.width = "0%";
    budgetFill.className = "bd-fill";
    return;
  }

  const monthKey = getCurrentMonthKey();
  const spent = transactions.reduce((total, transaction) => {
    return transaction.type === "expense" && transaction.date?.startsWith(monthKey)
      ? total + (Number(transaction.amount) || 0)
      : total;
  }, 0);

  const ratio = spent / monthlyBudget;
  const left = monthlyBudget - spent;
  const state = ratio > 1 ? "over" : ratio >= 0.8 ? "warn" : "ok";
  if (left >= 0) {
    budgetStatus.textContent = `Spent ${formatNumber(spent)} of ${formatNumber(monthlyBudget)} KES this month · ${formatNumber(left)} KES left (${Math.round(ratio * 100)}%)`;
  } else {
    budgetStatus.textContent = `Over budget by ${formatNumber(-left)} KES! Spent ${formatNumber(spent)} of ${formatNumber(monthlyBudget)} KES this month.`;
  }
  budgetStatus.className = state;
  budgetFill.style.width = `${Math.min(100, ratio * 100)}%`;
  budgetFill.className = `bd-fill ${state}`;
}

function renderBreakdown() {
  breakdownList.innerHTML = "";
  const totals = new Map();
  transactions.forEach((transaction) => {
    if (transaction.type !== "expense") return;
    const name = String(transaction.category || "").trim();
    const key = name.toLowerCase();
    if (key) totals.set(key, { name, amount: (totals.get(key)?.amount || 0) + (Number(transaction.amount) || 0) });
  });

  const entries = [...totals.values()].sort((a, b) => b.amount - a.amount);
  if (!entries.length) {
    const empty = document.createElement("li");
    empty.className = "bd-empty";
    empty.textContent = "No expenses yet.";
    breakdownList.appendChild(empty);
    return;
  }

  const totalSpent = entries.reduce((sum, entry) => sum + entry.amount, 0);
  entries.forEach(({ name, amount }) => {
    const raw = totalSpent ? (amount / totalSpent) * 100 : 0;
    const title = name.charAt(0).toUpperCase() + name.slice(1);
    const li = document.createElement("li");
    const label = document.createElement("div");
    label.className = "bd-label";
    label.textContent = `${title} · ${formatNumber(amount)} KES (${raw < 1 ? "<1%" : `${Math.round(raw)}%`})`;
    const bar = document.createElement("div");
    bar.className = "bd-bar";
    const fill = document.createElement("div");
    fill.className = "bd-fill";
    fill.style.width = `${Math.max(raw, 1)}%`;
    bar.appendChild(fill);
    li.append(label, bar);
    breakdownList.appendChild(li);
  });
}

function renderCategorySuggestions() {
  categoryList.innerHTML = "";
  const defaults = ["Food", "Transport", "Airtime/Data", "Rent/Hostel", "Books/Stationery", "Fees", "Entertainment", "Other"];
  const seen = new Set();
  [...transactions.map((transaction) => transaction.category), ...defaults].forEach((value) => {
    const name = String(value || "").trim();
    const key = name.toLowerCase();
    if (!name || seen.has(key)) return;
    seen.add(key);
    const option = document.createElement("option");
    option.value = name;
    categoryList.appendChild(option);
  });
}

function render() {
  list.innerHTML = "";
  let income = 0;
  let expenses = 0;
  if (!transactions.length) {
    const empty = document.createElement("li");
    empty.className = "empty";
    empty.textContent = "No transactions yet. Add your first one above.";
    list.appendChild(empty);
  }

  const sorted = [...transactions].sort((a, b) => b.date.localeCompare(a.date) || b.id - a.id);
  sorted.forEach((transaction) => {
    const amount = Number(transaction.amount) || 0;
    if (transaction.type === "income") income += amount;
    else expenses += amount;

    const li = document.createElement("li");
    li.classList.add(transaction.type === "income" ? "tx-income" : "tx-expense");
    if (transaction.id === editingId) li.classList.add("editing");
    const sign = transaction.type === "income" ? "+" : "-";
    const noteText = transaction.note ? ` · ${transaction.note}` : "";
    const text = document.createElement("span");
    text.textContent = `${transaction.date} · ${transaction.category}${noteText} · ${sign}${formatNumber(amount)} KES`;

    const actions = document.createElement("div");
    actions.className = "actions";
    const editBtn = document.createElement("button");
    editBtn.textContent = "Edit";
    editBtn.className = "edit-btn";
    editBtn.type = "button";
    editBtn.addEventListener("click", () => startEdit(transaction.id));
    const deleteBtn = document.createElement("button");
    deleteBtn.textContent = "Delete";
    deleteBtn.type = "button";
    deleteBtn.addEventListener("click", () => deleteTransaction(transaction.id));
    actions.append(editBtn, deleteBtn);
    li.append(text, actions);
    list.appendChild(li);
  });

  const balance = income - expenses;
  incomeEl.textContent = formatNumber(income);
  expensesEl.textContent = formatNumber(expenses);
  balanceEl.textContent = formatNumber(balance);
  balanceEl.classList.toggle("positive", balance >= 0);
  balanceEl.classList.toggle("negative", balance < 0);
  renderMonthlySummary();
  renderBreakdown();
  renderBudget();
  renderCategorySuggestions();
}

transactionForm.addEventListener("submit", (event) => {
  event.preventDefault();
  addTransaction();
});
cancelBtn.addEventListener("click", () => {
  exitEditMode();
  render();
});
budgetBtn.addEventListener("click", setBudget);

if (monthlyBudget > 0) budgetInput.value = monthlyBudget;
if (!dateInput.value) dateInput.value = getTodayISODate();
initializeApp();

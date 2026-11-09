function getTodayISODate() {
  const now = new Date();
  const localDate = new Date(now.getTime() - now.getTimezoneOffset() * 60000);
  return localDate.toISOString().slice(0, 10);
}

function getCurrentMonthKey() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

function formatNumber(number) {
  return Number(number || 0).toLocaleString("en-US", { maximumFractionDigits: 2 });
}

function formatCurrency(number) {
  return `KES ${formatNumber(number)}`;
}

const API_BASE_URL = window.BUDGET_API_URL || "http://127.0.0.1:5000/api";
let transactions = [];
let monthlyBudget = 0;
let editingId = null;
let currentUser = null;

const authPanel = document.getElementById("auth-panel");
const authForm = document.getElementById("auth-form");
const authEmail = document.getElementById("auth-email");
const authPassword = document.getElementById("auth-password");
const authMessage = document.getElementById("auth-message");
const loginBtn = document.getElementById("login-btn");
const registerBtn = document.getElementById("register-btn");
const appShell = document.getElementById("app-shell");
const appStatus = document.getElementById("app-status");
const userBanner = document.getElementById("user-banner");
const logoutBtn = document.getElementById("logout-btn");
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

async function apiRequest(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    credentials: "include",
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...options.headers,
    },
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(result.error || `Request failed (${response.status}).`);
  return result;
}

function setAuthMessage(message, isError = false) {
  authMessage.textContent = message;
  authMessage.classList.toggle("error", isError);
}

function setAppStatus(message, isError = false) {
  appStatus.textContent = message;
  appStatus.classList.toggle("error", isError);
}

function showSignedOut() {
  currentUser = null;
  transactions = [];
  monthlyBudget = 0;
  authPanel.classList.remove("hidden");
  appShell.classList.add("hidden");
}

function showSignedIn() {
  authPanel.classList.add("hidden");
  appShell.classList.remove("hidden");
  userBanner.textContent = currentUser.email;
}

async function loadAccountData() {
  const [loadedTransactions, budget] = await Promise.all([
    apiRequest("/transactions"),
    apiRequest("/budget"),
  ]);
  transactions = loadedTransactions;
  monthlyBudget = Number(budget.monthly_limit) || 0;
  budgetInput.value = monthlyBudget || "";
  render();
}

async function checkSession() {
  try {
    currentUser = await apiRequest("/auth/me");
    showSignedIn();
    setAppStatus("Signed in. Your data is saved to this account.");
    await loadAccountData();
  } catch (error) {
    showSignedOut();
    setAuthMessage(
      error.message.includes("Failed to fetch")
        ? "Cannot reach the API. Start Flask, then refresh this page."
        : "Log in or create an account to continue."
    );
  }
}

async function authenticate(endpoint) {
  const email = authEmail.value.trim();
  const password = authPassword.value;
  if (!email || !password) {
    setAuthMessage("Enter your email and password.", true);
    return;
  }
  loginBtn.disabled = true;
  registerBtn.disabled = true;
  try {
    currentUser = await apiRequest(endpoint, {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    authPassword.value = "";
    showSignedIn();
    setAuthMessage("");
    setAppStatus("Signed in. Your data is saved to this account.");
    await loadAccountData();
  } catch (error) {
    setAuthMessage(error.message, true);
  } finally {
    loginBtn.disabled = false;
    registerBtn.disabled = false;
  }
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
  cancelBtn.classList.add("hidden");
  typeInput.value = "expense";
  clearForm();
}

async function saveTransaction(event) {
  event.preventDefault();
  const transaction = {
    amount: Number(amountInput.value),
    type: typeInput.value,
    category: categoryInput.value.trim(),
    note: noteInput.value.trim(),
    date: dateInput.value,
  };
  if (!Number.isFinite(transaction.amount) || transaction.amount <= 0 || !transaction.category || !transaction.date) {
    alert("Please enter a valid amount, category and date.");
    return;
  }

  try {
    if (editingId === null) {
      const created = await apiRequest("/transactions", { method: "POST", body: JSON.stringify(transaction) });
      transactions.push(created);
      clearForm();
    } else {
      const updated = await apiRequest(`/transactions/${editingId}`, { method: "PUT", body: JSON.stringify(transaction) });
      transactions = transactions.map((item) => item.id === editingId ? updated : item);
      exitEditMode();
    }
    setAppStatus("Transaction saved.");
    render();
  } catch (error) {
    setAppStatus(error.message, true);
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
  cancelBtn.classList.remove("hidden");
  amountInput.scrollIntoView({ behavior: "smooth", block: "center" });
  amountInput.focus();
  render();
}

async function deleteTransaction(id) {
  try {
    await apiRequest(`/transactions/${id}`, { method: "DELETE" });
    if (editingId === id) exitEditMode();
    transactions = transactions.filter((item) => item.id !== id);
    setAppStatus("Transaction deleted.");
    render();
  } catch (error) {
    setAppStatus(error.message, true);
  }
}

async function saveBudget() {
  const value = Number(budgetInput.value);
  if (!Number.isFinite(value) || value <= 0) {
    setAppStatus("Enter a monthly budget greater than zero.", true);
    return;
  }
  try {
    const result = await apiRequest("/budget", {
      method: "PUT",
      body: JSON.stringify({ monthly_limit: value }),
    });
    monthlyBudget = result.monthly_limit;
    setAppStatus("Monthly budget saved to your account.");
    renderBudget();
  } catch (error) {
    setAppStatus(error.message, true);
  }
}

function renderMonthlySummary() {
  const monthKey = getCurrentMonthKey();
  monthLabelEl.textContent = new Intl.DateTimeFormat("en-US", { month: "long", year: "numeric" }).format(new Date());
  let income = 0;
  let expenses = 0;
  transactions.forEach((transaction) => {
    if (!transaction.date?.startsWith(monthKey)) return;
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
  const spent = transactions.reduce((sum, item) => item.type === "expense" && item.date?.startsWith(monthKey)
    ? sum + (Number(item.amount) || 0) : sum, 0);
  const ratio = spent / monthlyBudget;
  const left = monthlyBudget - spent;
  const state = ratio > 1 ? "over" : ratio >= 0.8 ? "warn" : "ok";
  budgetStatus.textContent = left >= 0
    ? `Spent ${formatNumber(spent)} of ${formatNumber(monthlyBudget)} KES this month · ${formatNumber(left)} KES left (${Math.round(ratio * 100)}%)`
    : `Over budget by ${formatNumber(-left)} KES! Spent ${formatNumber(spent)} of ${formatNumber(monthlyBudget)} KES this month.`;
  budgetStatus.className = state;
  budgetFill.style.width = `${Math.min(100, ratio * 100)}%`;
  budgetFill.className = `bd-fill ${state}`;
}

function renderBreakdown() {
  breakdownList.innerHTML = "";
  const totals = new Map();
  transactions.forEach((item) => {
    if (item.type !== "expense") return;
    const name = String(item.category || "").trim();
    const key = name.toLowerCase();
    if (!key) return;
    const existing = totals.get(key) || { name, amount: 0 };
    existing.amount += Number(item.amount) || 0;
    totals.set(key, existing);
  });
  const entries = [...totals.values()].sort((a, b) => b.amount - a.amount);
  if (!entries.length) {
    const empty = document.createElement("li");
    empty.className = "bd-empty";
    empty.textContent = "No expenses yet.";
    breakdownList.appendChild(empty);
    return;
  }
  const total = entries.reduce((sum, item) => sum + item.amount, 0);
  entries.forEach(({ name, amount }) => {
    const percent = total ? amount / total * 100 : 0;
    const li = document.createElement("li");
    const label = document.createElement("div");
    label.className = "bd-label";
    label.textContent = `${name} · ${formatNumber(amount)} KES (${percent < 1 ? "<1%" : `${Math.round(percent)}%`})`;
    const bar = document.createElement("div");
    bar.className = "bd-bar";
    const fill = document.createElement("div");
    fill.className = "bd-fill";
    fill.style.width = `${Math.max(percent, 1)}%`;
    bar.appendChild(fill);
    li.append(label, bar);
    breakdownList.appendChild(li);
  });
}

function renderCategorySuggestions() {
  categoryList.innerHTML = "";
  const defaults = ["Food", "Transport", "Airtime/Data", "Rent/Hostel", "Books/Stationery", "Fees", "Entertainment", "Other"];
  const used = new Set();
  [...transactions.map((item) => item.category), ...defaults].forEach((value) => {
    const name = String(value || "").trim();
    const key = name.toLowerCase();
    if (!name || used.has(key)) return;
    used.add(key);
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
  [...transactions].sort((a, b) => b.date.localeCompare(a.date) || b.id - a.id).forEach((item) => {
    const amount = Number(item.amount) || 0;
    if (item.type === "income") income += amount;
    else expenses += amount;
    const li = document.createElement("li");
    li.classList.add(item.type === "income" ? "tx-income" : "tx-expense");
    if (item.id === editingId) li.classList.add("editing");
    const text = document.createElement("span");
    const note = item.note ? ` · ${item.note}` : "";
    text.textContent = `${item.date} · ${item.category}${note} · ${item.type === "income" ? "+" : "-"}${formatNumber(amount)} KES`;
    const actions = document.createElement("div");
    actions.className = "actions";
    const edit = document.createElement("button");
    edit.type = "button";
    edit.className = "edit-btn";
    edit.textContent = "Edit";
    edit.addEventListener("click", () => startEdit(item.id));
    const remove = document.createElement("button");
    remove.type = "button";
    remove.textContent = "Delete";
    remove.addEventListener("click", () => deleteTransaction(item.id));
    actions.append(edit, remove);
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

authForm.addEventListener("submit", (event) => {
  event.preventDefault();
  authenticate("/auth/login");
});
registerBtn.addEventListener("click", () => authenticate("/auth/register"));
logoutBtn.addEventListener("click", async () => {
  try { await apiRequest("/auth/logout", { method: "POST" }); } catch (error) { console.warn(error); }
  showSignedOut();
  setAuthMessage("You have logged out.");
});
transactionForm.addEventListener("submit", saveTransaction);
cancelBtn.addEventListener("click", () => { exitEditMode(); render(); });
budgetBtn.addEventListener("click", saveBudget);

dateInput.value = getTodayISODate();
checkSession();

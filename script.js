// 1. Load saved data
let transactions = [];
try {
  transactions = JSON.parse(localStorage.getItem("transactions")) || [];
} catch (e) {
  transactions = [];
}

let monthlyBudget = 0;
try {
  monthlyBudget = parseFloat(localStorage.getItem("monthlyBudget")) || 0;
} catch (e) {
  monthlyBudget = 0;
}

// Which transaction is being edited (null = none)
let editingId = null;

// 2. Grab the page elements we need
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

function getTodayISODate() {
  return new Date().toISOString().split("T")[0];
}

function getCurrentMonthKey() {
  const now = new Date();
  return now.getFullYear() + "-" + String(now.getMonth() + 1).padStart(2, "0");
}

function getMonthLabel(date = new Date()) {
  return new Intl.DateTimeFormat("en-US", { month: "long", year: "numeric" }).format(date);
}

// 3. Format numbers with commas
function formatNumber(n) {
  return n.toLocaleString("en-US", { maximumFractionDigits: 2 });
}

function formatCurrency(n) {
  return `KES ${formatNumber(n)}`;
}

// 4. Save transactions to the browser
function save() {
  localStorage.setItem("transactions", JSON.stringify(transactions));
}

// 5. Form helpers
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

// 6. Add a new transaction, or save changes to one being edited
function addTransaction() {
  const amount = parseFloat(amountInput.value);
  const category = categoryInput.value.trim();

  if (isNaN(amount) || amount <= 0 || category === "" || dateInput.value === "") {
    alert("Please enter a valid amount, category and date.");
    return;
  }

  if (editingId !== null) {
    const t = transactions.find((item) => item.id === editingId);
    if (t) {
      t.amount = amount;
      t.type = typeInput.value;
      t.category = category;
      t.note = noteInput.value.trim();
      t.date = dateInput.value;
    }
    exitEditMode();
  } else {
    transactions.push({
      id: Date.now(),
      amount: amount,
      type: typeInput.value,
      category: category,
      note: noteInput.value.trim(),
      date: dateInput.value,
    });
    clearForm();
  }

  save();
  render();
}

// 7. Load a transaction into the form for editing
function startEdit(id) {
  const t = transactions.find((item) => item.id === id);
  if (!t) return;

  editingId = id;
  amountInput.value = t.amount;
  typeInput.value = t.type;
  categoryInput.value = t.category;
  noteInput.value = t.note || "";
  dateInput.value = t.date;

  addBtn.textContent = "Save changes";
  cancelBtn.style.display = "block";

  render();
  amountInput.scrollIntoView({ behavior: "smooth", block: "center" });
  amountInput.focus();
}

// 8. Delete a transaction
function deleteTransaction(id) {
  if (editingId === id) {
    exitEditMode();
  }
  transactions = transactions.filter((t) => t.id !== id);
  save();
  render();
}

// 9. Set the monthly budget limit
function setBudget() {
  const value = parseFloat(budgetInput.value);
  if (isNaN(value) || value <= 0) {
    alert("Please enter a monthly limit greater than 0.");
    return;
  }
  monthlyBudget = value;
  try {
    localStorage.setItem("monthlyBudget", String(value));
  } catch (e) {}
  render();
}

function renderMonthlySummary() {
  const now = new Date();
  const monthKey = getCurrentMonthKey();
  const monthLabel = getMonthLabel(now);
  monthLabelEl.textContent = monthLabel;

  let income = 0;
  let expenses = 0;

  transactions.forEach((t) => {
    if (!t.date || !t.date.startsWith(monthKey)) return;

    if (t.type === "income") {
      income += t.amount;
    } else if (t.type === "expense") {
      expenses += t.amount;
    }
  });

  const balance = income - expenses;

  monthlyIncomeEl.textContent = formatCurrency(income);
  monthlyExpensesEl.textContent = formatCurrency(expenses);
  monthlyBalanceEl.textContent = formatCurrency(balance);
  monthlyBalanceEl.parentElement.classList.toggle("positive", balance >= 0);
  monthlyBalanceEl.parentElement.classList.toggle("negative", balance < 0);
}

// 10. Show spending against the monthly limit (current month only)
function renderBudget() {
  if (monthlyBudget <= 0) {
    budgetStatus.textContent = "No limit set yet. Enter one above.";
    budgetStatus.className = "";
    budgetFill.style.width = "0%";
    budgetFill.className = "bd-fill";
    return;
  }

  const monthKey = getCurrentMonthKey();

  let spent = 0;
  transactions.forEach((t) => {
    if (t.type === "expense" && t.date.startsWith(monthKey)) {
      spent += t.amount;
    }
  });

  const ratio = spent / monthlyBudget;
  const left = monthlyBudget - spent;
  const state = ratio > 1 ? "over" : ratio >= 0.8 ? "warn" : "ok";

  if (left >= 0) {
    budgetStatus.textContent = `Spent ${formatNumber(spent)} of ${formatNumber(monthlyBudget)} KES this month · ${formatNumber(left)} KES left (${Math.round(ratio * 100)}%)`;
  } else {
    budgetStatus.textContent = `Over budget by ${formatNumber(-left)} KES! Spent ${formatNumber(spent)} of ${formatNumber(monthlyBudget)} KES this month.`;
  }

  budgetStatus.className = state;
  budgetFill.style.width = Math.min(100, ratio * 100) + "%";
  budgetFill.className = "bd-fill " + state;
}

// 11. Spending by category (expenses only)
function renderBreakdown() {
  breakdownList.innerHTML = "";

  const totals = {};
  transactions.forEach((t) => {
    if (t.type !== "expense") return;
    const key = t.category.trim().toLowerCase();
    totals[key] = (totals[key] || 0) + t.amount;
  });

  const entries = Object.entries(totals).sort((a, b) => b[1] - a[1]);

  if (entries.length === 0) {
    const empty = document.createElement("li");
    empty.className = "bd-empty";
    empty.textContent = "No expenses yet.";
    breakdownList.appendChild(empty);
    return;
  }

  const totalSpent = entries.reduce((sum, entry) => sum + entry[1], 0);

  entries.forEach(([name, amount]) => {
    const raw = (amount / totalSpent) * 100;
    const pct = Math.round(raw);
    const pctText = raw < 1 ? "<1%" : pct + "%";
    const title = name.charAt(0).toUpperCase() + name.slice(1);

    const li = document.createElement("li");

    const label = document.createElement("div");
    label.className = "bd-label";
    label.textContent = `${title} · ${formatNumber(amount)} KES (${pctText})`;

    const bar = document.createElement("div");
    bar.className = "bd-bar";
    const fill = document.createElement("div");
    fill.className = "bd-fill";
    fill.style.width = Math.max(raw, 1) + "%";
    bar.appendChild(fill);

    li.appendChild(label);
    li.appendChild(bar);
    breakdownList.appendChild(li);
  });
}

// 12. Suggest categories you have already used, plus a few common ones
function renderCategorySuggestions() {
  categoryList.innerHTML = "";

  const defaults = [
    "Food",
    "Transport",
    "Airtime/Data",
    "Rent/Hostel",
    "Books/Stationery",
    "Fees",
    "Entertainment",
    "Other",
  ];

  const all = [...transactions.map((t) => t.category), ...defaults];
  const seen = new Set();

  all.forEach((value) => {
    const name = String(value || "").trim();
    const key = name.toLowerCase();
    if (name === "" || seen.has(key)) return;
    seen.add(key);

    const option = document.createElement("option");
    option.value = name;
    categoryList.appendChild(option);
  });
}

// 13. Draw the list and the totals on the page
function render() {
  list.innerHTML = "";
  let income = 0;
  let expenses = 0;

  if (transactions.length === 0) {
    const empty = document.createElement("li");
    empty.className = "empty";
    empty.textContent = "No transactions yet. Add your first one above.";
    list.appendChild(empty);
  }

  const sorted = [...transactions].sort(
    (a, b) => b.date.localeCompare(a.date) || b.id - a.id
  );

  sorted.forEach((t) => {
    if (t.type === "income") {
      income += t.amount;
    } else {
      expenses += t.amount;
    }

    const li = document.createElement("li");
    li.classList.add(t.type === "income" ? "tx-income" : "tx-expense");
    if (t.id === editingId) {
      li.classList.add("editing");
    }

    const sign = t.type === "income" ? "+" : "-";
    const noteText = t.note ? ` · ${t.note}` : "";

    const text = document.createElement("span");
    text.textContent = `${t.date} · ${t.category}${noteText} · ${sign}${formatNumber(t.amount)} KES`;

    const actions = document.createElement("div");
    actions.className = "actions";

    const editBtn = document.createElement("button");
    editBtn.textContent = "Edit";
    editBtn.className = "edit-btn";
    editBtn.addEventListener("click", () => startEdit(t.id));

    const delBtn = document.createElement("button");
    delBtn.textContent = "Delete";
    delBtn.addEventListener("click", () => deleteTransaction(t.id));

    actions.appendChild(editBtn);
    actions.appendChild(delBtn);

    li.appendChild(text);
    li.appendChild(actions);
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

// 14. Connect the buttons, then draw the page once on load
transactionForm.addEventListener("submit", (event) => {
  event.preventDefault();
  addTransaction();
});

cancelBtn.addEventListener("click", () => {
  exitEditMode();
  render();
});
budgetBtn.addEventListener("click", setBudget);

if (monthlyBudget > 0) {
  budgetInput.value = monthlyBudget;
}

if (!dateInput.value) {
  dateInput.value = getTodayISODate();
}

render();

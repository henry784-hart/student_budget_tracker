// 1. Load saved transactions (or start with an empty list)
let transactions = [];
try {
  transactions = JSON.parse(localStorage.getItem("transactions")) || [];
} catch (e) {
  transactions = [];
}

// 2. Grab the page elements we need
const amountInput = document.getElementById("amount");
const typeInput = document.getElementById("type");
const categoryInput = document.getElementById("category");
const noteInput = document.getElementById("note");
const dateInput = document.getElementById("date");
const addBtn = document.getElementById("add-btn");
const list = document.getElementById("list");
const incomeEl = document.getElementById("income");
const expensesEl = document.getElementById("expenses");
const balanceEl = document.getElementById("balance");
const breakdownList = document.getElementById("breakdown-list");

// 3. Format numbers with commas
function formatNumber(n) {
  return n.toLocaleString("en-US", { maximumFractionDigits: 2 });
}

// 4. Save to the browser
function save() {
  localStorage.setItem("transactions", JSON.stringify(transactions));
}

// 5. Add a transaction
function addTransaction() {
  const amount = parseFloat(amountInput.value);
  const category = categoryInput.value.trim();

  if (isNaN(amount) || amount <= 0 || category === "" || dateInput.value === "") {
    alert("Please enter a valid amount, category and date.");
    return;
  }

  transactions.push({
    id: Date.now(),
    amount: amount,
    type: typeInput.value,
    category: category,
    note: noteInput.value.trim(),
    date: dateInput.value,
  });

  save();
  render();

  amountInput.value = "";
  categoryInput.value = "";
  noteInput.value = "";
  dateInput.value = "";
}

// 6. Delete a transaction
function deleteTransaction(id) {
  transactions = transactions.filter((t) => t.id !== id);
  save();
  render();
}

// 7. Draw the list and the totals on the page
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

    const sign = t.type === "income" ? "+" : "-";
    const noteText = t.note ? ` · ${t.note}` : "";
    li.textContent = `${t.date} · ${t.category}${noteText} · ${sign}${formatNumber(t.amount)} KES `;

    const btn = document.createElement("button");
    btn.textContent = "Delete";
    btn.addEventListener("click", () => deleteTransaction(t.id));

    li.appendChild(btn);
    list.appendChild(li);
  });

  const balance = income - expenses;

  incomeEl.textContent = formatNumber(income);
  expensesEl.textContent = formatNumber(expenses);
  balanceEl.textContent = formatNumber(balance);

  balanceEl.classList.toggle("positive", balance >= 0);
  balanceEl.classList.toggle("negative", balance < 0);
  renderBreakdown();
}
// Spending by category (expenses only)
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
    const pct = Math.round((amount / totalSpent) * 100);
    const title = name.charAt(0).toUpperCase() + name.slice(1);

    const li = document.createElement("li");

    const label = document.createElement("div");
    label.className = "bd-label";
    label.textContent = `${title} · ${formatNumber(amount)} KES (${pct}%)`;

    const bar = document.createElement("div");
    bar.className = "bd-bar";
    const fill = document.createElement("div");
    fill.className = "bd-fill";
    fill.style.width = pct + "%";
    bar.appendChild(fill);

    li.appendChild(label);
    li.appendChild(bar);
    breakdownList.appendChild(li);
  });
}
// 8. Connect the button, then draw the page once on load
addBtn.addEventListener("click", addTransaction);
render();
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
const dateInput = document.getElementById("date");
const addBtn = document.getElementById("add-btn");
const list = document.getElementById("list");
const incomeEl = document.getElementById("income");
const expensesEl = document.getElementById("expenses");
const balanceEl = document.getElementById("balance");

// 3. Format numbers with commas, e.g. 1500000 -> 1,500,000
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
    date: dateInput.value,
  });

  save();
  render();

  amountInput.value = "";
  categoryInput.value = "";
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

  // Empty message
  if (transactions.length === 0) {
    const empty = document.createElement("li");
    empty.className = "empty";
    empty.textContent = "No transactions yet. Add your first one above.";
    list.appendChild(empty);
  }

  // Newest date first (ties: most recently added first)
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
    li.textContent = `${t.date} · ${t.category} · ${sign}${formatNumber(t.amount)} KES `;

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

  // Balance colour: green if positive or zero, orange if negative
  balanceEl.classList.toggle("positive", balance >= 0);
  balanceEl.classList.toggle("negative", balance < 0);
}

// 8. Connect the button, then draw the page once on load
addBtn.addEventListener("click", addTransaction);
render();
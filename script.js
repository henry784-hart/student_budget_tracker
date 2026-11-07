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

// 3. Save to the browser
function save() {
  localStorage.setItem("transactions", JSON.stringify(transactions));
}

// 4. Add a transaction
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

// 5. Delete a transaction
function deleteTransaction(id) {
  transactions = transactions.filter((t) => t.id !== id);
  save();
  render();
}

// 6. Draw the list and the totals on the page
function render() {
  list.innerHTML = "";
  let income = 0;
  let expenses = 0;

  transactions.forEach((t) => {
    if (t.type === "income") {
      income += t.amount;
    } else {
      expenses += t.amount;
    }

    const li = document.createElement("li");
    const sign = t.type === "income" ? "+" : "-";
    li.textContent = `${t.date} · ${t.category} · ${sign}${t.amount} KES `;

    const btn = document.createElement("button");
    btn.textContent = "Delete";
    btn.addEventListener("click", () => deleteTransaction(t.id));

    li.appendChild(btn);
    list.appendChild(li);
  });

  incomeEl.textContent = income;
  expensesEl.textContent = expenses;
  balanceEl.textContent = income - expenses;
}

// 7. Connect the button, then draw the page once on load
addBtn.addEventListener("click", addTransaction);
render();
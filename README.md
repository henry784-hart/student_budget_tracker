* {
  box-sizing: border-box;
}

body {
  font-family: system-ui, sans-serif;
  background: #153552;
  color: #00fad4;
  margin: 0;
  padding: 1rem;
}

main {
  max-width: 600px;
  margin: 0 auto;
}

h1 {
  text-align: center;
  font-size: 1.5rem;
}

section {
  background: rgba(41, 139, 163, 0.25);
  border-radius: 10px;
  padding: 1rem;
  margin-bottom: 1rem;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.1);
}

.hidden {
  display: none !important;
}

.auth-panel {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 60vh;
}

.auth-card {
  width: min(100%, 420px);
  background: rgba(14, 32, 52, 0.85);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 16px;
  padding: 1.5rem;
}

.auth-card h2 {
  margin-top: 0;
  text-align: center;
  color: #00fad4;
}

.auth-message {
  margin-bottom: 1rem;
  color: #dbeafe;
  text-align: center;
}

.auth-message.error {
  color: #fca5a5;
}

#auth-form {
  display: grid;
  gap: 0.75rem;
}

#auth-form label {
  display: grid;
  gap: 0.4rem;
  color: #dbeafe;
  font-weight: 600;
}

#auth-form input {
  padding: 0.8rem 0.75rem;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  background: rgba(255, 255, 255, 0.95);
  color: #0f172a;
}

.auth-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
  margin-top: 0.5rem;
}

button {
  border: none;
  border-radius: 8px;
  padding: 0.8rem 1rem;
  font-weight: 700;
  cursor: pointer;
}

#login-btn,
#add-btn,
#budget-form button {
  background: #1a7f4b;
  color: white;
}

#register-btn,
#cancel-btn,
#logout-btn {
  background: #64748b;
  color: white;
}

#logout-btn {
  width: 100%;
  margin-top: 1rem;
}

.user-banner {
  text-align: center;
  margin-top: -0.5rem;
  margin-bottom: 1rem;
  color: #dbeafe;
}

#summary {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.5rem;
  text-align: center;
  font-weight: bold;
}

#monthly-summary {
  padding-top: 0.8rem;
}

.month-label {
  margin: 0 0 0.8rem;
  opacity: 0.8;
  font-size: 0.95rem;
}

.monthly-cards {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.75rem;
}

.monthly-card {
  background: rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  padding: 0.8rem 0.6rem;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  align-items: center;
  text-align: center;
}

.monthly-card .label {
  font-size: 0.8rem;
  opacity: 0.8;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.monthly-card strong {
  font-size: 0.95rem;
}

.monthly-card.income strong { color: #4ade80; }
.monthly-card.expense strong { color: #fb923c; }
.monthly-card.balance strong { color: #00fad4; }
.monthly-card.positive strong { color: #4ade80; }
.monthly-card.negative strong { color: #fb923c; }

#transaction-form { display: grid; gap: 0.6rem; }
#add-transaction input,
#add-transaction select,
#add-transaction button {
  display: block;
  width: 100%;
  padding: 0.7rem;
  font-size: 1rem;
  border: 1px solid #ccc;
  border-radius: 6px;
}

#add-transaction input,
#add-transaction select {
  background: white;
  color: #222;
  color-scheme: light;
}

#add-transaction input[type="date"]::-webkit-calendar-picker-indicator { cursor: pointer; }
#note { grid-column: 1 / -1; }

#list, #breakdown-list { list-style: none; padding: 0; margin: 0; }
#list li {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.75rem;
  padding: 0.6rem 0;
  border-bottom: 1px solid #eee;
}
#list li span { overflow-wrap: anywhere; }
#list li button {
  background: #c0392b;
  color: white;
  border: none;
  border-radius: 6px;
  padding: 0.3rem 0.7rem;
  cursor: pointer;
}
#list li.tx-income { color: #4ade80; }
#list li.tx-expense { color: #fb923c; }
#balance.positive { color: #4ade80; }
#balance.negative { color: #fb923c; }
#list li.empty { justify-content: center; border-bottom: none; opacity: 0.7; }
.actions { display: flex; gap: 0.5rem; flex-shrink: 0; }
#list li button.edit-btn { background: #2563eb; }
#list li.editing { outline: 2px solid #00e5c3; outline-offset: 4px; border-radius: 6px; }

#breakdown-list li { margin-bottom: 0.9rem; }
.bd-label { margin-bottom: 0.3rem; }
.bd-bar {
  height: 10px;
  background: rgba(255, 255, 255, 0.15);
  border-radius: 6px;
  overflow: hidden;
}
.bd-fill { height: 100%; background: #fb923c; border-radius: 6px; }
#breakdown-list li.bd-empty { opacity: 0.7; text-align: center; }

#budget-form { display: flex; gap: 0.6rem; margin-bottom: 0.8rem; }
#budget-form input {
  flex: 1;
  min-width: 0;
  padding: 0.7rem;
  font-size: 1rem;
  border: 1px solid #ccc;
  border-radius: 6px;
  background: white;
  color: #222;
  color-scheme: light;
}
#budget-status { margin: 0 0 0.6rem; }
#budget-status.warn { color: #fb923c; }
#budget-status.over { color: #f87171; font-weight: bold; }
#budget-fill.ok { background: #4ade80; }
#budget-fill.warn { background: #fb923c; }
#budget-fill.over { background: #ef4444; }

@media (min-width: 768px) {
  body { padding: 2rem; }
  main { max-width: 900px; }
  h1 { font-size: 2rem; }
  #summary { font-size: 1.2rem; }
  .monthly-card strong { font-size: 1.1rem; }
  #add-transaction { display: grid; grid-template-columns: repeat(2, 1fr); gap: 0.8rem; }
  #add-transaction h2 { grid-column: 1 / -1; margin: 0; }
  #transaction-form { grid-column: 1 / -1; grid-template-columns: repeat(2, 1fr); }
  #category, #note, #add-btn, #cancel-btn { grid-column: 1 / -1; }
}

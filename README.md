# Student Budget Tracker

A simple web app that helps university students record income and expenses,
see their balance, and keep track of where their money goes.

**Live app:** [https://henry784-hart.github.io/student_budget_tracker/](https://henry784-hart.github.io/student_budget_tracker/)

## Features

- Add, edit and delete income and expense transactions
- Optional note on each transaction
- Category suggestions while typing
- See total income, expenses and balance
- Spending breakdown by category
- Monthly budget limit with progress bar and warnings
- Newest transactions shown first
- Paste an M-Pesa message to fill in a transaction automatically
- Data is saved in a SQLite database through the Flask API
- Works on phones, tablets and laptops

## Built with

- **Frontend:** HTML, CSS and JavaScript
- **Backend:** Python, Flask and SQLite

## Run it locally

1. Clone the repo: `git clone https://github.com/henry784-hart/student_budget_tracker.git`
2. Open the folder in VS Code
3. Start the backend:

   ```bash
   cd backend
   python -m venv .venv
   .venv\Scripts\activate      # Windows
   source .venv/bin/activate   # macOS / Linux
   pip install -r requirements.txt
   python app.py
   ```

4. Open `index.html` with the Live Server extension (port 5500)
5. The API runs at `http://127.0.0.1:5000`

## API

| Method | Route | What it does |
| --- | --- | --- |
| GET | `/api/transactions` | List all transactions |
| POST | `/api/transactions` | Add a transaction |
| PUT | `/api/transactions/<id>` | Update a transaction |
| DELETE | `/api/transactions/<id>` | Delete a transaction |
| GET | `/api/budget?month=YYYY-MM` | Read the monthly limit |
| PUT | `/api/budget` | Set the monthly limit |
| POST | `/api/transactions/parse` | Turn an M-Pesa SMS into a draft transaction |

## Tests

```bash
cd backend
pip install -r requirements-dev.txt
python -m pytest tests -v
```

## Roadmap

- [x] Optional note on each transaction
- [x] Spending breakdown by category
- [x] Monthly budgets
- [x] Edit transactions
- [x] Category suggestions
- [x] Backend and database (Python + Flask)
- [x] M-Pesa message parser

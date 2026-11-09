# Student Budget Tracker

A web app for students to record income and expenses, monitor monthly spending and track a budget.

**Live static app:** https://henry784-hart.github.io/student_budget_tracker/

## Features
- Add, edit and delete income and expense transactions
- Monthly income, expenses and balance summary
- Spending breakdown by category and monthly budget progress
- Category suggestions and optional transaction notes
- SQLite persistence through the local Flask API; browser storage fallback when the API is unavailable
- Responsive layout for phones, tablets and laptops

## Run the full app locally

1. Install Python 3.10 or later.
2. In a terminal, from the repository root, install the backend packages:

   ```bash
   python -m pip install -r backend/requirements.txt
   ```

3. Start the API:

   ```bash
   python backend/app.py
   ```

   The API listens at `http://127.0.0.1:5000` and creates `backend/budget.db` automatically.
4. In a second terminal, serve the repository root (for example with the VS Code Live Server extension on port 5500), then open the served page. The frontend connects to the API by default.

Opening `index.html` directly or using GitHub Pages cannot run the Python backend. In that case the app reports that the API is unavailable and uses that browser's local storage. The monthly budget limit is still saved in browser storage.

Existing localStorage transactions are imported into SQLite automatically the first time the app connects to an empty database. Keep a backup of browser data before testing any migration.

## API endpoints
- `GET /api/health` — check API availability
- `GET /api/transactions` — list transactions
- `POST /api/transactions` — create a transaction
- `PUT /api/transactions/<id>` — update a transaction
- `DELETE /api/transactions/<id>` — delete a transaction
- `POST /api/transactions/import` — one-time import into an empty database

## Notes
This starter backend is intended for local development and has no user authentication. Do not expose it publicly with real personal data until authentication, HTTPS, and production deployment configuration are added.

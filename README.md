# Student Budget Tracker

A responsive student budgeting app with income/expense tracking, monthly summaries, category breakdowns, and per-account budgets.

## Local development

1. Install Python 3.10+.
2. From the repository root, install backend dependencies:

   ```bash
   python -m pip install -r backend/requirements.txt
   ```

3. Set a session secret in the same terminal. In PowerShell:

   ```powershell
   $env:SECRET_KEY = python -c "import secrets; print(secrets.token_hex(32))"
   ```

   For Command Prompt:

   ```bat
   for /f %i in ('python -c "import secrets; print(secrets.token_hex(32))"') do set SECRET_KEY=%i
   ```

4. Start the API from the repository root:

   ```bash
   python backend/app.py
   ```

   It listens on `http://127.0.0.1:5000` and creates `backend/budget.db`. Keep this terminal open.
5. In VS Code, start Live Server on `index.html` (port 5500), or from a second terminal at the repository root run `python -m http.server 8000` and open `http://127.0.0.1:8000`.
6. Create an account in the app, then log in. Transactions and monthly budget are saved in SQLite for that account.

## API routes
- `POST /api/auth/register` — create an account and sign in
- `POST /api/auth/login` — sign in
- `POST /api/auth/logout` — sign out
- `GET /api/auth/me` — check current session
- `GET`, `POST /api/transactions` — list/create the signed-in user's transactions
- `PUT`, `DELETE /api/transactions/<id>` — update/delete only that user's transaction
- `GET`, `PUT /api/budget` — read/update the signed-in user's monthly budget
- `GET /api/health` — API health check

## Data and deployment notes
The backend migration preserves older transaction rows but leaves them unassigned rather than exposing them to a newly registered account. Existing browser `localStorage` transactions and budgets are not imported automatically; retain a backup and migrate deliberately.

This is a local-development starter, not production-ready authentication. It has no password reset, rate limiting, email verification, or CSRF-token flow. Do not expose it publicly with real personal data until those protections, HTTPS, a persistent database, production server settings, and a stable `SECRET_KEY` are configured. For a deployed frontend and API on different sites, configure credentialed CORS and secure cookie settings for those exact origins.

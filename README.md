# Student Budget Tracker

A simple web app that helps university students record income and expenses,
see their balance, and keep track of where their money goes.

**Live app:** [https://henry784-hart.github.io/student_budget_tracker/](https://henry784-hart.github.io/student_budget_tracker/)

## Features

- **Sign in / create an account** — each user only ever sees their own data
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

## Security

- Passwords are stored only as salted hashes (`werkzeug.security`), never in plain text.
- Sign-in state lives in an **httpOnly**, `SameSite` session cookie, so page scripts cannot read it.
- Every `/api` route except register/login/logout requires a signed-in user (401 otherwise).
- Every query is filtered by the logged-in `user_id`, including update and delete, so one
  user can never read or change another user's transactions or budgets.
- All SQL uses parameter binding (no string-built queries), amounts must be finite numbers
  in range, and text fields have length limits.
- Request bodies are capped at 64 KB, CORS is restricted to a known origin list, and
  responses carry `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` and
  `Cache-Control: no-store`.

### Deploying

The repo already contains a `Procfile` (`web: gunicorn --chdir backend app:app`), so
Render starts the app correctly with no build command changes.

Set these **environment variables** on the host (Render → Environment). A ready-made
list is in `backend/.env.example`:

| Variable | Value | Why |
| --- | --- | --- |
| `SECRET_KEY` | a long random string | Signs the session cookie. Without it the app **refuses to start** on a real host, because every restart would log everyone out. |
| `CROSS_SITE_COOKIES` | `1` | GitHub Pages and Render are different sites, so the cookie must be `SameSite=None; Secure`. |
| `DB_PATH` | path on a persistent disk | Render's free disk is wiped on every deploy. Without a mounted volume your users' data disappears. |

Generate a key with:

```bash
python -c "import secrets; print(secrets.token_hex(48))"
```

Then run with `gunicorn`, never `debug=True`. Locally, a missing `SECRET_KEY` just
falls back to a throwaway key so development still works.

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

4. Open `login.html` with the Live Server extension (port 5500)
5. Create an account — you are taken to `index.html` with your own data
6. The API runs at `http://127.0.0.1:5000`

> Upgrading from the version without sign-in? The old `budget.db` tables had no owner,
> so they are dropped once on first start and you begin with a clean database.

## API

All `/api` routes except the auth ones return `401` when you are not signed in, and every
row is scoped to the signed-in user.

| Method | Route | What it does |
| --- | --- | --- |
| POST | `/api/auth/register` | Create an account (email + password) and sign in |
| POST | `/api/auth/login` | Sign in |
| POST | `/api/auth/logout` | Sign out |
| GET | `/api/auth/me` | The signed-in user's email |
| GET | `/api/transactions` | List **your** transactions |
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
- [x] Sign-in with per-user data isolation

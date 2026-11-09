import math
import os
import secrets
import sqlite3
from datetime import date

from flask import Flask, jsonify, request, session
from flask_cors import CORS
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "false").lower() == "true",
)
if not os.environ.get("SECRET_KEY"):
    print("WARNING: Using a temporary development session key. Set SECRET_KEY before deployment.")

CORS(
    app,
    supports_credentials=True,
    resources={
        r"/api/*": {
            "origins": [
                "http://localhost:5500",
                "http://127.0.0.1:5500",
                "http://localhost:8000",
                "http://127.0.0.1:8000",
            ]
        }
    },
)

DB_PATH = os.environ.get(
    "BUDGET_DB_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "budget.db"),
)
VALID_TYPES = {"income", "expense"}


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    db_directory = os.path.dirname(DB_PATH)
    if db_directory:
        os.makedirs(db_directory, exist_ok=True)
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                amount REAL NOT NULL CHECK (amount > 0),
                type TEXT NOT NULL CHECK (type IN ('income', 'expense')),
                category TEXT NOT NULL CHECK (length(trim(category)) > 0),
                note TEXT NOT NULL DEFAULT '',
                date TEXT NOT NULL,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        # Preserve existing transaction records, but leave their ownership unset.
        # They must not be silently exposed to whichever user registers first.
        columns = {row[1] for row in conn.execute("PRAGMA table_info(transactions)")}
        if "user_id" not in columns:
            conn.execute(
                "ALTER TABLE transactions ADD COLUMN user_id INTEGER REFERENCES users(id)"
            )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_transactions_user_date "
            "ON transactions(user_id, date DESC, id DESC)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS budgets (
                user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                monthly_limit REAL NOT NULL CHECK (monthly_limit > 0)
            )
            """
        )


def validate_transaction(data):
    if not isinstance(data, dict):
        return None, "Request body must be a JSON object."
    amount = data.get("amount")
    if isinstance(amount, bool):
        return None, "Amount must be a number greater than zero."
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return None, "Amount must be a number greater than zero."
    if not math.isfinite(amount) or amount <= 0:
        return None, "Amount must be a finite number greater than zero."

    transaction_type = data.get("type")
    if transaction_type not in VALID_TYPES:
        return None, "Type must be either 'income' or 'expense'."
    category = data.get("category")
    if not isinstance(category, str) or not category.strip():
        return None, "Category is required."
    note = data.get("note", "")
    if not isinstance(note, str):
        return None, "Note must be text."
    transaction_date = data.get("date")
    if not isinstance(transaction_date, str):
        return None, "Date must be a valid YYYY-MM-DD string."
    try:
        date.fromisoformat(transaction_date)
    except ValueError:
        return None, "Date must be a valid YYYY-MM-DD string."

    return {
        "amount": amount,
        "type": transaction_type,
        "category": category.strip(),
        "note": note.strip(),
        "date": transaction_date,
    }, None


def require_login():
    if session.get("user_id") is None:
        return jsonify({"error": "Please log in to continue."}), 401
    return None


@app.get("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.post("/api/auth/register")
def register():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Request body must be a JSON object."}), 400
    email = payload.get("email")
    password = payload.get("password")
    if not isinstance(email, str) or "@" not in email or len(email) > 254:
        return jsonify({"error": "Enter a valid email address."}), 400
    if not isinstance(password, str) or len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters."}), 400

    email = email.strip().lower()
    try:
        with get_db() as conn:
            cursor = conn.execute(
                "INSERT INTO users (email, password_hash) VALUES (?, ?)",
                (email, generate_password_hash(password)),
            )
            user_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        return jsonify({"error": "An account with that email already exists."}), 409

    session.clear()
    session["user_id"] = user_id
    return jsonify({"id": user_id, "email": email}), 201


@app.post("/api/auth/login")
def login():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Request body must be a JSON object."}), 400
    email = payload.get("email")
    password = payload.get("password")
    if not isinstance(email, str) or not isinstance(password, str):
        return jsonify({"error": "Email and password are required."}), 400

    with get_db() as conn:
        user = conn.execute(
            "SELECT id, email, password_hash FROM users WHERE email = ?",
            (email.strip().lower(),),
        ).fetchone()
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Invalid email or password."}), 401

    session.clear()
    session["user_id"] = user["id"]
    return jsonify({"id": user["id"], "email": user["email"]})


@app.post("/api/auth/logout")
def logout():
    session.clear()
    return jsonify({"message": "Logged out."})


@app.get("/api/auth/me")
def who_am_i():
    user_id = session.get("user_id")
    if user_id is None:
        return jsonify({"error": "Not logged in."}), 401
    with get_db() as conn:
        user = conn.execute("SELECT id, email FROM users WHERE id = ?", (user_id,)).fetchone()
    if user is None:
        session.clear()
        return jsonify({"error": "Session is no longer valid."}), 401
    return jsonify({"id": user["id"], "email": user["email"]})


@app.get("/api/transactions")
def get_transactions():
    auth_error = require_login()
    if auth_error:
        return auth_error
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, amount, type, category, note, date FROM transactions "
            "WHERE user_id = ? ORDER BY date DESC, id DESC",
            (session["user_id"],),
        ).fetchall()
    return jsonify([dict(row) for row in rows])


@app.post("/api/transactions")
def create_transaction():
    auth_error = require_login()
    if auth_error:
        return auth_error
    transaction, error = validate_transaction(request.get_json(silent=True))
    if error:
        return jsonify({"error": error}), 400
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO transactions (amount, type, category, note, date, user_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                transaction["amount"], transaction["type"], transaction["category"],
                transaction["note"], transaction["date"], session["user_id"],
            ),
        )
        row = conn.execute(
            "SELECT id, amount, type, category, note, date FROM transactions WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
    return jsonify(dict(row)), 201


@app.put("/api/transactions/<int:tx_id>")
def update_transaction(tx_id):
    auth_error = require_login()
    if auth_error:
        return auth_error
    transaction, error = validate_transaction(request.get_json(silent=True))
    if error:
        return jsonify({"error": error}), 400
    with get_db() as conn:
        cursor = conn.execute(
            "UPDATE transactions SET amount = ?, type = ?, category = ?, note = ?, date = ? "
            "WHERE id = ? AND user_id = ?",
            (
                transaction["amount"], transaction["type"], transaction["category"],
                transaction["note"], transaction["date"], tx_id, session["user_id"],
            ),
        )
        if cursor.rowcount == 0:
            return jsonify({"error": "Transaction not found."}), 404
        row = conn.execute(
            "SELECT id, amount, type, category, note, date FROM transactions WHERE id = ?",
            (tx_id,),
        ).fetchone()
    return jsonify(dict(row))


@app.delete("/api/transactions/<int:tx_id>")
def delete_transaction(tx_id):
    auth_error = require_login()
    if auth_error:
        return auth_error
    with get_db() as conn:
        cursor = conn.execute(
            "DELETE FROM transactions WHERE id = ? AND user_id = ?",
            (tx_id, session["user_id"]),
        )
        if cursor.rowcount == 0:
            return jsonify({"error": "Transaction not found."}), 404
    return jsonify({"deleted": tx_id})


@app.get("/api/budget")
def get_budget():
    auth_error = require_login()
    if auth_error:
        return auth_error
    with get_db() as conn:
        row = conn.execute(
            "SELECT monthly_limit FROM budgets WHERE user_id = ?",
            (session["user_id"],),
        ).fetchone()
    return jsonify({"monthly_limit": row["monthly_limit"] if row else None})


@app.put("/api/budget")
def set_budget():
    auth_error = require_login()
    if auth_error:
        return auth_error
    payload = request.get_json(silent=True)
    value = payload.get("monthly_limit") if isinstance(payload, dict) else None
    if isinstance(value, bool):
        return jsonify({"error": "Monthly limit must be a number greater than zero."}), 400
    try:
        value = float(value)
    except (TypeError, ValueError):
        return jsonify({"error": "Monthly limit must be a number greater than zero."}), 400
    if not math.isfinite(value) or value <= 0:
        return jsonify({"error": "Monthly limit must be a number greater than zero."}), 400
    with get_db() as conn:
        conn.execute(
            "INSERT INTO budgets (user_id, monthly_limit) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET monthly_limit = excluded.monthly_limit",
            (session["user_id"], value),
        )
    return jsonify({"monthly_limit": value})


init_db()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)

import math
import os
import sqlite3
from datetime import date

from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)

# This development API is intended for local use. Add your deployed frontend
# origin here if you later deploy the backend separately.
CORS(
    app,
    resources={
        r"/api/*": {
            "origins": [
                "http://localhost:5500",
                "http://127.0.0.1:5500",
                "http://localhost:8000",
                "http://127.0.0.1:8000",
                "https://henry784-hart.github.io",
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
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                amount REAL NOT NULL CHECK (amount > 0),
                type TEXT NOT NULL CHECK (type IN ('income', 'expense')),
                category TEXT NOT NULL CHECK (length(trim(category)) > 0),
                note TEXT NOT NULL DEFAULT '',
                date TEXT NOT NULL
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


def row_to_dict(row):
    return dict(row)


@app.get("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/api/transactions")
def get_transactions():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, amount, type, category, note, date "
            "FROM transactions ORDER BY date DESC, id DESC"
        ).fetchall()
    return jsonify([row_to_dict(row) for row in rows])


@app.post("/api/transactions")
def create_transaction():
    transaction, error = validate_transaction(request.get_json(silent=True))
    if error:
        return jsonify({"error": error}), 400

    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO transactions (amount, type, category, note, date) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                transaction["amount"],
                transaction["type"],
                transaction["category"],
                transaction["note"],
                transaction["date"],
            ),
        )
        row = conn.execute(
            "SELECT id, amount, type, category, note, date "
            "FROM transactions WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
    return jsonify(row_to_dict(row)), 201


@app.put("/api/transactions/<int:tx_id>")
def update_transaction(tx_id):
    transaction, error = validate_transaction(request.get_json(silent=True))
    if error:
        return jsonify({"error": error}), 400

    with get_db() as conn:
        cursor = conn.execute(
            "UPDATE transactions SET amount = ?, type = ?, category = ?, note = ?, date = ? "
            "WHERE id = ?",
            (
                transaction["amount"],
                transaction["type"],
                transaction["category"],
                transaction["note"],
                transaction["date"],
                tx_id,
            ),
        )
        if cursor.rowcount == 0:
            return jsonify({"error": "Transaction not found."}), 404
        row = conn.execute(
            "SELECT id, amount, type, category, note, date "
            "FROM transactions WHERE id = ?",
            (tx_id,),
        ).fetchone()
    return jsonify(row_to_dict(row))


@app.delete("/api/transactions/<int:tx_id>")
def delete_transaction(tx_id):
    with get_db() as conn:
        cursor = conn.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))
        if cursor.rowcount == 0:
            return jsonify({"error": "Transaction not found."}), 404
    return jsonify({"deleted": tx_id})


@app.post("/api/transactions/import")
def import_transactions():
    """Import existing browser transactions in one atomic database operation."""
    body = request.get_json(silent=True)
    items = body.get("transactions") if isinstance(body, dict) else None
    if not isinstance(items, list):
        return jsonify({"error": "transactions must be an array."}), 400

    validated = []
    for index, item in enumerate(items):
        transaction, error = validate_transaction(item)
        if error:
            return jsonify({"error": f"Transaction {index + 1}: {error}"}), 400
        validated.append(transaction)

    with get_db() as conn:
        existing = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
        if existing:
            return jsonify({"error": "Import is only allowed when the database is empty."}), 409
        conn.executemany(
            "INSERT INTO transactions (amount, type, category, note, date) "
            "VALUES (:amount, :type, :category, :note, :date)",
            validated,
        )
        rows = conn.execute(
            "SELECT id, amount, type, category, note, date "
            "FROM transactions ORDER BY date DESC, id DESC"
        ).fetchall()
    return jsonify([row_to_dict(row) for row in rows]), 201


init_db()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)

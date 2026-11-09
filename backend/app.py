import os
import sqlite3
from datetime import datetime

from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "budget.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount REAL NOT NULL,
            type TEXT NOT NULL,
            category TEXT NOT NULL,
            note TEXT NOT NULL DEFAULT '',
            date TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def clean(data):
    """Check the incoming JSON. Returns (values, error)."""
    if not data:
        return None, "Send JSON data."

    try:
        amount = float(data.get("amount"))
    except (TypeError, ValueError):
        return None, "Amount must be a number."
    if amount <= 0:
        return None, "Amount must be greater than 0."

    kind = data.get("type")
    if kind not in ("income", "expense"):
        return None, "Type must be 'income' or 'expense'."

    category = str(data.get("category", "")).strip()
    date = str(data.get("date", "")).strip()
    note = str(data.get("note", "")).strip()
    if not category or not date:
        return None, "Category and date are required."

    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        return None, "Date must look like 2026-11-09."

    return {
        "amount": amount,
        "type": kind,
        "category": category,
        "note": note,
        "date": date,
    }, None


init_db()


@app.route("/")
def home():
    return jsonify({"message": "Student Budget Tracker API is running"})


@app.route("/api/transactions", methods=["GET"])
def list_transactions():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM transactions ORDER BY date DESC, id DESC"
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/transactions", methods=["POST"])
def add_transaction():
    values, error = clean(request.get_json(silent=True))
    if error:
        return jsonify({"error": error}), 400

    conn = get_db()
    cur = conn.execute(
        "INSERT INTO transactions (amount, type, category, note, date) "
        "VALUES (?, ?, ?, ?, ?)",
        (values["amount"], values["type"], values["category"],
         values["note"], values["date"]),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM transactions WHERE id = ?", (cur.lastrowid,)
    ).fetchone()
    conn.close()
    return jsonify(dict(row)), 201


@app.route("/api/transactions/<int:tx_id>", methods=["PUT"])
def update_transaction(tx_id):
    values, error = clean(request.get_json(silent=True))
    if error:
        return jsonify({"error": error}), 400

    conn = get_db()
    cur = conn.execute(
        "UPDATE transactions SET amount = ?, type = ?, category = ?, "
        "note = ?, date = ? WHERE id = ?",
        (values["amount"], values["type"], values["category"],
         values["note"], values["date"], tx_id),
    )
    conn.commit()
    changed = cur.rowcount
    row = conn.execute(
        "SELECT * FROM transactions WHERE id = ?", (tx_id,)
    ).fetchone()
    conn.close()

    if changed == 0:
        return jsonify({"error": "Transaction not found."}), 404
    return jsonify(dict(row))


@app.route("/api/transactions/<int:tx_id>", methods=["DELETE"])
def delete_transaction(tx_id):
    conn = get_db()
    cur = conn.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))
    conn.commit()
    deleted = cur.rowcount
    conn.close()

    if deleted == 0:
        return jsonify({"error": "Transaction not found."}), 404
    return jsonify({"deleted": tx_id})


if __name__ == "__main__":
    app.run(debug=True)
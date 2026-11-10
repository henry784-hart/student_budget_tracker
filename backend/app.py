import os
import re
import sqlite3
from datetime import datetime

from flask import Flask, jsonify, request

try:
    from flask_cors import CORS
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "flask-cors is not installed. Run: python -m pip install -r requirements.txt"
    ) from exc

app = Flask(__name__)

# Allow the static frontend (Live Server / GitHub Pages) to call this API.
# Add your deployed frontend origin here when you go live.
ALLOWED_ORIGINS = [
    "http://127.0.0.1:5500",
    "http://localhost:5500",
    "http://127.0.0.1:5501",
    "http://localhost:5501",
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "https://henry784-hart.github.io",
]
CORS(app, resources={r"/api/*": {"origins": ALLOWED_ORIGINS}})

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
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS budgets (
            month TEXT PRIMARY KEY,
            limit_amount REAL NOT NULL
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


@app.route("/api/budget", methods=["GET"])
def get_budget():
    month = request.args.get("month") or datetime.now().strftime("%Y-%m")
    conn = get_db()
    row = conn.execute(
        "SELECT limit_amount FROM budgets WHERE month = ?", (month,)
    ).fetchone()
    conn.close()
    return jsonify({"month": month, "limit": row["limit_amount"] if row else 0})


@app.route("/api/budget", methods=["PUT"])
def set_budget():
    data = request.get_json(silent=True) or {}
    month = str(data.get("month") or datetime.now().strftime("%Y-%m")).strip()

    try:
        limit = float(data.get("limit"))
    except (TypeError, ValueError):
        return jsonify({"error": "Limit must be a number."}), 400
    if limit <= 0:
        return jsonify({"error": "Limit must be greater than 0."}), 400

    try:
        datetime.strptime(month, "%Y-%m")
    except ValueError:
        return jsonify({"error": "Month must look like 2026-11."}), 400

    conn = get_db()
    conn.execute(
        "INSERT INTO budgets (month, limit_amount) VALUES (?, ?) "
        "ON CONFLICT(month) DO UPDATE SET limit_amount = excluded.limit_amount",
        (month, limit),
    )
    conn.commit()
    conn.close()
    return jsonify({"month": month, "limit": limit})


# --- M-Pesa message parser -------------------------------------------------

MPESA_PATTERN = re.compile(
    r"(?P<code>[A-Z0-9]{10})\s+Confirmed\.\s+"
    r"(?:Ksh|KES)?\s*(?P<amount>[\d,]+(?:\.\d{1,2})?)\s+"
    r"(?P<kind>paid to|sent to|received from)\s+"
    r"(?P<party>.+?)\s+on\s+(?P<date>\d{1,2}/\d{1,2}/\d{2,4})",
    re.IGNORECASE,
)

CATEGORY_HINTS = {
    "Food": ["restaurant", "cafe", "hotel", "kfc", "java", "canteen",
             "butchery", "supermarket", "naivas", "quickmart", "chandarana"],
    "Transport": ["matatu", "uber", "bolt", "fuel", "petrol", "total",
                  "shell", "kenol", "bus", "taxi"],
    "Airtime/Data": ["safaricom", "airtime", "data bundles", "telkom", "airtel"],
    "Rent/Hostel": ["rent", "hostel", "landlord", "caretaker"],
    "Books/Stationery": ["bookshop", "textbook", "stationery", "text book"],
    "Fees": ["school fees", "tuition", "university", "college"],
    "Entertainment": ["cinema", "netflix", "spotify", "showmax", "game"],
}


def guess_category(party):
    low = party.lower()
    for category, words in CATEGORY_HINTS.items():
        if any(word in low for word in words):
            return category
    return "Other"


@app.route("/api/transactions/parse", methods=["POST"])
def parse_mpesa():
    data = request.get_json(silent=True) or {}
    text = str(data.get("message", "")).strip()
    if not text:
        return jsonify({"error": "Paste the M-Pesa message."}), 400

    match = MPESA_PATTERN.search(text)
    if not match:
        return jsonify({"error": "Could not read that M-Pesa message."}), 400

    amount = float(match.group("amount").replace(",", ""))
    kind = match.group("kind").lower()
    party = match.group("party").strip()
    raw_date = match.group("date")

    date = None
    for fmt in ("%d/%m/%y", "%d/%m/%Y"):
        try:
            date = datetime.strptime(raw_date, fmt).strftime("%Y-%m-%d")
            break
        except ValueError:
            continue
    if date is None:
        return jsonify({"error": "Could not read the date in that message."}), 400

    return jsonify({
        "amount": amount,
        "type": "income" if kind == "received from" else "expense",
        "category": guess_category(party),
        "note": party,
        "date": date,
        "code": match.group("code"),
    })


if __name__ == "__main__":
    app.run(debug=True)
import csv
import hashlib
import io
import json
import math
import os
import re
import secrets
import sqlite3
import time
import urllib.request
from datetime import datetime, timedelta, timezone

from flask import Flask, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

try:
    from flask_cors import CORS
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "flask-cors is not installed. Run: python -m pip install -r requirements.txt"
    ) from exc

app = Flask(__name__)

# --- Configuration ----------------------------------------------------------
# SECRET_KEY signs the session cookie. Set a long random value in the host's
# environment (see backend/.env.example). Only fall back to a throwaway key in
# local development; on a real host a missing key is a hard error.
SECRET_KEY = os.environ.get("SECRET_KEY")
IS_PRODUCTION = bool(os.environ.get("RENDER") or os.environ.get("FLASK_ENV") == "production")
if not SECRET_KEY:
    if IS_PRODUCTION:
        raise RuntimeError(
            "SECRET_KEY is not set. Sessions would be invalidated on every "
            "restart. Set it in the host's environment variables."
        )
    SECRET_KEY = secrets.token_hex(32)

# The frontend (GitHub Pages) and the API (Render) are different sites, so the
# session cookie needs SameSite=None; Secure. Local development stays on Lax.
CROSS_SITE_COOKIES = bool(os.environ.get("CROSS_SITE_COOKIES"))

app.config.update(
    SECRET_KEY=SECRET_KEY,
    SESSION_COOKIE_HTTPONLY=True,   # JavaScript cannot read the cookie
    SESSION_COOKIE_SAMESITE="None" if CROSS_SITE_COOKIES else "Lax",
    SESSION_COOKIE_SECURE=CROSS_SITE_COOKIES or IS_PRODUCTION,
    PERMANENT_SESSION_LIFETIME=timedelta(days=7),
    MAX_CONTENT_LENGTH=64 * 1024,   # reject bodies bigger than 64 KB
        SESSION_COOKIE_PARTITIONED=CROSS_SITE_COOKIES,  # lets the cookie survive third-party cookie blocking
)

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
CORS(app, resources={r"/api/*": {"origins": ALLOWED_ORIGINS, "supports_credentials": True}})

# On hosts with an ephemeral disk (Render free tier), point DB_PATH at a mounted
# persistent volume or the database is wiped on every deploy.
DB_PATH = os.environ.get("DB_PATH") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "budget.db"
)

DATABASE_URL = os.environ.get("DATABASE_URL")
USE_POSTGRES = bool(DATABASE_URL)
if USE_POSTGRES:
    import psycopg
    from psycopg.rows import dict_row
    DB_INTEGRITY_ERRORS = (psycopg.IntegrityError,)
else:
    DB_INTEGRITY_ERRORS = (sqlite3.IntegrityError,)

ID_COLUMN = "SERIAL PRIMARY KEY" if USE_POSTGRES else "INTEGER PRIMARY KEY AUTOINCREMENT"

MAX_AMOUNT = 1_000_000_000        # one billion KES is plenty for a student
MAX_CATEGORY_LEN = 40
MAX_NOTE_LEN = 200
MAX_MESSAGE_LEN = 2000
MIN_PASSWORD_LEN = 8
MAX_PASSWORD_LEN = 128

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")

# --- Rate limiting ------------------------------------------------------------
# Distribution on Render is a single instance, so an in-process counter is enough.
# If you ever run more than one worker, move this to Redis.
RATE_LIMIT_WINDOW = 15 * 60          # 15 minutes
RATE_LIMIT_LOGIN_PER_IP = 20         # login/reset attempts from one IP
RATE_LIMIT_LOGIN_PER_EMAIL = 6       # attempts against one account
_rate_events = {}                    # key -> list of attempt timestamps

RESET_TOKEN_TTL = timedelta(hours=1)


# --- Database ---------------------------------------------------------------

class Connection:
    """Lets the rest of the code keep writing '?' placeholders on both
    SQLite (local) and Postgres (Render)."""

    def __init__(self, raw):
        self._raw = raw

    def execute(self, sql, params=()):
        if USE_POSTGRES:
            sql = sql.replace("?", "%s")
        return self._raw.execute(sql, params)

    def commit(self):
        self._raw.commit()

    def close(self):
        self._raw.close()


def get_db():
    if USE_POSTGRES:
        return Connection(psycopg.connect(DATABASE_URL, row_factory=dict_row))
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return Connection(conn)


def _table_columns(conn, table):
    return [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]


def _drop_legacy_tables(conn):
    """SQLite only: databases from before sign-in had no users, so start fresh."""
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'")]
    if "transactions" in tables and "user_id" not in _table_columns(conn, "transactions"):
        conn.execute("DROP TABLE transactions")
    if "budgets" in tables and "user_id" not in _table_columns(conn, "budgets"):
        conn.execute("DROP TABLE budgets")
    conn.commit()

class Connection:
    """Lets the rest of the code keep writing '?' placeholders on both
    SQLite (local) and Postgres (Render)."""

    def __init__(self, raw):
        self._raw = raw

    def execute(self, sql, params=()):
        if USE_POSTGRES:
            sql = sql.replace("?", "%s")
        return self._raw.execute(sql, params)

    def commit(self):
        self._raw.commit()

    def close(self):
        self._raw.close()


def get_db():
    if USE_POSTGRES:
        return Connection(psycopg.connect(DATABASE_URL, row_factory=dict_row))
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return Connection(conn)


def _table_columns(conn, table):
    return [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]


def _drop_legacy_tables(conn):
    """SQLite only: databases from before sign-in had no users, so start fresh."""
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'")]
    if "transactions" in tables and "user_id" not in _table_columns(conn, "transactions"):
        conn.execute("DROP TABLE transactions")
    if "budgets" in tables and "user_id" not in _table_columns(conn, "budgets"):
        conn.execute("DROP TABLE budgets")
    conn.commit()


def init_db():
    conn = get_db()
    if not USE_POSTGRES:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 10000")
        _drop_legacy_tables(conn)
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS users (
            id {ID_COLUMN},
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS transactions (
            id {ID_COLUMN},
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            amount DOUBLE PRECISION NOT NULL,
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
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            month TEXT NOT NULL,
            limit_amount DOUBLE PRECISION NOT NULL,
            PRIMARY KEY (user_id, month)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_tx_user_date "
        "ON transactions (user_id, date DESC, id DESC)"
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS password_resets (
            token_hash TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            expires_at TEXT NOT NULL,
            used INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_reset_user ON password_resets (user_id)"
    )
    conn.commit()
    conn.close()

# --- Validation helpers -----------------------------------------------------
def parse_money(value):
    """Return a positive, finite amount rounded to 2 dp, or None if invalid."""
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(amount):  # rejects nan, inf, -inf
        return None
    if amount <= 0 or amount > MAX_AMOUNT:
        return None
    return round(amount, 2)


def clean(data):
    """Check the incoming transaction JSON. Returns (values, error)."""
    if not isinstance(data, dict) or not data:
        return None, "Send JSON data."

    amount = parse_money(data.get("amount"))
    if amount is None:
        return None, "Amount must be a number between 0.01 and 1,000,000,000."

    kind = data.get("type")
    if kind not in ("income", "expense"):
        return None, "Type must be 'income' or 'expense'."

    category = str(data.get("category", "")).strip()
    date = str(data.get("date", "")).strip()
    note = str(data.get("note", "")).strip()
    if not category or not date:
        return None, "Category and date are required."
    if len(category) > MAX_CATEGORY_LEN:
        return None, f"Category must be {MAX_CATEGORY_LEN} characters or fewer."
    if len(note) > MAX_NOTE_LEN:
        return None, f"Note must be {MAX_NOTE_LEN} characters or fewer."

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


def rate_limit_hit(key, limit):
    """Record an attempt for `key`. Returns True when the caller is over the limit."""
    now = time.monotonic()
    cutoff = now - RATE_LIMIT_WINDOW
    events = [t for t in _rate_events.get(key, []) if t > cutoff]
    events.append(now)
    _rate_events[key] = events
    return len(events) > limit


def rate_limit_clear(key):
    _rate_events.pop(key, None)


def client_ip():
    # On Render, Cloudflare sets True-Client-IP and a client cannot forge it.
    # X-Forwarded-For is NOT used: clients can send their own value.
    if IS_PRODUCTION:
        real = request.headers.get("True-Client-IP", "").strip()
        if real:
            return real
    return request.remote_addr or "unknown"

def send_email(to, subject, body):
    """Deliver an email. Uses Resend when RESEND_API_KEY is set; otherwise the
    message is logged so local development still works end to end."""
    api_key = os.environ.get("RESEND_API_KEY")
    sender = os.environ.get("MAIL_FROM", "Student Budget Tracker <onboarding@resend.dev>")
    if not api_key:
        app.logger.warning("EMAIL (not sent, no RESEND_API_KEY) to=%s subject=%s\n%s",
                           to, subject, body)
        return False

    payload = json.dumps({"from": sender, "to": [to], "subject": subject,
                          "text": body}).encode()
    req = urllib.request.Request(
        "https://api.resend.com/emails", data=payload, method="POST",
        headers={"Authorization": f"Bearer {api_key}",
                 "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return 200 <= resp.status < 300
    except Exception:  # pragma: no cover - network failure
        app.logger.exception("Could not send email to %s", to)
        return False


def get_json_body():
    """Return (data, error) for a JSON request body of a sane size."""
    data = request.get_json(silent=True)
    if data is None:
        return None, "Send JSON data."
    if not isinstance(data, dict):
        return None, "JSON body must be an object."
    return data, None


init_db()


# --- Auth plumbing ----------------------------------------------------------
def current_user_id():
    return session.get("user_id")


@app.before_request
def require_login():
    """Every /api route except register/login/logout needs a signed-in user."""
    if request.method == "OPTIONS":  # CORS preflight carries no cookies
        return None
    if not request.path.startswith("/api/"):
        return None
    if request.path in ("/api/auth/register", "/api/auth/login", "/api/auth/logout",
                        "/api/auth/forgot-password", "/api/auth/reset-password",
                        "/api/health"):
        return None
    if current_user_id() is None:
        return jsonify({"error": "Please sign in first."}), 401
    return None


@app.after_request
def security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    return response


def json_error(message, status):
    return jsonify({"error": message}), status


@app.errorhandler(413)
def too_large(_err):
    return json_error("That request is too large.", 413)


@app.errorhandler(404)
def not_found(_err):
    return json_error("Not found.", 404)


@app.errorhandler(405)
def bad_method(_err):
    return json_error("Method not allowed.", 405)


@app.errorhandler(500)
def server_error(_err):  # pragma: no cover - safety net
    return json_error("Something went wrong on the server.", 500)


# --- Health ------------------------------------------------------------------
@app.route("/")
def home():
    return jsonify({"message": "Student Budget Tracker API is running"})


@app.route("/api/health")
def health():
    return jsonify({"ok": True})


# --- Auth routes -------------------------------------------------------------
@app.route("/api/auth/register", methods=["POST"])
def register():
    data, error = get_json_body()
    if error:
        return json_error(error, 400)

    email = str(data.get("email", "")).strip().lower()
    password = data.get("password")

    if not EMAIL_PATTERN.match(email) or len(email) > 254:
        return json_error("Enter a valid email address.", 400)
    if not isinstance(password, str) or len(password) < MIN_PASSWORD_LEN:
        return json_error(f"Password must be at least {MIN_PASSWORD_LEN} characters.", 400)
    if len(password) > MAX_PASSWORD_LEN:
        return json_error(f"Password must be {MAX_PASSWORD_LEN} characters or fewer.", 400)

    if rate_limit_hit(f"register:{client_ip()}", RATE_LIMIT_LOGIN_PER_IP):
        return json_error("Too many sign-up attempts. Please wait 15 minutes.", 429)
    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT INTO users (email, password_hash, created_at) "
            "VALUES (?, ?, ?) RETURNING id",
            (email, generate_password_hash(password), datetime.now(timezone.utc).isoformat()),
        )
        new_id = cur.fetchone()["id"]
        conn.commit()
    except DB_INTEGRITY_ERRORS:
        conn.close()
        return json_error("An account with that email already exists.", 409)

    session.clear()
    session.permanent = True
    session["user_id"] = new_id
    conn.close()
    return jsonify({"email": email}), 201


@app.route("/api/auth/login", methods=["POST"])
def login():
    data, error = get_json_body()
    if error:
        return json_error(error, 400)

    email = str(data.get("email", "")).strip().lower()
    password = data.get("password")
    if not email or not isinstance(password, str) or not password:
        return json_error("Email and password are required.", 400)

    # Two limits: one IP cannot spray many accounts, one account cannot be
    # brute-forced from many IPs.
    ip_key = f"login-ip:{client_ip()}"
    email_key = f"login-email:{email}"
    if (rate_limit_hit(ip_key, RATE_LIMIT_LOGIN_PER_IP)
            or rate_limit_hit(email_key, RATE_LIMIT_LOGIN_PER_EMAIL)):
        return json_error("Too many sign-in attempts. Please wait 15 minutes.", 429)

    conn = get_db()
    row = conn.execute(
        "SELECT id, email, password_hash FROM users WHERE email = ?", (email,)
    ).fetchone()
    conn.close()

    # Same message and roughly the same work for unknown email and wrong
    # password, so the response does not reveal which emails are registered.
    if row is None or not check_password_hash(row["password_hash"], password):
        return json_error("Wrong email or password.", 401)

    rate_limit_clear(ip_key)
    rate_limit_clear(email_key)
    session.clear()
    session.permanent = True
    session["user_id"] = row["id"]
    return jsonify({"email": row["email"]})


# --- Password reset ----------------------------------------------------------
def hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


def frontend_url():
    return os.environ.get("FRONTEND_URL", "http://127.0.0.1:5500").rstrip("/")


def reset_link(token):
    return f"{frontend_url()}/reset-password.html?token={token}"


@app.route("/api/auth/forgot-password", methods=["POST"])
def forgot_password():
    """Start a password reset. Always answers 200 so the endpoint cannot be used
    to discover which email addresses have accounts."""
    data, error = get_json_body()
    if error:
        return json_error(error, 400)

    email = str(data.get("email", "")).strip().lower()
    if not EMAIL_PATTERN.match(email) or len(email) > 254:
        return json_error("Enter a valid email address.", 400)

    if rate_limit_hit(f"forgot-ip:{client_ip()}", RATE_LIMIT_LOGIN_PER_IP):
        return json_error("Too many reset requests. Please wait 15 minutes.", 429)

    conn = get_db()
    row = conn.execute("SELECT id, email FROM users WHERE email = ?", (email,)).fetchone()
    token = None
    if row is not None:
        token = secrets.token_urlsafe(32)
        expires = (datetime.now(timezone.utc) + RESET_TOKEN_TTL).isoformat()
        # One live token per account: a new request invalidates the old link.
        conn.execute("DELETE FROM password_resets WHERE user_id = ?", (row["id"],))
        conn.execute(
            "INSERT INTO password_resets (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
            (hash_token(token), row["id"], expires),
        )
        conn.commit()
    conn.close()

    if token is not None:
        send_email(
            email,
            "Reset your Student Budget Tracker password",
            "Someone asked to reset your password.\n\n"
            f"Open this link within 1 hour to choose a new one:\n{reset_link(token)}\n\n"
            "If this wasn't you, ignore this email - your password has not changed.",
        )

    response = {"message": "If that email has an account, a reset link is on its way."}
    # Local development only: surface the link so the flow can be tested without
    # an email provider. Never enabled unless explicitly asked for.
    if token is not None and os.environ.get("SHOW_RESET_LINK") == "1" and not IS_PRODUCTION:
        response["reset_link"] = reset_link(token)
    return jsonify(response)


@app.route("/api/auth/reset-password", methods=["POST"])
def reset_password():
    data, error = get_json_body()
    if error:
        return json_error(error, 400)

    token = str(data.get("token", "")).strip()
    password = data.get("password")
    if not token:
        return json_error("That reset link is not valid.", 400)
    if not isinstance(password, str) or len(password) < MIN_PASSWORD_LEN:
        return json_error(f"Password must be at least {MIN_PASSWORD_LEN} characters.", 400)
    if len(password) > MAX_PASSWORD_LEN:
        return json_error(f"Password must be {MAX_PASSWORD_LEN} characters or fewer.", 400)

    if rate_limit_hit(f"reset-ip:{client_ip()}", RATE_LIMIT_LOGIN_PER_IP):
        return json_error("Too many reset attempts. Please wait 15 minutes.", 429)

    conn = get_db()
    row = conn.execute(
        "SELECT user_id, expires_at, used FROM password_resets WHERE token_hash = ?",
        (hash_token(token),),
    ).fetchone()

    if row is None or row["used"]:
        conn.close()
        return json_error("That reset link is not valid. Ask for a new one.", 400)
    if datetime.fromisoformat(row["expires_at"]) < datetime.now(timezone.utc):
        conn.close()
        return json_error("That reset link has expired. Ask for a new one.", 400)

    conn.execute("UPDATE users SET password_hash = ? WHERE id = ?",
                 (generate_password_hash(password), row["user_id"]))
    # Burn every outstanding token for this user, not just the one used.
    conn.execute("DELETE FROM password_resets WHERE user_id = ?", (row["user_id"],))
    conn.commit()
    conn.close()

    return jsonify({"message": "Password changed. You can sign in now."})


@app.route("/api/auth/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True})


@app.route("/api/auth/me", methods=["GET"])
def me():
    conn = get_db()
    row = conn.execute(
        "SELECT email FROM users WHERE id = ?", (current_user_id(),)
    ).fetchone()
    conn.close()
    if row is None:
        session.clear()
        return json_error("Please sign in first.", 401)
    return jsonify({"email": row["email"]})


@app.route("/api/auth/account", methods=["DELETE"])
def delete_account():
    """Permanently delete the signed-in account and everything it owns."""
    data, error = get_json_body()
    if error:
        return json_error(error, 400)

    password = data.get("password")
    if not isinstance(password, str) or not password:
        return json_error("Enter your password to confirm.", 400)

    user_id = current_user_id()
    conn = get_db()
    row = conn.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None or not check_password_hash(row["password_hash"], password):
        conn.close()
        return json_error("Wrong password. Your account has not been deleted.", 401)

    # Cascades remove transactions, budgets and reset tokens.
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

    session.clear()
    return jsonify({"deleted": True})


@app.route("/api/transactions/export", methods=["GET"])
def export_transactions():
    """Download every transaction of the signed-in user as CSV."""
    conn = get_db()
    rows = conn.execute(
        "SELECT date, type, category, note, amount FROM transactions "
        "WHERE user_id = ? ORDER BY date DESC, id DESC",
        (current_user_id(),),
    ).fetchall()
    conn.close()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["date", "type", "category", "note", "amount_kes"])
    for r in rows:
        writer.writerow([r["date"], r["type"], r["category"], r["note"], f"{r['amount']:.2f}"])

    filename = f"budget-{datetime.now().strftime('%Y-%m-%d')}.csv"
    response = app.response_class(buffer.getvalue(), mimetype="text/csv")
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


# --- Transactions ------------------------------------------------------------
@app.route("/api/transactions", methods=["GET"])
def list_transactions():
    conn = get_db()
    rows = conn.execute(
        "SELECT id, amount, type, category, note, date FROM transactions "
        "WHERE user_id = ? ORDER BY date DESC, id DESC",
        (current_user_id(),),
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/transactions", methods=["POST"])
def add_transaction():
    values, error = clean(request.get_json(silent=True))
    if error:
        return json_error(error, 400)

    conn = get_db()
    row = conn.execute(
        "INSERT INTO transactions (user_id, amount, type, category, note, date) "
        "VALUES (?, ?, ?, ?, ?, ?) "
        "RETURNING id, amount, type, category, note, date",
        (current_user_id(), values["amount"], values["type"], values["category"],
         values["note"], values["date"]),
    ).fetchone()
    conn.commit()
    conn.close()
    return jsonify(dict(row)), 201

@app.route("/api/transactions/<int:tx_id>", methods=["PUT"])
def update_transaction(tx_id):
    values, error = clean(request.get_json(silent=True))
    if error:
        return json_error(error, 400)

    conn = get_db()
    cur = conn.execute(
        "UPDATE transactions SET amount = ?, type = ?, category = ?, "
        "note = ?, date = ? WHERE id = ? AND user_id = ?",
        (values["amount"], values["type"], values["category"],
         values["note"], values["date"], tx_id, current_user_id()),
    )
    conn.commit()
    changed = cur.rowcount
    row = conn.execute(
        "SELECT id, amount, type, category, note, date FROM transactions "
        "WHERE id = ? AND user_id = ?",
        (tx_id, current_user_id()),
    ).fetchone()
    conn.close()

    if changed == 0:
        return json_error("Transaction not found.", 404)
    return jsonify(dict(row))


@app.route("/api/transactions/<int:tx_id>", methods=["DELETE"])
def delete_transaction(tx_id):
    conn = get_db()
    cur = conn.execute(
        "DELETE FROM transactions WHERE id = ? AND user_id = ?",
        (tx_id, current_user_id()),
    )
    conn.commit()
    deleted = cur.rowcount
    conn.close()

    if deleted == 0:
        return json_error("Transaction not found.", 404)
    return jsonify({"deleted": tx_id})


# --- Budget ------------------------------------------------------------------
@app.route("/api/budget", methods=["GET"])
def get_budget():
    month = request.args.get("month") or datetime.now().strftime("%Y-%m")
    conn = get_db()
    row = conn.execute(
        "SELECT limit_amount FROM budgets WHERE month = ? AND user_id = ?",
        (month, current_user_id()),
    ).fetchone()
    conn.close()
    return jsonify({"month": month, "limit": row["limit_amount"] if row else 0})


@app.route("/api/budget", methods=["PUT"])
def set_budget():
    data, error = get_json_body()
    if error:
        return json_error(error, 400)

    month = str(data.get("month") or datetime.now().strftime("%Y-%m")).strip()

    limit = parse_money(data.get("limit"))
    if limit is None:
        return json_error("Limit must be a number between 0.01 and 1,000,000,000.", 400)

    try:
        datetime.strptime(month, "%Y-%m")
    except ValueError:
        return json_error("Month must look like 2026-11.", 400)

    conn = get_db()
    conn.execute(
        "INSERT INTO budgets (user_id, month, limit_amount) VALUES (?, ?, ?) "
        "ON CONFLICT(user_id, month) DO UPDATE SET limit_amount = excluded.limit_amount",
        (current_user_id(), month, limit),
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
    if not isinstance(data, dict):
        return json_error("Send JSON data.", 400)
    text = str(data.get("message", "")).strip()
    if not text:
        return json_error("Paste the M-Pesa message.", 400)
    if len(text) > MAX_MESSAGE_LEN:
        return json_error("That message is too long.", 400)

    match = MPESA_PATTERN.search(text)
    if not match:
        return json_error("Could not read that M-Pesa message.", 400)

    amount = parse_money(match.group("amount").replace(",", ""))
    if amount is None:
        return json_error("Could not read the amount in that message.", 400)
    kind = match.group("kind").lower()
    party = match.group("party").strip()[:MAX_NOTE_LEN]
    raw_date = match.group("date")

    date = None
    for fmt in ("%d/%m/%y", "%d/%m/%Y"):
        try:
            date = datetime.strptime(raw_date, fmt).strftime("%Y-%m-%d")
            break
        except ValueError:
            continue
    if date is None:
        return json_error("Could not read the date in that message.", 400)

    return jsonify({
        "amount": amount,
        "type": "income" if kind == "received from" else "expense",
        "category": guess_category(party)[:MAX_CATEGORY_LEN],
        "note": party,
        "date": date,
        "code": match.group("code"),
    })


if __name__ == "__main__":
    app.run(debug=False)

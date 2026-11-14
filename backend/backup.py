"""Back up (and restore) the budget database.

Usage (Postgres on Neon is the default):
    python backup.py                      # asks for DATABASE_URL, writes budget-DATE.json
    python backup.py --keep 14            # keep only the newest 14 backups
    python backup.py --copy-to D:\\backups # also copy the new backup somewhere else
    python backup.py --sqlite             # back up the local SQLite file instead
    python backup.py --restore FILE.json  # load a backup into an EMPTY database

DATABASE_URL is read from the environment if it is set. Otherwise you are asked
for it and what you type is hidden, so it never ends up in your shell history.

Backups go to  ~/budget-backups  by default, deliberately OUTSIDE the project
folder so they can never be committed to GitHub by accident. A backup holds
every user's email and password hash: keep the files private.

Needs one extra package for Postgres:   pip install pg8000
"""

import argparse
import getpass
import json
import os
import shutil
import sqlite3
import ssl
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

HERE = Path(__file__).resolve().parent
DEFAULT_DB = os.environ.get("DB_PATH") or str(HERE / "budget.db")
DEFAULT_OUT = Path.home() / "budget-backups"

# Tables in the order they must be restored (users first, other tables point at it).
# password_resets is left out on purpose: those links expire after an hour.
TABLES = {
    "users": ["id", "email", "password_hash", "created_at"],
    "transactions": ["id", "user_id", "amount", "type", "category", "note", "date"],
    "budgets": ["user_id", "month", "limit_amount"],
}
ORDER_BY = {
    "users": "id",
    "transactions": "id",
    "budgets": "user_id, month",
}


# --- Postgres ---------------------------------------------------------------
def get_url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        if not sys.stdin.isatty():
            raise SystemExit("DATABASE_URL is not set.")
        url = getpass.getpass("Paste your DATABASE_URL (input is hidden): ").strip()
    if not url:
        raise SystemExit("No DATABASE_URL given.")
    return url


def pg_connect(url: str):
    try:
        import pg8000.dbapi as pg
    except ImportError:
        raise SystemExit("Install the Postgres driver first:  pip install pg8000")

    parts = urlparse(url)
    if parts.scheme not in ("postgresql", "postgres") or not parts.hostname:
        raise SystemExit("That does not look like a Postgres connection string.")
    sslmode = (parse_qs(parts.query).get("sslmode") or ["require"])[0]

    options = dict(
        user=unquote(parts.username or ""),
        password=unquote(parts.password or ""),
        host=parts.hostname,
        port=parts.port or 5432,
        database=(parts.path or "/").lstrip("/"),
    )
    if sslmode != "disable":
        options["ssl_context"] = ssl.create_default_context()
    try:
        return pg.connect(**options), parts.hostname
    except Exception as exc:  # network, password, SSL ...
        raise SystemExit(f"Could not connect to the database: {exc}")


def read_postgres(url: str) -> dict:
    conn, _host = pg_connect(url)
    try:
        cur = conn.cursor()
        # One consistent snapshot, even if someone is using the app right now.
        cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        data = {}
        for table, cols in TABLES.items():
            cur.execute(f"SELECT {', '.join(cols)} FROM {table} ORDER BY {ORDER_BY[table]}")
            data[table] = [dict(zip(cols, row)) for row in cur.fetchall()]
        return data
    finally:
        conn.close()


def counts(data: dict) -> dict:
    return {table: len(rows) for table, rows in data.items()}


def backup_postgres(out_dir: Path) -> Path:
    data = read_postgres(get_url())
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    target = out_dir / f"budget-{stamp}.json"
    temp = out_dir / f"budget-{stamp}.json.tmp"

    payload = {
        "format": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": "postgres",
        "counts": counts(data),
        "tables": data,
    }
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    # Prove the file can be read back and matches before keeping it.
    check = json.loads(temp.read_text(encoding="utf-8"))
    if counts(check["tables"]) != counts(data):
        temp.unlink()
        raise SystemExit("Backup failed the read-back check. Nothing was kept.")
    os.replace(temp, target)

    print(f"Backup written: {target}")
    print("  " + "  ".join(f"{t}={n}" for t, n in counts(data).items()))
    return target


def restore_postgres(path: Path) -> None:
    if not path.exists():
        raise SystemExit(f"Backup file not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("format") != 1:
        raise SystemExit("This file is not a backup made by this script.")
    tables = payload["tables"]

    conn, host = pg_connect(get_url())
    try:
        cur = conn.cursor()
        for table in TABLES:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            if cur.fetchone()[0]:
                raise SystemExit(
                    f"The table '{table}' already has rows. Restore only works into an "
                    "EMPTY database (start the app once against a new database so it "
                    "creates empty tables, then restore)."
                )

        print(f"About to restore into database host: {host}")
        print("  " + "  ".join(f"{t}={len(tables.get(t, []))}" for t in TABLES))
        if input("Type RESTORE to continue: ").strip() != "RESTORE":
            raise SystemExit("Cancelled. Nothing was changed.")

        for table, cols in TABLES.items():
            marks = ", ".join(["%s"] * len(cols))
            sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({marks})"
            for row in tables.get(table, []):
                cur.execute(sql, [row[c] for c in cols])

        # Make the id counters continue after the highest restored id.
        for table in ("users", "transactions"):
            cur.execute(
                f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                f"COALESCE((SELECT MAX(id) FROM {table}), 0) + 1, false)"
            )
        conn.commit()
        print("Restore finished.")
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


# --- SQLite (local development database) ---------------------------------
def backup_sqlite(db_path: Path, out_dir: Path) -> Path:
    """Copy the SQLite file safely, even while the app is running."""
    if not db_path.exists():
        raise SystemExit(f"Database not found: {db_path}")

    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    target = out_dir / f"budget-{stamp}.db"

    source = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=10)
    dest = sqlite3.connect(target)
    try:
        source.backup(dest)
        check = dest.execute("PRAGMA integrity_check").fetchone()[0]
        if check != "ok":
            raise SystemExit(f"Backup failed integrity check: {check}")
        users = dest.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        txns = dest.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    finally:
        source.close()
        dest.close()

    print(f"Backup written: {target}")
    print(f"  users={users} transactions={txns}")
    return target


# --- shared ---------------------------------------------------------------
def prune(out_dir: Path, keep: int, pattern: str) -> None:
    backups = sorted(out_dir.glob(pattern))
    for old in backups[:-keep] if keep > 0 else []:
        old.unlink()
        print(f"Removed old backup: {old.name}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Back up the budget database.")
    parser.add_argument("--sqlite", action="store_true",
                        help="back up the local SQLite file instead of Postgres")
    parser.add_argument("--db", default=DEFAULT_DB, help="SQLite file (with --sqlite)")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="output folder")
    parser.add_argument("--keep", type=int, default=7, help="how many backups to keep")
    parser.add_argument("--copy-to", default=None,
                        help="optional second location (e.g. a USB drive)")
    parser.add_argument("--restore", metavar="FILE", default=None,
                        help="load a .json backup into an empty Postgres database")
    args = parser.parse_args(argv)

    if args.restore:
        restore_postgres(Path(args.restore))
        return 0

    out_dir = Path(args.out)
    if args.sqlite:
        target = backup_sqlite(Path(args.db), out_dir)
        prune(out_dir, args.keep, "budget-*.db")
    else:
        target = backup_postgres(out_dir)
        prune(out_dir, args.keep, "budget-*.json")

    if args.copy_to:
        dest = Path(args.copy_to)
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, dest / target.name)
        print(f"Copied to: {dest / target.name}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

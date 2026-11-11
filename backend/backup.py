"""Back up the SQLite database safely, even while the app is running.

Usage:
    python backup.py                 # writes backups/budget-YYYY-MM-DD-HHMMSS.db
    python backup.py --keep 14       # keep only the newest 14 backups
    python backup.py --out D:\\backups

The SQLite online backup API is used instead of copying the file, so a write
happening at the same moment cannot produce a corrupt copy.

On Render: run this from a cron job / scheduled task and point --out at a
mounted disk, then copy that folder to off-box storage (S3, Backblaze,
Google Drive). A backup that lives on the same disk as the database is not a
backup.
"""

import argparse
import os
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_DB = os.environ.get("DB_PATH") or str(HERE / "budget.db")


def make_backup(db_path: Path, out_dir: Path) -> Path:
    if not db_path.exists():
        raise SystemExit(f"Database not found: {db_path}")

    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    target = out_dir / f"budget-{stamp}.db"

    source = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=10)
    dest = sqlite3.connect(target)
    try:
        source.backup(dest)
        # Prove the copy is readable before declaring success.
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


def prune(out_dir: Path, keep: int) -> None:
    backups = sorted(out_dir.glob("budget-*.db"))
    for old in backups[:-keep] if keep > 0 else []:
        old.unlink()
        print(f"Removed old backup: {old.name}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Back up the budget database.")
    parser.add_argument("--db", default=DEFAULT_DB, help="path to budget.db")
    parser.add_argument("--out", default=str(HERE / "backups"), help="output folder")
    parser.add_argument("--keep", type=int, default=7, help="how many backups to keep")
    parser.add_argument("--copy-to", default=None,
                        help="optional second location (e.g. a synced folder)")
    args = parser.parse_args(argv)

    out_dir = Path(args.out)
    target = make_backup(Path(args.db), out_dir)
    prune(out_dir, args.keep)

    if args.copy_to:
        dest = Path(args.copy_to)
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, dest / target.name)
        print(f"Copied to: {dest / target.name}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

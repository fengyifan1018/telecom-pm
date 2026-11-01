"""
One-time migration: add columns that were introduced after the DB was first created.
Safe to run multiple times (checks before adding).
"""
import sqlite3

import os

# 兼容部署：优先从 DATABASE_URL 解析 SQLite 路径（支持相对/绝对），缺省 ./data.db
_db_url = os.environ.get("DATABASE_URL", "")
if _db_url.startswith("sqlite"):
    DB_PATH = _db_url.split("///", 1)[-1] or "./data.db"
else:
    DB_PATH = "./data.db"

MIGRATIONS = [
    # (table, column, definition)
    ("tasks", "estimated_days", "INTEGER NOT NULL DEFAULT 1"),
    ("tasks", "version",        "INTEGER NOT NULL DEFAULT 1"),
    ("tasks", "auto_schedule",  "BOOLEAN NOT NULL DEFAULT 1"),
    ("tasks", "progress",       "INTEGER NOT NULL DEFAULT 0"),
    ("projects", "init_submitted_by", "INTEGER"),
    ("projects", "init_reject_reason", "TEXT"),
    ("projects", "template_id", "INTEGER"),
    ("users", "wecom_userid", "VARCHAR(64)"),
    ("notifications", "push_status", "VARCHAR(10) DEFAULT 'pending'"),
    ("notifications", "push_error", "VARCHAR(255)"),
    ("notifications", "push_attempts", "INTEGER DEFAULT 0"),
]


def run():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    for table, column, definition in MIGRATIONS:
        cur.execute(f"PRAGMA table_info({table})")
        existing = [row[1] for row in cur.fetchall()]
        if column not in existing:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
            print(f"  Added {table}.{column}")
        else:
            print(f"  Skip  {table}.{column} (already exists)")
    conn.commit()
    conn.close()
    print("Migration complete.")


if __name__ == "__main__":
    run()

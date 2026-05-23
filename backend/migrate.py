"""
One-time migration: add columns that were introduced after the DB was first created.
Safe to run multiple times (checks before adding).
"""
import sqlite3

DB_PATH = "./data.db"

MIGRATIONS = [
    # (table, column, definition)
    ("tasks", "estimated_days", "INTEGER NOT NULL DEFAULT 1"),
    ("tasks", "version",        "INTEGER NOT NULL DEFAULT 1"),
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

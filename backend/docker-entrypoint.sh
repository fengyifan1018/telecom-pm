#!/bin/sh
set -e

echo "[entrypoint] ensuring tables..."
python init_db.py
echo "[entrypoint] running migrations..."
python migrate.py

echo "[entrypoint] starting uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1

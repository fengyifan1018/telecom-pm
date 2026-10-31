#!/bin/sh
# SQLite 在线备份（backup API 保证一致性）+ 附件目录打包
# 用法：在服务器项目目录执行  ./deploy/backup.sh [保留份数，默认14]
set -e
KEEP="${1:-14}"
STAMP=$(date +%Y%m%d_%H%M%S)
DIR="backups"
mkdir -p "$DIR"

echo "[backup] database..."
docker compose exec -T backend python - <<PYEOF
import sqlite3
src = sqlite3.connect("/app/data/telecom.db")
dst = sqlite3.connect("/tmp/telecom_$STAMP.db")
src.backup(dst)
dst.close(); src.close()
print("consistent copy done")
PYEOF
docker compose cp backend:/tmp/telecom_$STAMP.db "$DIR/telecom_$STAMP.db"
docker compose exec -T backend rm /tmp/telecom_$STAMP.db

echo "[backup] uploads（宿主机挂载目录直接打包）..."
mkdir -p data/uploads 2>/dev/null || true
if [ -d data/uploads ] && [ -n "$(ls -A data/uploads 2>/dev/null)" ]; then
  tar -czf "$DIR/uploads_$STAMP.tar.gz" -C data uploads
  echo "[backup] uploads 已打包"
else
  echo "[backup] uploads 为空，跳过"
fi

echo "[backup] prune old (keep $KEEP)..."
ls -1t "$DIR"/telecom_*.db 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm -f
ls -1dt "$DIR"/uploads_*.tar.gz 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm -f

echo "[backup] done: $DIR/telecom_$STAMP.db + uploads_$STAMP.tar.gz"

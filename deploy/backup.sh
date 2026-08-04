#!/usr/bin/env bash
# ============================================================================
# VUP 数据备份脚本
# ----------------------------------------------------------------------------
# 把 SQLite 数据库（命名卷 vup-data 内的 /data/app.db）一致性备份到 backups/ 目录。
# 在容器内用 Python sqlite3 在线备份 API（等价 sqlite3 .backup）完成：
#   一致性备份 -> PRAGMA integrity_check 校验 -> gzip 压缩，
# 再用 docker cp 取出，最后按天清理旧备份。
# 建议配合 crontab 定时执行：
#   crontab -e
#   0 3 * * * /path/to/ValuesUnderPressure/deploy/backup.sh >> /var/log/vup-backup.log 2>&1
#
# 可用环境变量：
#   BACKUP_DIR  备份输出目录（默认 <仓库根>/backups）
#   KEEP_DAYS   保留天数（默认 14）
#   DB_PATH     容器内数据库路径（默认 /data/app.db）
# ============================================================================
set -euo pipefail

cd "$(dirname "$0")/.."

BACKUP_DIR="${BACKUP_DIR:-backups}"
KEEP_DAYS="${KEEP_DAYS:-14}"
DB_PATH="${DB_PATH:-/data/app.db}"

# 容器需处于运行状态
if ! docker compose ps backend --format '{{.Name}}' 2>/dev/null | grep -q backend; then
  echo "错误: 后端容器未运行，跳过备份" >&2
  exit 1
fi

TS=$(date +%Y%m%d_%H%M%S)
mkdir -p "$BACKUP_DIR"
TMP_IN_CONTAINER="/tmp/vup_backup_${TS}.db.gz"
BACKUP_FILE="$BACKUP_DIR/app_${TS}.db.gz"

# 容器内：一致性在线备份 + 完整性校验 + gzip 压缩（宿主机无需 sqlite3/gzip）
if ! docker compose exec -T backend python - "$DB_PATH" "$TMP_IN_CONTAINER" <<'PY'
import sqlite3, gzip, os, shutil, sys, tempfile

db_path, out_path = sys.argv[1], sys.argv[2]

# 1) 在线一致性备份（SQLite Online Backup API）
src = sqlite3.connect(db_path)
fd, tmp = tempfile.mkstemp(suffix=".db")
os.close(fd)
dst = sqlite3.connect(tmp)
try:
    src.backup(dst)
finally:
    dst.close()
    src.close()

# 2) 完整性校验
check = sqlite3.connect(tmp)
try:
    row = check.execute("PRAGMA integrity_check;").fetchone()
finally:
    check.close()
if row[0] != "ok":
    print("完整性校验失败: %s" % row[0], file=sys.stderr)
    os.unlink(tmp)
    sys.exit(1)

# 3) gzip 压缩
with open(tmp, "rb") as f, gzip.GzipFile(filename=out_path, mode="wb") as gz:
    shutil.copyfileobj(f, gz)
os.unlink(tmp)
print("容器内备份完成: %s" % out_path, file=sys.stderr)
PY
then
  echo "错误: 容器内备份失败" >&2
  exit 1
fi

# 取出备份文件到宿主机
docker cp "backend:$TMP_IN_CONTAINER" "$BACKUP_FILE"
if [ $? -ne 0 ]; then
  echo "错误: 拷贝备份文件失败" >&2
  exit 1
fi
docker compose exec -T backend rm -f "$TMP_IN_CONTAINER" 2>/dev/null || true

echo "[backup] 已备份: $BACKUP_FILE ($(du -h "$BACKUP_FILE" | cut -f1))"

# 按天清理旧备份（默认 14 天）
find "$BACKUP_DIR" -name 'app_*.db.gz' -mtime +"$KEEP_DAYS" -delete
echo "[backup] 已清理 ${KEEP_DAYS} 天前的备份，当前保留:"
ls -1t "$BACKUP_DIR"/app_*.db.gz 2>/dev/null | head -n 5

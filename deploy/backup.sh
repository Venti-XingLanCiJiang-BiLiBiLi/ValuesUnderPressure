#!/usr/bin/env bash
# ============================================================================
# VUP 数据备份脚本
# ----------------------------------------------------------------------------
# 把 SQLite 数据库（命名卷 vup-data 内的 /data/app.db）导出到 backups/ 目录。
# 建议配合 crontab 定时执行：
#   crontab -e
#   0 3 * * * /path/to/ValuesUnderPressure/deploy/backup.sh >> /var/log/vup-backup.log 2>&1
# ============================================================================
set -euo pipefail

cd "$(dirname "$0")/.."

# 容器需处于运行状态
if ! docker compose ps backend --format '{{.Name}}' 2>/dev/null | grep -q backend; then
  echo "错误: 后端容器未运行，跳过备份" >&2
  exit 1
fi

TS=$(date +%Y%m%d_%H%M%S)
mkdir -p backups

# 通过 exec 读取容器内数据库文件（先 sqlite 在线备份可避免写锁，这里直接拷贝文件）
docker compose exec -T backend sh -c 'cat /data/app.db' > "backups/app_${TS}.db"

echo "[backup] 已备份: backups/app_${TS}.db ($(du -h "backups/app_${TS}.db" | cut -f1))"

# 只保留最近 14 份
ls -1t backups/app_*.db 2>/dev/null | tail -n +15 | xargs -r rm -f
echo "[backup] 已清理过期备份，当前保留:"
ls -1t backups/app_*.db 2>/dev/null | head -n 5

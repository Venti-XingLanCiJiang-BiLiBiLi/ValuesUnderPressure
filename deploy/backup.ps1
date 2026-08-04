<#
.SYNOPSIS
VUP 数据备份脚本（Windows PowerShell / Docker Desktop）

.DESCRIPTION
与 deploy/backup.sh 对应的 Windows 版本。
把 SQLite 数据库（命名卷 vup-data 内的 /data/app.db）一致性备份到 backups\ 目录。
在容器内用 Python sqlite3 在线备份 API（等价 sqlite3 .backup）完成：
  一致性备份 -> PRAGMA integrity_check 校验 -> gzip 压缩，
再用 docker cp 取出，最后按天清理旧备份。

.PARAMETER BackupsDir
备份输出目录（默认 <仓库根>\backups）

.PARAMETER KeepDays
保留天数（默认 14）

.EXAMPLE
.\deploy\backup.ps1
.\deploy\backup.ps1 -KeepDays 7
#>
[CmdletBinding()]
param(
    [string]$BackupsDir,
    [int]$KeepDays = 14
)

$ErrorActionPreference = 'Stop'

# 定位仓库根目录（脚本位于 deploy\ 下）
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not $BackupsDir) { $BackupsDir = Join-Path $Root 'backups' }

# --- 1. 容器需处于运行状态 ------------------------------------------------------
$backendName = (& docker compose ps backend --format '{{.Name}}') 2>$null | Select-Object -First 1
if (-not $backendName) {
    Write-Host '错误: 后端容器未运行，跳过备份' -ForegroundColor Red
    exit 1
}

New-Item -ItemType Directory -Force -Path $BackupsDir | Out-Null
$TS = Get-Date -Format 'yyyyMMdd_HHmmss'
$tmpInContainer = "/tmp/vup_backup_${TS}.db.gz"
$backupFile = Join-Path $BackupsDir "app_${TS}.db.gz"

# --- 2. 容器内：一致性在线备份 + 完整性校验 + gzip 压缩 -------------------------
$pyScript = @'
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
'@

Write-Host '[backup] 容器内备份中 ...'
& docker compose exec -T backend python -c $pyScript '/data/app.db' $tmpInContainer
if ($LASTEXITCODE -ne 0) {
    Write-Host '错误: 容器内备份失败' -ForegroundColor Red
    exit 1
}

# --- 3. 取出备份文件到宿主机 ----------------------------------------------------
Write-Host '[backup] 取出备份文件 ...'
& docker cp "backend:$tmpInContainer" $backupFile
if ($LASTEXITCODE -ne 0) {
    Write-Host '错误: 拷贝备份文件失败' -ForegroundColor Red
    exit 1
}
& docker compose exec -T backend rm -f $tmpInContainer 2>$null

$sizeMB = [Math]::Round((Get-Item $backupFile).Length / 1MB, 2)
Write-Host "[backup] 已备份: $backupFile ($sizeMB MB)"

# --- 4. 按天清理旧备份 ----------------------------------------------------------
$cutoff = (Get-Date).AddDays(-$KeepDays)
Get-ChildItem -Path $BackupsDir -Filter 'app_*.db.gz' -File |
    Where-Object { $_.LastWriteTime -lt $cutoff } |
    Remove-Item -Force

Write-Host "[backup] 已清理 $KeepDays 天前的备份，当前保留:"
Get-ChildItem -Path $BackupsDir -Filter 'app_*.db.gz' -File |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 5 |
    ForEach-Object { Write-Host "  $($_.Name)" }

<#
.SYNOPSIS
VUP 一键部署脚本（Windows PowerShell / Docker Desktop 本地自测）

.DESCRIPTION
与 deploy/deploy.sh 对应的 Windows 版本。
构建并启动前后端容器，等待后端健康检查通过后输出访问地址。
适合在 Windows + Docker Desktop 环境本地自测整套部署编排。

.PARAMETER NoPull
跳过 git pull（本地自测常用）。

.PARAMETER NoCache
强制 --no-cache 重新构建镜像（依赖或层缓存异常时使用）。

.PARAMETER Logs
部署完成后跟进前端容器日志（Ctrl+C 退出）。

.PARAMETER Open
部署完成后用默认浏览器打开前端页面。

.EXAMPLE
.\deploy\deploy.ps1
.\deploy\deploy.ps1 -NoPull -Open
.\deploy\deploy.ps1 -NoCache
#>
[CmdletBinding()]
param(
    [switch]$NoPull,
    [switch]$NoCache,
    [switch]$Logs,
    [switch]$Open
)

$ErrorActionPreference = 'Stop'

# 定位仓库根目录（脚本位于 deploy\ 下）
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

# --- 1. 依赖检查 --------------------------------------------------------------
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host '错误: 未找到 docker，请先安装 Docker Desktop：https://www.docker.com/products/docker-desktop/' -ForegroundColor Red
    exit 1
}
docker compose version *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host '错误: 未找到 docker compose 插件，请升级 Docker Desktop（需 Compose v2）' -ForegroundColor Red
    exit 1
}

# --- 2. 环境文件（不存在则从样例复制）-----------------------------------------
$envFile = Join-Path $Root '.env'
if (-not (Test-Path $envFile)) {
    Write-Host '[deploy] 未发现 .env，从 deploy\.env.example 复制一份' -ForegroundColor Yellow
    Copy-Item (Join-Path $Root 'deploy\.env.example') $envFile
}

# --- 2.1 生产环境检查 --------------------------------------------------------
$envContent = Get-Content $envFile -ErrorAction SilentlyContinue -Raw
$envMode = ''
if ($envContent -match '^ENV=(.+)$') { $envMode = $Matches[1].Trim() }
if (-not $envMode -and $envContent -match '^APP_ENV=(.+)$') { $envMode = $Matches[1].Trim() }
if ($envMode -eq 'production') {
    Write-Host "[deploy] 生产模式检测: 请确保已在 .env 中设置 CORS_ALLOWED_ORIGINS 和 ADMIN_TOKEN"
    if ($envContent -notmatch '^CORS_ALLOWED_ORIGINS=.+') {
        Write-Host '  警告: CORS_ALLOWED_ORIGINS 未设置 —— 生产环境将阻止浏览器请求。' -ForegroundColor Yellow
    }
    if ($envContent -notmatch '^ADMIN_TOKEN=.+') {
        Write-Host '  警告: ADMIN_TOKEN 未设置 —— 热更新接口将无效或不安全。' -ForegroundColor Yellow
    }
}

# --- 3. 拉取最新代码（可选）----------------------------------------------------
if (-not $NoPull) {
    if (Test-Path (Join-Path $Root '.git')) {
        Write-Host '[deploy] git pull ...'
        git pull --ff-only
        if ($LASTEXITCODE -ne 0) {
            Write-Host '错误: git pull 失败，请处理冲突后重试（或加 -NoPull 跳过）' -ForegroundColor Red
            exit 1
        }
    }
    else {
        Write-Host '[deploy] 非 git 仓库，跳过 pull' -ForegroundColor Yellow
    }
}

# --- 4. 构建镜像 --------------------------------------------------------------
Write-Host '[deploy] 构建镜像 ...'
$buildArgs = @('compose', 'build')
if ($NoCache) { $buildArgs += '--no-cache' }
# PS 5.1 下 docker 把构建进度写到 stderr，需 2>&1 并入 stdout，避免 $ErrorActionPreference='Stop' 触发 NativeCommandError
& docker @buildArgs 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host '错误: 镜像构建失败，请检查上方输出' -ForegroundColor Red
    exit 1
}

# --- 5. 启动容器 --------------------------------------------------------------
Write-Host '[deploy] 启动容器 ...'
& docker compose up -d --remove-orphans 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host '错误: 容器启动失败，请检查上方输出' -ForegroundColor Red
    exit 1
}

# --- 6. 健康检查 --------------------------------------------------------------
Write-Host '[deploy] 等待后端健康检查就绪 ...'
$ready = $false
for ($i = 1; $i -le 60; $i++) {
    $health = (& docker compose ps backend --format '{{.Health}}') 2>$null | Select-Object -First 1
    if ($health -eq 'healthy') {
        $ready = $true
        break
    }
    Start-Sleep -Seconds 3
}

if (-not $ready) {
    Write-Host '警告: 后端未在预期时间内就绪，请排查：' -ForegroundColor Yellow
    Write-Host '  docker compose logs --tail=50 backend'
    Write-Host '  docker compose ps'
}

# --- 7. 汇总 ------------------------------------------------------------------
$port = '8080'
if (Test-Path $envFile) {
    $line = Select-String -Path $envFile -Pattern '^VUP_PORT=' | Select-Object -Last 1
    if ($line) { $port = ($line.Line -split '=', 2)[1].Trim().Trim('"') }
}

Write-Host ''
Write-Host '====================== 部署完成 ======================'
Write-Host "  前端页面:   http://localhost:$port"
Write-Host "  API 文档:   http://localhost:$port/docs"
Write-Host "  健康检查:   http://localhost:$port/api/health"
Write-Host '  ----------'
Write-Host '  数据:       SQLite 保存在命名卷 vup-data（docker volume ls）'
Write-Host '  停止:       docker compose down'
Write-Host '  日志:       docker compose logs -f'
Write-Host '  重新部署:   .\deploy\deploy.ps1'
Write-Host '======================================================'

if ($Open) {
    Start-Process "http://localhost:$port"
}

if ($Logs) {
    Write-Host '[deploy] 跟进前端日志（Ctrl+C 退出）...'
    docker compose logs -f frontend
}

# ============================================================================
# pack-toy.ps1 — 一键打包 B 站 Toy 上传包（vup-toy.zip 到项目根目录）
# ============================================================================
# 流程：
#   1. 在 frontend/ 下执行 npm run build（含 vue-tsc 类型检查）；
#   2. 把 dist/ 全部产物 + 封面图 frontend/cover-4x3.png 合并；
#   3. 用 bsdtar（Windows 10+ 自带 tar.exe）打包为 vup-toy.zip 输出到项目根目录。
#
# 注意：必须用 tar.exe（-a 按扩展名自动压缩），不要改用 Compress-Archive ——
# 后者会把条目路径写成反斜杠（assets\index-xxx.js），Toy 端解包后资源查找
# 失败导致白屏。
#
# 用法：在项目根目录执行  .\pack-toy.ps1
# ============================================================================

$ErrorActionPreference = 'Stop'

$root = $PSScriptRoot
$frontend = Join-Path $root 'frontend'
$dist = Join-Path $frontend 'dist'
$cover = Join-Path $frontend 'cover-4x3.png'
$out = Join-Path $root 'vup-toy.zip'

Write-Host "[1/3] npm run build (frontend/) ..."
Push-Location $frontend
try {
    if (-not (Test-Path 'node_modules')) {
        Write-Host 'node_modules 缺失，先执行 npm install ...'
        npm.cmd install
        if ($LASTEXITCODE -ne 0) { throw 'npm install 失败' }
    }
    npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw 'npm run build 失败' }
} finally {
    Pop-Location
}

if (-not (Test-Path $dist)) {
    throw "构建产物不存在：$dist"
}

Write-Host "[2/3] 合并 dist/ 与封面图 ..."
$staging = Join-Path $env:TEMP "vup-pack-$PID"
if (Test-Path $staging) { Remove-Item -Recurse -Force $staging }
New-Item -ItemType Directory -Path $staging | Out-Null
Copy-Item -Path (Join-Path $dist '*') -Destination $staging -Recurse
if (Test-Path $cover) {
    Copy-Item -Path $cover -Destination (Join-Path $staging 'cover-4x3.png')
    Write-Host "封面已并入：$cover"
} else {
    Write-Warning "未找到封面 $cover，跳过（上传后仍可单独上传封面）"
}

Write-Host "[3/3] 打包 vup-toy.zip ..."
if (Test-Path $out) { Remove-Item -Force $out }
$names = @(Get-ChildItem -Path $staging | ForEach-Object { $_.Name })
tar.exe -a -c -f $out -C $staging $names
if ($LASTEXITCODE -ne 0) { throw 'tar 打包失败' }
Remove-Item -Recurse -Force $staging

# 校验：条目数 + 无反斜杠路径
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::OpenRead($out)
try {
    $bad = @($zip.Entries | Where-Object { $_.FullName -match '\\' })
    if ($bad.Count -gt 0) {
        throw "检测到反斜杠条目路径：$($bad.FullName -join ', ')"
    }
    $size = [math]::Round((Get-Item $out).Length / 1KB, 1)
    Write-Host "完成：$out（$($zip.Entries.Count) 个条目，$size KB，路径全部正斜杠）"
} finally {
    $zip.Dispose()
}

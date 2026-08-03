<#
.SYNOPSIS
等待 Docker 引擎就绪（配合 Docker Desktop 重启后使用）。
用法: powershell -NoProfile -ExecutionPolicy Bypass -File .\deploy\wait-docker.ps1
#>
[CmdletBinding()]
param([int]$MaxSeconds = 120)

$docker = 'C:\Program Files\Docker\Docker\resources\bin\docker.exe'
for ($i = 0; $i -lt $MaxSeconds; $i += 2) {
  & $docker info *> $null
  if ($LASTEXITCODE -eq 0) {
    Write-Host ("DOCKER-READY (after {0}s)" -f $i)
    exit 0
  }
  Start-Sleep -Seconds 2
}
Write-Host 'DOCKER-NOT-READY'
exit 1

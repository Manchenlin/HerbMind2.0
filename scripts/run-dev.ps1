#requires -Version 5
<#
  HerbMind 后端一键启动（PowerShell 版，不需要 bash / Git Bash）
  前置：已跑过 setup.ps1（PostgreSQL 里已有数据），且 backend/ 下已打好的 jar 存在
  用法：
    .\scripts\run-dev.ps1            # 启动 8 个服务（identity/catalog/search/training/graph/insight/bff/gateway）
    .\scripts\run-dev.ps1 stop       # 停止

  ⚠ 端口参数必须整体作为一个字符串传给 -ArgumentList（2026-11-11 修复）：
    原先写成 @("-jar", $jarPath, "--server.port=" + $Port) 时端口参数到不了 JVM，
     8 个服务全部回落到 application.yml 的默认值 8080，只有第一个抢到端口，
     其余报 "Port 8080 was already in use"，且 8080 上跑的是 catalog 而不是网关。
#>
param([string]$Action = "start")

$root = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $root "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

# 启动顺序：先被依赖的基础服务，最后网关（对外唯一入口）
$services = @(
    [pscustomobject]@{ Name = "svc-identity";  Jar = "backend\svc-identity\target\svc-identity-2.0.0-SNAPSHOT.jar"; Port = 8081 },
    [pscustomobject]@{ Name = "svc-catalog";   Jar = "backend\svc-catalog\target\svc-catalog-2.0.0-SNAPSHOT.jar"; Port = 8082 },
    [pscustomobject]@{ Name = "svc-search";    Jar = "backend\svc-search\target\svc-search-2.0.0-SNAPSHOT.jar"; Port = 8083 },
    [pscustomobject]@{ Name = "svc-training";  Jar = "backend\svc-training\target\svc-training-2.0.0-SNAPSHOT.jar"; Port = 8084 },
    [pscustomobject]@{ Name = "svc-graph";     Jar = "backend\svc-graph\target\svc-graph-2.0.0-SNAPSHOT.jar"; Port = 8085 },
    [pscustomobject]@{ Name = "svc-insight";   Jar = "backend\svc-insight\target\svc-insight-2.0.0-SNAPSHOT.jar"; Port = 8086 },
    [pscustomobject]@{ Name = "herbmind-bff";  Jar = "backend\herbmind-bff\target\herbmind-bff-2.0.0-SNAPSHOT.jar"; Port = 8090 },
    [pscustomobject]@{ Name = "gateway";       Jar = "backend\herbmind-gateway\target\herbmind-gateway-2.0.0-SNAPSHOT.jar"; Port = 8080 }
)

if ($Action -eq "stop") {
    foreach ($s in $services) {
        $conn = Get-NetTCPConnection -LocalPort $s.Port -State Listen -ErrorAction SilentlyContinue
        if ($conn) {
            $conn | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object {
                Write-Host "停止 $($s.Name)（PID $_）"
                Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue
            }
        }
    }
    Write-Host "已停止" -ForegroundColor Green
    exit 0
}

# 清掉会覆盖 yml 端口的环境变量（本机曾出现 SERVER__PORT 让多个服务抢同一端口）
Remove-Item Env:SERVER_PORT -ErrorAction SilentlyContinue
Remove-Item Env:SERVER__PORT -ErrorAction SilentlyContinue

$java = "java"
if (Get-Command java -ErrorAction SilentlyContinue) { $java = (Get-Command java).Source }

$started = @()
foreach ($s in $services) {
    $jarPath = Join-Path $root $s.Jar
    if (-not (Test-Path $jarPath)) {
        Write-Host "[跳过] $($s.Name)：缺 jar，先在 backend/ 执行 mvn package" -ForegroundColor Yellow
        continue
    }
    $out = Join-Path $logDir ($s.Name + ".log")
    $err = Join-Path $logDir ($s.Name + ".err.log")
    # 关键：整体一个字符串，且 jar 路径加引号（路径可能带空格）
    $argString = '-jar "' + $jarPath + '" --server.port=' + $s.Port
    Write-Host "启动 $($s.Name) :$($s.Port)  (日志 logs/$($s.Name).log)"
    Start-Process -FilePath $java -ArgumentList $argString -WindowStyle Hidden -RedirectStandardOutput $out -RedirectStandardError $err
    $started += $s
    Start-Sleep -Seconds 4
}

# 端口就绪检查：轮询最多 40 秒，避免"刚起还没监听"被误判为失败
Write-Host "`n等待端口就绪…" -ForegroundColor Cyan
$deadline = (Get-Date).AddSeconds(40)
$pending = @($started)
$ok = @{}
while ($pending.Count -gt 0 -and (Get-Date) -lt $deadline) {
    foreach ($s in @($pending)) {
        if (Get-NetTCPConnection -LocalPort $s.Port -State Listen -ErrorAction SilentlyContinue) {
            $ok[$s.Port] = $true
            $pending = @($pending | Where-Object { $_.Port -ne $s.Port })
        }
    }
    if ($pending.Count -gt 0) { Start-Sleep -Seconds 2 }
}

Write-Host "`n端口检查：" -ForegroundColor Cyan
foreach ($s in $started) {
    if ($ok.ContainsKey($s.Port)) {
        Write-Host ("  {0,-14} :{1}  OK" -f $s.Name, $s.Port) -ForegroundColor Green
    } else {
        Write-Host ("  {0,-14} :{1}  FAIL（看 logs/{0}.log）" -f $s.Name, $s.Port) -ForegroundColor Red
    }
}

Write-Host "`n验证：" -ForegroundColor Cyan
Write-Host "  curl.exe http://localhost:8082/internal/catalog/books"
Write-Host "  curl.exe http://localhost:8083/internal/search?q=麻黄汤"
Write-Host "  curl.exe 'http://localhost:8085/internal/graph/subgraph?limit=5'"
Write-Host "  curl.exe http://localhost:8090/api/biz/home"
Write-Host "  前端：cd frontend; npm run dev  -> http://localhost:5173"

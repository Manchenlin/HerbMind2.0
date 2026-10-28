#requires -Version 5
<#
  HerbMind 后端一键启动（PowerShell 版，不需要 bash / Git Bash）
  前置：已跑过 setup.ps1（PostgreSQL 里已有数据），且 backend/ 下已打好的 jar 存在
  用法：
    .\scripts\run-dev.ps1            # 启动 5 个服务（catalog/search/insight/bff/gateway）
    .\scripts\run-dev.ps1 stop       # 停止
#>
param([string]$Action = "start")

$root = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $root "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$services = @(
    [pscustomobject]@{ Name = "svc-catalog";  Jar = "backend\svc-catalog\target\svc-catalog-2.0.0-SNAPSHOT.jar"; Port = 8082 },
    [pscustomobject]@{ Name = "svc-search";   Jar = "backend\svc-search\target\svc-search-2.0.0-SNAPSHOT.jar"; Port = 8083 },
    [pscustomobject]@{ Name = "svc-insight";  Jar = "backend\svc-insight\target\svc-insight-2.0.0-SNAPSHOT.jar"; Port = 8086 },
    [pscustomobject]@{ Name = "herbmind-bff"; Jar = "backend\herbmind-bff\target\herbmind-bff-2.0.0-SNAPSHOT.jar"; Port = 8090 },
    [pscustomobject]@{ Name = "gateway";      Jar = "backend\herbmind-gateway\target\herbmind-gateway-2.0.0-SNAPSHOT.jar"; Port = 8080 }
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

# 清掉会覆盖 yml 端口的环境变量
Remove-Item Env:SERVER_PORT -ErrorAction SilentlyContinue
Remove-Item Env:SERVER__PORT -ErrorAction SilentlyContinue

$java = "java"
if (Get-Command java -ErrorAction SilentlyContinue) { $java = (Get-Command java).Source }

foreach ($s in $services) {
    $jarPath = Join-Path $root $s.Jar
    if (-not (Test-Path $jarPath)) {
        Write-Host "[跳过] $($s.Name)：缺 jar，先在 IDEA 里 mvn package" -ForegroundColor Yellow
        continue
    }
    $out = Join-Path $logDir ($s.Name + ".log")
    $err = Join-Path $logDir ($s.Name + ".err.log")
    $argList = @("-jar", $jarPath, "--server.port=" + $s.Port)
    Write-Host "启动 $($s.Name) :$($s.Port)  (日志 logs/$($s.Name).log)"
    Start-Process -FilePath $java -ArgumentList $argList -WindowStyle Hidden -RedirectStandardOutput $out -RedirectStandardError $err
    Start-Sleep -Seconds 6
}

Write-Host "`n检查端口：" -ForegroundColor Cyan
foreach ($s in $services) {
    $ok = Test-NetConnection -ComputerName 127.0.0.1 -Port $s.Port -InformationLevel Quiet -WarningAction SilentlyContinue
    if ($ok) { $mark = "OK" } else { $mark = "FAIL" }
    Write-Host ("  {0,-14} :{1}  {2}" -f $s.Name, $s.Port, $mark)
}

Write-Host "`n验证：" -ForegroundColor Cyan
Write-Host "  curl.exe http://localhost:8082/internal/catalog/books"
Write-Host "  curl.exe http://localhost:8083/internal/search?q=麻黄汤"
Write-Host "  curl.exe http://localhost:8090/api/biz/home"
Write-Host "  前端：cd frontend; npm run dev  -> http://localhost:5173"

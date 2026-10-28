#requires -Version 5
<#
  HerbMind 中间件 + 数据一键准备（PowerShell 版，不需要 bash）
  前置：Docker Desktop 已安装并启动（托盘图标变绿）
  用法：
    # 只起中间件
    .\scripts\setup.ps1
    # 导入镜像（首次）+ 起中间件 + 导数据
    .\scripts\setup.ps1 -Images "C:\...\herbmind-middleware-images.tar.gz" -Sql "C:\...\herbmind_data.sql"
    # 库里已有数据、想清空重来
    .\scripts\setup.ps1 -Sql "C:\...\herbmind_data.sql" -Reset
#>
param(
    [string]$Images = "",
    [string]$Sql = "",
    [switch]$Reset
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$container = "herbmind-v2-pg"
$db = "herbmind"
$dbUser = "postgres"

function Step($msg) { Write-Host "`n== $msg" -ForegroundColor Cyan }
function Fail($msg) { Write-Host "`n[失败] $msg" -ForegroundColor Red; exit 1 }

Step "0/5 检查 Docker"
try { docker version *> $null } catch { Fail "找不到 docker 命令：请先安装 Docker Desktop 并重新打开终端。" }
if ($LASTEXITCODE -ne 0) {
    Fail "Docker 守护进程未运行：请启动 Docker Desktop（等托盘图标变绿），再重试。"
}
Write-Host "  Docker 就绪" -ForegroundColor Green

if ($Images) {
    Step "1/5 导入中间件镜像（约 1.1GB，第一次会慢）"
    if (-not (Test-Path $Images)) { Fail "镜像包不存在：$Images" }
    docker load -i $Images
    if ($LASTEXITCODE -ne 0) { Fail "docker load 失败：确认文件完整（757MB）" }
} else {
    Step "1/5 跳过镜像导入（-Images 未指定）"
}

Step "2/5 启动中间件（PostgreSQL / Neo4j / Redis / Nacos）"
Push-Location $root
docker compose -f docker/docker-compose.infra.yml up -d
if ($LASTEXITCODE -ne 0) { Pop-Location; Fail "docker compose 启动失败" }
Pop-Location

Step "3/5 等待 PostgreSQL 就绪"
$ok = $false
foreach ($i in 1..60) {
    docker exec $container pg_isready -U $dbUser -d $db *> $null
    if ($LASTEXITCODE -eq 0) { $ok = $true; Write-Host "  就绪（第 $i 次探测）" -ForegroundColor Green; break }
    Start-Sleep -Seconds 2
}
if (-not $ok) { Fail "PostgreSQL 60 次探测仍未就绪，看：docker logs $container" }

if (-not $Sql) {
    Step "4/5 未指定 -Sql，跳过数据导入"
} else {
    if (-not (Test-Path $Sql)) { Fail "数据快照不存在：$Sql" }
    if ($Reset) {
        Step "4/5 清空 public schema（-Reset）"
        docker exec $container psql -U $dbUser -d $db -q -c "SET client_min_messages=warning;" -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
        if ($LASTEXITCODE -ne 0) { Fail "重置失败" }
    }
    Step "4/5 导入数据（先 docker cp 进容器，避免管道编码问题）"
    docker cp $Sql "${container}:/tmp/herbmind_data.sql"
    if ($LASTEXITCODE -ne 0) { Fail "docker cp 失败" }
    docker exec -e PGCLIENTENCODING=UTF8 $container psql -U $dbUser -d $db -q -v ON_ERROR_STOP=1 -f /tmp/herbmind_data.sql
    if ($LASTEXITCODE -ne 0) {
        Fail "导入失败。若提示 duplicate key，说明库里已有数据：加 -Reset 重来。"
    }
    Write-Host "  导入完成，核对计数：" -ForegroundColor Green
    docker exec $container psql -U $dbUser -d $db -t -c "SELECT 'formula='||(SELECT count(*) FROM formula)||'  case='||(SELECT count(*) FROM case_record)||'  quote='||(SELECT count(*) FROM classic_quote)||'  unit='||(SELECT count(*) FROM content_unit)||'  向量='||(SELECT count(*) FROM content_unit WHERE embedding IS NOT NULL);"

    Step "5/5 建图（Neo4j，可选）"
    $py = (Get-Command python -ErrorAction SilentlyContinue)
    if ($py) {
        Push-Location (Join-Path $root "database\etl")
        try { python build_graph.py } catch { Write-Host "  建图失败（不影响内容域）：$_" -ForegroundColor Yellow }
        Pop-Location
    } else {
        Write-Host "  未找到 python，跳过建图（C 域的图谱页会空，A 域不受影响）" -ForegroundColor Yellow
    }
}

Step "完成"
Write-Host "  下一步：.\scripts\run-dev.ps1     然后另开终端起前端" -ForegroundColor Green
Write-Host "  ⚠ 不要执行 docker compose down -v（会删数据卷）" -ForegroundColor Yellow

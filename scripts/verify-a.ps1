#requires -Version 5
<#
  HerbMind 域1（A）验收 —— PowerShell 版，不需要 bash
  前置：setup.ps1 已导完数据、run-dev.ps1 已起 5 个服务
  用法：.\scripts\verify-a.ps1
#>
$ErrorActionPreference = "Continue"

$catalog = "http://localhost:8082"
$search  = "http://localhost:8083"
$insight = "http://localhost:8086"
$bff     = "http://localhost:8090"

$pass = 0
$fail = 0
$failed = @()

function Check([string]$name, [string]$url, [string]$expect) {
    try {
        $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 20
        if ($r.Content.Contains($expect)) {
            $script:pass++
            Write-Host ("  [OK]   " + $name) -ForegroundColor Green
        } else {
            $script:fail++
            $script:failed += $name
            $snippet = $r.Content
            if ($snippet.Length -gt 160) { $snippet = $snippet.Substring(0, 160) }
            Write-Host ("  [FAIL] " + $name + "  ->  " + $snippet) -ForegroundColor Red
        }
    } catch {
        $script:fail++
        $script:failed += $name
        Write-Host ("  [FAIL] " + $name + "  ->  " + $_.Exception.Message) -ForegroundColor Red
    }
}

function CheckPost([string]$name, [string]$url, [string]$body, [string]$expect) {
    try {
        $r = Invoke-WebRequest -Uri $url -Method Post -ContentType "application/json; charset=utf-8" `
             -Body ([System.Text.Encoding]::UTF8.GetBytes($body)) -UseBasicParsing -TimeoutSec 20
        if ($r.Content.Contains($expect)) {
            $script:pass++
            Write-Host ("  [OK]   " + $name) -ForegroundColor Green
        } else {
            $script:fail++
            $script:failed += $name
            Write-Host ("  [FAIL] " + $name + "  ->  " + $r.Content.Substring(0, [Math]::Min(160, $r.Content.Length))) -ForegroundColor Red
        }
    } catch {
        $script:fail++
        $script:failed += $name
        Write-Host ("  [FAIL] " + $name + "  ->  " + $_.Exception.Message) -ForegroundColor Red
    }
}

$qMah = [uri]::EscapeDataString("麻黄汤")
$qNl  = [uri]::EscapeDataString("无汗而喘、脉浮紧用什么方")

Write-Host "== 1. 数据 / 目录 ==" -ForegroundColor Cyan
Check "catalog 书架可读"        "$catalog/internal/catalog/books" '"title"'
Check "统计：245 方"            "$catalog/internal/catalog/stats" '"formulas":245'
Check "统计：535 向量"          "$catalog/internal/catalog/stats" '"vectors":535'
Check "目录树 bk_1"             "$catalog/internal/catalog/tree?bookId=bk_1" '太阳病'
Check "节点详情（含方剂）"      "$catalog/internal/catalog/node/n_g1/detail" '"formulas"'
Check "节点详情（含面包屑）"    "$catalog/internal/catalog/node/n_g1/detail" '"breadcrumb"'

Write-Host "== 2. 内容详情（A1） ==" -ForegroundColor Cyan
Check "方剂 f_1 = 麻黄汤"       "$catalog/internal/catalog/formula/f_1" '麻黄汤'
Check "方剂含药味字段"          "$catalog/internal/catalog/formula/f_1" '"herbs"'
Check "方剂含条文"              "$catalog/internal/catalog/formula/f_1" '"quotes"'
Check "医案 cs_1"               "$catalog/internal/catalog/case/cs_1" '"sections"'
Check "条文 q_1 拆条"           "$catalog/internal/catalog/quote/q_1" '"items"'
Check "条文列表 /quote/list"    "$catalog/internal/catalog/quote/list?size=3" '"total"'
Check "今日方证"                "$catalog/internal/catalog/daily" '"herbs"'

Write-Host "== 3. 检索（A2） ==" -ForegroundColor Cyan
Check "检索：麻黄汤有结果"      "$search/internal/search?q=$qMah" '"total"'
Check "检索：自然语言有结果"    "$search/internal/search?q=$qNl" '"total"'
Check "检索：分面"              "$search/internal/search/facets?q=$qMah" '"types"'
Check "条文反向索引"            "$search/internal/search/quote-index?q=$qMah" '"articleNo"'
CheckPost "语义检索 POST"       "$search/internal/search/semantic" '{"q":"无汗而喘、脉浮紧用什么方","size":5}' '"mode"'

Write-Host "== 4. 科研统计 ==" -ForegroundColor Cyan
Check "用药频次"                "$insight/internal/insight/herbs?limit=5" '"herb"'
Check "证候分布"                "$insight/internal/insight/syndrome?limit=5" '"label"'
Check "经典/章节分布"           "$insight/internal/insight/trend" '"books"'
Check "CSV 导出"                "$insight/internal/insight/export?kind=herbs&format=csv" 'herb,count'

Write-Host "== 5. BFF / 首页（A4） ==" -ForegroundColor Cyan
Check "首页聚合"                "$bff/api/biz/home" '"today"'
Check "首页 search 聚合"        "$bff/api/biz/home" '"hotHits"'
Check "首页图谱预览"            "$bff/api/biz/home" '"graph"'
Check "BFF 目录树"              "$bff/api/biz/library/tree?bookId=bk_1" '太阳病'
Check "BFF 方剂页"              "$bff/api/biz/formula/f_1/page" '麻黄汤'
Check "BFF 条文列表"            "$bff/api/biz/quote/list?size=3" '"total"'

Write-Host ""
if ($fail -eq 0) {
    Write-Host "全部通过：$pass 项" -ForegroundColor Green
    exit 0
} else {
    Write-Host "通过 $pass 项，失败 $fail 项：" -ForegroundColor Yellow
    $failed | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
    Write-Host "排查：logs\*.log；确认 setup.ps1 已打印 formula=245" -ForegroundColor Yellow
    exit 1
}

#!/usr/bin/env bash
# 本地一键起后端五件套（svc-catalog → svc-search → svc-insight → bff → gateway），日志写到 logs/。
# 前置：已执行 database/etl 的种子导入；中间件已起。
# 用法：bash scripts/run-dev.sh          # 启动
#       bash scripts/run-dev.sh stop     # 停止
set -u

# Git Bash 下 pwd -W 给出 Windows 风格路径（Java 才能识别）；勿用多分支拼接，会带出换行
ROOT="$(cd "$(dirname "$0")/.." && pwd -W)"
LOG="$ROOT/logs"
mkdir -p "$LOG"

# 本机 mvn 的 wrapper 可能损坏；直接用可用的 Maven 安装
JAVA_HOME="${JAVA_HOME:-D:/software/IDEA/JDK/jdk-17.0.14+7}"
JAR_CATALOG="$ROOT/backend/svc-catalog/target/svc-catalog-2.0.0-SNAPSHOT.jar"
JAR_SEARCH="$ROOT/backend/svc-search/target/svc-search-2.0.0-SNAPSHOT.jar"
JAR_INSIGHT="$ROOT/backend/svc-insight/target/svc-insight-2.0.0-SNAPSHOT.jar"
JAR_BFF="$ROOT/backend/herbmind-bff/target/herbmind-bff-2.0.0-SNAPSHOT.jar"
JAR_GATEWAY="$ROOT/backend/herbmind-gateway/target/herbmind-gateway-2.0.0-SNAPSHOT.jar"

stop() {
  echo "stopping..."
  for p in svc-catalog svc-search svc-insight herbmind-bff herbmind-gateway; do
    pkill -f "$p-2.0.0-SNAPSHOT.jar" 2>/dev/null && echo "  killed $p"
  done
}

if [ "${1:-}" = "stop" ]; then stop; exit 0; fi

for jar in "$JAR_CATALOG" "$JAR_SEARCH" "$JAR_INSIGHT" "$JAR_BFF" "$JAR_GATEWAY"; do
  [ -f "$jar" ] || { echo "缺少 jar：$jar（先在 backend/ 执行 mvn package）"; exit 1; }
done

# 宿主环境可能设了 SERVER_PORT / SERVER__PORT，会覆盖 yml 的 server.port
# （本机实测 SERVER__PORT=61099 会让多个服务都去抢同一端口）—— 清掉并用命令行参数强制端口
unset SERVER_PORT SERVER__PORT

echo "starting svc-catalog :8082"
nohup "$JAVA_HOME/bin/java" -jar "$JAR_CATALOG" --server.port=8082 > "$LOG/svc-catalog.log" 2>&1 &
sleep 6

echo "starting svc-search :8083"
nohup "$JAVA_HOME/bin/java" -jar "$JAR_SEARCH" --server.port=8083 > "$LOG/svc-search.log" 2>&1 &
sleep 5

echo "starting svc-insight :8086"
nohup "$JAVA_HOME/bin/java" -jar "$JAR_INSIGHT" --server.port=8086 > "$LOG/svc-insight.log" 2>&1 &
sleep 4

echo "starting herbmind-bff :8090"
nohup "$JAVA_HOME/bin/java" -jar "$JAR_BFF" --server.port=8090 > "$LOG/herbmind-bff.log" 2>&1 &
sleep 5

echo "starting herbmind-gateway :8080"
nohup "$JAVA_HOME/bin/java" -jar "$JAR_GATEWAY" --server.port=8080 > "$LOG/herbmind-gateway.log" 2>&1 &
sleep 4

echo
echo "验证："
echo "  curl 'http://localhost:8082/internal/catalog/books'"
echo "  curl 'http://localhost:8083/internal/search?q=%E9%BA%BB%E9%BB%84%E6%B1%A4'"
echo "  curl 'http://localhost:8086/internal/insight/trend'"
echo "  curl 'http://localhost:8090/api/biz/home'"
echo "日志：$LOG/"

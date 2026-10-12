#!/usr/bin/env bash
# 本地一键起后端三件套（svc-catalog → bff → gateway），日志写到 logs/。
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
JAR_BFF="$ROOT/backend/herbmind-bff/target/herbmind-bff-2.0.0-SNAPSHOT.jar"
JAR_GATEWAY="$ROOT/backend/herbmind-gateway/target/herbmind-gateway-2.0.0-SNAPSHOT.jar"

stop() {
  echo "stopping..."
  for p in svc-catalog herbmind-bff herbmind-gateway; do
    pkill -f "$p-2.0.0-SNAPSHOT.jar" 2>/dev/null && echo "  killed $p"
  done
}

if [ "${1:-}" = "stop" ]; then stop; exit 0; fi

for jar in "$JAR_CATALOG" "$JAR_BFF" "$JAR_GATEWAY"; do
  [ -f "$jar" ] || { echo "缺少 jar：$jar（先在 backend/ 执行 mvn package）"; exit 1; }
done

# 宿主环境可能设了 SERVER_PORT / SERVER__PORT，会覆盖 yml 的 server.port
# （本机实测 SERVER__PORT=61099 会让三个服务都去抢同一端口）—— 清掉并用命令行参数强制端口
unset SERVER_PORT SERVER__PORT

echo "starting svc-catalog :8082"
nohup "$JAVA_HOME/bin/java" -jar "$JAR_CATALOG" --server.port=8082 > "$LOG/svc-catalog.log" 2>&1 &
sleep 6

echo "starting herbmind-bff :8090"
nohup "$JAVA_HOME/bin/java" -jar "$JAR_BFF" --server.port=8090 > "$LOG/herbmind-bff.log" 2>&1 &
sleep 5

echo "starting herbmind-gateway :8080"
nohup "$JAVA_HOME/bin/java" -jar "$JAR_GATEWAY" --server.port=8080 > "$LOG/herbmind-gateway.log" 2>&1 &
sleep 5

echo
echo "验证：curl 'http://localhost:8090/api/biz/library/tree?bookId=sh'"
echo "日志：$LOG/"

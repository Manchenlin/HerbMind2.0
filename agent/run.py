"""本地开发启动器（给 PyCharm / 命令行用，比直接跑 app/main.py 多几个开关）。

用法（工作目录必须是 agent/）：
    python run.py                # 8091 启动，改代码不自动重启
    python run.py --reload       # 8091 启动，改代码自动重启（开发推荐）
    python run.py --port 8092    # 换端口（8091 被占用时临时用）
    python run.py --host 0.0.0.0 # 允许局域网访问

PyCharm 里配运行配置时，Script path 指向本文件即可。
注意：Debug 断点调试时不要加 --reload（子进程会影响断点命中）。
"""

import argparse

import uvicorn

from app.config import get_settings


def main() -> None:
    s = get_settings()
    parser = argparse.ArgumentParser(description="HerbMind Agent 本地启动器")
    parser.add_argument("--port", type=int, default=s.app_port, help="监听端口，默认 8091")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址，默认 127.0.0.1")
    parser.add_argument("--reload", action="store_true", help="改代码自动重启（开发用）")
    args = parser.parse_args()

    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        reload_dirs=["app"] if args.reload else None,
    )


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Web 监控仪表板启动脚本

BTC 碰撞引擎的 Web 监控仪表板快速启动入口。
运行后可通过浏览器访问 http://localhost:8080 查看引擎运行状态。

使用方式:
    python start_dashboard.py
    python start_dashboard.py --port 3000
    python start_dashboard.py --debug

依赖:
    pip install flask
"""

from src.web.dashboard import main

if __name__ == "__main__":
    main()

"""Web 监控仪表板

提供基于 Flask 的轻量级 Web 监控仪表板，用于远程查看 BTC 碰撞引擎运行状态。

功能:
- 实时统计面板 (速度/总数/匹配数/CPU/内存)
- 历史性能数据 API
- 错误日志查看
- 引擎状态监控
- 性能趋势可视化

启动方式:
    python -m src.web.dashboard
    # 或
    python start_dashboard.py

版本: v1.0
创建日期: 2026-05-01
"""

__version__ = "1.0.0"

from .dashboard import create_app, run_dashboard

__all__ = ["create_app", "run_dashboard"]

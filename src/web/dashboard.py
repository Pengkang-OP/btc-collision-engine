"""Web 监控仪表板 - Flask 应用

BTC 碰撞引擎的 Web 监控仪表板，提供:
- RESTful API 接口查询运行状态
- HTML 仪表板页面实时展示引擎指标
- 历史性能数据查询
- 错误日志浏览

安全:
- 支持 API Key 认证（--api-key 参数或 DASHBOARD_API_KEY 环境变量）
- /health 端点无需认证（供负载均衡器健康检查）

启动:
    python -m src.web.dashboard --host 0.0.0.0 --port 8080 --api-key YOUR_SECRET_KEY

API 端点:
    GET  /api/status        - 当前运行状态
    GET  /api/history       - 历史数据 (支持 ?limit=N)
    GET  /api/errors        - 错误日志 (支持 ?limit=N)
    GET  /api/report        - 日报告摘要
    GET  /api/security-audit - 安全审计状态 (已脱敏)
    GET  /health            - 健康检查 (无需认证)
    GET  /                  - 仪表板 HTML 页面
"""

import argparse
import json
import logging
import os
import secrets
import sys
import time
from functools import wraps
from pathlib import Path
from typing import Any

try:
    from flask import Flask, abort, jsonify, render_template_string, request

    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False
    Flask: Any = None  # type: ignore[no-redef]
    jsonify: Any = None  # type: ignore[no-redef]
    render_template_string: Any = None  # type: ignore[no-redef]
    request: Any = None  # type: ignore[no-redef]
    abort: Any = None  # type: ignore[no-redef]

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────
# API Key 认证
# ──────────────────────────────────────────────────────────────────

UNPROTECTED_ROUTES = {"health"}

_api_key: str | None = None
_api_key_required: bool = False


def set_api_key(key: str | None) -> None:
    global _api_key, _api_key_required
    _api_key = key
    _api_key_required = key is not None and len(key) > 0


def _validate_api_key() -> bool:
    if not _api_key_required:
        return True
    # 仅从 Authorization 头读取，避免 URL 查询参数泄露 API Key 到日志/浏览器历史
    provided = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    return secrets.compare_digest(provided, _api_key or "")


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if f.__name__ in UNPROTECTED_ROUTES:
            return f(*args, **kwargs)
        if not _validate_api_key():
            abort(401)
        return f(*args, **kwargs)

    return decorated


# ──────────────────────────────────────────────────────────────────
# HTML 模板 (内嵌，无需外部文件)
# ──────────────────────────────────────────────────────────────────

DASHBOARD_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="30">
    <title>BTC 碰撞引擎 - 监控仪表板</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
            background: #0d1117; color: #c9d1d9;
            min-height: 100vh; padding: 20px;
        }
        h1 { color: #58a6ff; font-size: 1.8em; margin-bottom: 10px; }
        .subtitle { color: #8b949e; font-size: 0.9em; margin-bottom: 24px; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; margin-bottom: 24px; }  # noqa: E501
        .card {
            background: #161b22; border: 1px solid #30363d;
            border-radius: 8px; padding: 20px;
        }
        .card h3 { color: #58a6ff; font-size: 0.85em; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px; } # noqa: E501
        .card .value { font-size: 2.2em; font-weight: 700; color: #f0f6fc; }
        .card .label { color: #8b949e; font-size: 0.8em; margin-top: 4px; }
        .status-ok { color: #3fb950; }
        .status-warn { color: #d29922; }
        .status-error { color: #f85149; }
        .section { margin-bottom: 24px; }
        .section h2 { color: #58a6ff; font-size: 1.2em; margin-bottom: 12px; border-bottom: 1px solid #30363d; padding-bottom: 8px; } # noqa: E501
        table { width: 100%; border-collapse: collapse; font-size: 0.9em; }
        th, td { padding: 10px 14px; text-align: left; border-bottom: 1px solid #21262d; }
        th { color: #8b949e; font-weight: 600; background: #161b22; }
        tr:hover { background: #1c2129; }
        .badge {
            display: inline-block; padding: 2px 8px; border-radius: 12px;
            font-size: 0.75em; font-weight: 600;
        }
        .badge-info { background: #1f6feb33; color: #58a6ff; }
        .badge-warn { background: #d2992233; color: #d29922; }
        .empty { color: #8b949e; font-style: italic; padding: 12px; }
        .footer { text-align: center; color: #484f58; font-size: 0.8em; margin-top: 32px; }
    </style>
</head>
<body>
    <h1>🔑 BTC 碰撞引擎 - 监控仪表板</h1>
    <p class="subtitle">实时运行状态 | 自动刷新: 30秒 | 生成时间: {{ generated_at }}</p>

    <!-- 核心指标 -->
    <div class="section"><h2>📊 核心指标</h2>
    <div class="grid">
        <div class="card">
            <h3>检测速率</h3>
            <div class="value">{{ "%.0f"|format(stats.get('speed', 0)) }}<span style="font-size:0.5em">/s</span></div>  # noqa: E501
            <div class="label">平均: {{ "%.0f"|format(stats.get('avg_speed', 0)) }}/s | 最大: {{ "%.0f"|format(stats.get('max_speed', 0)) }}/s</div>  # noqa: E501
        </div>
        <div class="card">
            <h3>已检测总数</h3>
            <div class="value">{{ "{:,}".format(stats.get('total_checked', 0)) }}</div>
            <div class="label">匹配: {{ stats.get('matches_found', 0) }}</div>
        </div>
        <div class="card">
            <h3>运行时间</h3>
            <div class="value">{{ uptime_display }}</div>
            <div class="label">引擎状态:
                <span class="{% if stats.get('is_running', false) %}status-ok{% else %}status-warn{% endif %}">  # noqa: E501
                    {{ "运行中" if stats.get('is_running', false) else "已停止" }}
                </span>
            </div>
        </div>
        <div class="card">
            <h3>系统资源</h3>
            <div class="value" style="font-size:1.2em">
                CPU: {{ "%.1f"|format(stats.get('cpu_usage', 0)) }}%<br>
                内存: {{ "%.0f"|format(stats.get('memory_usage', 0)) }} MB
            </div>
        </div>
    </div></div>

    <!-- 引擎信息 -->
    <div class="section"><h2>⚙️ 引擎信息</h2>
    <div class="grid">
        <div class="card">
            <h3>运行模式</h3>
            <div class="value" style="font-size:1.2em"><span class="badge badge-info">{{ engine.mode or "N/A" }}</span></div>  # noqa: E501
        </div>
        <div class="card">
            <h3>目标地址</h3>
            <div class="value" style="font-size:1.2em">{{ engine.target_count or 0 }}</div>
        </div>
        <div class="card">
            <h3>当前位置</h3>
            <div class="value" style="font-size:1.2em">{{ "{:,}".format(engine.current_position or 0) }}</div>  # noqa: E501
        </div>
        <div class="card">
            <h3>操作系统</h3>
            <div class="value" style="font-size:1.2em">{{ system.os or "N/A" }}</div>
            <div class="label">Python {{ system.python_version or "N/A" }} | PID: {{ system.pid or "N/A" }}</div>  # noqa: E501
        </div>
    </div></div>

    <!-- 安全审计 -->
    <div class="section"><h2>🔒 安全审计状态</h2>
    <div class="grid">
        <div class="card">
            <h3>日志安全过滤器</h3>
            <div class="value" style="font-size:1.2em">
                {% if security_audit.security_filter_enabled %}
                <span class="status-ok">✅ 已启用</span>
                {% else %}
                <span class="status-error">❌ 未启用</span>
                {% endif %}
            </div>
            <div class="label">自动屏蔽私钥/WIF/地址等敏感信息</div>
        </div>
        <div class="card">
            <h3>密钥操作审计</h3>
            <div class="value" style="font-size:1.2em">
                {% if security_audit.key_audit_active %}
                <span class="status-ok">{{ security_audit.total_key_operations }}</span>
                {% else %}
                <span style="color:#8b949e">暂无操作</span>
                {% endif %}
            </div>
            <div class="label">已审计的密钥操作总数</div>
        </div>
        <div class="card">
            <h3>审计日志文件</h3>
            <div class="value" style="font-size:1.2em">
                {% if security_audit.audit_log_exists %}
                <span class="status-ok">📄 存在</span>
                {% else %}
                <span style="color:#8b949e">暂无</span>
                {% endif %}
            </div>
            <div class="label">key_audit.log 审计日志</div>
        </div>
        <div class="card">
            <h3>加密后端安全</h3>
            <div class="value" style="font-size:1.1em">
                {% if security_audit.crypto_backend_ready %}
                <span class="status-ok">✅ 通过</span>
                {% else %}
                <span class="status-error">❌ 未通过</span>
                {% endif %}
            </div>
            <div class="label">
                后端: {{ security_audit.crypto_backend_name }}<br>
                安全级别:
                {% if security_audit.crypto_backend_security_level == 'secure' %}
                <span class="status-ok">安全</span>
                {% elif security_audit.crypto_backend_security_level == 'partial' %}
                <span class="status-warn">部分安全</span>
                {% elif security_audit.crypto_backend_security_level == 'insecure' %}
                <span class="status-error">不安全</span>
                {% else %}
                {{ security_audit.crypto_backend_security_level }}
                {% endif %}
                {% if security_audit.crypto_backend_constant_time %}<br><span class="status-ok">恒定时间: 是</span>{% endif %}
            </div>
        </div>
        <div class="card">
            <h3>整体安全状态</h3>
            <div class="value" style="font-size:1.2em">
                {% if security_audit.has_critical_alert %}
                <span class="status-error">⚠ 有告警</span>
                {% elif security_audit.has_warning_alert %}
                <span class="status-warn">⚡ 需关注</span>
                {% else %}
                <span class="status-ok">✅ 正常</span>
                {% endif %}
            </div>
            <div class="label">{% set alert_count = (security_audit.audit_alerts or [])|length %}{% if alert_count > 0 %}{{ alert_count }} 条告警{% else %}无安全告警{% endif %}</div>
        </div>
    </div>

    {% set alerts = security_audit.audit_alerts or [] %}
    {% if alerts|length > 0 %}
    <div style="margin-top:12px">
    {% for alert in alerts %}
    <div style="background:#161b22;border:1px solid {% if alert.level == 'critical' %}#f85149{% else %}#d29922{% endif %};border-radius:6px;padding:8px 14px;margin-bottom:6px;font-size:0.85em">
        <span style="font-weight:600;color:{% if alert.level == 'critical' %}#f85149{% else %}#d29922{% endif %}">
            {{ "🔴" if alert.level == 'critical' else "🟡" }} {{ alert.level|upper }}
        </span>: {{ alert.message }}
    </div>
    {% endfor %}
    </div>
    {% endif %}

    {% if security_audit.operations_by_type %}
    <div style="margin-top:12px">
    <table>
        <thead><tr><th>操作类型</th><th>次数</th><th>风险提示</th></tr></thead>
        <tbody>
        {% for op_type, count in security_audit.operations_by_type.items() %}
        <tr>
            <td>{{ op_type }}</td>
            <td>{{ count }}</td>
            <td>
                {% if op_type == 'display' %}
                <span class="badge badge-warn">密钥显示</span>
                {% elif op_type == 'hash' %}
                <span class="badge badge-info">哈希生成</span>
                {% elif op_type == 'export' %}
                <span class="badge badge-warn">密钥导出</span>
                {% else %}
                <span class="badge badge-info">{{ op_type }}</span>
                {% endif %}
            </td>
        </tr>
        {% endfor %}
        </tbody>
    </table>
    </div>
    {% endif %}

    {% if security_audit.recent_audit_events %}
    <div style="margin-top:12px">
    <details>
    <summary style="color:#8b949e;cursor:pointer;font-size:0.9em;margin-bottom:8px">📋 最近审计事件 ({{ security_audit.recent_audit_events|length }})</summary>
    <table style="font-size:0.85em">
        <thead><tr><th>时间</th><th>操作</th><th>级别</th><th>详情</th></tr></thead>
        <tbody>
        {% for e in security_audit.recent_audit_events %}
        <tr>
            <td>{{ e.timestamp or "N/A" }}</td>
            <td><span class="badge badge-info">{{ e.operation or "N/A" }}</span></td>
            <td>
                {% if e.level == 'critical' %}<span class="badge" style="background:#f8514933;color:#f85149">严重</span>
                {% elif e.level == 'warning' %}<span class="badge badge-warn">警告</span>
                {% else %}<span class="badge badge-info">信息</span>
                {% endif %}
            </td>
            <td>{{ e.details or e.display_mode or "-" }}</td>
        </tr>
        {% endfor %}
        </tbody>
    </table>
    </details>
    </div>
    {% endif %}
    </div>

    <!-- 错误日志 -->
    <div class="section"><h2>⚠️ 最近错误 ({{ errors|length }})</h2>
    {% if errors %}
    <table>
        <thead><tr><th>时间</th><th>类型</th><th>消息</th><th>异常</th></tr></thead>
        <tbody>
        {% for e in errors %}
        <tr>
            <td>{{ e.datetime or "N/A" }}</td>
            <td><span class="badge badge-warn">{{ e.type or "N/A" }}</span></td>
            <td>{{ e.message[:100] if e.message else "N/A" }}</td>
            <td>{{ e.exception_type or "-" }}</td>
        </tr>
        {% endfor %}
        </tbody>
    </table>
    {% else %}
    <p class="empty">✅ 暂无错误记录</p>
    {% endif %}</div>

    <!-- 历史数据 -->
    <div class="section"><h2>📈 最近历史数据 ({{ history|length }} 条)</h2>
    {% if history %}
    <table>
        <thead><tr><th>时间</th><th>速度/s</th><th>总数</th><th>匹配</th><th>CPU%</th><th>内存MB</th></tr></thead>
        <tbody>
        {% for h in history %}
        <tr>
            <td>{{ h.datetime or "N/A" }}</td>
            <td>{{ "%.0f"|format(h.speed or 0) }}</td>
            <td>{{ "{:,}".format(h.total_checked or 0) }}</td>
            <td>{{ h.matches_found or 0 }}</td>
            <td>{{ "%.1f"|format(h.cpu_usage or 0) }}</td>
            <td>{{ "%.0f"|format(h.memory_usage or 0) }}</td>
        </tr>
        {% endfor %}
        </tbody>
    </table>
    {% else %}
    <p class="empty">暂无历史数据</p>
    {% endif %}</div>

    <div class="footer">
        BTC 碰撞引擎 v{{ version }} | Web 监控仪表板 v4.2.1
    </div>
</body>
</html>"""

# ──────────────────────────────────────────────────────────────────
# 数据读取工具
# ──────────────────────────────────────────────────────────────────


def _find_data_logs_dir() -> Path:
    """查找 data_logs 目录"""
    candidates = [
        Path("data_logs"),
        Path(__file__).parent.parent.parent / "data_logs",
    ]
    for c in candidates:
        if c.exists():
            return c
    return Path("data_logs")


def _safe_read_json(path: Path) -> Any:
    """安全读取 JSON 文件"""
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"读取 JSON 失败 {path}: {e}")
        return None


def get_current_stats(data_dir: Path) -> dict[str, Any]:
    """获取当前统计信息"""
    data = _safe_read_json(data_dir / "current_data.json") or {}
    perf = data.get("performance", {})
    engine_info = data.get("engine", {})
    system_info = data.get("system", {})

    return {
        "speed": perf.get("speed", 0) if isinstance(perf, dict) else 0,
        "avg_speed": perf.get("avg_speed", 0) if isinstance(perf, dict) else 0,
        "max_speed": 0,
        "total_checked": perf.get("total_checked", 0) if isinstance(perf, dict) else 0,
        "matches_found": perf.get("matches_found", 0) if isinstance(perf, dict) else 0,
        "cpu_usage": perf.get("cpu_usage", 0) if isinstance(perf, dict) else 0,
        "memory_usage": perf.get("memory_usage", 0) if isinstance(perf, dict) else 0,
        "thread_count": perf.get("thread_count", 0) if isinstance(perf, dict) else 0,
        "uptime": data.get("uptime", 0),
        "is_running": (engine_info.get("is_running", False) if isinstance(engine_info, dict) else False),
        "mode": engine_info.get("mode", "") if isinstance(engine_info, dict) else "",
        "target_count": engine_info.get("target_count", 0) if isinstance(engine_info, dict) else 0,
        "current_position": (
            engine_info.get("current_position", 0) if isinstance(engine_info, dict) else 0
        ),
        "os": system_info.get("os", "N/A") if isinstance(system_info, dict) else "N/A",
        "python_version": (
            system_info.get("python_version", "N/A") if isinstance(system_info, dict) else "N/A"
        ),
        "pid": system_info.get("pid", "N/A") if isinstance(system_info, dict) else "N/A",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def get_history(data_dir: Path, limit: int = 20) -> list[dict[str, Any]]:
    """获取历史数据"""
    data = _safe_read_json(data_dir / "history_data.json") or []
    if isinstance(data, list):
        return data[-limit:]
    return []


def get_errors(data_dir: Path, limit: int = 20) -> list[dict[str, Any]]:
    """获取错误日志"""
    data = _safe_read_json(data_dir / "error_log.json") or []
    if isinstance(data, list):
        return data[-limit:]
    return []


def format_uptime(seconds: float) -> str:
    """格式化运行时间"""
    if seconds < 60:
        return f"{int(seconds)}秒"
    elif seconds < 3600:
        return f"{int(seconds // 60)}分{int(seconds % 60)}秒"
    else:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        return f"{h}小时{m}分"


def get_security_audit_data(data_dir: Path) -> dict[str, Any]:
    """获取安全审计状态数据（已脱敏，不暴露私钥等敏感信息）

    聚合多来源审计信息：
    1. CryptoBackend 安全性验证（verify_production_ready）
    2. KeyAuditLogger 运行内存统计（密钥操作次数）
    3. key_audit.log 最近审计事件（可选）
    4. SecurityLogFilter 启用状态

    Returns:
        脱敏后的安全审计状态字典
    """
    audit_info: dict[str, Any] = {
        "security_filter_enabled": True,  # 默认已启用
        "key_audit_active": False,
        "total_key_operations": 0,
        "operations_by_type": {},
        "recent_audit_events": [],
        "audit_log_exists": False,
        "audit_alerts": [],
        "has_critical_alert": False,
        "has_warning_alert": False,
        # Crypto backend security
        "crypto_backend_ready": True,
        "crypto_backend_name": "unknown",
        "crypto_backend_security_level": "unknown",
        "crypto_backend_constant_time": False,
        "crypto_backend_message": "",
    }

    # 1. 尝试从 KeyAuditLogger 获取运行内存统计
    try:
        from src.utils.key_audit import get_audit_logger

        audit_logger = get_audit_logger()
        stats = audit_logger.get_statistics()
        audit_info["key_audit_active"] = stats.get("total_operations", 0) > 0
        audit_info["total_key_operations"] = stats.get("total_operations", 0)
        audit_info["operations_by_type"] = stats.get("operations_by_type", {})
    except Exception as e:
        logger.debug(f"无法获取 KeyAuditLogger 统计: {e}")
        audit_info["key_audit_active"] = False

    # 2. 读取 key_audit.log（如果有的话）获取最近审计事件
    audit_log_path = data_dir / "key_audit.log"
    if audit_log_path.exists():
        audit_info["audit_log_exists"] = True
        try:
            recent_events = _parse_audit_log_entries(audit_log_path, limit=20)
            audit_info["recent_audit_events"] = recent_events

            # 统计最近事件中的告警
            critical_count = sum(1 for e in recent_events if e.get("level") == "critical")
            warning_count = sum(1 for e in recent_events if e.get("level") == "warning")

            if critical_count > 0:
                audit_info["audit_alerts"].append(
                    {
                        "level": "critical",
                        "message": f"检测到 {critical_count} 次严重级别密钥操作（最近记录）",
                    }
                )
            if warning_count > 0:
                audit_info["audit_alerts"].append(
                    {
                        "level": "warning",
                        "message": f"检测到 {warning_count} 次警告级别密钥操作（最近记录）",
                    }
                )

            audit_info["has_critical_alert"] = critical_count > 0
            audit_info["has_warning_alert"] = warning_count > 0
        except Exception as e:
            logger.warning(f"解析审计日志失败: {e}")

    # 3. 检查 SecurityLogFilter 是否已初始化
    try:
        from src.utils.logging_config import _security_filter_initialized as _sfi

        audit_info["security_filter_enabled"] = _sfi
    except ImportError:
        audit_info["security_filter_enabled"] = True  # 默认假设已启用

    # 4. CryptoBackend 安全性验证
    #    仅暴露后端名称、安全级别、恒定时间状态，不暴露私钥或密码学材料
    try:
        from src.core.crypto_backend import get_backend_security_info, verify_production_ready

        is_ready, message = verify_production_ready()
        backend_info = get_backend_security_info()

        audit_info["crypto_backend_ready"] = is_ready
        audit_info["crypto_backend_name"] = backend_info.get("backend", "unknown") or "unknown"
        audit_info["crypto_backend_security_level"] = backend_info.get("security_level", "unknown")
        audit_info["crypto_backend_constant_time"] = backend_info.get("is_constant_time", False)
        audit_info["crypto_backend_message"] = message

        if not is_ready:
            security_level = backend_info.get("security_level", "unknown")
            if security_level == "insecure":
                audit_info["audit_alerts"].append(
                    {
                        "level": "critical",
                        "message": (
                            f"加密后端不安全 (当前: {audit_info['crypto_backend_name']})，"
                            f"建议立即安装 coincurve 或 cryptography"
                        ),
                    }
                )
                audit_info["has_critical_alert"] = True
            elif security_level == "partial":
                audit_info["audit_alerts"].append(
                    {
                        "level": "warning",
                        "message": (
                            f"加密后端部分安全 (当前: {audit_info['crypto_backend_name']})，"
                            f"建议安装 coincurve 以获得完全恒定时间保护"
                        ),
                    }
                )
                audit_info["has_warning_alert"] = True
    except Exception as e:
        logger.warning(f"无法获取加密后端安全信息: {e}")
        # 获取失败时保持默认值，不影响 Dashboard 其他功能

    return audit_info


def _parse_audit_log_entries(log_path: Path, limit: int = 20) -> list[dict[str, Any]]:
    """解析 key_audit.log 文件，提取最近 N 条审计条目（已脱敏）

    日志格式示例:
    2026-05-20 12:00:00,000 - src.utils.key_audit - INFO - [KEY_AUDIT] 2026-05-20T12:00:00 | Operation: display | Level: info | Address: 1A1zP1...eP5Q | KeyHash: a1b2c3d4e5f6... | DisplayMode: masked | Details: 私钥已脱敏显示

    注意：所有敏感信息已在日志写入时被 SecurityLogFilter 脱敏处理。
    此处仅解析和聚合，不暴露私钥相关敏感内容。

    W3修复: 使用正则解析替代脆弱的 split(' | ') 分割，
    对日志格式变更和值中包含空格/特殊字符更具容忍性。
    """
    import re

    entries: list[dict[str, Any]] = []
    try:
        with open(log_path, encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return entries

    # 匹配 [KEY_AUDIT] <timestamp> | Key: value | Key: value ...
    _key_audit_re = re.compile(r"\[KEY_AUDIT\]\s*(\S+)")
    _kv_re = re.compile(r"(\w+):\s*((?:[^|]|\|(?!\s))+?)\s*(?=\|\s+\w+:|$)")

    # 从后往前读，取最近 N 条 [KEY_AUDIT] 行
    for line in reversed(lines):
        if "[KEY_AUDIT]" not in line:
            continue
        if len(entries) >= limit:
            break

        entry: dict[str, Any] = {}
        line_stripped = line.strip()

        # 提取 [KEY_AUDIT] 后的时间戳
        ts_match = _key_audit_re.search(line_stripped)
        if ts_match:
            entry["timestamp"] = ts_match.group(1)
            # 截取时间戳之后的部分（键值对区域）
            kv_region = line_stripped[ts_match.end() :]
        else:
            kv_region = line_stripped

        # 正则提取所有 Key: value 对
        known_keys = {"Operation", "Level", "DisplayMode", "Details"}
        for m in _kv_re.finditer(kv_region):
            key = m.group(1)
            value = m.group(2).strip()
            if key in known_keys:
                entry[key.lower()] = value

        if entry:
            entries.append(entry)

    # 恢复正序
    entries.reverse()
    return entries


# ──────────────────────────────────────────────────────────────────
# Flask 应用工厂
# ──────────────────────────────────────────────────────────────────


def create_app(data_dir: Path | None = None) -> "Flask":
    """创建 Flask 应用

    Args:
        data_dir: data_logs 目录路径，为 None 时自动查找

    Returns:
        Flask 应用实例
    """
    if not FLASK_AVAILABLE:
        raise ImportError("Flask 未安装。请运行: pip install flask")

    app = Flask(__name__)
    data_logs_dir = data_dir or _find_data_logs_dir()

    if _api_key_required:
        logger.info("Web 仪表板 API Key 认证已启用")
    else:
        logger.warning(
            "Web 仪表板未设置 API Key，所有端点可公开访问。请通过 --api-key 参数或 DASHBOARD_API_KEY 环境变量设置密钥。"
        )

    # 从 web 包元数据获取版本号（避免硬编码和触发 OpenCL 初始化）
    try:
        from . import __version__ as web_version

        version = web_version
    except ImportError:
        version = "1.0.0"

    @app.route("/")
    @require_auth
    def index():
        """仪表板主页"""
        stats = get_current_stats(data_logs_dir)
        history = get_history(data_logs_dir, limit=20)
        errors = get_errors(data_logs_dir, limit=15)
        security_audit = get_security_audit_data(data_logs_dir)

        uptime_display = format_uptime(stats.get("uptime", 0))

        return render_template_string(
            DASHBOARD_TEMPLATE,
            stats=stats,
            history=history,
            errors=errors,
            uptime_display=uptime_display,
            security_audit=security_audit,
            engine={
                "mode": stats.get("mode", ""),
                "target_count": stats.get("target_count", 0),
                "current_position": stats.get("current_position", 0),
            },
            system={
                "os": stats.get("os", "N/A"),
                "python_version": stats.get("python_version", "N/A"),
                "pid": stats.get("pid", "N/A"),
            },
            version=version,
            generated_at=time.strftime("%Y-%m-%d %H:%M:%S"),
        )

    @app.route("/api/status")
    @require_auth
    def api_status():
        """API: 当前运行状态"""
        return jsonify(get_current_stats(data_logs_dir))

    @app.route("/api/history")
    @require_auth
    def api_history():
        """API: 历史数据

        Query params:
            limit: 返回条数 (默认 50, 最大 200)
        """
        limit = request.args.get("limit", 50, type=int)
        limit = min(limit, 200)
        return jsonify(get_history(data_logs_dir, limit=limit))

    @app.route("/api/errors")
    @require_auth
    def api_errors():
        """API: 错误日志

        Query params:
            limit: 返回条数 (默认 50, 最大 200)
        """
        limit = request.args.get("limit", 50, type=int)
        limit = min(limit, 200)
        return jsonify(get_errors(data_logs_dir, limit=limit))

    @app.route("/api/report")
    @require_auth
    def api_report():
        """API: 日报告摘要"""
        stats = get_current_stats(data_logs_dir)
        history = get_history(data_logs_dir, limit=100)

        speeds = [h.get("speed", 0) for h in history if h.get("speed")]
        avg_speed = sum(speeds) / len(speeds) if speeds else 0
        max_speed = max(speeds) if speeds else 0

        return jsonify(
            {
                "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "summary": {
                    "total_checked": stats.get("total_checked", 0),
                    "matches_found": stats.get("matches_found", 0),
                    "avg_speed": round(avg_speed, 2),
                    "max_speed": round(max_speed, 2),
                    "uptime_seconds": stats.get("uptime", 0),
                    "cpu_usage": stats.get("cpu_usage", 0),
                    "memory_usage": stats.get("memory_usage", 0),
                },
                "engine": {
                    "mode": stats.get("mode", ""),
                    "is_running": stats.get("is_running", False),
                },
            }
        )

    @app.route("/api/security-audit")
    @require_auth
    def api_security_audit():
        """API: 安全审计状态（已脱敏，不暴露私钥等敏感信息）

        Returns:
            密钥操作统计、审计日志概述、安全过滤器状态、
            加密后端安全性验证、审计告警
        """
        audit_data = get_security_audit_data(data_logs_dir)
        return jsonify(audit_data)

    @app.route("/health")
    def health():
        """健康检查端点"""
        return jsonify({"status": "ok", "timestamp": time.time()})

    return app


def run_dashboard(
    host: str = "0.0.0.0",  # nosec B104: Web仪表板默认绑定所有接口，用户可通过--host覆盖
    port: int = 8080,
    data_dir: str | None = None,
    debug: bool = False,
    use_reloader: bool = False,
    api_key: str | None = None,
) -> None:
    """启动 Web 监控仪表板

    Args:
        host: 监听地址 (默认 0.0.0.0)
        port: 监听端口 (默认 8080)
        data_dir: data_logs 目录路径
        debug: 是否开启调试模式
        use_reloader: 是否启用 Flask 自动重载 (开发模式，默认关闭)
        api_key: API 认证密钥 (None=不启用认证)
    """
    if not FLASK_AVAILABLE:
        print("❌ Flask 未安装。请运行: pip install flask")
        sys.exit(1)

    set_api_key(api_key)

    data_path = Path(data_dir) if data_dir else None
    app = create_app(data_dir=data_path)

    auth_status = "已启用" if _api_key_required else "未启用 (公开访问)"  # noqa: F841
    print(f"""
╔══════════════════════════════════════════════════════╗
║     BTC 碰撞引擎 - Web 监控仪表板 v4.2.1               ║
╠══════════════════════════════════════════════════════╣
║  本地访问: http://127.0.0.1:{port:<5}                  ║
║  API Key:  {auth_status:<38}║
║  API 端点:                                           ║
║    GET /api/status         - 当前运行状态            ║
║    GET /api/history        - 历史数据 (?limit=N)     ║
║    GET /api/errors         - 错误日志 (?limit=N)     ║
║    GET /api/report         - 日报告摘要              ║
║    GET /api/security-audit - 安全审计状态            ║
║    GET /health             - 健康检查                ║
╚══════════════════════════════════════════════════════╝
""")

    # 安全: debug模式下强制绑定localhost，防止远程代码执行
    if debug and host not in ("127.0.0.1", "localhost"):
        logger.warning(f"Debug 模式仅允许本地绑定，已自动将 host 从 {host} 改为 127.0.0.1")
        host = "127.0.0.1"

    app.run(host=host, port=port, debug=debug, use_reloader=use_reloader)


# ──────────────────────────────────────────────────────────────────
# CLI 入口
# ──────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="BTC 碰撞引擎 - Web 监控仪表板",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python -m src.web.dashboard                              # 默认 0.0.0.0:8080, 无认证
  python -m src.web.dashboard --port 3000                  # 自定义端口
  python -m src.web.dashboard --host 127.0.0.1             # 仅本地访问
  python -m src.web.dashboard --api-key YOUR_SECRET        # 启用 API Key 认证
  python -m src.web.dashboard --debug                      # 调试模式

环境变量:
  DASHBOARD_API_KEY    设置 API 认证密钥 (与 --api-key 等效)
        """,
    )
    parser.add_argument("--host", default="0.0.0.0", help="监听地址 (默认: 0.0.0.0)")  # nosec B104
    parser.add_argument("--port", type=int, default=8080, help="监听端口 (默认: 8080)")
    parser.add_argument("--data-dir", default=None, help="data_logs 目录路径")
    parser.add_argument("--debug", action="store_true", help="开启 Flask 调试模式")
    parser.add_argument("--reload", action="store_true", help="启用 Flask 自动重载 (开发模式)")
    parser.add_argument(
        "--api-key",
        default=os.environ.get("DASHBOARD_API_KEY", None),
        help="API 认证密钥 (默认读取 DASHBOARD_API_KEY 环境变量, 不设置则不启用认证)",
    )
    args = parser.parse_args()

    run_dashboard(
        host=args.host,
        port=args.port,
        data_dir=args.data_dir,
        debug=args.debug,
        use_reloader=args.reload,
        api_key=args.api_key,
    )


if __name__ == "__main__":
    main()

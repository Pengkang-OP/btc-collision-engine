"""端到端自动化闭环管理系统.

从数据分析到自动化测试再到智能审核的完整闭环管控系统.

核心功能:
1. 数据分析模块 - 自动处理输入数据并生成深度分析报告
2. 自动化测试模块 - 基于分析结果执行全面的测试用例
3. 智能审核模块 - 校验测试结果与业务规则，拦截异常
4. 闭环控制器 - 协调各模块，异常自动触发反馈回路
"""

from .audit import AuditModule
from .auto_test import AutoTestModule
from .data_analysis import DataAnalysisModule
from .loop_controller import LoopController
from .models import AnalysisReport, AuditResult, SystemStatus, TestResult, TestSuiteResult

from src import __version__ as __version__  # noqa: F401 — 从包根统一读取
__all__ = [
    "AnalysisReport",
    "AuditModule",
    "AuditResult",
    "AutoTestModule",
    "DataAnalysisModule",
    "LoopController",
    "SystemStatus",
    "TestResult",
    "TestSuiteResult",
]

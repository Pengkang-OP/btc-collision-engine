"""
数据分析模块
=============
自动处理输入数据并生成深度分析报告
"""

import ast
import hashlib
import json
import logging
import os
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# 添加项目路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from .models import AnalysisReport, Issue, Severity


class DataAnalysisModule:
    """数据分析模块 - 自动处理输入数据并生成深度分析报告"""

    def __init__(self, project_root: Path | None = None):
        self.project_root = project_root or Path(__file__).parent.parent.parent.parent
        self.analysis_cache = {}

    def analyze(self, target_path: str | None = None) -> AnalysisReport:
        """
        执行完整的数据分析
        """
        report_id = self._generate_report_id()

        # 收集数据
        data_summary = self._collect_data_summary(target_path)

        # 统计分析
        statistics = self._compute_statistics(data_summary)

        # 识别问题
        issues = self._identify_issues(data_summary, statistics)

        # 生成建议
        recommendations = self._generate_recommendations(issues, statistics)

        return AnalysisReport(
            report_id=report_id,
            timestamp=datetime.now(),
            data_summary=data_summary,
            statistics=statistics,
            issues=issues,
            recommendations=recommendations,
            metadata={
                "project_root": str(self.project_root),
                "target_path": target_path,
            },
        )

    def _generate_report_id(self) -> str:
        """生成唯一报告ID"""
        timestamp = datetime.now().isoformat()
        return f"analysis_{hashlib.md5(timestamp.encode()).hexdigest()[:12]}"

    def _collect_data_summary(self, target_path: str | None = None) -> dict[str, Any]:
        """收集数据摘要

        自 v4.3.1: 合并 _analyze_project_structure 和 _analyze_code_metrics
        为单次 src/ 遍历，减少约 50% 的 os.walk + ast.parse 调用。
        """
        # 合并后的结构+代码指标分析
        combined = self._analyze_source_code()

        summary = {
            "project_structure": combined["structure"],
            "code_metrics": combined["metrics"],
            "dependencies": self._analyze_dependencies(),
            "test_coverage": self._analyze_test_coverage(),
            "configuration": self._analyze_configuration(),
        }

        if target_path:
            summary["target_analysis"] = self._analyze_target(target_path)

        return summary

    def _analyze_source_code(self) -> dict[str, Any]:
        """合并分析项目结构和代码指标（单次遍历 src/ 目录）

        自 v4.3.1: 将 _analyze_project_structure 和 _analyze_code_metrics
        合并为一次 os.walk，对每个 .py 文件一次性提取所有指标。

        Returns:
            {"structure": {...}, "metrics": {...}}
        """
        structure = {
            "total_files": 0,
            "python_files": 0,
            "total_modules": 0,
            "total_classes": 0,
            "total_functions": 0,
            "module_depth": 0,
        }
        metrics_data = {
            "avg_file_length": 0,
            "max_file_length": 0,
            "total_lines": 0,
            "code_complexity": {},
            "import_counts": defaultdict(int),
        }

        src_dir = self.project_root / "src"
        if not src_dir.exists():
            return {"structure": structure, "metrics": metrics_data}

        file_lengths: list[int] = []

        for root, dirs, files in os.walk(src_dir):
            structure["total_files"] += len(files)
            py_files = [f for f in files if f.endswith(".py") and not f.startswith("__")]
            structure["python_files"] += len(py_files)

            for py_file in py_files:
                filepath = Path(root) / py_file
                try:
                    with open(filepath, encoding="utf-8") as f:
                        content = f.read()

                    # 结构指标: AST 解析
                    tree = ast.parse(content)
                    structure["total_classes"] += sum(
                        1 for n in ast.walk(tree) if isinstance(n, ast.ClassDef)
                    )
                    structure["total_functions"] += sum(
                        1 for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                    )

                    # 代码指标: 行数和导入
                    lines = content.splitlines()
                    file_length = len(lines)
                    file_lengths.append(file_length)
                    metrics_data["total_lines"] += file_length

                    # 分析导入（扩展至前50行以捕获延迟导入）
                    for line in lines[:50]:
                        match = re.match(r"^\s*import\s+(\w+)", line)
                        if match:
                            metrics_data["import_counts"][match.group(1)] += 1

                except (SyntaxError, ValueError) as e:
                    logger.debug(f"AST解析失败: {filepath} - {e}")
                except (OSError, UnicodeDecodeError):
                    pass  # 忽略无法读取的文件

        structure["module_depth"] = len(list(src_dir.rglob("__init__.py")))

        if file_lengths:
            metrics_data["avg_file_length"] = sum(file_lengths) / len(file_lengths)
            metrics_data["max_file_length"] = max(file_lengths)

        metrics_data["import_counts"] = dict(metrics_data["import_counts"])

        return {"structure": structure, "metrics": metrics_data}

    def _analyze_dependencies(self) -> dict[str, Any]:
        """分析依赖关系"""
        deps = {
            "required": [],
            "optional": [],
            "circular_imports": [],
            "missing_imports": [],
        }

        requirements_file = self.project_root / "requirements.txt"
        if requirements_file.exists():
            with open(requirements_file) as f:
                deps["required"] = [
                    line.strip() for line in f if line.strip() and not line.startswith("#")
                ]

        return deps

    def _analyze_test_coverage(self) -> dict[str, Any]:
        """分析测试覆盖"""
        coverage = {
            "test_files": 0,
            "test_cases": 0,
            "coverage_percent": 0.0,
        }

        tests_dir = self.project_root / "tests"
        if tests_dir.exists():
            for root, dirs, files in os.walk(tests_dir):
                test_files = [f for f in files if f.startswith("test_") and f.endswith(".py")]
                coverage["test_files"] += len(test_files)

                for tf in test_files:
                    filepath = Path(root) / tf
                    try:
                        with open(filepath, encoding="utf-8") as f:
                            content = f.read()

                        # 统计测试函数
                        tree = ast.parse(content)
                        test_funcs = [
                            n.name
                            for n in ast.walk(tree)
                            if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")
                        ]
                        coverage["test_cases"] += len(test_funcs)
                    except (SyntaxError, ValueError) as e:
                        logger.debug(f"AST解析测试文件失败: {filepath} - {e}")

        return coverage

    def _analyze_configuration(self) -> dict[str, Any]:
        """分析配置文件"""
        config = {
            "config_exists": False,
            "config_valid": False,
            "missing_keys": [],
        }

        config_file = self.project_root / "config.json"
        if config_file.exists():
            config["config_exists"] = True
            try:
                from src.utils.fast_json import fast_load

                with open(config_file) as f:
                    data = fast_load(f)
                config["config_valid"] = True
                config["keys"] = list(data.keys())
            except (OSError, json.JSONDecodeError, KeyError):
                config["config_valid"] = False

        return config

    def _analyze_target(self, target_path: str) -> dict[str, Any]:
        """分析目标数据"""
        analysis = {
            "path": target_path,
            "exists": False,
            "is_file": False,
            "size": 0,
            "line_count": 0,
        }

        path = Path(target_path)
        if path.exists():
            analysis["exists"] = True
            analysis["is_file"] = path.is_file()
            if path.is_file():
                analysis["size"] = path.stat().st_size
                try:
                    with open(path, encoding="utf-8") as f:
                        analysis["line_count"] = sum(1 for _ in f)
                except (OSError, UnicodeDecodeError):
                    pass  # 忽略无法读取的文件

        return analysis

    def _compute_statistics(self, data_summary: dict[str, Any]) -> dict[str, Any]:
        """计算统计信息"""
        stats = {
            "quality_score": 100,
            "complexity_score": 0,
            "maintainability_index": 100,
            "technical_debt": 0,
        }

        # 计算质量分数
        structure = data_summary.get("project_structure", {})
        metrics = data_summary.get("code_metrics", {})
        coverage = data_summary.get("test_coverage", {})
        config = data_summary.get("configuration", {})

        # 基于文件数量调整
        total_files = structure.get("total_files", 0)
        if total_files < 10:
            stats["quality_score"] -= 10

        # 基于测试覆盖率
        test_files = coverage.get("test_files", 0)
        if test_files < 10:
            stats["quality_score"] -= 15

        # 基于配置文件
        if not config.get("config_valid", False):
            stats["quality_score"] -= 20

        # 计算复杂度
        avg_length = metrics.get("avg_file_length", 0)
        if avg_length > 500:
            stats["complexity_score"] += 30

        # 计算可维护性指数
        total_lines = metrics.get("total_lines", 0)
        if total_lines > 10000:
            stats["maintainability_index"] -= 20

        # 确保分数在合理范围内
        stats["quality_score"] = max(0, min(100, stats["quality_score"]))
        stats["maintainability_index"] = max(0, min(100, stats["maintainability_index"]))

        return stats

    def _identify_issues(
        self, data_summary: dict[str, Any], statistics: dict[str, Any]
    ) -> list[Issue]:
        """识别问题"""
        issues = []

        structure = data_summary.get("project_structure", {})
        metrics = data_summary.get("code_metrics", {})
        coverage = data_summary.get("test_coverage", {})
        config = data_summary.get("configuration", {})

        issue_id = 1

        # 检查项目结构
        if structure.get("python_files", 0) == 0:
            issues.append(
                Issue(
                    id=f"ISSUE-{issue_id:03d}",
                    severity=Severity.CRITICAL,
                    category="Structure",
                    title="无Python文件",
                    description="项目中未找到Python源文件",
                    location="src/",
                )
            )
            issue_id += 1

        # 检查测试覆盖
        test_files = coverage.get("test_files", 0)
        if test_files < 5:
            issues.append(
                Issue(
                    id=f"ISSUE-{issue_id:03d}",
                    severity=Severity.HIGH,
                    category="Testing",
                    title="测试覆盖不足",
                    description=f"测试文件数量不足: {test_files} < 5",
                    suggestions=["增加测试文件", "提高测试覆盖率"],
                )
            )
            issue_id += 1

        # 检查配置文件
        if not config.get("config_valid", False):
            issues.append(
                Issue(
                    id=f"ISSUE-{issue_id:03d}",
                    severity=Severity.HIGH,
                    category="Configuration",
                    title="配置文件无效",
                    description="config.json格式错误或无法解析",
                    location="config.json",
                    suggestions=["检查JSON格式", "参考config.example.json"],
                )
            )
            issue_id += 1

        # 检查代码复杂度
        if statistics.get("complexity_score", 0) > 50:
            issues.append(
                Issue(
                    id=f"ISSUE-{issue_id:03d}",
                    severity=Severity.MEDIUM,
                    category="Complexity",
                    title="代码复杂度较高",
                    description="项目存在较高的代码复杂度，可能影响可维护性",
                    suggestions=["拆分大型模块", "简化复杂逻辑"],
                )
            )
            issue_id += 1

        # 检查可维护性
        if statistics.get("maintainability_index", 100) < 70:
            issues.append(
                Issue(
                    id=f"ISSUE-{issue_id:03d}",
                    severity=Severity.MEDIUM,
                    category="Maintainability",
                    title="可维护性指数偏低",
                    description="项目可维护性需要改进",
                    suggestions=["重构大型文件", "添加文档注释"],
                )
            )
            issue_id += 1

        # 检查文件大小
        avg_length = metrics.get("avg_file_length", 0)
        max_length = metrics.get("max_file_length", 0)
        if max_length > 2000:
            issues.append(
                Issue(
                    id=f"ISSUE-{issue_id:03d}",
                    severity=Severity.LOW,
                    category="Code Style",
                    title="存在超长文件",
                    description=f"最大文件长度: {max_length}行，建议拆分",
                    suggestions=["拆分超过2000行的文件", "按功能模块分离"],
                )
            )
            issue_id += 1

        return issues

    def _generate_recommendations(
        self, issues: list[Issue], statistics: dict[str, Any]
    ) -> list[str]:
        """生成建议"""
        recommendations = []

        # 基于问题生成建议
        critical_issues = [i for i in issues if i.severity == Severity.CRITICAL]
        high_issues = [i for i in issues if i.severity == Severity.HIGH]

        if critical_issues:
            recommendations.append("⚠️ 发现严重问题，必须立即修复")

        if high_issues:
            recommendations.append("🔴 高优先级问题需要尽快处理")

        # 基于统计生成建议
        if statistics.get("quality_score", 100) < 80:
            recommendations.append("📊 建议进行代码质量改进")

        if statistics.get("complexity_score", 0) > 30:
            recommendations.append("🔄 建议降低代码复杂度")

        if not recommendations:
            recommendations.append("✅ 代码质量良好，保持当前标准")

        return recommendations


# 便捷函数
def analyze_project(project_root: Path | None = None) -> AnalysisReport:
    """分析项目并生成报告"""
    module = DataAnalysisModule(project_root)
    return module.analyze()

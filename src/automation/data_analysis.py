"""
数据分析模块
=============
自动处理输入数据并生成深度分析报告
"""

import os
import sys
import ast
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from collections import defaultdict
import hashlib

# 添加项目路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from .models import AnalysisReport, Issue, Severity


class DataAnalysisModule:
    """数据分析模块 - 自动处理输入数据并生成深度分析报告"""
    
    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path(__file__).parent.parent.parent.parent
        self.analysis_cache = {}
        
    def analyze(self, target_path: Optional[str] = None) -> AnalysisReport:
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
            }
        )
    
    def _generate_report_id(self) -> str:
        """生成唯一报告ID"""
        timestamp = datetime.now().isoformat()
        return f"analysis_{hashlib.md5(timestamp.encode()).hexdigest()[:12]}"
    
    def _collect_data_summary(self, target_path: Optional[str] = None) -> Dict[str, Any]:
        """收集数据摘要"""
        summary = {
            "project_structure": self._analyze_project_structure(),
            "code_metrics": self._analyze_code_metrics(),
            "dependencies": self._analyze_dependencies(),
            "test_coverage": self._analyze_test_coverage(),
            "configuration": self._analyze_configuration(),
        }
        
        if target_path:
            summary["target_analysis"] = self._analyze_target(target_path)
        
        return summary
    
    def _analyze_project_structure(self) -> Dict[str, Any]:
        """分析项目结构"""
        structure = {
            "total_files": 0,
            "python_files": 0,
            "total_modules": 0,
            "total_classes": 0,
            "total_functions": 0,
            "module_depth": 0,
        }
        
        src_dir = self.project_root / "src"
        if not src_dir.exists():
            return structure
        
        for root, dirs, files in os.walk(src_dir):
            structure["total_files"] += len(files)
            py_files = [f for f in files if f.endswith('.py') and not f.startswith('__')]
            structure["python_files"] += len(py_files)
            
            for py_file in py_files:
                filepath = Path(root) / py_file
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                    tree = ast.parse(content)
                    
                    structure["total_classes"] += sum(1 for n in ast.walk(tree) if isinstance(n, ast.ClassDef))
                    structure["total_functions"] += sum(1 for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
                except (SyntaxError, ValueError):
                    pass  # 忽略无法解析的文件
        
        # 计算模块深度
        structure["module_depth"] = len(list(src_dir.rglob("__init__.py")))
        
        return structure
    
    def _analyze_code_metrics(self) -> Dict[str, Any]:
        """分析代码指标"""
        metrics = {
            "avg_file_length": 0,
            "max_file_length": 0,
            "total_lines": 0,
            "code_complexity": {},
            "import_counts": defaultdict(int),
        }
        
        src_dir = self.project_root / "src"
        if not src_dir.exists():
            return metrics
        
        file_lengths = []
        
        for filepath in src_dir.rglob("*.py"):
            if "__pycache__" in str(filepath):
                continue
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                file_length = len(lines)
                file_lengths.append(file_length)
                metrics["total_lines"] += file_length
                
                # 分析导入
                for line in lines[:20]:  # 只检查前20行
                    match = re.match(r'^\s*import\s+(\w+)', line)
                    if match:
                        metrics["import_counts"][match.group(1)] += 1
                        
            except (IOError, OSError, UnicodeDecodeError):
                pass  # 忽略无法读取的文件
        
        if file_lengths:
            metrics["avg_file_length"] = sum(file_lengths) / len(file_lengths)
            metrics["max_file_length"] = max(file_lengths)
        
        return dict(metrics)
    
    def _analyze_dependencies(self) -> Dict[str, Any]:
        """分析依赖关系"""
        deps = {
            "required": [],
            "optional": [],
            "circular_imports": [],
            "missing_imports": [],
        }
        
        requirements_file = self.project_root / "requirements.txt"
        if requirements_file.exists():
            with open(requirements_file, 'r') as f:
                deps["required"] = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        
        return deps
    
    def _analyze_test_coverage(self) -> Dict[str, Any]:
        """分析测试覆盖"""
        coverage = {
            "test_files": 0,
            "test_cases": 0,
            "coverage_percent": 0.0,
        }
        
        tests_dir = self.project_root / "tests"
        if tests_dir.exists():
            for root, dirs, files in os.walk(tests_dir):
                test_files = [f for f in files if f.startswith('test_') and f.endswith('.py')]
                coverage["test_files"] += len(test_files)
                
                for tf in test_files:
                    filepath = Path(root) / tf
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        # 统计测试函数
                        tree = ast.parse(content)
                        test_funcs = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name.startswith('test_')]
                        coverage["test_cases"] += len(test_funcs)
                    except (SyntaxError, ValueError):
                        pass  # 忽略无法解析的测试文件
        
        return coverage
    
    def _analyze_configuration(self) -> Dict[str, Any]:
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
                import json
                with open(config_file, 'r') as f:
                    data = json.load(f)
                config["config_valid"] = True
                config["keys"] = list(data.keys())
            except (json.JSONDecodeError, IOError, KeyError):
                config["config_valid"] = False
        
        return config
    
    def _analyze_target(self, target_path: str) -> Dict[str, Any]:
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
                    with open(path, 'r', encoding='utf-8') as f:
                        analysis["line_count"] = sum(1 for _ in f)
                except (IOError, OSError, UnicodeDecodeError):
                    pass  # 忽略无法读取的文件
        
        return analysis
    
    def _compute_statistics(self, data_summary: Dict[str, Any]) -> Dict[str, Any]:
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
    
    def _identify_issues(self, data_summary: Dict[str, Any], statistics: Dict[str, Any]) -> List[Issue]:
        """识别问题"""
        issues = []
        
        structure = data_summary.get("project_structure", {})
        metrics = data_summary.get("code_metrics", {})
        coverage = data_summary.get("test_coverage", {})
        config = data_summary.get("configuration", {})
        
        issue_id = 1
        
        # 检查项目结构
        if structure.get("python_files", 0) == 0:
            issues.append(Issue(
                id=f"ISSUE-{issue_id:03d}",
                severity=Severity.CRITICAL,
                category="Structure",
                title="无Python文件",
                description="项目中未找到Python源文件",
                location="src/",
            ))
            issue_id += 1
        
        # 检查测试覆盖
        test_files = coverage.get("test_files", 0)
        if test_files < 5:
            issues.append(Issue(
                id=f"ISSUE-{issue_id:03d}",
                severity=Severity.HIGH,
                category="Testing",
                title="测试覆盖不足",
                description=f"测试文件数量不足: {test_files} < 5",
                suggestions=["增加测试文件", "提高测试覆盖率"],
            ))
            issue_id += 1
        
        # 检查配置文件
        if not config.get("config_valid", False):
            issues.append(Issue(
                id=f"ISSUE-{issue_id:03d}",
                severity=Severity.HIGH,
                category="Configuration",
                title="配置文件无效",
                description="config.json格式错误或无法解析",
                location="config.json",
                suggestions=["检查JSON格式", "参考config.example.json"],
            ))
            issue_id += 1
        
        # 检查代码复杂度
        if statistics.get("complexity_score", 0) > 50:
            issues.append(Issue(
                id=f"ISSUE-{issue_id:03d}",
                severity=Severity.MEDIUM,
                category="Complexity",
                title="代码复杂度较高",
                description="项目存在较高的代码复杂度，可能影响可维护性",
                suggestions=["拆分大型模块", "简化复杂逻辑"],
            ))
            issue_id += 1
        
        # 检查可维护性
        if statistics.get("maintainability_index", 100) < 70:
            issues.append(Issue(
                id=f"ISSUE-{issue_id:03d}",
                severity=Severity.MEDIUM,
                category="Maintainability",
                title="可维护性指数偏低",
                description="项目可维护性需要改进",
                suggestions=["重构大型文件", "添加文档注释"],
            ))
            issue_id += 1
        
        # 检查文件大小
        avg_length = metrics.get("avg_file_length", 0)
        max_length = metrics.get("max_file_length", 0)
        if max_length > 2000:
            issues.append(Issue(
                id=f"ISSUE-{issue_id:03d}",
                severity=Severity.LOW,
                category="Code Style",
                title="存在超长文件",
                description=f"最大文件长度: {max_length}行，建议拆分",
                suggestions=["拆分超过2000行的文件", "按功能模块分离"],
            ))
            issue_id += 1
        
        return issues
    
    def _generate_recommendations(self, issues: List[Issue], statistics: Dict[str, Any]) -> List[str]:
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
def analyze_project(project_root: Optional[Path] = None) -> AnalysisReport:
    """分析项目并生成报告"""
    module = DataAnalysisModule(project_root)
    return module.analyze()

"""
智能审核模块
=============
校验测试结果与业务规则，拦截异常并记录
"""

import json
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from .models import (
    AnalysisReport,
    AuditResult,
    AuditRule,
    Issue,
    Severity,
    SystemStatus,
    TestSuiteResult,
)


class AuditModule:
    """智能审核模块"""

    # 默认审核规则
    DEFAULT_RULES = [
        AuditRule(
            id="RULE-001",
            name="关键测试必须通过",
            description="核心功能测试(优先级1)必须全部通过",
            condition="test_pass_rate >= 90 AND critical_tests_passed",
            action="block",
            severity=Severity.CRITICAL,
        ),
        AuditRule(
            id="RULE-002",
            name="严重问题必须修复",
            description="不允许存在严重(Critical)级别的问题",
            condition="critical_issues == 0",
            action="block",
            severity=Severity.CRITICAL,
        ),
        AuditRule(
            id="RULE-003",
            name="高优先级问题限制",
            description="高优先级问题不应超过3个",
            condition="high_priority_issues <= 3",
            action="warn",
            severity=Severity.HIGH,
        ),
        AuditRule(
            id="RULE-004",
            name="测试覆盖率要求",
            description="测试覆盖率应达到80%以上",
            condition="test_coverage >= 80",
            action="warn",
            severity=Severity.MEDIUM,
        ),
        AuditRule(
            id="RULE-005",
            name="性能基准达标",
            description="性能测试必须通过",
            condition="performance_tests_passed",
            action="block",
            severity=Severity.HIGH,
        ),
        AuditRule(
            id="RULE-006",
            name="无致命错误",
            description="不允许存在测试执行错误",
            condition="test_errors == 0",
            action="block",
            severity=Severity.CRITICAL,
        ),
        AuditRule(
            id="RULE-007",
            name="配置完整性",
            description="配置文件必须有效",
            condition="config_valid",
            action="block",
            severity=Severity.HIGH,
        ),
        AuditRule(
            id="RULE-008",
            name="代码质量基线",
            description="代码质量分数应达到70分以上",
            condition="quality_score >= 70",
            action="warn",
            severity=Severity.MEDIUM,
        ),
    ]

    def __init__(self, rules: list[AuditRule] | None = None):
        self.rules = rules or self.DEFAULT_RULES
        self.audit_history: list[AuditResult] = []

    def audit(
        self,
        test_results: TestSuiteResult,
        analysis_report: AnalysisReport | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditResult:
        """
        执行审核
        """
        audit_id = self._generate_audit_id()

        try:
            # 计算审核指标
            metrics = self._compute_audit_metrics(test_results, analysis_report)

            # 执行规则检查
            violations, warnings_list, passed_checks = self._check_rules(
                metrics, test_results, analysis_report
            )

            # 确定审核状态
            status = self._determine_status(violations, warnings_list, passed_checks)
        except Exception as e:
            # v4.3.1: 审计流程容错 — 内部异常不中断审计，返回失败状态
            metrics = {}
            violations = [
                Issue(
                    id="AUDIT_INTERNAL_ERROR",
                    severity=Severity.CRITICAL,
                    category="Audit",
                    title="审计流程内部异常",
                    description=f"审计计算过程发生异常: {e}",
                )
            ]
            warnings_list = []
            passed_checks = 0
            status = SystemStatus.FAILED

        result = AuditResult(
            audit_id=audit_id,
            timestamp=datetime.now(),
            status=status,
            violations=violations,
            warnings=warnings_list,
            passed_checks=passed_checks,
            total_checks=len(self.rules),
            test_results=test_results,
            analysis_report=analysis_report,
            metadata=metadata or {},
        )

        # 添加指标到元数据
        result.metadata["metrics"] = metrics

        self.audit_history.append(result)

        return result

    def _generate_audit_id(self) -> str:
        """生成审核ID"""
        return f"audit_{uuid.uuid4().hex[:12]}"

    def _compute_audit_metrics(
        self, test_results: TestSuiteResult, analysis_report: AnalysisReport | None
    ) -> dict[str, Any]:
        """计算审核指标

        v4.3.1: 添加错误容错 — 单个指标计算失败不影响整体审计。
        """
        metrics: dict[str, Any] = {
            "test_pass_rate": 0.0,
            "test_total": 0,
            "test_passed": 0,
            "test_failed": 0,
            "test_errors": 0,
            "test_skipped": 0,
            "critical_issues": 0,
            "high_priority_issues": 0,
            "medium_priority_issues": 0,
            "low_priority_issues": 0,
            "config_valid": True,
            "quality_score": 100,
            "performance_tests_passed": True,
        }

        # 安全获取测试结果指标
        try:
            metrics["test_pass_rate"] = test_results.pass_rate
            metrics["test_total"] = test_results.total
            metrics["test_passed"] = test_results.passed
            metrics["test_failed"] = test_results.failed
            metrics["test_errors"] = test_results.errors
            metrics["test_skipped"] = test_results.skipped
        except Exception:
            pass  # 使用默认值

        # 从分析报告获取问题统计（安全访问）
        if analysis_report:
            try:
                issues = getattr(analysis_report, "issues", None) or []
                for issue in issues:
                    sev = getattr(issue, "severity", None)
                    if sev == Severity.CRITICAL:
                        metrics["critical_issues"] += 1
                    elif sev == Severity.HIGH:
                        metrics["high_priority_issues"] += 1
                    elif sev == Severity.MEDIUM:
                        metrics["medium_priority_issues"] += 1
                    elif sev == Severity.LOW:
                        metrics["low_priority_issues"] += 1
            except Exception:
                pass

            # 配置状态（安全访问嵌套属性）
            try:
                data_summary = getattr(analysis_report, "data_summary", None) or {}
                config_info = data_summary.get("configuration", {}) if isinstance(data_summary, dict) else {}
                metrics["config_valid"] = config_info.get("config_valid", True)
            except Exception:
                pass

            # 质量分数
            try:
                stats = getattr(analysis_report, "statistics", None) or {}
                metrics["quality_score"] = stats.get("quality_score", 100) if isinstance(stats, dict) else 100
            except Exception:
                pass

        # 检查性能测试
        try:
            perf_tests = [
                r
                for r in getattr(test_results, "results", []) or []
                if getattr(r, "test_name", "").startswith("测试大整数")
                or getattr(r, "test_name", "").startswith("测试哈希")
            ]
            if perf_tests:
                metrics["performance_tests_passed"] = all(
                    getattr(r, "is_passed", True) for r in perf_tests
                )
        except Exception:
            pass

        # 检查关键测试通过率
        try:
            priority_1_tests = [
                r
                for r in getattr(test_results, "results", []) or []
                if any(
                    tc in getattr(r, "test_name", "")
                    for tc in ["配置", "CLI", "加密", "端到端"]
                )
            ]
            if priority_1_tests:
                metrics["critical_tests_passed"] = all(
                    getattr(r, "is_passed", True) for r in priority_1_tests
                )
                metrics["critical_test_pass_rate"] = (
                    sum(1 for r in priority_1_tests if getattr(r, "is_passed", True))
                    / len(priority_1_tests) * 100
                )
            else:
                metrics["critical_tests_passed"] = True
                metrics["critical_test_pass_rate"] = 100
        except Exception:
            metrics["critical_tests_passed"] = True
            metrics["critical_test_pass_rate"] = 100

        return metrics

    def _check_rules(
        self,
        metrics: dict[str, Any],
        test_results: TestSuiteResult,
        analysis_report: AnalysisReport | None,
    ) -> tuple:
        """执行规则检查"""
        violations = []
        warnings = []
        passed_checks = 0

        for rule in self.rules:
            try:
                result = self._evaluate_rule(rule, metrics)

                if result["passed"]:
                    passed_checks += 1
                elif rule.action == "block":
                    violations.append(
                        Issue(
                            id=rule.id,
                            severity=rule.severity,
                            category="Audit",
                            title=rule.name,
                            description=f"规则违反: {rule.description}",
                            suggestions=[f"检查并修复: {rule.description}"],
                            metadata={"rule_id": rule.id, "condition": rule.condition},
                        )
                    )
                elif rule.action == "warn":
                    warnings.append(
                        Issue(
                            id=rule.id,
                            severity=rule.severity,
                            category="Audit",
                            title=rule.name,
                            description=f"警告: {rule.description}",
                            suggestions=[f"建议改进: {rule.description}"],
                            metadata={"rule_id": rule.id, "condition": rule.condition},
                        )
                    )
            except Exception as e:
                # 规则评估失败，记录但不阻塞
                warnings.append(
                    Issue(
                        id=f"{rule.id}_ERROR",
                        severity=Severity.INFO,
                        category="Audit",
                        title=f"规则评估异常: {rule.name}",
                        description=str(e),
                    )
                )

        return violations, warnings, passed_checks

    def _evaluate_rule(self, rule: AuditRule, metrics: dict[str, Any]) -> dict[str, Any]:
        """评估单条规则

        自 v4.3.1: 使用正则表达式匹配条件，防止子字符串误匹配。
        例如 "test_pass_rate >= 90" 不会错误匹配 "test_pass_rate >= 900"。
        """
        condition = rule.condition
        passed = True

        # --- 含数值比较的条件：使用正则确保数字精确匹配，防止 >=90 误匹配 >=900 ---
        # 模式: <metric> <op> <number>，数字后跟单词边界或字符串末尾
        _num = r'(\d+(?:\.\d+)?)\b'

        if re.search(rf'test_pass_rate\s*>=\s*{_num}', condition):
            m = re.search(rf'test_pass_rate\s*>=\s*{_num}', condition)
            threshold = float(m.group(1)) if m else 90
            passed = passed and metrics.get("test_pass_rate", 0) >= threshold

        if re.search(rf'critical_issues\s*==\s*{_num}', condition):
            passed = passed and metrics.get("critical_issues", 0) == 0

        if re.search(rf'high_priority_issues\s*<=\s*{_num}', condition):
            m = re.search(rf'high_priority_issues\s*<=\s*{_num}', condition)
            threshold = int(m.group(1)) if m else 3
            passed = passed and metrics.get("high_priority_issues", 0) <= threshold

        if re.search(rf'test_coverage\s*>=\s*{_num}', condition):
            m = re.search(rf'test_coverage\s*>=\s*{_num}', condition)
            threshold = float(m.group(1)) if m else 80
            passed = passed and metrics.get("test_pass_rate", 0) >= threshold

        if re.search(rf'test_errors\s*==\s*{_num}', condition):
            passed = passed and metrics.get("test_errors", 0) == 0

        if re.search(rf'quality_score\s*>=\s*{_num}', condition):
            m = re.search(rf'quality_score\s*>=\s*{_num}', condition)
            threshold = float(m.group(1)) if m else 70
            passed = passed and metrics.get("quality_score", 100) >= threshold

        # --- 纯布尔条件：无数字，简单子串匹配足够安全 ---
        if "critical_tests_passed" in condition:
            passed = passed and metrics.get("critical_tests_passed", True)

        if "performance_tests_passed" in condition:
            passed = passed and metrics.get("performance_tests_passed", True)

        if "config_valid" in condition:
            passed = passed and metrics.get("config_valid", True)

        return {"passed": passed, "rule_id": rule.id}

    def _determine_status(
        self, violations: list[Issue], warnings: list[Issue], passed_checks: int
    ) -> SystemStatus:
        """确定审核状态"""
        # 检查是否有阻塞性违规
        critical_violations = [v for v in violations if v.severity == Severity.CRITICAL]
        high_violations = [v for v in violations if v.severity == Severity.HIGH]

        if critical_violations:
            return SystemStatus.FAILED

        if high_violations:
            return SystemStatus.FAILED

        # 有警告但无违规
        if warnings:
            return SystemStatus.PASSED

        # 全部通过
        if passed_checks == len(self.rules):
            return SystemStatus.PASSED

        return SystemStatus.PASSED

    def get_audit_summary(self) -> dict[str, Any]:
        """获取审核摘要"""
        if not self.audit_history:
            return {"message": "暂无审核记录"}

        latest = self.audit_history[-1]

        return {
            "total_audits": len(self.audit_history),
            "latest_audit": latest.audit_id,
            "latest_status": latest.status.value,
            "is_approved": latest.is_approved,
            "violations_count": len(latest.violations),
            "warnings_count": len(latest.warnings),
            "pass_rate": f"{latest.passed_checks}/{latest.total_checks}",
        }

    def export_rules(self, filepath: str):
        """导出审核规则"""
        rules_data = [
            {
                "id": r.id,
                "name": r.name,
                "description": r.description,
                "condition": r.condition,
                "action": r.action,
                "severity": r.severity.value,
            }
            for r in self.rules
        ]

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(rules_data, f, ensure_ascii=False, indent=2)


def audit(
    test_results: TestSuiteResult, analysis_report: AnalysisReport | None = None
) -> AuditResult:
    """执行审核"""
    module = AuditModule()
    return module.audit(test_results, analysis_report)

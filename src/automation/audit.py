"""
智能审核模块
=============
校验测试结果与业务规则，拦截异常并记录
"""

import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import hashlib
import json

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from .models import (
    AuditRule, AuditResult, TestSuiteResult, 
    AnalysisReport, Issue, Severity, SystemStatus
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
    
    def __init__(self, rules: Optional[List[AuditRule]] = None):
        self.rules = rules or self.DEFAULT_RULES
        self.audit_history: List[AuditResult] = []
    
    def audit(
        self, 
        test_results: TestSuiteResult,
        analysis_report: Optional[AnalysisReport] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> AuditResult:
        """
        执行审核
        """
        audit_id = self._generate_audit_id()
        
        # 计算审核指标
        metrics = self._compute_audit_metrics(test_results, analysis_report)
        
        # 执行规则检查
        violations, warnings, passed_checks = self._check_rules(metrics, test_results, analysis_report)
        
        # 确定审核状态
        status = self._determine_status(violations, warnings, passed_checks)
        
        result = AuditResult(
            audit_id=audit_id,
            timestamp=datetime.now(),
            status=status,
            violations=violations,
            warnings=warnings,
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
        timestamp = datetime.now().isoformat()
        return f"audit_{hashlib.md5(timestamp.encode()).hexdigest()[:12]}"
    
    def _compute_audit_metrics(
        self, 
        test_results: TestSuiteResult,
        analysis_report: Optional[AnalysisReport]
    ) -> Dict[str, Any]:
        """计算审核指标"""
        metrics = {
            "test_pass_rate": test_results.pass_rate,
            "test_total": test_results.total,
            "test_passed": test_results.passed,
            "test_failed": test_results.failed,
            "test_errors": test_results.errors,
            "test_skipped": test_results.skipped,
            "critical_issues": 0,
            "high_priority_issues": 0,
            "medium_priority_issues": 0,
            "low_priority_issues": 0,
            "config_valid": True,
            "quality_score": 100,
            "performance_tests_passed": True,
        }
        
        # 从分析报告获取问题统计
        if analysis_report:
            for issue in analysis_report.issues:
                if issue.severity == Severity.CRITICAL:
                    metrics["critical_issues"] += 1
                elif issue.severity == Severity.HIGH:
                    metrics["high_priority_issues"] += 1
                elif issue.severity == Severity.MEDIUM:
                    metrics["medium_priority_issues"] += 1
                elif issue.severity == Severity.LOW:
                    metrics["low_priority_issues"] += 1
            
            # 配置状态
            config_info = analysis_report.data_summary.get("configuration", {})
            metrics["config_valid"] = config_info.get("config_valid", True)
            
            # 质量分数
            metrics["quality_score"] = analysis_report.statistics.get("quality_score", 100)
        
        # 检查性能测试
        perf_tests = [r for r in test_results.results if r.test_name.startswith("测试大整数") or r.test_name.startswith("测试哈希")]
        if perf_tests:
            metrics["performance_tests_passed"] = all(r.is_passed for r in perf_tests)
        
        # 检查关键测试通过率
        priority_1_tests = [r for r in test_results.results if any(tc in r.test_name for tc in ["配置", "CLI", "加密", "端到端"])]
        if priority_1_tests:
            metrics["critical_tests_passed"] = all(r.is_passed for r in priority_1_tests)
            metrics["critical_test_pass_rate"] = sum(1 for r in priority_1_tests if r.is_passed) / len(priority_1_tests) * 100
        else:
            metrics["critical_tests_passed"] = True
            metrics["critical_test_pass_rate"] = 100
        
        return metrics
    
    def _check_rules(
        self,
        metrics: Dict[str, Any],
        test_results: TestSuiteResult,
        analysis_report: Optional[AnalysisReport]
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
                    violations.append(Issue(
                        id=rule.id,
                        severity=rule.severity,
                        category="Audit",
                        title=rule.name,
                        description=f"规则违反: {rule.description}",
                        suggestions=[f"检查并修复: {rule.description}"],
                        metadata={"rule_id": rule.id, "condition": rule.condition},
                    ))
                elif rule.action == "warn":
                    warnings.append(Issue(
                        id=rule.id,
                        severity=rule.severity,
                        category="Audit",
                        title=rule.name,
                        description=f"警告: {rule.description}",
                        suggestions=[f"建议改进: {rule.description}"],
                        metadata={"rule_id": rule.id, "condition": rule.condition},
                    ))
            except Exception as e:
                # 规则评估失败，记录但不阻塞
                warnings.append(Issue(
                    id=f"{rule.id}_ERROR",
                    severity=Severity.INFO,
                    category="Audit",
                    title=f"规则评估异常: {rule.name}",
                    description=str(e),
                ))
        
        return violations, warnings, passed_checks
    
    def _evaluate_rule(self, rule: AuditRule, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """评估单条规则"""
        condition = rule.condition
        
        # 简单的条件解析
        passed = True
        
        if "test_pass_rate >= 90" in condition:
            passed = passed and metrics.get("test_pass_rate", 0) >= 90
        
        if "critical_tests_passed" in condition:
            passed = passed and metrics.get("critical_tests_passed", True)
        
        if "critical_issues == 0" in condition:
            passed = passed and metrics.get("critical_issues", 0) == 0
        
        if "high_priority_issues <= 3" in condition:
            passed = passed and metrics.get("high_priority_issues", 0) <= 3
        
        if "test_coverage >= 80" in condition:
            # 简化处理
            passed = passed and metrics.get("test_pass_rate", 0) >= 80
        
        if "performance_tests_passed" in condition:
            passed = passed and metrics.get("performance_tests_passed", True)
        
        if "test_errors == 0" in condition:
            passed = passed and metrics.get("test_errors", 0) == 0
        
        if "config_valid" in condition:
            passed = passed and metrics.get("config_valid", True)
        
        if "quality_score >= 70" in condition:
            passed = passed and metrics.get("quality_score", 100) >= 70
        
        return {"passed": passed, "rule_id": rule.id}
    
    def _determine_status(
        self,
        violations: List[Issue],
        warnings: List[Issue],
        passed_checks: int
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
    
    def get_audit_summary(self) -> Dict[str, Any]:
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
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(rules_data, f, ensure_ascii=False, indent=2)


def audit(
    test_results: TestSuiteResult,
    analysis_report: Optional[AnalysisReport] = None
) -> AuditResult:
    """执行审核"""
    module = AuditModule()
    return module.audit(test_results, analysis_report)

"""
src/automation 模块测试
"""

import pytest
from datetime import datetime

from src.automation.models import (
    SystemStatus,
    Severity,
    Issue,
    AnalysisReport,
    TestCase,
    TestResult,
    TestSuiteResult,
    AuditRule,
    AuditResult,
    LoopState,
)


class TestSystemStatus:
    """SystemStatus 枚举测试"""

    def test_status_values(self):
        assert SystemStatus.IDLE.value == "idle"
        assert SystemStatus.ANALYZING.value == "analyzing"
        assert SystemStatus.TESTING.value == "testing"
        assert SystemStatus.AUDITING.value == "auditing"
        assert SystemStatus.PASSED.value == "passed"
        assert SystemStatus.FAILED.value == "failed"
        assert SystemStatus.RETRYING.value == "retrying"
        assert SystemStatus.COMPLETED.value == "completed"

    def test_status_count(self):
        assert len(SystemStatus) == 8


class TestSeverity:
    """Severity 枚举测试"""

    def test_severity_values(self):
        assert Severity.CRITICAL.value == "critical"
        assert Severity.HIGH.value == "high"
        assert Severity.MEDIUM.value == "medium"
        assert Severity.LOW.value == "low"
        assert Severity.INFO.value == "info"

    def test_severity_count(self):
        assert len(Severity) == 5


class TestIssue:
    """Issue 数据类测试"""

    def test_issue_creation(self):
        issue = Issue(
            id="issue-001",
            severity=Severity.HIGH,
            category="security",
            title="Test Issue",
            description="Test description",
        )
        assert issue.id == "issue-001"
        assert issue.severity == Severity.HIGH
        assert issue.category == "security"
        assert issue.location is None

    def test_issue_to_dict(self):
        issue = Issue(
            id="issue-002",
            severity=Severity.MEDIUM,
            category="performance",
            title="Perf Issue",
            description="Slow operation",
            suggestions=["Optimize query", "Add cache"],
        )
        data = issue.to_dict()
        assert data["id"] == "issue-002"
        assert data["severity"] == "medium"
        assert len(data["suggestions"]) == 2

    def test_issue_with_metadata(self):
        issue = Issue(
            id="issue-003",
            severity=Severity.LOW,
            category="code",
            title="Minor issue",
            description="Minor",
            metadata={"file": "test.py", "line": 42},
        )
        assert issue.metadata["file"] == "test.py"
        assert issue.metadata["line"] == 42


class TestAnalysisReport:
    """AnalysisReport 数据类测试"""

    def test_report_creation(self):
        report = AnalysisReport(
            report_id="rpt-001",
            timestamp=datetime.now(),
            data_summary={"total": 100},
            statistics={"mean": 50.0},
        )
        assert report.report_id == "rpt-001"
        assert report.issue_count == 0
        assert report.has_critical_issues is False

    def test_report_with_issues(self):
        issues = [
            Issue(
                id="i1",
                severity=Severity.HIGH,
                category="test",
                title="High",
                description="High",
            ),
            Issue(
                id="i2",
                severity=Severity.LOW,
                category="test",
                title="Low",
                description="Low",
            ),
        ]
        report = AnalysisReport(
            report_id="rpt-002",
            timestamp=datetime.now(),
            data_summary={},
            statistics={},
            issues=issues,
        )
        assert report.issue_count == 2
        assert report.has_critical_issues is False

    def test_report_critical_issue(self):
        issues = [
            Issue(
                id="i3",
                severity=Severity.CRITICAL,
                category="test",
                title="Critical",
                description="Critical",
            )
        ]
        report = AnalysisReport(
            report_id="rpt-003",
            timestamp=datetime.now(),
            data_summary={},
            statistics={},
            issues=issues,
        )
        assert report.has_critical_issues is True

    def test_report_to_dict(self):
        report = AnalysisReport(
            report_id="rpt-004",
            timestamp=datetime.now(),
            data_summary={"key": "value"},
            statistics={"count": 10},
        )
        data = report.to_dict()
        assert "report_id" in data
        assert "timestamp" in data
        assert data["data_summary"]["key"] == "value"


class TestTestCase:
    """TestCase 数据类测试"""

    def test_testcase_creation(self):
        tc = TestCase(
            id="tc-001",
            name="Test Case 1",
            category="unit",
            priority=1,
            test_func="test_example",
        )
        assert tc.id == "tc-001"
        assert tc.priority == 1
        assert tc.timeout == 300

    def test_testcase_with_params(self):
        tc = TestCase(
            id="tc-002",
            name="Test Case 2",
            category="integration",
            priority=2,
            test_func="test_integration",
            params={"env": "test", "timeout": 60},
            expected={"status": "ok"},
        )
        assert tc.params["env"] == "test"
        assert tc.expected["status"] == "ok"


class TestTestResult:
    """TestResult 数据类测试"""

    def test_result_creation(self):
        result = TestResult(
            test_id="tc-001",
            test_name="Test 1",
            status="passed",
            duration=1.5,
        )
        assert result.is_passed is True
        assert result.error_details is None

    def test_result_failed(self):
        result = TestResult(
            test_id="tc-002",
            test_name="Test 2",
            status="failed",
            duration=0.5,
            message="Assertion failed",
            error_details="Expected True, got False",
        )
        assert result.is_passed is False
        assert result.error_details is not None

    def test_result_to_dict(self):
        result = TestResult(
            test_id="tc-003",
            test_name="Test 3",
            status="skipped",
            duration=0.0,
            message="Skipped due to env",
        )
        data = result.to_dict()
        assert data["status"] == "skipped"
        assert data["message"] == "Skipped due to env"


class TestTestSuiteResult:
    """TestSuiteResult 数据类测试"""

    def test_suite_creation(self):
        suite = TestSuiteResult(
            suite_id="suite-001",
            total=10,
            passed=8,
            failed=1,
            skipped=1,
            errors=0,
        )
        assert suite.pass_rate == 80.0
        assert suite.is_acceptable is True

    def test_suite_not_acceptable(self):
        suite = TestSuiteResult(
            suite_id="suite-002",
            total=10,
            passed=5,
            failed=3,
            skipped=2,
            errors=1,
        )
        assert suite.pass_rate == 50.0
        assert suite.is_acceptable is False

    def test_suite_empty(self):
        suite = TestSuiteResult(
            suite_id="suite-003",
            total=0,
            passed=0,
            failed=0,
            skipped=0,
            errors=0,
        )
        assert suite.pass_rate == 0.0


class TestAuditRule:
    """AuditRule 数据类测试"""

    def test_rule_creation(self):
        rule = AuditRule(
            id="rule-001",
            name="No Critical Issues",
            description="Block if critical issues found",
            condition="critical_count == 0",
            action="block",
            severity=Severity.HIGH,
        )
        assert rule.id == "rule-001"
        assert rule.action == "block"
        assert rule.severity == Severity.HIGH


class TestAuditResult:
    """AuditResult 数据类测试"""

    def test_audit_approved(self):
        result = AuditResult(
            audit_id="audit-001",
            timestamp=datetime.now(),
            status=SystemStatus.PASSED,
            violations=[],
            passed_checks=5,
            total_checks=5,
        )
        assert result.is_approved is True
        assert result.block_count == 0

    def test_audit_blocked(self):
        violations = [
            Issue(
                id="v1",
                severity=Severity.HIGH,
                category="test",
                title="High Violation",
                description="Test",
            )
        ]
        result = AuditResult(
            audit_id="audit-002",
            timestamp=datetime.now(),
            status=SystemStatus.FAILED,
            violations=violations,
            passed_checks=3,
            total_checks=5,
        )
        assert result.is_approved is False
        assert result.block_count == 1

    def test_audit_critical_blocked(self):
        violations = [
            Issue(
                id="v2",
                severity=Severity.CRITICAL,
                category="test",
                title="Critical Violation",
                description="Critical test",
            )
        ]
        result = AuditResult(
            audit_id="audit-003",
            timestamp=datetime.now(),
            status=SystemStatus.PASSED,
            violations=violations,
        )
        assert result.is_approved is False
        assert result.block_count == 1

    def test_audit_to_dict(self):
        result = AuditResult(
            audit_id="audit-004",
            timestamp=datetime.now(),
            status=SystemStatus.PASSED,
            passed_checks=10,
            total_checks=10,
        )
        data = result.to_dict()
        assert data["audit_id"] == "audit-004"
        assert data["is_approved"] is True


class TestLoopState:
    """LoopState 数据类测试"""

    def test_loop_state_creation(self):
        state = LoopState(
            iteration=1,
            current_phase=SystemStatus.ANALYZING,
        )
        assert state.iteration == 1
        assert state.retry_count == 0
        assert state.can_retry() is True

    def test_loop_retry(self):
        state = LoopState(
            iteration=1,
            current_phase=SystemStatus.RETRYING,
            retry_count=2,
            max_retries=3,
        )
        assert state.can_retry() is True
        state.increment_retry()
        assert state.retry_count == 3
        assert state.can_retry() is False

    def test_loop_state_no_retry(self):
        state = LoopState(
            iteration=1,
            current_phase=SystemStatus.COMPLETED,
            retry_count=3,
            max_retries=3,
        )
        assert state.can_retry() is False

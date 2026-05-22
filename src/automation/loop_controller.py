"""
闭环控制器
==========
协调各模块，异常自动触发反馈回路，形成严格的闭环管控
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import threading  # noqa: E402
from collections.abc import Callable  # noqa: E402
from datetime import datetime  # noqa: E402
from typing import Any  # noqa: E402

from .audit import AuditModule  # noqa: E402
from .auto_test import AutoTestModule  # noqa: E402
from .data_analysis import DataAnalysisModule  # noqa: E402
from .models import (  # noqa: E402
    AnalysisReport, AuditResult, LoopState, Severity, SystemStatus, TestSuiteResult,
)


class LoopController:
    """
    闭环控制器
    协调分析->测试->审核的完整流程
    异常自动触发反馈回路

    v4.3.1: 阶段失败不再硬中断整个循环，而是继续下一轮迭代。
    """

    def __init__(
        self,
        project_root: Path | None = None,
        max_iterations: int = 3,
        auto_fix: bool = False,
    ):
        self.project_root = project_root or Path(__file__).parent.parent.parent.parent

        self.analysis_module = DataAnalysisModule(self.project_root)
        self.test_module = AutoTestModule(self.project_root)
        self.audit_module = AuditModule()

        self.max_iterations = max_iterations
        self.auto_fix = auto_fix

        self.state = LoopState(
            iteration=0,
            current_phase=SystemStatus.IDLE,
        )

        self.on_phase_change: Callable | None = None
        self.on_issue_found: Callable | None = None
        self.on_audit_complete: Callable | None = None

        self._lock = threading.Lock()

        self.total_iterations = 0
        self.start_time: datetime | None = None
        self.end_time: datetime | None = None

        # v4.3.1: 阶段失败计数
        self._phase_failures: dict[str, int] = {"analysis": 0, "test": 0, "audit": 0}

    def run(self) -> AuditResult:
        """
        执行完整的闭环流程
        分析 -> 测试 -> 审核 -> (异常则反馈回路)

        v4.3.1: 阶段失败不再硬中断，而是重试下一轮迭代。
        """
        self.start_time = datetime.now()
        self.state = LoopState(
            iteration=0,
            current_phase=SystemStatus.ANALYZING,
        )

        final_audit_result = None

        while self.state.iteration < self.max_iterations:
            self.state.iteration += 1
            self.total_iterations += 1

            print(f"\n{'=' * 60}")
            print(f">> Loop Iteration #{self.state.iteration}/{self.max_iterations}")
            print(f"{'=' * 60}")

            try:
                # 阶段1: 数据分析
                self._set_phase(SystemStatus.ANALYZING)
                analysis_report = self._run_analysis_phase()

                if analysis_report is None:
                    print("[FAIL] Analysis phase failed, retrying...")
                    self._phase_failures["analysis"] += 1
                    self.state.increment_retry()
                    continue

                self.state.analysis_report = analysis_report
                self.state.issues_found.extend(analysis_report.issues)

                # 阶段2: 自动化测试
                self._set_phase(SystemStatus.TESTING)
                test_results = self._run_test_phase(analysis_report)

                if test_results is None:
                    print("[FAIL] Test phase failed, retrying...")
                    self._phase_failures["test"] += 1
                    self.state.increment_retry()
                    continue

                self.state.test_results = test_results

                # 阶段3: 智能审核
                self._set_phase(SystemStatus.AUDITING)
                audit_result = self._run_audit_phase(test_results, analysis_report)

                if audit_result is None:
                    print("[FAIL] Audit phase failed, retrying...")
                    self._phase_failures["audit"] += 1
                    self.state.increment_retry()
                    continue

                self.state.audit_results.append(audit_result)
                final_audit_result = audit_result

                # 检查审核结果
                if audit_result.is_approved:
                    print("\n[PASS] Audit passed!")
                    self._set_phase(SystemStatus.PASSED)
                    break
                else:
                    block_count = audit_result.block_count
                    print(f"\n[WARN] Audit rejected ({block_count} blocking issues)")

                    if self.on_audit_complete:
                        self.on_audit_complete(audit_result)

                    if not self.state.can_retry():
                        print(f"[FAIL] Max retries reached ({self.max_iterations})")
                        self._set_phase(SystemStatus.FAILED)
                        break

                    self.state.increment_retry()
                    self._set_phase(SystemStatus.RETRYING)
                    self._execute_feedback_loop(audit_result)

            except Exception as e:
                print(f"[ERROR] Loop execution error: {str(e)}")
                self.state.current_phase = SystemStatus.FAILED
                break

        self.end_time = datetime.now()
        self._set_phase(SystemStatus.COMPLETED)

        return final_audit_result or self._create_failed_result()

    def _run_analysis_phase(self) -> AnalysisReport | None:
        """执行分析阶段"""
        print("\n[Phase 1] Data Analysis Module")
        print("-" * 40)

        try:
            report = self.analysis_module.analyze()

            print(f"   Report ID: {report.report_id}")
            print(f"   Issues found: {report.issue_count}")
            print(f"   Quality score: {report.statistics.get('quality_score', 'N/A')}")

            if report.issues:
                print("\n   Issue summary:")
                for issue in report.issues[:5]:
                    sev_icon = {
                        Severity.CRITICAL: "[CRITICAL]",
                        Severity.HIGH: "[HIGH]",
                        Severity.MEDIUM: "[MEDIUM]",
                        Severity.LOW: "[LOW]",
                        Severity.INFO: "[INFO]",
                    }.get(issue.severity, "[INFO]")
                    print(f"      {sev_icon} {issue.title}")

            if self.on_issue_found:
                for issue in report.issues:
                    self.on_issue_found(issue)

            return report

        except Exception as e:
            print(f"   [ERROR] Analysis failed: {str(e)}")
            return None

    def _run_test_phase(self, analysis_report: AnalysisReport) -> TestSuiteResult | None:
        """执行测试阶段"""
        print("\n[Phase 2] Auto Test Module")
        print("-" * 40)

        try:
            results = self.test_module.run_all_tests(analysis_report)

            print(f"   Test suite: {results.suite_id}")
            print(f"   Total: {results.total}")
            print(
                f"   Passed: {results.passed} | Failed: {results.failed} "
                f"| Skipped: {results.skipped} | Errors: {results.errors}"
            )
            print(f"   Pass rate: {results.pass_rate:.1f}%")
            print(f"   Duration: {results.duration:.2f}s")

            if results.failed > 0 or results.errors > 0:
                print("\n   Failed/Error tests:")
                for result in results.results:
                    if result.status in ("failed", "error"):
                        status_mark = "[X]" if result.status == "failed" else "[!]"
                        print(f"      {status_mark} {result.test_name}: {result.message[:50]}")

            return results

        except Exception as e:
            print(f"   [ERROR] Test failed: {str(e)}")
            return None

    def _run_audit_phase(
        self, test_results: TestSuiteResult, analysis_report: AnalysisReport
    ) -> AuditResult | None:
        """执行审核阶段"""
        print("\n[Phase 3] Audit Module")
        print("-" * 40)

        try:
            result = self.audit_module.audit(test_results, analysis_report)

            print(f"   Audit ID: {result.audit_id}")
            print(f"   Status: {result.status.value}")
            print(f"   Checks: {result.passed_checks}/{result.total_checks}")

            if result.violations:
                print(f"\n   Blocking violations ({len(result.violations)}):")
                for v in result.violations:
                    print(f"      - {v.title}")

            if result.warnings:
                print(f"\n   Warnings ({len(result.warnings)}):")
                for w in result.warnings[:3]:
                    print(f"      - {w.title}")

            verdict = "PASS" if result.is_approved else "REJECT"
            print(f"\n   Verdict: {verdict}")

            return result

        except Exception as e:
            print(f"   [ERROR] Audit failed: {str(e)}")
            return None

    def _execute_feedback_loop(self, audit_result: AuditResult):
        """执行反馈回路"""
        print("\n[Feedback Loop] Preparing re-analysis...")

        all_issues = list(self.state.issues_found)
        all_issues.extend(audit_result.violations)
        all_issues.extend(audit_result.warnings)

        seen_ids = set()
        unique_issues = []
        for issue in all_issues:
            if issue.id not in seen_ids:
                seen_ids.add(issue.id)
                unique_issues.append(issue)

        self.state.issues_found = unique_issues
        print(f"   Total issues: {len(unique_issues)}")

        if self.on_issue_found:
            for violation in audit_result.violations:
                self.on_issue_found(violation)

    def _set_phase(self, phase: SystemStatus):
        """设置当前阶段"""
        with self._lock:
            self.state.previous_phase = self.state.current_phase
            self.state.current_phase = phase

        if self.on_phase_change:
            self.on_phase_change(phase)

    def _create_failed_result(self) -> AuditResult:
        """创建失败结果"""
        return AuditResult(
            audit_id="failed",
            timestamp=datetime.now(),
            status=SystemStatus.FAILED,
            violations=[],
            warnings=[],
            passed_checks=0,
            total_checks=0,
        )

    def get_summary(self) -> dict[str, Any]:
        """获取执行摘要"""
        duration = None
        if self.start_time and self.end_time:
            duration = (self.end_time - self.start_time).total_seconds()

        return {
            "total_iterations": self.total_iterations,
            "final_status": self.state.current_phase.value,
            "issues_found": len(self.state.issues_found),
            "audits_performed": len(self.state.audit_results),
            "duration_seconds": duration,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "phase_failures": dict(self._phase_failures),
        }

    def save_report(self, filepath: str):
        """保存完整报告"""
        summary = self.get_summary()

        report = {
            "summary": summary,
            "final_audit": (
                self.state.audit_results[-1].to_dict() if self.state.audit_results else None
            ),
            "all_issues": [i.to_dict() for i in self.state.issues_found],
            "iterations": self.total_iterations,
        }

        from src.utils.fast_json import fast_dump

        with open(filepath, "w", encoding="utf-8") as f:
            fast_dump(report, f, ensure_ascii=False, indent=2)


def run_automation_loop(
    project_root: Path | None = None,
    max_iterations: int = 3,
) -> AuditResult:
    """便捷函数: 运行自动化闭环"""
    controller = LoopController(project_root, max_iterations)
    return controller.run()

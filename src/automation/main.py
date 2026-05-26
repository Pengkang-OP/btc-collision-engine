"""端到端自动化闭环管理系统 - 主入口
提供命令行接口和API接口
"""

import argparse
import os
import sys
from pathlib import Path
from typing import cast

from . import (
    AnalysisReport,
    AuditModule,
    AuditResult,
    AutoTestModule,
    DataAnalysisModule,
    LoopController,
    TestSuiteResult,
)

_project_root = Path(__file__).resolve().parent.parent.parent

# v5.2.2: 将 chdir 延迟到 main() 函数内执行，避免模块级副作用
_os_chdir_done = False


def _ensure_cwd() -> None:
    """确保工作目录为项目根目录（延迟执行）。"""
    global _os_chdir_done
    if not _os_chdir_done:
        os.chdir(str(_project_root))
        _os_chdir_done = True


# 导入延迟到 main() 函数内执行，避免模块级副作用


def print_banner() -> None:
    banner = """
=================================================================
       End-to-End Automation Loop Control System v5.0.0
=================================================================
  Modules:
  1. Data Analysis Module
  2. Auto Test Module
  3. Audit Module
  4. Loop Controller
=================================================================
    """
    print(banner)


def run_analysis_only(args: argparse.Namespace) -> "AnalysisReport":
    project_root: str | None = cast(str | None, args.project_root)
    output: str | None = cast(str | None, args.output)

    print("\n[1/4] 运行数据分析模块...")
    module = DataAnalysisModule(Path(project_root) if project_root else None)
    report = module.analyze()

    print(f"   报告ID: {report.report_id}")
    print(f"   质量分数: {report.statistics.get('quality_score', 'N/A')}")
    print(f"   发现问题: {report.issue_count} 个")

    if output:
        report.save(output)
        print(f"   已保存到: {output}")

    return report


def run_tests_only(args: argparse.Namespace) -> "TestSuiteResult":
    project_root: str | None = cast(str | None, args.project_root)
    output: str | None = cast(str | None, args.output)

    print("\n[2/4] 运行自动化测试模块...")
    module = AutoTestModule(Path(project_root) if project_root else None)
    results = module.run_all_tests()

    print(f"   测试套件: {results.suite_id}")
    print(f"   通过率: {results.pass_rate:.1f}%")
    print(f"   通过: {results.passed} | 失败: {results.failed}")

    if output:
        import json

        with Path(output).open("w") as f:
            json.dump(
                {
                    "suite_id": results.suite_id,
                    "total": results.total,
                    "passed": results.passed,
                    "failed": results.failed,
                    "pass_rate": results.pass_rate,
                },
                f,
                indent=2,
            )
        print(f"   已保存到: {output}")

    return results


def run_audit_only(args: argparse.Namespace) -> "AuditResult":
    project_root: str | None = cast(str | None, args.project_root)
    output: str | None = cast(str | None, args.output)

    print("\n[3/4] 运行智能审核模块...")

    analysis_module = DataAnalysisModule(Path(project_root) if project_root else None)
    test_module = AutoTestModule(Path(project_root) if project_root else None)
    audit_module = AuditModule()

    analysis_report = analysis_module.analyze()
    test_results = test_module.run_all_tests(analysis_report)
    audit_result = audit_module.audit(test_results, analysis_report)

    print(f"   审核ID: {audit_result.audit_id}")
    print(f"   状态: {'通过' if audit_result.is_approved else '拒绝'}")

    if output:
        audit_result.save(output)
        print(f"   已保存到: {output}")

    return audit_result


def run_full_loop(args: argparse.Namespace) -> "AuditResult":
    project_root: str | None = cast(str | None, args.project_root)
    output: str | None = cast(str | None, args.output)
    max_iterations: int = cast(int, args.max_iterations)
    auto_fix: bool = cast(bool, args.auto_fix)

    print_banner()
    print("\n启动端到端自动化闭环系统...")
    print(f"最大迭代次数: {max_iterations}")

    controller = LoopController(
        project_root=Path(project_root) if project_root else None,
        max_iterations=max_iterations,
        auto_fix=auto_fix,
    )

    result = controller.run()

    print("\n" + "=" * 60)
    print("执行摘要")
    print("=" * 60)
    summary = controller.get_summary()
    for key, value in summary.items():
        print(f"  {key}: {value}")

    if output:
        controller.save_report(output)
        print(f"\n完整报告已保存到: {output}")

    return result


def main() -> None:

    parser = argparse.ArgumentParser(description="端到端自动化闭环管理系统")

    _ = parser.add_argument("--project-root", "-p", type=str, default=None)

    _ensure_cwd()

    mode_group = parser.add_mutually_exclusive_group()
    _ = mode_group.add_argument("--full", "-f", action="store_true", help="运行完整闭环")
    _ = mode_group.add_argument("--analyze", "-a", action="store_true", help="仅运行分析")
    _ = mode_group.add_argument("--test", "--test-only", action="store_true", help="仅运行测试")
    _ = mode_group.add_argument("--audit", "-u", action="store_true", help="仅运行审核")

    _ = parser.add_argument("--max-iterations", "-m", type=int, default=3)
    _ = parser.add_argument("--auto-fix", action="store_true")
    _ = parser.add_argument("--output", "-o", type=str, default=None)
    _ = parser.add_argument("--verbose", "-v", action="store_true")

    args = parser.parse_args()

    full: bool = cast(bool, args.full)
    analyze: bool = cast(bool, args.analyze)
    test: bool = cast(bool, args.test)
    audit: bool = cast(bool, args.audit)
    verbose: bool = cast(bool, args.verbose)

    if not any([full, analyze, test, audit]):
        args.full = True
        full = True

    try:
        if analyze:
            _ = run_analysis_only(args)
        elif test:
            _ = run_tests_only(args)
        elif audit:
            _ = run_audit_only(args)
        elif full:
            result = run_full_loop(args)
            sys.exit(0 if result.is_approved else 1)
    except KeyboardInterrupt:
        print("\n\n用户中断执行")
        sys.exit(130)
    except Exception as e:
        print(f"\n执行错误: {e!s}")
        if verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

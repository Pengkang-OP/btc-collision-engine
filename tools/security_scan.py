#!/usr/bin/env python3
"""自动化安全扫描工具.

使用bandit扫描代码中的安全问题,生成报告并检查是否通过安全门禁。

使用方法:
    # 扫描所有源代码
    python tools/security_scan.py

    # 生成HTML报告
    python tools/security_scan.py --format html --output security_report.html

    # 仅扫描高严重性问题
    python tools/security_scan.py --severity high

    # CI/CD模式(失败时退出码非0)
    python tools/security_scan.py --ci-mode
"""

import json
import subprocess
import sys
from pathlib import Path


def run_bandit_scan(severity="medium", format_type="json"):
    """运行bandit安全扫描."""
    cmd = [
        sys.executable,
        "-m",
        "bandit",
        "-r",
        "src/",
        "-f",
        format_type,
        "-ll",  # 仅显示medium和high
    ]

    if severity == "high":
        cmd.append("-lll")  # 仅显示high

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return result
    except subprocess.TimeoutExpired:
        print("❌ 扫描超时(60秒)")
        return None
    except Exception as e:
        print(f"❌ 扫描失败: {e}")
        return None


def parse_json_report(json_file="bandit_report.json"):
    """解析JSON格式的安全报告."""
    report_path = Path(json_file)
    if not report_path.exists():
        return None

    try:
        with open(report_path, encoding="utf-8") as f:
            data = json.load(f)

        return data
    except Exception as e:
        print(f"❌ 解析报告失败: {e}")
        return None


def print_summary(report):
    """打印安全扫描总结."""
    if not report:
        print("❌ 无报告数据")
        return

    issues = report.get("results", [])  # bandit使用results而非issues

    print("\n" + "=" * 80)
    print("🔒 安全扫描报告总结")
    print("=" * 80)

    # 统计问题
    severity_counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for issue in issues:
        severity = issue.get("issue_severity", "LOW")
        if severity in severity_counts:
            severity_counts[severity] += 1

    metrics = report.get("metrics", {})
    print("\n📊 扫描统计:")
    print(f"   扫描文件数: {len(metrics) - 1}")  # 减去_totals
    print(f"   发现问题数: {len(issues)}")

    print("\n🚨 问题统计:")
    print(f"   高危(High): {severity_counts['HIGH']}")
    print(f"   中危(Medium): {severity_counts['MEDIUM']}")
    print(f"   低危(Low): {severity_counts['LOW']}")

    total_issues = len(issues)
    print(f"   总计: {total_issues}")

    # 显示高危问题详情
    high_issues = [i for i in issues if i.get("issue_severity") == "HIGH"]
    if high_issues:
        print(f"\n⚠️  高危问题详情 ({len(high_issues)}个):")
        for i, issue in enumerate(high_issues[:5], 1):  # 最多显示5个
            print(f"\n  {i}. [{issue.get('test_id')}] {issue.get('issue_text')}")
            print(f"     文件: {issue.get('filename')}:{issue.get('line_number')}")
            print(f"     严重性: {issue.get('issue_severity')}")
            print(f"     置信度: {issue.get('issue_confidence')}")

    # 安全评分
    if severity_counts["HIGH"] == 0 and severity_counts["MEDIUM"] == 0:
        score = "✅ 优秀 (10/10)"
    elif severity_counts["HIGH"] == 0:
        score = "🟡 良好 (7-9/10)"
    else:
        score = "🔴 需要改进 (<7/10)"

    print(f"\n🏆 安全评分: {score}")
    print("=" * 80)


def generate_html_report(report, output_file="security_report.html"):
    """生成HTML格式的安全报告."""
    if not report:
        return

    issues = report.get("results", [])  # bandit 使用 results 而非 issues

    html_content = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>安全扫描报告 - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white;
            padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        h1 {{ color: #333; border-bottom: 3px solid #4CAF50; padding-bottom: 10px; }}
        h2 {{ color: #555; margin-top: 30px; }}
        .summary {{ background: #e8f5e9; padding: 15px; border-radius: 5px; margin: 20px 0; }}
        .issue {{ background: #fff3cd; padding: 15px; margin: 10px 0;
            border-left: 4px solid #ffc107; border-radius: 4px; }}
        .issue.high {{ background: #f8d7da; border-left-color: #dc3545; }}
        .issue.medium {{ background: #fff3cd; border-left-color: #ffc107; }}
        .issue.low {{ background: #d1ecf1; border-left-color: #17a2b8; }}
        .code {{ background: #f8f9fa; padding: 10px; border-radius: 4px;
            font-family: monospace; font-size: 0.9em; overflow-x: auto; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background: #4CAF50; color: white; }}
        .badge {{ display: inline-block; padding: 4px 8px;
            border-radius: 4px; font-size: 0.85em; font-weight: bold; }}
        .badge.high {{ background: #dc3545; color: white; }}
        .badge.medium {{ background: #ffc107; color: #333; }}
        .badge.low {{ background: #17a2b8; color: white; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🔒 安全扫描报告</h1>
        <p><strong>生成时间:</strong> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>

        <div class="summary">
            <h2>📊 扫描统计</h2>
            <table>
                <tr><td>总代码行数</td><td>{metrics.get("_total_lines_of_code", 0):,}</td></tr>
                <tr><td>高危问题</td><td>{metrics.get("_issue_severity", {}).get("HIGH", 0)}</td></tr>
                <tr><td>中危问题</td><td>{metrics.get("_issue_severity", {}).get("MEDIUM", 0)}</td></tr>
                <tr><td>低危问题</td><td>{metrics.get("_issue_severity", {}).get("LOW", 0)}</td></tr>
            </table>
        </div>

        <h2>🚨 问题详情</h2>
"""

    for issue in issues:
        html_content += """
        <div class="issue {severity}">
            <h3>
                <span class="badge {severity}">{issue.get("issue_severity")}</span>
                [{issue.get("test_id")}] {issue.get("issue_text")}
            </h3>
            <p><strong>文件:</strong> {issue.get("filename")}:{issue.get("line_number")}</p>
            <p><strong>置信度:</strong> {issue.get("issue_confidence")}</p>
            <div class="code">{issue.get("code", "")}</div>
        </div>
"""

    html_content += """
    </div>
</body>
</html>"""

    output_path = Path(output_file)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"✅ HTML报告已生成: {output_path}")


def main():
    """主函数."""
    import argparse

    parser = argparse.ArgumentParser(description="自动化安全扫描工具")
    parser.add_argument("--format", choices=["json", "html", "text"], default="json", help="报告格式")
    parser.add_argument("--output", help="报告输出路径")
    parser.add_argument(
        "--severity", choices=["low", "medium", "high"], default="medium", help="最低严重性级别",
    )
    parser.add_argument("--ci-mode", action="store_true", help="CI/CD模式(有高危问题时退出码非0)")

    args = parser.parse_args()

    print("=" * 80)
    print("🔒 BTC碰撞引擎 - 自动化安全扫描")
    print("=" * 80)

    # 运行扫描
    print("\n🔍 正在运行安全扫描...")
    result = run_bandit_scan(args.severity, "json")

    if result is None:
        sys.exit(1)

    # 解析报告
    report = parse_json_report("bandit_report.json")

    if report is None:
        print("❌ 无法解析扫描报告")
        sys.exit(1)

    # 打印总结
    print_summary(report)

    # 生成HTML报告
    if args.format == "html":
        output = args.output or "security_report.html"
        generate_html_report(report, output)

    # CI/CD模式检查
    if args.ci_mode:
        severity_counts = report.get("metrics", {}).get("_issue_severity", {})

        if severity_counts.get("HIGH", 0) > 0:
            print("\n❌ CI/CD检查失败: 发现高危安全问题")
            sys.exit(1)
        else:
            print("\n✅ CI/CD检查通过: 无高危安全问题")
            sys.exit(0)
    else:
        # 普通模式,始终成功退出
        sys.exit(0)


if __name__ == "__main__":
    main()

#!/usr/bin/env python
"""文档质量趋势分析工具.

跟踪和分析文档质量的历史变化趋势

使用方法:
    python tools/quality_trend.py [--history-file quality_history.json]
"""

import json
from datetime import datetime
from pathlib import Path

# 修复Windows控制台编码问题
from utf8_helper import setup_windows_utf8

setup_windows_utf8()

import contextlib  # noqa: E402

from tools.check_document_quality import DocumentQualityChecker  # noqa: E402


class QualityTrendAnalyzer:
    """质量趋势分析器."""

    def __init__(self, history_file: str = "quality_history.json"):
        self.history_file = Path(history_file)
        self._cleanup_temp()  # 清理残留临时文件
        self.history: list[dict] = self.load_history()

    def _cleanup_temp(self):
        """清理残留的临时文件."""
        temp_file = self.history_file.with_suffix(".tmp")
        if temp_file.exists():
            with contextlib.suppress(OSError):
                temp_file.unlink()

    def load_history(self) -> list[dict]:
        """加载历史记录."""
        if self.history_file.exists():
            try:
                with open(self.history_file, encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return data
                    print("⚠️  历史记录格式错误，重置为空列表")
                    return []
            except json.JSONDecodeError as e:
                print(f"⚠️  历史记录JSON解析失败: {e}")
                print("💡 重置为空列表")
                return []
            except (OSError, PermissionError) as e:
                print(f"⚠️  无法读取历史记录: {e}")
                return []
        return []

    def save_history(self):
        """保存历史记录."""
        try:
            # 使用临时文件避免写入中断导致数据损坏
            temp_file = self.history_file.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(self.history, f, indent=2, ensure_ascii=False)
            # 原子替换
            temp_file.replace(self.history_file)
        except (OSError, PermissionError) as e:
            print(f"⚠️  无法保存历史记录: {e}")

    def add_record(self, avg_score: float, doc_count: int, details: dict):
        """添加新记录.

        Args:
            avg_score: 平均评分
            doc_count: 文档数量
            details: 详细信息
        """
        record = {
            "timestamp": datetime.now().isoformat(),
            "avg_score": round(avg_score, 2),
            "doc_count": doc_count,
            "details": details,
        }

        self.history.append(record)
        self.save_history()

    def get_trend(self, last_n: int = 10) -> dict:
        """获取趋势分析.

        Args:
            last_n: 最近N次记录

        Returns:
            趋势分析结果
        """
        if len(self.history) < 2:
            return {"status": "insufficient_data", "message": "数据不足，至少需要2次记录"}

        recent = self.history[-last_n:]

        scores = [r["avg_score"] for r in recent]
        avg_score = sum(scores) / len(scores)
        min_score = min(scores)
        max_score = max(scores)

        # 计算趋势
        if len(scores) >= 2:
            trend = scores[-1] - scores[-2]
            if trend > 0.2:
                trend_status = "improving"
                trend_icon = "📈"
            elif trend < -0.2:
                trend_status = "declining"
                trend_icon = "📉"
            else:
                trend_status = "stable"
                trend_icon = "➡️"
        else:
            trend = 0
            trend_status = "stable"
            trend_icon = "➡️"

        return {
            "status": "success",
            "avg_score": round(avg_score, 2),
            "min_score": round(min_score, 2),
            "max_score": round(max_score, 2),
            "trend": round(trend, 2),
            "trend_status": trend_status,
            "trend_icon": trend_icon,
            "record_count": len(recent),
            "scores": scores,
        }

    def print_trend_report(self):
        """打印趋势报告."""
        trend = self.get_trend()

        print(f"\n{'=' * 60}")
        print("📊 文档质量趋势分析报告")
        print(f"{'=' * 60}")

        if trend["status"] == "insufficient_data":
            print(f"\n⚠️  {trend['message']}")
            print(f"当前记录数: {len(self.history)}")
            print("\n💡 建议: 运行多次质量检查以积累数据")
            print("   python tools/check_document_quality.py")
            return

        print("\n📈 统计信息:")
        print(f"  记录次数: {trend['record_count']}")
        print(f"  平均评分: {trend['avg_score']}/10")
        print(f"  最低评分: {trend['min_score']}/10")
        print(f"  最高评分: {trend['max_score']}/10")

        print(f"\n📊 质量趋势: {trend['trend_icon']} {trend['trend_status'].upper()}")
        print(f"  最近变化: {trend['trend']:+.2f}")

        if trend["trend_status"] == "improving":
            print("  ✅ 文档质量正在提升!")
        elif trend["trend_status"] == "declining":
            print("  ⚠️  文档质量下降，需要关注!")
        else:
            print("  ➡️  文档质量稳定")

        # 评分历史
        print("\n📝 最近评分历史:")
        for i, score in enumerate(trend["scores"][-10:], 1):
            print(f"  {i:2d}. {score}/10")

        print(f"\n{'=' * 60}")

    def export_csv(self, output_file: str = "quality_trend.csv"):
        """导出为CSV格式."""
        if not self.history:
            print("❌ 没有历史数据")
            return

        try:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write("timestamp,avg_score,doc_count\n")
                f.writelines(
                    f"{record['timestamp']},{record['avg_score']},{record['doc_count']}\n"
                    for record in self.history
                )  # noqa: E501

            print(f"✅ 数据已导出到: {output_file}")
        except (OSError, PermissionError) as e:
            print(f"❌ 无法导出CSV: {e}")


def main():
    """主函数."""
    import argparse

    parser = argparse.ArgumentParser(description="文档质量趋势分析工具")
    parser.add_argument("--docs-dir", default="docs", help="文档目录路径 (默认: docs)")
    parser.add_argument(
        "--history-file",
        default="quality_history.json",
        help="历史记录文件 (默认: quality_history.json)",
    )
    parser.add_argument("--check", action="store_true", help="执行质量检查并记录")
    parser.add_argument("--export-csv", default=None, help="导出为CSV文件")

    args = parser.parse_args()

    analyzer = QualityTrendAnalyzer(args.history_file)

    # 执行质量检查
    if args.check:
        print("🔍 执行质量检查...")
        checker = DocumentQualityChecker(args.docs_dir)
        scores = checker.check_all()

        if scores:
            avg_score = sum(s.score for s in scores) / len(scores)

            # 统计详情
            excellent = sum(1 for s in scores if s.score >= 8.5)
            good = sum(1 for s in scores if 7.0 <= s.score < 8.5)
            needs_improvement = sum(1 for s in scores if s.score < 7.0)

            details = {"excellent": excellent, "good": good, "needs_improvement": needs_improvement}

            # 记录
            analyzer.add_record(avg_score, len(scores), details)
            print("\n✅ 质量检查完成，已记录")
            print(f"   平均评分: {avg_score:.1f}/10")
            print(f"   文档数量: {len(scores)}")

    # 打印趋势报告
    analyzer.print_trend_report()

    # 导出CSV
    if args.export_csv:
        analyzer.export_csv(args.export_csv)


if __name__ == "__main__":
    main()

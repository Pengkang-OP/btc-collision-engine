#!/usr/bin/env python
"""
文档质量检查工具

检查项目文档的质量，包括：
- 文档结构完整性
- 版本信息存在性
- 链接有效性
- 代码示例格式
- Markdown语法正确性
- 文件编码和格式

使用方法:
    python tools/check_document_quality.py
"""

import re
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

# 修复Windows控制台编码问题 - 使用共享模块
# 添加工具目录到路径
_tools_dir = Path(__file__).parent
if str(_tools_dir) not in sys.path:
    sys.path.insert(0, str(_tools_dir))
from utf8_helper import setup_windows_utf8

setup_windows_utf8()


class Severity(Enum):
    """问题严重程度"""

    ERROR = "❌"
    WARNING = "⚠️"
    INFO = "ℹ️"
    SUCCESS = "✅"


class IssueType:
    """问题类型常量 - 用于分类统计"""

    CODE_BLOCK = "代码块"
    LINK = "链接"
    TOC = "目录"
    VERSION = "版本"
    HEADING = "标题"
    ENCODING = "编码"
    TABLE = "表格"
    FILE_ENDING = "文件结尾"


@dataclass
class ScoringConfig:
    """评分配置 - 可定制权重"""

    error_weight: float = 1.5
    code_block_weight: float = 0.2
    code_block_max: float = 2.0
    link_weight: float = 0.8
    link_max: float = 3.0
    other_warning_weight: float = 0.3
    info_weight: float = 0.1
    toc_bonus: float = 0.3
    version_bonus: float = 0.2

    def validate(self) -> None:
        """验证配置有效性

        Raises:
            ValueError: 当配置值无效时
        """
        # 权重必须非负
        if self.error_weight < 0:
            raise ValueError(f"error_weight must be >= 0, got {self.error_weight}")
        if self.code_block_weight < 0:
            raise ValueError(f"code_block_weight must be >= 0, got {self.code_block_weight}")
        if self.link_weight < 0:
            raise ValueError(f"link_weight must be >= 0, got {self.link_weight}")
        if self.other_warning_weight < 0:
            raise ValueError(f"other_warning_weight must be >= 0, got {self.other_warning_weight}")
        if self.info_weight < 0:
            raise ValueError(f"info_weight must be >= 0, got {self.info_weight}")

        # 上限必须非负且合理
        if self.code_block_max < 0:
            raise ValueError(f"code_block_max must be >= 0, got {self.code_block_max}")
        if self.link_max < 0:
            raise ValueError(f"link_max must be >= 0, got {self.link_max}")

        # 奖励必须非负
        if self.toc_bonus < 0:
            raise ValueError(f"toc_bonus must be >= 0, got {self.toc_bonus}")
        if self.version_bonus < 0:
            raise ValueError(f"version_bonus must be >= 0, got {self.version_bonus}")

        # 奖励总和不应过高（建议不超过1分）
        total_bonus = self.toc_bonus + self.version_bonus
        if total_bonus > 1.0:
            raise ValueError(f"Total bonus ({total_bonus}) should not exceed 1.0")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScoringConfig":
        """从字典创建配置"""
        config = cls(**{k: v for k, v in data.items() if k in cls.__annotations__})
        config.validate()  # 验证配置
        return config

    @classmethod
    def from_file(cls, path: str) -> "ScoringConfig":
        """从 JSON文件加载配置"""
        import json

        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "error_weight": self.error_weight,
            "code_block_weight": self.code_block_weight,
            "code_block_max": self.code_block_max,
            "link_weight": self.link_weight,
            "link_max": self.link_max,
            "other_warning_weight": self.other_warning_weight,
            "info_weight": self.info_weight,
            "toc_bonus": self.toc_bonus,
            "version_bonus": self.version_bonus,
        }

    def save_to_file(self, path: str):
        """保存配置到JSON文件"""
        import json

        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)


@dataclass
class Issue:
    """文档问题"""

    severity: Severity
    file: str
    line: int
    message: str


@dataclass
class DocumentScore:
    """文档评分"""

    file: str
    score: float
    issues: list[Issue]


class DocumentQualityChecker:
    """文档质量检查器"""

    def __init__(self, docs_dir: str = "docs", config: ScoringConfig | None = None):
        self.docs_dir = Path(docs_dir)
        self.issues: list[Issue] = []
        self.scores: list[DocumentScore] = []
        self.config = config or ScoringConfig()

    @staticmethod
    def get_changed_docs(docs_dir: Path) -> list[Path]:
        """获取Git变更的文档列表

        Returns:
            变更的.md文件列表
        """
        try:
            # 获取git diff中的.md文件
            result = subprocess.run(
                ["git", "diff", "--name-only", "HEAD", "--", str(docs_dir)],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                print(f"⚠️  Git命令执行失败: {result.stderr}")
                return []

            # 解析输出，只保留.md文件
            changed_files = []
            for line in result.stdout.strip().split("\n"):
                if line.endswith(".md"):
                    changed_files.append(Path(line))

            return changed_files

        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            print(f"⚠️  无法获取Git变更: {e}")
            return []

    def check_all(self, changed_only: bool = False) -> list[DocumentScore]:
        """检查所有文档

        Args:
            changed_only: 是否只检查变更的文档
        """
        print("🔍 开始检查文档质量...\n")

        md_files = list(self.docs_dir.glob("*.md"))
        # 排除archive目录中的文件
        md_files = [f for f in md_files if "archive" not in str(f)]

        # 增量检查模式
        if changed_only:
            print("🔄 增量检查模式: 只检查Git变更的文档")
            changed_files = self.get_changed_docs(self.docs_dir)
            if not changed_files:
                print("ℹ️  没有检测到变更的文档，检查所有文档")
            else:
                md_files = [f for f in md_files if f in changed_files]
                print(f"📝 检测到 {len(md_files)} 个变更文档\n")
        else:
            print(f"📁 找到 {len(md_files)} 个核心文档\n")

        for md_file in sorted(md_files):
            score = self.check_document(md_file)
            self.scores.append(score)

        self.print_summary()
        return self.scores

    def check_document(self, file_path: Path) -> DocumentScore:
        """检查单个文档"""
        self.issues = []

        try:
            content = file_path.read_text(encoding="utf-8")
            lines = content.split("\n")

            # 执行各项检查
            self.check_file_encoding(file_path)
            self.check_file_ending(file_path, content)
            self.check_document_structure(file_path, content, lines)
            self.check_version_info(file_path, content, lines)
            self.check_links(file_path, content, lines)
            self.check_code_blocks(file_path, content, lines)
            self.check_headings(file_path, content, lines)
            self.check_tables(file_path, content, lines)

            # 计算评分
            score = self.calculate_score()

            # 打印结果
            self.print_document_result(file_path, score)

            return DocumentScore(file=str(file_path), score=score, issues=self.issues.copy())

        except KeyboardInterrupt:
            raise
        except Exception as e:
            print(f"❌ {file_path.name}: 检查失败 - {e}")
            return DocumentScore(
                file=str(file_path),
                score=0.0,
                issues=[Issue(Severity.ERROR, str(file_path), 0, f"检查失败: {e}")],
            )

    def check_file_encoding(self, file_path: Path):
        """检查文件编码"""
        try:
            file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            self.issues.append(Issue(Severity.ERROR, str(file_path), 0, "文件编码不是UTF-8"))

    def check_file_ending(self, file_path: Path, content: str):
        """检查文件末尾是否有换行符"""
        if content and not content.endswith("\n"):
            self.issues.append(
                Issue(Severity.WARNING, str(file_path), len(content.split("\n")), "文件末尾缺少换行符")
            )

    def check_document_structure(self, file_path: Path, content: str, lines: list[str]):
        """检查文档结构"""
        # 检查是否有标题
        if not re.search(r"^#\s+.+", content, re.MULTILINE):
            self.issues.append(Issue(Severity.ERROR, str(file_path), 0, "缺少主标题 (# Title)"))

        # 检查是否有目录（对于长文档）
        if len(lines) > 50:
            if not re.search(r"##\s+目录", content):
                self.issues.append(Issue(Severity.WARNING, str(file_path), 0, "长文档建议添加目录"))

    def check_version_info(self, file_path: Path, content: str, lines: list[str]):
        """检查版本信息"""
        # 检查是否包含版本信息（在前20行）
        first_20_lines = "\n".join(lines[:20])
        if not re.search(r"[*]*[*]版本[*]*[*]:\s*v?\d+\.\d+", first_20_lines):
            # 某些文档可能不需要版本信息（如README）
            if file_path.name not in ["README.md", "CONTRIBUTING.md"]:
                self.issues.append(
                    Issue(
                        Severity.WARNING, str(file_path), 1, "建议添加版本信息 (例如: **版本**: v4.2.2)"
                    )
                )

    def check_links(self, file_path: Path, content: str, lines: list[str]):
        """检查链接"""
        # 查找Markdown链接
        link_pattern = r"\[([^\]]+)\]\(([^)]+)\)"
        links = re.finditer(link_pattern, content)

        for match in links:
            link_text = match.group(1)
            link_url = match.group(2)
            line_num = content[: match.start()].count("\n") + 1

            # 跳过外部链接和锚点链接
            if link_url.startswith(("http://", "https://", "mailto:", "#")):
                continue

            # 检查相对路径链接
            if not link_url.startswith(("mailto:", "tel:")):
                # 移除锚点
                link_path = link_url.split("#")[0]

                if link_path:  # 不是纯锚点链接
                    # 计算实际路径
                    if link_path.startswith("/"):
                        target_path = Path(self.docs_dir.parent) / link_path[1:]
                    else:
                        target_path = (file_path.parent / link_path).resolve()

                    # 检查文件是否存在
                    if not target_path.exists():
                        self.issues.append(
                            Issue(
                                Severity.WARNING,
                                str(file_path),
                                line_num,
                                f"链接可能断裂: [{link_text}]({link_url})",
                            )
                        )

    def check_code_blocks(self, file_path: Path, content: str, lines: list[str]):
        """检查代码块格式"""
        in_code_block = False

        for i, line in enumerate(lines, 1):
            if line.strip().startswith("```"):
                if not in_code_block:
                    in_code_block = True
                    # 检查是否指定了语言
                    if line.strip() == "```":
                        self.issues.append(
                            Issue(
                                Severity.WARNING,
                                str(file_path),
                                i,
                                "代码块建议指定语言类型 (例如: ```python)",
                            )
                        )
                else:
                    in_code_block = False

    def check_headings(self, file_path: Path, content: str, lines: list[str]):
        """检查标题层级"""
        headings = []
        for i, line in enumerate(lines, 1):
            match = re.match(r"^(#{1,6})\s+", line)
            if match:
                level = len(match.group(1))
                headings.append((level, line.strip(), i))

        # 检查标题层级是否跳跃
        for i in range(1, len(headings)):
            prev_level = headings[i - 1][0]
            curr_level = headings[i][0]

            if curr_level > prev_level + 1:
                self.issues.append(
                    Issue(
                        Severity.WARNING,
                        str(file_path),
                        headings[i][2],
                        f"标题层级跳跃: 从 {'#' * prev_level} 到 {'#' * curr_level}",
                    )
                )

    def check_tables(self, file_path: Path, content: str, lines: list[str]):
        """检查表格格式"""
        in_table = False

        for i, line in enumerate(lines, 1):
            if "|" in line and line.strip():
                if not in_table:
                    in_table = True

                # 检查表格对齐（简单检查）
                columns = [col.strip() for col in line.split("|") if col.strip()]
                if len(columns) > 1 and len(columns) < 10:  # 合理列数
                    # 可以在这里添加更复杂的表格检查
                    pass
            else:
                if in_table:
                    in_table = False

    def calculate_score(self) -> float:
        """计算文档评分 - 优化版（使用可配置权重）"""
        if not self.issues:
            return 10.0

        # 统计各类型问题数量
        error_count = sum(1 for i in self.issues if i.severity == Severity.ERROR)
        warning_count = sum(1 for i in self.issues if i.severity == Severity.WARNING)
        info_count = sum(1 for i in self.issues if i.severity == Severity.INFO)

        # 分类统计 - 使用常量避免字符串匹配错误
        code_block_issues = sum(1 for i in self.issues if IssueType.CODE_BLOCK in i.message)
        link_issues = sum(1 for i in self.issues if IssueType.LINK in i.message)
        toc_issues = sum(1 for i in self.issues if IssueType.TOC in i.message)
        version_issues = sum(1 for i in self.issues if IssueType.VERSION in i.message)
        heading_issues = sum(1 for i in self.issues if IssueType.HEADING in i.message)

        # 使用配置的计算机制
        deduction = 0.0

        # ERROR问题
        error_deduction = error_count * self.config.error_weight
        deduction += error_deduction

        # WARNING问题：分类处理
        code_block_deduction = 0.0
        if code_block_issues > 0:
            code_block_deduction = min(
                code_block_issues * self.config.code_block_weight, self.config.code_block_max
            )
            deduction += code_block_deduction

        # 链接问题
        link_deduction = min(link_issues * self.config.link_weight, self.config.link_max)
        deduction += link_deduction

        # 其他WARNING问题
        other_warnings = max(0, warning_count - code_block_issues - link_issues)
        other_warning_deduction = other_warnings * self.config.other_warning_weight
        deduction += other_warning_deduction

        # INFO问题
        info_deduction = info_count * self.config.info_weight
        deduction += info_deduction

        # 奖励机制
        bonus = 0.0
        toc_bonus = 0.0
        version_bonus = 0.0

        if not any(IssueType.TOC in i.message for i in self.issues):
            toc_bonus = self.config.toc_bonus
            bonus += toc_bonus

        if not any(IssueType.VERSION in i.message for i in self.issues):
            version_bonus = self.config.version_bonus
            bonus += version_bonus

        # 详细日志输出
        print("\n📊 评分详情:")
        print(f"  问题统计: ERROR={error_count}, WARNING={warning_count}, INFO={info_count}")
        print(f"  分类统计: 代码块={code_block_issues}, 链接={link_issues}, 标题={heading_issues}")
        print("  扣分详情:")
        print(f"    ERROR: {error_count} × {self.config.error_weight} = {error_deduction:.1f}")
        print(
            f"    代码块: {code_block_issues} × {self.config.code_block_weight} = {code_block_deduction:.1f} (上限{self.config.code_block_max})"
        )
        print(
            f"    链接: {link_issues} × {self.config.link_weight} = {link_deduction:.1f} (上限{self.config.link_max})"
        )
        print(
            f"    其他WARNING: {other_warnings} × {self.config.other_warning_weight} = {other_warning_deduction:.1f}"
        )
        print(f"    INFO: {info_count} × {self.config.info_weight} = {info_deduction:.1f}")
        print(f"  总扣分: {deduction:.1f}")
        print("  奖励详情:")
        print(f"    目录: +{toc_bonus:.1f}")
        print(f"    版本: +{version_bonus:.1f}")
        print(f"  总奖励: {bonus:.1f}")

        # 最终分数
        score = max(0.0, min(10.0, 10.0 - deduction + bonus))
        return round(score, 1)

    def print_document_result(self, file_path: Path, score: float):
        """打印单个文档的检查结果"""
        emoji = "✅" if score >= 8.5 else "⚠️" if score >= 7.0 else "❌"

        print(f"{emoji} {file_path.name} - 质量评分: {score}/10")

        if self.issues:
            for issue in self.issues:
                print(f"   {issue.severity.value} {issue.message}")

        print()

    def print_summary(self):
        """打印总体统计"""
        print("=" * 60)
        print("📊 文档质量检查报告")
        print("=" * 60)

        if not self.scores:
            print("没有找到文档")
            return

        total_docs = len(self.scores)
        avg_score = sum(s.score for s in self.scores) / total_docs

        excellent = sum(1 for s in self.scores if s.score >= 8.5)
        good = sum(1 for s in self.scores if 7.0 <= s.score < 8.5)
        poor = sum(1 for s in self.scores if s.score < 7.0)

        print(f"\n核心文档总数: {total_docs}")
        print(f"平均质量评分: {avg_score:.1f}/10")
        print("\n质量分布:")
        print(f"  ✅ 优秀 (≥8.5): {excellent} 个")
        print(f"  ⚠️  良好 (7.0-8.4): {good} 个")
        print(f"  ❌ 需改进 (<7.0): {poor} 个")

        # 列出需要改进的文档
        poor_docs = [s for s in self.scores if s.score < 7.0]
        if poor_docs:
            print("\n⚠️  需要改进的文档:")
            for doc in poor_docs:
                print(f"  - {Path(doc.file).name}: {doc.score}/10")

        # 总体评价
        print("\n总体评价: ", end="")
        if avg_score >= 9.0:
            print("✅ 优秀")
        elif avg_score >= 8.0:
            print("✅ 良好")
        elif avg_score >= 7.0:
            print("⚠️  需改进")
        else:
            print("❌ 不合格")

        print("=" * 60)


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="文档质量检查工具")
    parser.add_argument("--docs-dir", default=None, help="文档目录路径 (默认: project_root/docs)")
    parser.add_argument("--config", default=None, help="评分配置文件路径 (JSON格式)")
    parser.add_argument("--save-config", default=None, help="保存当前配置到文件")
    parser.add_argument("--changed-only", action="store_true", help="只检查Git变更的文档(增量检查模式)")

    args = parser.parse_args()

    # 从项目根目录运行
    project_root = Path(__file__).parent.parent
    docs_dir = Path(args.docs_dir) if args.docs_dir else project_root / "docs"

    if not docs_dir.exists():
        print(f"❌ 文档目录不存在: {docs_dir}")
        sys.exit(1)

    # 加载配置
    config = None
    if args.config:
        config_path = Path(args.config)
        if config_path.exists():
            config = ScoringConfig.from_file(str(config_path))
            print(f"📝 使用配置文件: {config_path}")
        else:
            print(f"⚠️  配置文件不存在: {config_path}，使用默认配置")

    # 保存配置（如果指定）
    if args.save_config:
        default_config = ScoringConfig()
        default_config.save_to_file(args.save_config)
        print(f"✅ 配置已保存到: {args.save_config}")
        sys.exit(0)

    checker = DocumentQualityChecker(str(docs_dir), config)
    scores = checker.check_all(changed_only=args.changed_only)

    # 返回退出码（如果有严重问题则返回非0）
    has_errors = any(issue.severity == Severity.ERROR for score in scores for issue in score.issues)

    sys.exit(1 if has_errors else 0)


if __name__ == "__main__":
    main()

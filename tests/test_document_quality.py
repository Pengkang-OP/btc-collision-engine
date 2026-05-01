#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文档质量检查器单元测试

测试评分计算、边界条件、配置加载等核心功能
"""

import sys
import io
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tools.check_document_quality import (
    DocumentQualityChecker,
    ScoringConfig,
    Issue,
    Severity,
    IssueType,
)


def test_perfect_score():
    """测试满分情况"""
    checker = DocumentQualityChecker()
    checker.issues = []
    score = checker.calculate_score()
    assert score == 10.0, f"预期10.0，实际{score}"
    print("✅ 测试通过: 满分情况")


def test_error_deduction():
    """测试ERROR扣分"""
    checker = DocumentQualityChecker()
    checker.issues = [Issue(Severity.ERROR, "test.md", 1, "编码错误")]
    score = checker.calculate_score()
    # 10.0 - 1.5 (error) + 0.3 (toc) + 0.2 (version) = 9.0
    expected = 9.0
    assert score == expected, f"预期{expected}，实际{score}"
    print("✅ 测试通过: ERROR扣分")


def test_code_block_cap():
    """测试代码块扣分上限"""
    checker = DocumentQualityChecker()
    # 创建100个代码块问题，应该最多扣2分
    checker.issues = [
        Issue(Severity.WARNING, "test.md", i, "代码块建议指定语言类型") for i in range(1, 101)
    ]
    score = checker.calculate_score()
    # 10.0 - 2.0 (code_block_max) = 8.0
    assert score >= 8.0, f"预期>=8.0，实际{score}（扣分过多）"
    print("✅ 测试通过: 代码块扣分上限")


def test_link_cap():
    """测试链接扣分上限"""
    checker = DocumentQualityChecker()
    # 创建100个链接问题，应该最多扣3分
    checker.issues = [Issue(Severity.WARNING, "test.md", i, "链接可能断裂") for i in range(1, 101)]
    score = checker.calculate_score()
    # 10.0 - 3.0 (link_max) = 7.0
    assert score >= 7.0, f"预期>=7.0，实际{score}（扣分过多）"
    print("✅ 测试通过: 链接扣分上限")


def test_bonus_toc_and_version():
    """测试目录和版本信息奖励"""
    checker = DocumentQualityChecker()
    # 没有任何问题，应该获得满分+奖励（但最高10分）
    checker.issues = []
    score = checker.calculate_score()
    assert score == 10.0, f"预期10.0，实际{score}"
    print("✅ 测试通过: 奖励机制（满分封顶）")


def test_bonus_partial():
    """测试部分奖励"""
    checker = DocumentQualityChecker()
    # 有一个小问题，但已添加目录和版本
    checker.issues = [Issue(Severity.INFO, "test.md", 1, "文件建议添加结尾换行")]
    score = checker.calculate_score()
    # 10.0 - 0.1 (info) + 0.3 (toc) + 0.2 (version) = 10.4 -> 10.0 (封顶)
    expected = 10.0
    assert score == expected, f"预期{expected}，实际{score}"
    print("✅ 测试通过: 部分奖励")


def test_no_bonus_with_issues():
    """测试有问题时不奖励"""
    checker = DocumentQualityChecker()
    # 有目录和版本相关的问题
    checker.issues = [
        Issue(Severity.WARNING, "test.md", 1, "长文档建议添加目录"),
        Issue(Severity.WARNING, "test.md", 2, "文档缺少版本信息"),
    ]
    score = checker.calculate_score()
    # 10.0 - 0.3 - 0.3 = 9.4 (无奖励)
    expected = 9.4
    assert score == expected, f"预期{expected}，实际{score}"
    print("✅ 测试通过: 有问题时不奖励")


def test_boundary_negative_warnings():
    """测试负数边界情况"""
    checker = DocumentQualityChecker()
    # 故意构造可能导致负数的情况
    checker.issues = [
        Issue(Severity.WARNING, "test.md", 1, "代码块建议"),
        Issue(Severity.WARNING, "test.md", 2, "代码块建议"),
        Issue(Severity.WARNING, "test.md", 3, "链接问题"),
    ]
    # warning_count=3, code_block=2, link=1
    # other_warnings = max(0, 3-2-1) = 0
    score = checker.calculate_score()
    assert score > 0, f"预期>0，实际{score}"
    print("✅ 测试通过: 负数边界")


def test_score_bounds():
    """测试分数边界（0-10）"""
    checker = DocumentQualityChecker()
    # 创建大量ERROR，应该扣分但最低0分
    checker.issues = [Issue(Severity.ERROR, "test.md", i, "严重错误") for i in range(1, 20)]
    score = checker.calculate_score()
    assert 0.0 <= score <= 10.0, f"分数{score}超出范围[0, 10]"
    print("✅ 测试通过: 分数边界")


def test_config_load_save():
    """测试配置加载和保存"""
    import json
    import tempfile

    # 创建默认配置
    config = ScoringConfig()

    # 保存到临时文件
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        temp_path = f.name

    try:
        config.save_to_file(temp_path)

        # 加载配置
        loaded_config = ScoringConfig.from_file(temp_path)

        # 验证配置一致
        assert config.error_weight == loaded_config.error_weight
        assert config.code_block_max == loaded_config.code_block_max
        assert config.toc_bonus == loaded_config.toc_bonus

        print("✅ 测试通过: 配置加载保存")
    finally:
        Path(temp_path).unlink()


def test_custom_config():
    """测试自定义配置"""
    custom_config = ScoringConfig(error_weight=2.0, code_block_weight=0.5, toc_bonus=0.5)

    checker = DocumentQualityChecker(config=custom_config)
    checker.issues = [Issue(Severity.ERROR, "test.md", 1, "错误")]

    score = checker.calculate_score()
    # 10.0 - 2.0 (error) + 0.5 (toc) + 0.2 (version) = 8.7
    expected = 8.7
    assert score == expected, f"预期{expected}，实际{score}"
    print("✅ 测试通过: 自定义配置")


def test_issue_type_constants():
    """测试问题类型常量"""
    assert IssueType.CODE_BLOCK == "代码块"
    assert IssueType.LINK == "链接"
    assert IssueType.TOC == "目录"
    assert IssueType.VERSION == "版本"
    print("✅ 测试通过: 问题类型常量")


def test_config_validation_negative_weight():
    """测试配置验证 - 负权重"""
    import pytest

    try:
        config = ScoringConfig(error_weight=-1.0)
        config.validate()
        assert False, "应该抛出ValueError"
    except ValueError as e:
        assert "error_weight must be >= 0" in str(e)
        print("✅ 测试通过: 负权重验证")


def test_config_validation_excessive_bonus():
    """测试配置验证 - 过高奖励"""
    try:
        config = ScoringConfig(toc_bonus=0.8, version_bonus=0.8)
        config.validate()
        assert False, "应该抛出ValueError"
    except ValueError as e:
        assert "Total bonus" in str(e)
        print("✅ 测试通过: 过高奖励验证")


def test_config_validation_valid():
    """测试配置验证 - 有效配置"""
    config = ScoringConfig(error_weight=2.0, toc_bonus=0.3, version_bonus=0.2)
    config.validate()  # 不应抛出异常
    print("✅ 测试通过: 有效配置验证")


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("🧪 开始运行单元测试")
    print("=" * 60)
    print()

    tests = [
        test_perfect_score,
        test_error_deduction,
        test_code_block_cap,
        test_link_cap,
        test_bonus_toc_and_version,
        test_bonus_partial,
        test_no_bonus_with_issues,
        test_boundary_negative_warnings,
        test_score_bounds,
        test_config_load_save,
        test_custom_config,
        test_issue_type_constants,
        test_config_validation_negative_weight,
        test_config_validation_excessive_bonus,
        test_config_validation_valid,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"❌ 测试失败: {test.__name__}")
            print(f"   错误: {e}")
            failed += 1
        except Exception as e:
            print(f"❌ 测试异常: {test.__name__}")
            print(f"   错误: {e}")
            failed += 1

    print()
    print("=" * 60)
    print(f"📊 测试结果: {passed}通过, {failed}失败")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

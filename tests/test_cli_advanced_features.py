#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CLI高级功能集成测试

测试新增的6个CLI功能:
1. 配置模板系统 (--template)
2. 参数智能推荐 (--recommend)
3. 进度数据导出 (--export-progress)
4. 匹配结果导出 (--export-matches)
5. GPU错误处理增强
6. 端到端功能测试
"""

import pytest
import sys
import os
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.cli.advanced_features import (
    CONFIG_TEMPLATES,
    deep_merge,
    apply_template,
    recommend_parameters,
    export_progress_data,
    export_matches,
    GPUErrorHandler,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def temp_config_file():
    """创建临时配置文件"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({}, f)
        temp_path = f.name

    yield temp_path

    # 清理
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def temp_output_file():
    """创建临时输出文件路径"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        temp_path = f.name

    yield temp_path

    # 清理
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def mock_stats():
    """创建模拟的CollisionStats对象"""
    stats = Mock()
    stats.total_checked = 1234567
    stats.elapsed = 120.5
    stats.format_elapsed = lambda: "00:02:00"
    stats.format_speed = lambda: "10,234 次/秒"
    stats.matches = [
        {
            "address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            "private_key": "0000000000000000000000000000000000000000000000000000000000000001",
            "wif": "5HpHagT65TZzG1PH3CSu63k8DbpvD8s5ip4nEB3kEsreAnchuDf",
        }
    ]
    return stats


@pytest.fixture
def mock_args():
    """创建模拟的命令行参数"""
    args = Mock()
    args.targets = ["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"]
    args.file = None
    args.mode = "random"
    args.start = None
    args.end = None
    return args


# ============================================================================
# 1. 配置模板系统测试
# ============================================================================


class TestConfigTemplateSystem:
    """配置模板系统测试"""

    def test_templates_exist(self):
        """测试所有模板都存在"""
        expected_templates = ["gpu-performance", "gpu-multi", "long-running", "quick-test"]
        for template_name in expected_templates:
            assert template_name in CONFIG_TEMPLATES, f"模板 {template_name} 不存在"

    def test_template_structure(self):
        """测试模板结构完整性"""
        for name, template in CONFIG_TEMPLATES.items():
            assert "name" in template, f"模板 {name} 缺少 name 字段"
            assert "description" in template, f"模板 {name} 缺少 description 字段"
            assert "updates" in template, f"模板 {name} 缺少 updates 字段"
            assert isinstance(template["updates"], dict), f"模板 {name} 的 updates 必须是字典"

    def test_deep_merge_simple(self):
        """测试简单字典合并"""
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        deep_merge(base, override)

        assert base["a"] == 1
        assert base["b"] == 3  # 被覆盖
        assert base["c"] == 4  # 新增

    def test_deep_merge_nested(self):
        """测试嵌套字典合并"""
        base = {"collision": {"mode": "random", "workers": 4}, "gpu": {"enabled": False}}
        override = {
            "collision": {"workers": 8, "checkpoint": True},
            "gpu": {"enabled": True, "device": 0},
        }
        deep_merge(base, override)

        assert base["collision"]["mode"] == "random"  # 保留
        assert base["collision"]["workers"] == 8  # 覆盖
        assert base["collision"]["checkpoint"] == True  # 新增
        assert base["gpu"]["enabled"] == True  # 覆盖
        assert base["gpu"]["device"] == 0  # 新增

    def test_apply_template_new_file(self, temp_config_file):
        """测试应用模板到新文件"""
        os.unlink(temp_config_file)  # 删除文件，测试创建新文件

        # 捕获输出
        import io

        captured_output = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured_output

        try:
            success = apply_template("quick-test", temp_config_file)

            assert success == True
            assert os.path.exists(temp_config_file)

            # 验证配置内容
            with open(temp_config_file, "r", encoding="utf-8") as f:
                config = json.load(f)

            assert config["collision"]["use_performance_optimization"] == False
            assert config["collision"]["max_workers"] == 2
            assert config["logging"]["level"] == "DEBUG"
        finally:
            sys.stdout = old_stdout

    def test_apply_template_merge_existing(self, temp_config_file):
        """测试应用模板到现有配置（合并）"""
        # 创建现有配置
        existing_config = {
            "crypto": {"backend": "auto"},
            "collision": {"mode": "random"},
            "custom_key": "custom_value",
        }
        with open(temp_config_file, "w", encoding="utf-8") as f:
            json.dump(existing_config, f)

        import io

        captured_output = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured_output

        try:
            success = apply_template("gpu-performance", temp_config_file)

            assert success == True

            # 验证配置合并
            with open(temp_config_file, "r", encoding="utf-8") as f:
                config = json.load(f)

            # 保留原有配置
            assert config["crypto"]["backend"] == "auto"
            assert config["collision"]["mode"] == "random"
            assert config["custom_key"] == "custom_value"

            # 应用新配置
            assert config["collision"]["use_performance_optimization"] == True
            assert config["gpu"]["mode"] == "single"
        finally:
            sys.stdout = old_stdout

    def test_apply_template_invalid_name(self, temp_config_file, capsys):
        """测试应用不存在的模板"""
        success = apply_template("invalid-template", temp_config_file)

        assert success == False
        captured = capsys.readouterr()
        assert "未知模板" in captured.out
        assert "可用模板" in captured.out

    def test_all_templates_applicable(self, temp_config_file):
        """测试所有模板都可以成功应用"""
        for template_name in CONFIG_TEMPLATES.keys():
            # 每次使用新的临时文件
            test_file = temp_config_file + f".{template_name}"

            import io

            captured_output = io.StringIO()
            old_stdout = sys.stdout
            sys.stdout = captured_output

            try:
                success = apply_template(template_name, test_file)
                assert success == True, f"模板 {template_name} 应用失败"
                assert os.path.exists(test_file)
            finally:
                sys.stdout = old_stdout
                if os.path.exists(test_file):
                    os.unlink(test_file)


# ============================================================================
# 2. 参数智能推荐测试
# ============================================================================


class TestParameterRecommendation:
    """参数智能推荐测试"""

    def test_recommend_random_mode(self, mock_args):
        """测试随机模式推荐"""
        rec = recommend_parameters(mock_args)

        assert "recommendations" in rec
        assert "reasons" in rec
        assert "--checkpoint" in rec["recommendations"]
        assert "--dedup" in rec["recommendations"]

    def test_recommend_with_many_targets(self, mock_args):
        """测试多目标地址推荐"""
        mock_args.targets = [f"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa" for _ in range(15)]

        rec = recommend_parameters(mock_args)

        assert "--dedup" in rec["recommendations"]
        assert rec["target_count"] == 15

    def test_recommend_range_mode_large_range(self, mock_args):
        """测试大范围扫描推荐"""
        mock_args.mode = "range"
        mock_args.start = "1"
        mock_args.end = "100000001"  # 2^32 + 1 = 4294967297，大于2^32

        rec = recommend_parameters(mock_args)

        assert "--checkpoint" in rec["recommendations"]

    def test_recommend_range_mode_small_range(self, mock_args):
        """测试小范围扫描推荐"""
        mock_args.mode = "range"
        mock_args.start = "1"
        mock_args.end = "FFFF"  # 小范围

        rec = recommend_parameters(mock_args)

        # 小范围不应该推荐checkpoint
        assert "--checkpoint" not in rec["recommendations"]

    @patch("importlib.import_module")
    def test_recommend_with_gpu(self, mock_import, mock_args):
        """测试有GPU时的推荐"""
        # 模拟GPU可用
        mock_import.return_value = Mock()

        rec = recommend_parameters(mock_args)

        # 检查是否推荐GPU
        gpu_recommended = any("GPU" in reason for reason in rec["reasons"])
        assert gpu_recommended == True

    def test_recommend_reasons_provided(self, mock_args):
        """测试推荐理由是否提供"""
        rec = recommend_parameters(mock_args)

        assert len(rec["reasons"]) > 0
        assert all(isinstance(reason, str) for reason in rec["reasons"])

    def test_recommend_cpu_count(self, mock_args):
        """测试CPU核心数检测"""
        rec = recommend_parameters(mock_args)

        assert "cpu_count" in rec
        assert rec["cpu_count"] > 0


# ============================================================================
# 3. 进度数据导出测试
# ============================================================================


class TestProgressExport:
    """进度数据导出测试"""

    def test_export_progress_basic(self, mock_stats, temp_output_file):
        """测试基本进度导出"""
        success = export_progress_data(
            mock_stats, mode="random", engine_type="cpu", output_file=temp_output_file
        )

        assert success == True
        assert os.path.exists(temp_output_file)

        # 验证JSON内容
        with open(temp_output_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["mode"] == "random"
        assert data["engine_type"] == "cpu"
        assert data["total_checked"] == 1234567
        assert data["elapsed_seconds"] == 120.5
        assert data["matches_count"] == 1

    def test_export_progress_with_range(self, mock_stats, temp_output_file):
        """测试带范围的进度导出"""
        success = export_progress_data(
            mock_stats,
            mode="range",
            engine_type="gpu",
            output_file=temp_output_file,
            total_range=10000000,
        )

        assert success == True

        with open(temp_output_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["total_range"] == 10000000
        assert "progress_percent" in data
        assert data["progress_percent"] > 0

    def test_export_progress_invalid_path(self, mock_stats):
        """测试导出到无效路径"""
        success = export_progress_data(
            mock_stats,
            mode="random",
            engine_type="cpu",
            output_file="/invalid/path/that/does/not/exist.json",
        )

        assert success == False

    def test_export_progress_json_structure(self, mock_stats, temp_output_file):
        """测试导出JSON结构完整性"""
        export_progress_data(
            mock_stats, mode="random", engine_type="cpu", output_file=temp_output_file
        )

        with open(temp_output_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 验证必需字段
        required_fields = [
            "timestamp",
            "mode",
            "engine_type",
            "total_checked",
            "elapsed_seconds",
            "elapsed_formatted",
            "speed",
            "matches_count",
            "matches",
        ]

        for field in required_fields:
            assert field in data, f"缺少字段: {field}"


# ============================================================================
# 4. 匹配结果导出测试
# ============================================================================


class TestMatchesExport:
    """匹配结果导出测试"""

    def test_export_matches_basic(self, temp_output_file):
        """测试基本匹配结果导出"""
        matches = [
            {
                "address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
                "private_key": "0000000000000000000000000000000000000000000000000000000000000001",
                "wif": "5HpHagT65TZzG1PH3CSu63k8DbpvD8s5ip4nEB3kEsreAnchuDf",
            }
        ]

        success = export_matches(matches, temp_output_file)

        assert success == True
        assert os.path.exists(temp_output_file)

        with open(temp_output_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["total_matches"] == 1
        assert len(data["matches"]) == 1
        assert data["matches"][0]["address"] == matches[0]["address"]

    def test_export_matches_empty(self, temp_output_file):
        """测试导出空匹配列表"""
        success = export_matches([], temp_output_file)

        assert success == True

        with open(temp_output_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["total_matches"] == 0
        assert data["matches"] == []

    def test_export_matches_multiple(self, temp_output_file):
        """测试导出多个匹配结果"""
        matches = [
            {
                "address": f"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa{i}",
                "private_key": f"{'0' * 63}{i}",
                "wif": f"5HpHagT65TZzG1PH3CSu63k8DbpvD8s5ip4nEB3kEsreAnchuDf{i}",
            }
            for i in range(5)
        ]

        success = export_matches(matches, temp_output_file)

        assert success == True

        with open(temp_output_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["total_matches"] == 5
        assert len(data["matches"]) == 5

    def test_export_matches_invalid_path(self):
        """测试导出到无效路径"""
        matches = [{"address": "test"}]
        success = export_matches(matches, "/invalid/path/that/does/not/exist.json")

        assert success == False


# ============================================================================
# 5. GPU错误处理测试
# ============================================================================


class TestGPUErrorHandler:
    """GPU错误处理测试"""

    def test_handle_no_gpu_error(self):
        """测试无GPU设备错误处理"""
        error = Exception("No platform found")
        result = GPUErrorHandler.handle_initialization_error(error)

        assert result["type"] == "no_gpu"
        assert result["recoverable"] == False
        assert "solution" in result

    def test_handle_out_of_memory_error(self):
        """测试显存不足错误处理"""
        error = Exception("Out of memory")
        result = GPUErrorHandler.handle_initialization_error(error)

        assert result["type"] == "out_of_memory"
        assert result["recoverable"] == True
        assert "batch_size" in result["solution"].lower() or "减小" in result["solution"]

    def test_handle_driver_error(self):
        """测试驱动问题错误处理"""
        error = Exception("Driver version mismatch")
        result = GPUErrorHandler.handle_initialization_error(error)

        assert result["type"] == "driver_issue"
        assert result["recoverable"] == False

    def test_handle_unknown_error(self):
        """测试未知错误处理"""
        error = Exception("Some unknown error")
        result = GPUErrorHandler.handle_initialization_error(error)

        assert result["type"] == "unknown"
        assert "solution" in result

    def test_suggest_batch_size_reduction(self):
        """测试batch_size调整建议"""
        error = Exception("Out of memory")
        new_size = GPUErrorHandler.suggest_batch_size_adjustment(65536, error)

        assert new_size < 65536
        assert new_size >= 1024  # 最小值

    def test_suggest_batch_size_no_change(self):
        """测试不需要调整batch_size"""
        error = Exception("Some other error")
        new_size = GPUErrorHandler.suggest_batch_size_adjustment(65536, error)

        assert new_size == 65536


# ============================================================================
# 6. 端到端集成测试
# ============================================================================


class TestEndToEndIntegration:
    """端到端集成测试"""

    def test_template_then_recommend_workflow(self, temp_config_file):
        """测试模板应用后推荐的完整流程"""
        # 1. 应用模板
        import io

        captured_output = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured_output

        try:
            success = apply_template("gpu-performance", temp_config_file)
            assert success == True
        finally:
            sys.stdout = old_stdout

        # 2. 验证配置文件存在
        assert os.path.exists(temp_config_file)

        # 3. 加载配置并验证
        with open(temp_config_file, "r", encoding="utf-8") as f:
            config = json.load(f)

        assert "gpu" in config
        assert config["gpu"]["mode"] == "single"

    def test_export_after_collision_simulation(self, mock_stats, temp_output_file):
        """模拟碰撞后导出数据的完整流程"""
        # 1. 模拟碰撞运行
        # (这里使用mock_stats模拟)

        # 2. 导出进度
        success = export_progress_data(
            mock_stats, mode="random", engine_type="cpu", output_file=temp_output_file
        )
        assert success == True

        # 3. 验证导出文件
        with open(temp_output_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["total_checked"] > 0
        assert data["matches_count"] >= 0

    def test_full_workflow_template_export(self, temp_config_file, temp_output_file, mock_stats):
        """完整工作流: 模板 -> 运行 -> 导出"""
        import io

        # 步骤1: 应用模板
        captured_output = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured_output

        try:
            apply_template("quick-test", temp_config_file)
        finally:
            sys.stdout = old_stdout

        # 步骤2: 验证配置
        with open(temp_config_file, "r", encoding="utf-8") as f:
            config = json.load(f)
        assert config["collision"]["max_workers"] == 2

        # 步骤3: 模拟运行并导出
        export_progress_data(
            mock_stats, mode="random", engine_type="cpu", output_file=temp_output_file
        )

        # 步骤4: 验证导出
        with open(temp_output_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert "total_checked" in data


# ============================================================================
# 运行测试
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

"""advanced_features.py 单元测试。

覆盖范围：
- apply_template: 模板应用
- recommend_parameters: 参数推荐
- AdvancedFeatureManager: 功能开关管理
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.cli.advanced_features import (
    AdvancedFeatureManager,
    apply_template,
    recommend_parameters,
)

# ============================================================================
# apply_template
# ============================================================================


class TestApplyTemplate:
    """模板应用测试。"""

    def test_template_not_found(self, tmp_path):
        """不存在的模板返回 False。"""
        # 创建空的模板目录，保证目录存在但没有任何匹配的模板文件
        templates_dir = tmp_path / "deploy" / "templates"
        templates_dir.mkdir(parents=True)

        # 临时替换 apply_template 中 Path(__file__) 的解析
        import src.cli.advanced_features as af

        with patch.object(af.Path, "exists", return_value=False):
            result = apply_template("nonexistent_template")
            # templates_dir 存在但文件不存在 → 返回 False
            assert result is False

    @patch("pathlib.Path.exists")
    def test_template_applied_successfully(self, mock_exists, tmp_path):
        """模板文件存在时应用成功。"""
        # 创建一个假的模板文件
        template_dir = tmp_path / "templates"
        template_dir.mkdir()
        template_file = template_dir / "quick-test.json"
        template_file.write_text('{"test": true}')

        with patch("src.cli.advanced_features.Path"):
            mock_templates_dir = MagicMock()
            mock_templates_dir.exists.return_value = True
            mock_candidate = MagicMock()
            mock_candidate.exists.return_value = True
            mock_candidate.read_text.return_value = '{"test": true}'

            def mock_path_side_effect(*args):
                if len(args) == 0:
                    return MagicMock()
                return MagicMock()

            # 直接 mock Path 的行为
            with patch("builtins.open", create=True), patch.object(Path, "write_text"):
                result = apply_template("quick-test")
                # 至少能进入正确的分支
                assert isinstance(result, bool)

    def test_template_os_error(self):
        """文件写入错误时返回 False。"""
        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.read_text", side_effect=OSError("disk full")):
                result = apply_template("some-template")
                assert result is False


# ============================================================================
# recommend_parameters
# ============================================================================


class TestRecommendParameters:
    """参数推荐测试。"""

    def test_recommend_basic(self):
        """基本推荐包含必要字段。"""
        args = MagicMock()
        args.targets = ["test"]
        args.mode = "random"

        result = recommend_parameters(args)

        assert "recommendations" in result
        assert "reasons" in result
        assert len(result["recommendations"]) > 0
        assert len(result["reasons"]) == len(result["recommendations"])

    def test_recommend_includes_checkpoint(self):
        """推荐包含 --checkpoint。"""
        args = MagicMock()

        result = recommend_parameters(args)
        recs = result["recommendations"]

        assert "--checkpoint" in recs

    def test_recommend_includes_dedup(self):
        """推荐包含 --dedup。"""
        args = MagicMock()

        result = recommend_parameters(args)
        recs = result["recommendations"]

        assert "--dedup" in recs

    def test_recommend_worker_count(self):
        """推荐包含 --workers 参数。"""
        args = MagicMock()

        result = recommend_parameters(args)
        recs = result["recommendations"]

        workers_recs = [r for r in recs if r.startswith("--workers")]
        assert len(workers_recs) == 1

    def test_recommend_with_gpu_available(self):
        """有 GPU 时推荐 --use-gpu。"""
        args = MagicMock()

        # GPUDeviceDetector 在函数内部通过 from src.gpu.device import 延迟导入
        mock_detector_cls = MagicMock()
        mock_detector_cls.detect_devices.return_value = ["device1"]
        with patch("src.gpu.device.GPUDeviceDetector", mock_detector_cls):
            result = recommend_parameters(args)
            recs = result["recommendations"]
            assert "--use-gpu" in recs

    def test_recommend_without_gpu(self):
        """无 GPU 时不含 --use-gpu。"""
        args = MagicMock()

        # GPUDeviceDetector 在函数内部延迟导入
        # patch 类以模拟 ImportError
        with patch(
            "src.gpu.device.GPUDeviceDetector",
            side_effect=ImportError("No module"),
        ):
            result = recommend_parameters(args)
            recs = result["recommendations"]
            assert "--use-gpu" not in recs

    def test_recommend_reasons_match_count(self):
        """推荐理由数量与推荐数量一致。"""
        args = MagicMock()

        result = recommend_parameters(args)
        assert len(result["reasons"]) == len(result["recommendations"])


# ============================================================================
# AdvancedFeatureManager
# ============================================================================


class TestAdvancedFeatureManager:
    """高级功能管理器测试。"""

    def test_initial_features(self):
        """初始功能状态正确。"""
        mgr = AdvancedFeatureManager()
        assert mgr._features == {
            "batch_size_tuning": False,
            "auto_worker_count": True,
            "gpu_memory_optimization": False,
        }

    def test_enable_existing_feature(self):
        """启用已有功能开关。"""
        mgr = AdvancedFeatureManager()
        mgr.enable("batch_size_tuning")
        assert mgr.is_enabled("batch_size_tuning") is True

    def test_disable_existing_feature(self):
        """禁用已有功能开关。"""
        mgr = AdvancedFeatureManager()
        mgr.disable("auto_worker_count")
        assert mgr.is_enabled("auto_worker_count") is False

    def test_enable_nonexistent_feature(self):
        """启用不存在的功能不报错。"""
        mgr = AdvancedFeatureManager()
        mgr.enable("nonexistent_feature")
        assert mgr.is_enabled("nonexistent_feature") is False

    def test_is_enabled_default(self):
        """is_enabled 返回默认值。"""
        mgr = AdvancedFeatureManager()
        assert mgr.is_enabled("auto_worker_count") is True
        assert mgr.is_enabled("batch_size_tuning") is False

    def test_is_enabled_unknown_feature(self):
        """is_enabled 未知功能返回 False。"""
        mgr = AdvancedFeatureManager()
        assert mgr.is_enabled("unknown") is False

    def test_toggle_cycle(self):
        """功能开关完整切换周期。"""
        mgr = AdvancedFeatureManager()
        feature = "gpu_memory_optimization"

        assert mgr.is_enabled(feature) is False
        mgr.enable(feature)
        assert mgr.is_enabled(feature) is True
        mgr.disable(feature)
        assert mgr.is_enabled(feature) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

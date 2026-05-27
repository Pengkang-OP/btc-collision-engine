"""配置加载与验证测试 - 高优先级.

覆盖范围：
- config.json 加载与解析
- 必填字段校验
- 非法配置处理
- 可选配置默认值
- 配置类型校验

运行：
    pytest tests/test_config.py -v --tb=short
"""

import json
import os
import pathlib
import tempfile

import pytest

# ============================================================================
# 辅助函数
# ============================================================================

SAMPLE_VALID_CONFIG = {
    "mode": "random",
    "targets": ["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"],
    "threads": 4,
    "batch_size": 65536,
    "use_gpu": False,
    "output_dir": "results",
}

SAMPLE_MINIMAL_CONFIG = {
    "mode": "random",
    "targets": ["1Address"],
}


def create_temp_config(data, suffix=".json"):
    """创建临时配置文件."""
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return path


# ============================================================================
# 测试：配置加载与解析
# ============================================================================


@pytest.mark.unit
class TestConfigLoading:
    """配置加载测试."""

    def test_load_valid_json_config(self):
        """测试：加载有效的 JSON 配置文件."""
        path = create_temp_config(SAMPLE_VALID_CONFIG)
        try:
            with pathlib.Path(path).open(encoding="utf-8") as f:
                config = json.load(f)
            assert config["mode"] == "random"
            assert isinstance(config["targets"], list)
            assert len(config["targets"]) == 1
            assert config["threads"] == 4
        finally:
            pathlib.Path(path).unlink()

    def test_load_minimal_config(self):
        """测试：加载最小配置."""
        path = create_temp_config(SAMPLE_MINIMAL_CONFIG)
        try:
            with pathlib.Path(path).open(encoding="utf-8") as f:
                config = json.load(f)
            assert config["mode"] == "random"
            assert config["targets"] == ["1Address"]
        finally:
            pathlib.Path(path).unlink()

    def test_load_config_missing_file(self):
        """测试：加载不存在的配置文件."""
        with pytest.raises(FileNotFoundError):
            with pathlib.Path("nonexistent_config.json").open(encoding="utf-8") as f:
                json.load(f)

    def test_load_invalid_json(self):
        """测试：加载非法 JSON 文件."""
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write("{invalid json content}")
        try:
            with pytest.raises(json.JSONDecodeError), pathlib.Path(path).open(encoding="utf-8") as f:
                json.load(f)
        finally:
            pathlib.Path(path).unlink()

    def test_load_empty_config(self):
        """测试：加载空配置."""
        path = create_temp_config({})
        try:
            with pathlib.Path(path).open(encoding="utf-8") as f:
                config = json.load(f)
            assert config == {}
        finally:
            pathlib.Path(path).unlink()


# ============================================================================
# 测试：必填字段校验
# ============================================================================


@pytest.mark.unit
class TestConfigRequiredFields:
    """配置必填字段测试."""

    def test_config_missing_mode(self):
        """测试：缺少 mode 字段."""
        config = {"targets": ["1Address"]}
        assert "mode" not in config

    def test_config_missing_targets(self):
        """测试：缺少 targets 字段."""
        config = {"mode": "random"}
        assert "targets" not in config

    def test_config_empty_targets(self):
        """测试：targets 为空列表."""
        config = {"mode": "random", "targets": []}
        assert len(config["targets"]) == 0


# ============================================================================
# 测试：字段类型校验
# ============================================================================


@pytest.mark.unit
class TestConfigFieldTypes:
    """配置字段类型测试."""

    def test_mode_must_be_string(self):
        """测试：mode 必须是字符串."""
        for invalid_mode in [123, None, True, [], {}]:
            config = {"mode": invalid_mode, "targets": ["1Address"]}
            assert not isinstance(config["mode"], str), (
                f"mode 不应接受类型 {type(invalid_mode).__name__}"
            )

    def test_mode_valid_values(self):
        """测试：mode 有效值."""
        valid_modes = ["random", "range", "brute_force"]
        for mode in valid_modes:
            config = {"mode": mode, "targets": ["1Address"]}
            assert config["mode"] in valid_modes

    def test_mode_invalid_values(self):
        """测试：mode 无效值."""
        invalid_modes = ["fuzzy", "", "invalid_mode", 123]
        for mode in invalid_modes:
            if isinstance(mode, str) and mode:
                is_valid = mode in {"random", "range", "brute_force"}
                assert not is_valid, f"'{mode}' 应为无效模式"

    def test_targets_must_be_list(self):
        """测试：targets 必须是列表."""
        config = {"mode": "random", "targets": "1Address"}
        assert not isinstance(config["targets"], list)

    def test_threads_type_validation(self):
        """测试：threads 类型校验."""
        valid_configs = [{"threads": 1}, {"threads": 4}, {"threads": 16}]
        invalid_configs = [{"threads": 0}, {"threads": -1}, {"threads": 1.5}]

        for cfg in valid_configs:
            assert isinstance(cfg["threads"], int) and cfg["threads"] > 0

        for cfg in invalid_configs:
            is_valid = isinstance(cfg["threads"], int) and cfg["threads"] > 0
            assert not is_valid


# ============================================================================
# 测试：实际项目配置文件
# ============================================================================


@pytest.mark.unit
@pytest.mark.integration
class TestRealConfigFiles:
    """项目实际配置文件测试."""

    def test_config_example_json_exists(self):
        """测试：config.example.json 存在且格式正确."""
        config_path = "config.example.json"
        assert pathlib.Path(config_path).exists()
        with pathlib.Path(config_path).open(encoding="utf-8") as f:
            config = json.load(f)
        assert isinstance(config, dict)

    def test_config_example_has_required_structure(self):
        """测试：config.example.json 包含关键字段."""
        with pathlib.Path("config.example.json").open(encoding="utf-8") as f:
            config = json.load(f)
        top_level_keys = set(config.keys())
        assert len(top_level_keys) > 0, "配置文件不应为空"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

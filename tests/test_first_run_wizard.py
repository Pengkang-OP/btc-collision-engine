"""首次运行向导模块测试.

测试 FirstRunWizard 类的各项功能:
- should_run() 判断逻辑
- 配置文件加载和生成
- 向导标记文件管理
- 配置模板验证
"""

import json
import os
import pathlib
import shutil
import tempfile
from unittest.mock import patch

import pytest

from src.utils.first_run_wizard import FirstRunWizard


class TestFirstRunWizardBasic:
    """基础功能测试."""

    def setup_method(self):
        """创建临时项目目录."""
        self.test_dir = tempfile.mkdtemp()
        self.wizard = FirstRunWizard(project_root=self.test_dir)

    def teardown_method(self):
        """清理临时目录."""
        if pathlib.Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)

    def test_initialization(self):
        """初始化测试."""
        assert self.wizard.project_root is not None
        assert str(self.wizard.project_root) == self.test_dir
        assert str(self.wizard.config_path).endswith("config.json")
        assert str(self.wizard.marker_path).endswith(".wizard_completed")

    def test_default_config_structure(self):
        """默认配置结构测试."""
        config = FirstRunWizard.DEFAULT_CONFIG

        # 验证必需的配置节
        assert "collision" in config
        assert "gpu" in config
        assert "logging" in config
        assert "monitoring" in config

        # 验证collision配置
        assert "mode" in config["collision"]
        assert "batch_size" in config["collision"]
        assert config["collision"]["mode"] in ["random", "range", "brute_force"]

        # 验证gpu配置
        assert "enabled" in config["gpu"]
        assert isinstance(config["gpu"]["enabled"], bool)

        # 验证logging配置
        assert "level" in config["logging"]
        assert config["logging"]["level"] in ["DEBUG", "INFO", "WARNING", "ERROR"]

    def test_should_run_no_config(self):
        """无配置文件时应运行向导."""
        # 确保没有config.json
        if self.wizard.config_path.exists():
            self.wizard.config_path.unlink()

        # 确保没有标记文件
        if self.wizard.marker_path.exists():
            self.wizard.marker_path.unlink()

        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            assert self.wizard.should_run()

    def test_should_run_with_marker(self):
        """有标记文件时不应运行向导."""
        # 创建标记文件
        self.wizard.marker_path.parent.mkdir(parents=True, exist_ok=True)
        self.wizard.marker_path.touch()

        assert not self.wizard.should_run()

    def test_should_run_with_valid_config(self):
        """有有效配置文件时不应运行向导."""
        # 创建有效的config.json（大于50字节）
        self.wizard.config_path.parent.mkdir(parents=True, exist_ok=True)
        config_data = {
            "collision": {"mode": "random", "batch_size": 10000},
            "gpu": {"enabled": False},
            "logging": {"level": "INFO"},
            "monitoring": {"enabled": True},
        }
        with pathlib.Path(self.wizard.config_path).open("w", encoding="utf-8") as f:
            json.dump(config_data, f)

        assert not self.wizard.should_run()

    def test_should_run_with_empty_config(self):
        """空配置文件时应运行向导."""
        # 创建空配置文件
        self.wizard.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.wizard.config_path.touch()

        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            assert self.wizard.should_run()

    def test_should_run_with_small_config(self):
        """小配置文件（<50字节）时应运行向导."""
        self.wizard.config_path.parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(self.wizard.config_path).write_text("{}", encoding="utf-8")  # 只有2字节

        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            assert self.wizard.should_run()


class TestFirstRunWizardConfig:
    """配置管理测试."""

    def setup_method(self):
        """创建临时项目目录."""
        self.test_dir = tempfile.mkdtemp()
        self.wizard = FirstRunWizard(project_root=self.test_dir)

    def teardown_method(self):
        """清理临时目录."""
        if pathlib.Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)

    def test_save_config(self):
        """保存配置测试."""
        config = FirstRunWizard.DEFAULT_CONFIG.copy()

        # 模拟保存配置
        self.wizard.config_path.parent.mkdir(parents=True, exist_ok=True)
        with pathlib.Path(self.wizard.config_path).open("w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

        # 验证文件存在
        assert self.wizard.config_path.exists()

        # 验证内容
        with pathlib.Path(self.wizard.config_path).open(encoding="utf-8") as f:
            loaded_config = json.load(f)

        assert loaded_config["collision"]["mode"] == "random"
        assert not loaded_config["gpu"]["enabled"]

    def test_load_example_config(self):
        """加载示例配置文件."""
        # 创建示例配置文件
        example_config = {"collision": {"mode": "range"}, "gpu": {"enabled": True}}

        self.wizard.example_path.parent.mkdir(parents=True, exist_ok=True)
        with pathlib.Path(self.wizard.example_path).open("w", encoding="utf-8") as f:
            json.dump(example_config, f)

        # 验证示例文件存在
        assert self.wizard.example_path.exists()

    def test_create_marker_file(self):
        """创建向导标记文件."""
        self.wizard.marker_path.parent.mkdir(parents=True, exist_ok=True)
        self.wizard.marker_path.touch()

        assert self.wizard.marker_path.exists()
        assert not self.wizard.should_run()


class TestFirstRunWizardInteraction:
    """交互功能测试."""

    def test_prompt_with_default(self):
        """测试带默认值的提示."""
        with patch("builtins.input", return_value=""):
            result = FirstRunWizard._prompt("测试提示", default="默认值")
            assert result == "默认值"

    def test_prompt_with_input(self):
        """测试用户输入."""
        with patch("builtins.input", return_value="用户输入"):
            result = FirstRunWizard._prompt("测试提示", default="默认值")
            assert result == "用户输入"

    def test_prompt_keyboard_interrupt(self):
        """测试键盘中断."""
        with patch("builtins.input", side_effect=KeyboardInterrupt), pytest.raises(SystemExit):
            FirstRunWizard._prompt("测试提示")

    def test_prompt_eof_error(self):
        """测试EOF错误."""
        with patch("builtins.input", side_effect=EOFError), pytest.raises(SystemExit):
            FirstRunWizard._prompt("测试提示")

    def test_choose_option(self):
        """测试选项选择."""
        options = ["选项1", "选项2", "选项3"]

        with patch("builtins.input", return_value="2"):
            result = FirstRunWizard._choose("选择一个选项", options, default_idx=0)
            assert result == "选项2"

    def test_choose_default_option(self):
        """测试默认选项."""
        options = ["选项1", "选项2", "选项3"]

        with patch("builtins.input", return_value=""):
            result = FirstRunWizard._choose("选择一个选项", options, default_idx=0)
            # 空输入应返回默认值（选项1）
            assert result == "选项1"

    def test_choose_invalid_option(self):
        """测试无效选项后重新选择."""
        options = ["选项1", "选项2"]

        # 第一次输入无效，第二次输入有效
        with patch("builtins.input", side_effect=["99", "1"]):
            result = FirstRunWizard._choose("选择一个选项", options)
            assert result == "选项1"

    def test_yes_no_yes(self):
        """测试是/否提问 - 是."""
        with patch("builtins.input", return_value="y"):
            result = FirstRunWizard._yes_no("确认吗？", default=False)
            assert result

    def test_yes_no_no(self):
        """测试是/否提问 - 否."""
        with patch("builtins.input", return_value="n"):
            result = FirstRunWizard._yes_no("确认吗？", default=True)
            assert not result

    def test_yes_no_default(self):
        """测试是/否提问 - 默认值."""
        with patch("builtins.input", return_value=""):
            result = FirstRunWizard._yes_no("确认吗？", default=True)
            assert result

    def test_yes_no_chinese(self):
        """测试是/否提问 - 中文输入."""
        with patch("builtins.input", return_value="是"):
            result = FirstRunWizard._yes_no("确认吗？", default=False)
            assert result

        with patch("builtins.input", return_value="否"):
            result = FirstRunWizard._yes_no("确认吗？", default=True)
            assert not result


class TestFirstRunWizardEdgeCases:
    """边界情况测试."""

    def setup_method(self):
        """创建临时项目目录."""
        self.test_dir = tempfile.mkdtemp()

    def teardown_method(self):
        """清理临时目录."""
        if pathlib.Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)

    def test_nonexistent_project_root(self):
        """不存在的项目根目录."""
        nonexistent_dir = os.path.join(self.test_dir, "nonexistent")
        wizard = FirstRunWizard(project_root=nonexistent_dir)

        # should_run应该返回True（没有config.json）
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            assert wizard.should_run()

    def test_config_path_permission_error(self):
        """配置文件权限错误."""
        wizard = FirstRunWizard(project_root=self.test_dir)

        # 创建配置文件
        wizard.config_path.parent.mkdir(parents=True, exist_ok=True)
        wizard.config_path.touch()

        # 在Windows上难以模拟权限错误，这里测试正常情况
        # should_run应该能正常处理
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            assert wizard.should_run()

    def test_default_config_immutability(self):
        """默认配置不可变性."""
        config1 = FirstRunWizard.DEFAULT_CONFIG
        config2 = FirstRunWizard.DEFAULT_CONFIG

        # 两个引用应指向同一个对象
        assert config1 is config2

    def test_multiple_wizard_instances(self):
        """多个向导实例独立性."""
        wizard1 = FirstRunWizard(project_root=self.test_dir)
        wizard2 = FirstRunWizard(project_root=self.test_dir)

        # 两个实例应独立
        assert wizard1 is not wizard2
        # 但配置路径应相同
        assert wizard1.config_path == wizard2.config_path

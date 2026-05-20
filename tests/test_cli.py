#!/usr/bin/env python3
"""CLI 基础功能测试"""

import pytest
import sys
import os
from unittest.mock import Mock, patch

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.cli.main import (  # noqa: E402
    parse_args,
    validate_args,
    load_targets,
    format_progress,
    main,
)  # noqa: E402
from src.collision.collision_stats import CollisionStats  # noqa: E402


class TestCLI:
    """CLI 测试类"""

    def setup_method(self):
        """每个测试前重置 CLIOutput、LogWindow 单例，并固定为中文语言。"""
        from src.cli.output import CLIOutput

        CLIOutput.reset_instance()
        from src.cli.log_window import reset_log_window_instance

        reset_log_window_instance()

        # 固定 i18n 语言为 zh_CN，确保中文断言在任意 locale 环境下一致
        from src.i18n import set_language, get_language

        self._saved_language = get_language()
        set_language("zh_CN")

    def teardown_method(self):
        """每个测试后恢复原始语言，避免跨测试污染。"""
        from src.i18n import set_language

        set_language(self._saved_language)

    def test_parse_args(self):
        """测试命令行参数解析"""
        # 测试随机模式
        with patch(
            "sys.argv", ["cli.py", "-t", "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "-m", "random"]
        ):
            args = parse_args()
            assert args.targets == ["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"]
            assert args.mode == "random"
            assert args.checkpoint is False
            assert args.dedup is False

        # 测试范围模式
        with patch(
            "sys.argv",
            [
                "cli.py",
                "-t",
                "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
                "-m",
                "range",
                "--start",
                "1",
                "--end",
                "FFFF",
            ],
        ):
            args = parse_args()
            assert args.mode == "range"
            assert args.start == "1"
            assert args.end == "FFFF"

        # 测试暴力穷举模式
        with patch(
            "sys.argv",
            [
                "cli.py",
                "-t",
                "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
                "-m",
                "brute_force",
                "--start",
                "1",
            ],
        ):
            args = parse_args()
            assert args.mode == "brute_force"
            assert args.start == "1"

    def test_parse_args_no_color_env(self, monkeypatch):
        """NO_COLOR 环境变量设置后 args.no_color 为 True"""
        monkeypatch.setenv("NO_COLOR", "1")
        with patch(
            "sys.argv", ["cli.py", "-t", "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"]
        ):
            args = parse_args()
            assert args.no_color is True

    def test_parse_args_verbose_count(self):
        """-vvv 叠加 verbose 计数为 3"""
        with patch(
            "sys.argv",
            ["cli.py", "-t", "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "-vvv"],
        ):
            args = parse_args()
            assert args.verbose == 3

    def test_validate_args(self):
        """测试参数验证"""

        # 模拟参数对象
        class Args:
            def __init__(self, **kwargs):
                # 添加所有必需的属性（包括新增的工具命令属性）
                self.targets = kwargs.get("targets", None)
                self.file = kwargs.get("file", None)
                self.mode = kwargs.get("mode", "random")
                self.start = kwargs.get("start", None)
                self.end = kwargs.get("end", None)
                self.workers = kwargs.get("workers", 4)
                self.duration = kwargs.get("duration", 60)
                # 新增工具命令属性
                self.health_check = kwargs.get("health_check", False)
                self.platform_check = kwargs.get("platform_check", False)
                self.cleanup = kwargs.get("cleanup", False)
                self.validate_addresses = kwargs.get("validate_addresses", None)

        # 测试有效参数
        args = Args(mode="random", targets=["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"])
        assert validate_args(args) is True

        # 测试范围模式缺少 start
        args = Args(mode="range", start=None, end="FFFF", workers=4, duration=60)
        assert validate_args(args) is False

        # 测试范围模式缺少 end
        args = Args(mode="range", start="1", end=None, workers=4, duration=60)
        assert validate_args(args) is False

        # 测试无效的 start 值
        args = Args(mode="range", start="invalid", end="FFFF", workers=4, duration=60)
        assert validate_args(args) is False

        # 测试 start >= end
        args = Args(mode="range", start="FFFF", end="1", workers=4, duration=60)
        assert validate_args(args) is False

        # 测试无效的 workers
        args = Args(mode="random", start=None, end=None, workers=0, duration=60)
        assert validate_args(args) is False

        # 测试无效的 duration
        args = Args(mode="random", start=None, end=None, workers=4, duration=-10)
        assert validate_args(args) is False

    def test_format_progress(self):
        """测试进度格式化"""
        stats = CollisionStats()
        stats.total_checked = 1000
        stats.start_time = 1000  # 模拟开始时间

        # 测试随机模式进度（新格式：[elapsed] | 1.0K | 速度: ... | ETA: -- | 匹配: 0）
        progress_str = format_progress(stats, "random")
        assert "1.0K" in progress_str  # 已检查数量以缩写显示
        assert "速度:" in progress_str
        assert "匹配: 0" in progress_str

        # 测试范围模式进度（带进度条和百分比）
        progress_str = format_progress(stats, "range", total_range=10000)
        assert "1.0K" in progress_str  # 已检查数量
        assert "10.0%" in progress_str  # 进度百分比

    def test_format_progress_initializing_state(self):
        """checked=0 且运行时间不足阈值时显示初始化状态"""
        import time

        stats = CollisionStats()
        stats.total_checked = 0
        stats.elapsed = 0.5
        stats.start_time = time.time() - 5  # 仅运行 5 秒
        stats.matches = []
        progress_str = format_progress(stats, "random")
        assert "Initializing" in progress_str
        assert "初始化中" in progress_str

    def test_format_progress_invalid_engine_type(self):
        """无效 engine_type 降级为 cpu 标签"""
        stats = CollisionStats()
        stats.total_checked = 1000
        stats.start_time = 1000
        stats.elapsed = 20  # > INIT_CHECK_THRESHOLD，跳出初始化
        stats.matches = []
        progress_str = format_progress(stats, "random", engine_type="invalid")
        assert "[CPU]" in progress_str

    def test_format_progress_eta_done(self):
        """checked >= total_range 时 ETA 显示 [Done] 完成"""
        stats = CollisionStats()
        stats.total_checked = 1000
        stats.start_time = 1000
        stats.elapsed = 20
        stats.matches = []
        progress_str = format_progress(stats, "range", total_range=1000)
        assert "Done" in progress_str or "完成" in progress_str

    def test_format_progress_with_total_range(self):
        """传入有效 total_range 时显示进度条和百分比"""
        stats = CollisionStats()
        stats.total_checked = 500
        stats.start_time = 1000
        stats.elapsed = 20
        stats.matches = []
        progress_str = format_progress(stats, "range", total_range=10000)
        assert "5.0%" in progress_str

    def test_format_progress_billion_checked(self):
        """checked >= 10 亿时显示 B 后缀"""
        stats = CollisionStats()
        stats.total_checked = 2_500_000_000
        stats.start_time = 1000
        stats.elapsed = 3600
        stats.matches = []
        progress_str = format_progress(stats, "random")
        assert "2.50B" in progress_str

    def test_format_progress_million_checked(self):
        """checked >= 100 万时显示 M 后缀"""
        stats = CollisionStats()
        stats.total_checked = 8_500_000
        stats.start_time = 1000
        stats.elapsed = 3600
        stats.matches = []
        progress_str = format_progress(stats, "random")
        assert "8.50M" in progress_str

    def test_format_progress_range_billion_total(self):
        """range 模式 total_range >= 10 亿时显示 B 后缀"""
        stats = CollisionStats()
        stats.total_checked = 500_000_000
        stats.start_time = 1000
        stats.elapsed = 3600
        stats.matches = []
        progress_str = format_progress(stats, "range", total_range=3_000_000_000)
        assert "3.00B" in progress_str

    def test_format_progress_range_million_total(self):
        """range 模式 total_range >= 100 万时显示 M 后缀"""
        stats = CollisionStats()
        stats.total_checked = 500_000
        stats.start_time = 1000
        stats.elapsed = 3600
        stats.matches = []
        progress_str = format_progress(stats, "range", total_range=5_000_000)
        assert "5.00M" in progress_str

    def test_format_progress_zero_elapsed_eta(self):
        """elapsed_sec <= 0 时 ETA 显示 --"""
        stats = CollisionStats()
        stats.total_checked = 1000
        stats.start_time = 0
        stats.elapsed = 0
        stats.matches = []
        progress_str = format_progress(stats, "range", total_range=10000)
        assert "ETA: --" in progress_str

    def test_load_targets(self, tmp_path):
        """测试目标地址加载"""
        # 模拟 TargetResolver（延迟导入，需 patch collision 模块）
        with patch("src.collision.TargetResolver") as mock_resolver:
            mock_instance = Mock()
            mock_instance.load_from_file.return_value = {
                "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
                "1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH",
            }
            mock_instance.resolve_multiple.return_value = {"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"}
            mock_resolver.return_value = mock_instance

            # 模拟参数对象
            class Args:
                def __init__(self, **kwargs):
                    for key, value in kwargs.items():
                        setattr(self, key, value)

            # 测试从文件加载（同时 mock validate_file_path 跳过文件存在性检查）
            with patch("src.cli.main.validate_file_path", return_value=True):
                args = Args(file="test.txt", targets=None)
                targets = load_targets(args)
                assert len(targets) >= 2

            # 测试从命令行参数加载
            args = Args(file=None, targets=["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"])
            targets = load_targets(args)
            assert len(targets) >= 1

    def test_main_random_mode(self, capsys, monkeypatch):
        """测试主程序随机模式"""
        # 模拟命令行参数
        monkeypatch.setattr(
            "sys.argv",
            [
                "cli.py",
                "-t",
                "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
                "-m",
                "random",
                "--duration",
                "1",
            ],
        )

        # 创建 mock 引擎实例
        mock_instance = Mock()
        mock_instance.is_running.side_effect = [True, False, False]

        mock_stats = Mock()
        mock_stats.total_checked = 1000
        mock_stats.elapsed = 1.0
        mock_stats.start_time = 1000
        mock_stats.format_elapsed = lambda: "0:00:01"
        mock_stats.format_speed = lambda: "1,000 次/秒"
        mock_stats.matches = []

        mock_instance.get_stats.return_value = mock_stats
        mock_instance.start = Mock()
        mock_instance.stop = Mock()

        # 直接 patch build_engine，跳过实际引擎创建
        with patch("src.cli.engine_runner.build_engine", return_value=(mock_instance, "cpu")):
            # 模拟 time.sleep
            with patch("time.sleep", return_value=None):
                # 模拟 time.time: 前1次返回1000，之后均返回2000（确保超时被触发）
                _time_call_count = [0]

                def _mock_time():
                    _time_call_count[0] += 1
                    return 1000 if _time_call_count[0] == 1 else 2000

                with patch("time.time", side_effect=_mock_time):
                    main()

        # 检查输出
        captured = capsys.readouterr()
        assert "开始对撞" in captured.out
        assert "对撞结束" in captured.out
        # Rich Panel 输出格式：「总检查数」后面是空格填充而非「 : 」
        assert "总检查数" in captured.out and "1,000" in captured.out

    def test_main_range_mode(self, capsys, monkeypatch):
        """测试主程序范围模式"""
        # 模拟命令行参数
        monkeypatch.setattr(
            "sys.argv",
            [
                "cli.py",
                "-t",
                "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
                "-m",
                "range",
                "--start",
                "1",
                "--end",
                "1000",
                "--duration",
                "1",
            ],
        )

        # 创建 mock 引擎实例
        mock_instance = Mock()
        mock_instance.is_running.side_effect = [True, False, False]

        mock_stats = Mock()
        mock_stats.total_checked = 500
        mock_stats.elapsed = 1.0
        mock_stats.start_time = 1000
        mock_stats.format_elapsed = lambda: "0:00:01"
        mock_stats.format_speed = lambda: "500 次/秒"
        mock_stats.matches = []

        mock_instance.get_stats.return_value = mock_stats
        mock_instance.start = Mock()
        mock_instance.stop = Mock()

        # 直接 patch build_engine，跳过实际引擎创建
        with patch("src.cli.engine_runner.build_engine", return_value=(mock_instance, "cpu")):
            with patch("time.sleep", return_value=None):
                _time_call_count = [0]

                def _mock_time():
                    _time_call_count[0] += 1
                    return 1000 if _time_call_count[0] == 1 else 2000

                with patch("time.time", side_effect=_mock_time):
                    main()

        # 检查输出
        captured = capsys.readouterr()
        assert "开始对撞" in captured.out
        assert "对撞结束" in captured.out
        # Rich Panel 输出格式：「总检查数」后面是空格填充而非「 : 」
        assert "总检查数" in captured.out and "500" in captured.out

    def test_main_brute_force_mode(self, capsys, monkeypatch):
        """测试主程序暴力穷举模式"""
        # 模拟命令行参数
        monkeypatch.setattr(
            "sys.argv",
            [
                "cli.py",
                "-t",
                "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
                "-m",
                "brute_force",
                "--start",
                "1",
                "--duration",
                "1",
            ],
        )

        # 创建 mock 引擎实例
        mock_instance = Mock()
        mock_instance.is_running.side_effect = [True, False, False]

        mock_stats = Mock()
        mock_stats.total_checked = 2000
        mock_stats.elapsed = 1.0
        mock_stats.start_time = 1000
        mock_stats.format_elapsed = lambda: "0:00:01"
        mock_stats.format_speed = lambda: "2,000 次/秒"
        mock_stats.matches = []

        mock_instance.get_stats.return_value = mock_stats
        mock_instance.start = Mock()
        mock_instance.stop = Mock()

        # 直接 patch build_engine，跳过实际引擎创建
        with patch("src.cli.engine_runner.build_engine", return_value=(mock_instance, "cpu")):
            with patch("time.sleep", return_value=None):
                _time_call_count = [0]

                def _mock_time():
                    _time_call_count[0] += 1
                    return 1000 if _time_call_count[0] == 1 else 2000

                with patch("time.time", side_effect=_mock_time):
                    main()

        # 检查输出
        captured = capsys.readouterr()
        assert "开始对撞" in captured.out
        assert "对撞结束" in captured.out
        # Rich Panel 输出格式：「总检查数」后面是空格填充而非「 : 」
        assert "总检查数" in captured.out and "2,000" in captured.out

    def test_validate_args_gpu_mutual_exclusion(self):
        """测试GPU参数互斥性：--use-gpu 和 --multi-gpu 由 argparse mutually_exclusive_group 处理"""
        # 现在互斥性由 argparse 的 mutually_exclusive_group 自动处理，
        # parse_args() 在遇到两者同时存在时会直接 sys.exit(2)。
        with patch(
            "sys.argv",
            ["cli.py", "-t", "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "--use-gpu", "--multi-gpu"],
        ):
            with pytest.raises(SystemExit) as exc_info:
                parse_args()
            assert exc_info.value.code == 2

    def test_validate_args_checkpoint_interval_auto_enable(self):
        """测试 checkpoint-interval 非默认值时自动启用 checkpoint"""

        class Args:
            def __init__(self, **kwargs):
                self.targets = kwargs.get("targets", ["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"])
                self.file = None
                self.mode = "random"
                self.start = None
                self.end = None
                self.workers = 4
                self.duration = 60
                self.health_check = False
                self.platform_check = False
                self.cleanup = False
                self.validate_addresses = None
                self.use_gpu = False
                self.multi_gpu = False
                self.checkpoint = kwargs.get("checkpoint", False)
                self.checkpoint_interval = kwargs.get("checkpoint_interval", 30)
                self.dedup = kwargs.get("dedup", False)
                self.dedup_max_size = kwargs.get("dedup_max_size", 1000000)
                self.examples = False
                self.config_check = False
                self.quick_start = False

        args = Args(checkpoint=False, checkpoint_interval=60)
        result = validate_args(args)
        assert result is True
        assert args.checkpoint is True  # 应自动启用

    def test_validate_args_dedup_max_size_auto_enable(self):
        """测试 dedup-max-size 非默认值时自动启用 dedup"""

        class Args:
            def __init__(self, **kwargs):
                self.targets = kwargs.get("targets", ["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"])
                self.file = None
                self.mode = "random"
                self.start = None
                self.end = None
                self.workers = 4
                self.duration = 60
                self.health_check = False
                self.platform_check = False
                self.cleanup = False
                self.validate_addresses = None
                self.use_gpu = False
                self.multi_gpu = False
                self.checkpoint = False
                self.checkpoint_interval = 30
                self.dedup = kwargs.get("dedup", False)
                self.dedup_max_size = kwargs.get("dedup_max_size", 1000000)
                self.examples = False
                self.config_check = False
                self.quick_start = False

        args = Args(dedup=False, dedup_max_size=500000)
        result = validate_args(args)
        assert result is True
        assert args.dedup is True  # 应自动启用

    def test_quick_start_generates_command(self, monkeypatch, capsys):
        """测试 quick-start 生成正确的命令"""
        from src.cli.commands import _cmd_quick_start
        from io import StringIO
        from unittest.mock import MagicMock

        # 屏蔽 Windows 平台下 sys.stdout 被替换（避免 capsys 捕获失效）
        monkeypatch.setattr("sys.platform", "linux")
        # 同时 mock 掉 src.cli.commands 模块内的 sys.platform
        monkeypatch.setattr("src.cli.commands.sys.platform", "linux")
        # Windows 上 mock fcntl（Unix 文件锁），避免 No module named 'fcntl'
        mock_fcntl = MagicMock()
        monkeypatch.setitem(sys.modules, "fcntl", mock_fcntl)

        # 模拟用户输入：选择单个地址、输入地址、选random模式、启用checkpoint(Y)、启用dedup(Y)、时长选无限(1)、GPU选CPU模式(1)、不执行(n)
        inputs = iter(["1", "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "1", "Y", "Y", "1", "1", "n"])
        monkeypatch.setattr("builtins.input", lambda _="": next(inputs))

        # mock 掉 PlatformUtils.ensure_utf8_output，避免 StringIO 没有 buffer 属性报错
        monkeypatch.setattr(
            "src.utils.platform_utils.PlatformUtils.ensure_utf8_output", staticmethod(lambda: None)
        )
        # 使用 StringIO 手动捕获输出，避免 Windows 下 sys.stdout 被替换导致 capsys 失效
        buf = StringIO()
        monkeypatch.setattr("sys.stdout", buf)
        monkeypatch.setattr("src.cli.commands.sys.stdout", buf)
        _cmd_quick_start()
        output = buf.getvalue()
        assert "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa" in output
        assert "-m random" in output

    def test_import_compatibility(self):
        """确保拆分后的导入路径兼容"""
        # 旧路径（向后兼容）
        from src.cli.main import validate_args, format_progress

        # 新路径
        from src.cli.validation import validate_args as va
        from src.cli.progress import format_progress as fp

        # 验证是同一个函数对象
        assert validate_args is va
        assert format_progress is fp


# ─────────────────────────────────────────────────────────────────────────────
# 新增测试类
# ─────────────────────────────────────────────────────────────────────────────


class TestLoadConfigWithValidation:
    """配置加载测试"""

    def setup_method(self):
        """每个测试前重置 CLIOutput 和 LogWindow 单例，确保测试隔离"""
        from src.cli.output import CLIOutput

        CLIOutput.reset_instance()
        from src.cli.log_window import reset_log_window_instance

        reset_log_window_instance()

    @staticmethod
    def _get_config_loader_module():
        """Safety helper: 获取 src.cli.config_loader 模块对象（_project_root 在此模块）"""
        import importlib
        import sys as _sys

        mod = _sys.modules.get("src.cli.config_loader")
        if mod is None:
            mod = importlib.import_module("src.cli.config_loader")
        return mod

    def test_config_not_found(self, tmp_path, monkeypatch):
        """config.json不存在时返回None"""

        mod = self._get_config_loader_module()
        monkeypatch.setattr(mod, "_project_root", str(tmp_path))
        result = mod.load_config_with_validation()
        assert result is None

    def test_config_invalid_json(self, tmp_path, monkeypatch):
        """config.json JSON格式错误时返回None"""
        mod = self._get_config_loader_module()
        config_file = tmp_path / "config.json"
        config_file.write_text("{invalid json", encoding="utf-8")
        monkeypatch.setattr(mod, "_project_root", str(tmp_path))
        result = mod.load_config_with_validation()
        assert result is None

    def test_config_valid(self, tmp_path, monkeypatch):
        """正常config.json成功加载"""
        import json

        mod = self._get_config_loader_module()
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"crypto": {}, "collision": {}}), encoding="utf-8")
        monkeypatch.setattr(mod, "_project_root", str(tmp_path))
        result = mod.load_config_with_validation()
        assert isinstance(result, dict)
        assert "crypto" in result

    def test_config_not_dict(self, tmp_path, monkeypatch):
        """config.json根节点不是dict时返回None"""
        mod = self._get_config_loader_module()
        config_file = tmp_path / "config.json"
        config_file.write_text('["not", "a", "dict"]', encoding="utf-8")
        monkeypatch.setattr(mod, "_project_root", str(tmp_path))
        result = mod.load_config_with_validation()
        assert result is None

    def test_config_unicode_decode_error(self, tmp_path, monkeypatch):
        """文件编码非UTF-8时返回None"""
        import json as _json_mod

        mod = self._get_config_loader_module()
        config_file = tmp_path / "config.json"
        config_file.write_text(_json_mod.dumps({"crypto": {}}), encoding="utf-8")
        monkeypatch.setattr(mod, "_project_root", str(tmp_path))

        # mock builtins.open 使其在读取 config.json 时抛出 UnicodeDecodeError
        real_open = open

        def _mock_open(file, mode="r", **kw):
            if "config.json" in str(file) and "r" in str(mode):
                raise UnicodeDecodeError("utf-8", b"x", 0, 1, "mock")
            return real_open(file, mode, **kw)

        import builtins

        monkeypatch.setattr(builtins, "open", _mock_open)
        result = mod.load_config_with_validation()
        assert result is None

    def test_config_permission_error(self, tmp_path, monkeypatch):
        """文件无读取权限时返回None"""
        import json as _json_mod

        mod = self._get_config_loader_module()
        config_file = tmp_path / "config.json"
        config_file.write_text(_json_mod.dumps({"crypto": {}}), encoding="utf-8")
        monkeypatch.setattr(mod, "_project_root", str(tmp_path))

        real_open = open

        def _mock_open(file, mode="r", **kw):
            if "config.json" in str(file) and "r" in str(mode):
                raise PermissionError("permission denied")
            return real_open(file, mode, **kw)

        import builtins

        monkeypatch.setattr(builtins, "open", _mock_open)
        result = mod.load_config_with_validation()
        assert result is None

    def test_config_generic_exception(self, tmp_path, monkeypatch):
        """json.load 抛出通用异常时返回None"""
        import json as _json_mod

        mod = self._get_config_loader_module()
        config_file = tmp_path / "config.json"
        config_file.write_text(_json_mod.dumps({"crypto": {}}), encoding="utf-8")
        monkeypatch.setattr(mod, "_project_root", str(tmp_path))
        monkeypatch.setattr(
            _json_mod, "load",
            lambda f: (_ for _ in ()).throw(Exception("unexpected")),
        )
        result = mod.load_config_with_validation()
        assert result is None

    def test_config_explicit_path(self, tmp_path, monkeypatch):
        """传入显式 config_file 路径时使用该路径加载"""
        import json as _json_mod

        mod = self._get_config_loader_module()
        config_file = tmp_path / "my_config.json"
        config_file.write_text(
            _json_mod.dumps({"crypto": {}, "collision": {}}), encoding="utf-8"
        )
        monkeypatch.setattr(mod, "_project_root", str(tmp_path))
        result = mod.load_config_with_validation(str(config_file))
        assert isinstance(result, dict)
        assert "crypto" in result

    def test_config_path_traversal_blocked(self, tmp_path, monkeypatch):
        """config_file 路径在项目目录外 → 拒绝加载, 返回 None"""
        mod = self._get_config_loader_module()
        # 设置 project_root 为 tmp_path
        monkeypatch.setattr(mod, "_project_root", str(tmp_path))
        # 提供一个项目目录外的路径
        outside_path = tmp_path.parent / "outside_config.json"
        result = mod.load_config_with_validation(str(outside_path))
        assert result is None

    def test_module_sys_path_insert(self, monkeypatch):
        """模块首次加载时 _project_root 不在 sys.path → sys.path.insert (L16)。"""
        import importlib
        import sys

        mod = self._get_config_loader_module()
        project_root = mod._project_root

        # 1. 从 sys.modules 移除
        sys.modules.pop("src.cli.config_loader", None)
        # 2. 临时从 sys.path 移除项目根目录
        original_path = list(sys.path)
        sys.path = [p for p in sys.path if p != project_root]
        try:
            # 3. 重新导入，触发 L16
            new_mod = importlib.import_module("src.cli.config_loader")
            assert new_mod is not None
            assert hasattr(new_mod, "_project_root")
            assert project_root in sys.path  # 验证 L16 insert 已执行
        finally:
            sys.path[:] = original_path
            # 恢复模块
            sys.modules.pop("src.cli.config_loader", None)
            importlib.import_module("src.cli.config_loader")


class TestBuildEngine:
    """引擎构建测试"""

    def setup_method(self):
        """每个测试前重置 CLIOutput 和 LogWindow 单例，确保测试隔离"""
        from src.cli.output import CLIOutput

        CLIOutput.reset_instance()
        from src.cli.log_window import reset_log_window_instance

        reset_log_window_instance()

    def test_build_cpu_engine(self, monkeypatch):
        """默认构建CPU引擎"""
        from unittest.mock import Mock
        import src.cli.engine_builder as eb

        mock_engine = Mock()
        monkeypatch.setattr(eb, "KeyCollisionEngine", lambda **kwargs: mock_engine)

        class MockArgs:
            use_gpu = False
            multi_gpu = False
            no_optimize = False
            window_size = 8
            no_simd = False
            no_memory_pool = False
            workers = 2
            checkpoint = False
            checkpoint_interval = 30
            dedup = False
            dedup_max_size = 1000000

        targets = {"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"}
        engine, engine_type = eb.build_engine(MockArgs(), targets)
        assert engine_type == "cpu"
        assert engine is mock_engine

    def test_build_gpu_when_unavailable(self, monkeypatch):
        """GPU不可用时请求GPU引擎应抛出GPUNotAvailableError"""
        import src.cli.engine_builder as eb

        monkeypatch.setattr(eb, "GPU_AVAILABLE", False)

        class MockArgs:
            use_gpu = True
            multi_gpu = False

        with pytest.raises(eb.GPUNotAvailableError):
            eb.build_engine(MockArgs(), {"addr1"})

    def test_build_multi_gpu_when_unavailable(self, monkeypatch):
        """GPU不可用时请求多GPU引擎应抛出GPUNotAvailableError"""
        import src.cli.engine_builder as eb

        monkeypatch.setattr(eb, "GPU_AVAILABLE", False)

        class MockArgs:
            use_gpu = False
            multi_gpu = True

        with pytest.raises(eb.GPUNotAvailableError):
            eb.build_engine(MockArgs(), {"addr1"})


class TestUtilityCommands:
    """工具命令测试"""

    def setup_method(self):
        """每个测试前重置 CLIOutput 和 LogWindow 单例，确保测试隔离"""
        from src.cli.output import CLIOutput

        CLIOutput.reset_instance()
        from src.cli.log_window import reset_log_window_instance

        reset_log_window_instance()

    def test_examples_output(self, monkeypatch):
        """--examples 输出包含示例命令"""
        from io import StringIO
        from src.cli.commands import _cmd_examples

        monkeypatch.setattr("sys.platform", "linux")
        import src.cli.commands as cmd_mod

        monkeypatch.setattr(cmd_mod.sys, "platform", "linux")
        # mock 掉 ensure_utf8_output，避免 StringIO 没有 buffer 属性报错
        monkeypatch.setattr(
            "src.utils.platform_utils.PlatformUtils.ensure_utf8_output", staticmethod(lambda: None)
        )
        buf = StringIO()
        monkeypatch.setattr(cmd_mod.sys, "stdout", buf)
        _cmd_examples()
        output = buf.getvalue()
        assert "random" in output
        assert "-t" in output
        assert "--use-gpu" in output

    def test_config_check_missing(self, monkeypatch, tmp_path):
        """config.json不存在时config-check报告缺失"""
        from io import StringIO
        from src.cli.commands import _cmd_config_check

        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr("sys.platform", "linux")
        import src.cli.commands as cmd_mod

        monkeypatch.setattr(cmd_mod.sys, "platform", "linux")
        # mock 掉 ensure_utf8_output，避免 StringIO 没有 buffer 属性报错
        monkeypatch.setattr(
            "src.utils.platform_utils.PlatformUtils.ensure_utf8_output", staticmethod(lambda: None)
        )
        buf = StringIO()
        monkeypatch.setattr(cmd_mod.sys, "stdout", buf)
        _cmd_config_check()
        output = buf.getvalue()
        # 不存在时输出含 ❌ 和 不存在
        assert "不存在" in output or "config.json" in output

    def test_config_check_valid(self, monkeypatch, tmp_path):
        """config.json有效时config-check通过"""
        import json
        from io import StringIO
        from src.cli.commands import _cmd_config_check

        config_file = tmp_path / "config.json"
        config_file.write_text(
            json.dumps({"crypto": {}, "collision": {}, "logging": {}}), encoding="utf-8"
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr("sys.platform", "linux")
        import src.cli.commands as cmd_mod

        monkeypatch.setattr(cmd_mod.sys, "platform", "linux")
        # mock 掉 ensure_utf8_output，避免 StringIO 没有 buffer 属性报错
        monkeypatch.setattr(
            "src.utils.platform_utils.PlatformUtils.ensure_utf8_output", staticmethod(lambda: None)
        )
        buf = StringIO()
        monkeypatch.setattr(cmd_mod.sys, "stdout", buf)
        _cmd_config_check()
        output = buf.getvalue()
        assert len(output) > 0
        assert "config.json" in output

    def test_validate_addresses_file_not_found(self, monkeypatch, tmp_path):
        """验证不存在的地址文件时应触发 SystemExit"""
        from src.cli.commands import _cmd_validate_addresses

        # 使用 tmp_path 下不存在的路径（tmp_path 是真实绝对路径，且文件不存在）
        nonexistent = str(tmp_path / "nonexistent_test_addresses_xyz.txt")
        # validate_file_path 遇到不存在文件会返回 False，_cmd_validate_addresses 中
        # validate_file_path 返回 False 后直接 return，因此需要让文件通过路径检查但不存在
        # 方案: mock validate_file_path 返回 True，让代码走到文件不存在的分支抛 SystemExit
        with patch("src.cli.commands.validate_file_path", return_value=True):
            with pytest.raises(SystemExit):
                _cmd_validate_addresses(nonexistent)


class TestAdvancedFeatures:
    """高级功能测试"""

    def setup_method(self):
        """每个测试前重置 CLIOutput 和 LogWindow 单例，确保测试隔离"""
        from src.cli.output import CLIOutput

        CLIOutput.reset_instance()
        from src.cli.log_window import reset_log_window_instance

        reset_log_window_instance()

    def test_apply_template_valid(self, tmp_path):
        """应用合法模板成功"""
        import json
        from src.cli.advanced_features import apply_template

        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"crypto": {}}), encoding="utf-8")
        result = apply_template("quick-test", str(config_file))
        assert result is True
        with open(config_file, "r", encoding="utf-8") as f:
            config = json.load(f)
        assert isinstance(config, dict)
        # quick-test 模板应写入 collision 段
        assert "collision" in config

    def test_apply_template_invalid_name(self):
        """不存在的模板名返回False"""
        from src.cli.advanced_features import apply_template

        result = apply_template("nonexistent-template")
        assert result is False

    def test_recommend_parameters(self):
        """参数推荐返回正确结构"""
        from src.cli.advanced_features import recommend_parameters

        class MockArgs:
            targets = ["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"]
            file = None
            mode = "random"
            use_gpu = False
            multi_gpu = False
            start = None
            end = None

        result = recommend_parameters(MockArgs())
        assert "recommendations" in result
        assert "reasons" in result
        assert isinstance(result["recommendations"], list)
        assert isinstance(result["reasons"], list)

    def test_export_progress_data(self, tmp_path):
        """导出进度数据到JSON文件"""
        import json
        from unittest.mock import Mock
        from src.cli.advanced_features import export_progress_data

        mock_stats = Mock()
        mock_stats.total_checked = 1000
        mock_stats.elapsed = 10.0
        mock_stats.start_time = 1000
        mock_stats.matches = []
        mock_stats.format_elapsed = lambda: "0:00:10"
        mock_stats.format_speed = lambda: "100 次/秒"

        output_file = str(tmp_path / "progress.json")
        result = export_progress_data(mock_stats, "random", "cpu", output_file)
        assert result is True

        with open(output_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["total_checked"] == 1000

    def test_export_matches(self, tmp_path):
        """导出匹配结果"""
        import json
        from src.cli.advanced_features import export_matches

        matches = [{"address": "1A1z...", "private_key": "abc123", "wif": "5J..."}]
        output_file = str(tmp_path / "matches.json")
        result = export_matches(matches, output_file)
        assert result is True

        with open(output_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert len(data["matches"]) == 1


class TestSecurity:
    """安全性测试"""

    def setup_method(self):
        """每个测试前重置 CLIOutput 和 LogWindow 单例，确保测试隔离"""
        from src.cli.output import CLIOutput

        CLIOutput.reset_instance()
        from src.cli.log_window import reset_log_window_instance

        reset_log_window_instance()

    def test_file_path_traversal_blocked(self):
        """路径遍历攻击被阻止"""
        from src.cli.validation import validate_file_path

        # 尝试访问项目目录之外的路径
        result = validate_file_path("../../../etc/passwd")
        assert result is False

    def test_private_key_masking(self, monkeypatch, capsys):
        """私钥脱敏模式正常工作"""
        import src.cli.engine_builder as eb

        # on_match_callback 现在是工厂函数，通过参数指定脱敏模式
        callback = eb.on_match_callback(sensitive_mode="masked")

        test_key = bytes.fromhex("0123456789abcdef" * 4)
        callback(test_key, "1TestAddress", "5JTestWIF12345678")

        captured = capsys.readouterr()
        full_hex = test_key.hex()
        # hash_only 模式下不应包含完整私钥（stdout 非 TTY）
        assert full_hex not in captured.out
        # 应包含 SHA256 哈希前缀标记
        assert "[SHA256:" in captured.out


class TestModuleExports:
    """模块导出完整性测试"""

    def setup_method(self):
        """每个测试前重置 CLIOutput 和 LogWindow 单例，确保测试隔离"""
        from src.cli.output import CLIOutput

        CLIOutput.reset_instance()
        from src.cli.log_window import reset_log_window_instance

        reset_log_window_instance()

    def test_all_public_api_importable(self):
        """__all__ 中所有符号可导入"""
        from src.cli import __all__
        import src.cli as cli_module

        for name in __all__:
            assert hasattr(cli_module, name), f"缺失导出: {name}"

    def test_advanced_features_importable(self):
        """高级功能API可从__init__导入"""
        from src.cli import (
            apply_template,
            recommend_parameters,
        )

        assert callable(apply_template)
        assert callable(recommend_parameters)


class TestV3Improvements:
    """V3版本新增功能测试"""

    def setup_method(self):
        """每个测试前重置 CLIOutput 和 LogWindow 单例，确保测试隔离"""
        from src.cli.output import CLIOutput

        CLIOutput.reset_instance()
        from src.cli.log_window import reset_log_window_instance

        reset_log_window_instance()

    # ── 通用 Args 构建辅助 ───────────────────────────────────────────────────
    @staticmethod
    def _make_args(**kwargs):
        """构造最小合法 Args 对象，支持覆盖任意字段"""

        class Args:
            pass

        a = Args()
        # 基本必填字段
        a.targets = kwargs.get("targets", ["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"])
        a.file = kwargs.get("file", None)
        a.mode = kwargs.get("mode", "random")
        a.start = kwargs.get("start", None)
        a.end = kwargs.get("end", None)
        a.workers = kwargs.get("workers", 4)
        a.duration = kwargs.get("duration", 60)
        # 工具命令标志
        a.health_check = kwargs.get("health_check", False)
        a.platform_check = kwargs.get("platform_check", False)
        a.cleanup = kwargs.get("cleanup", False)
        a.validate_addresses = kwargs.get("validate_addresses", None)
        a.examples = kwargs.get("examples", False)
        a.config_check = kwargs.get("config_check", False)
        a.quick_start = kwargs.get("quick_start", False)
        # GPU 参数
        a.use_gpu = kwargs.get("use_gpu", False)
        a.multi_gpu = kwargs.get("multi_gpu", False)
        # 断点 / 去重
        a.checkpoint = kwargs.get("checkpoint", False)
        a.checkpoint_interval = kwargs.get("checkpoint_interval", 30)
        a.dedup = kwargs.get("dedup", False)
        a.dedup_max_size = kwargs.get("dedup_max_size", 1000000)
        # 性能优化
        a.window_size = kwargs.get("window_size", 8)
        a.no_optimize = kwargs.get("no_optimize", False)
        a.no_simd = kwargs.get("no_simd", False)
        a.no_memory_pool = kwargs.get("no_memory_pool", False)
        # 安全模式
        a.sensitive_mode = kwargs.get("sensitive_mode", "masked")
        return a

    # ── 测试 1: window_size 范围验证 ────────────────────────────────────────
    def test_window_size_validation(self):
        """window-size 超出 4-8 范围时 validate_args 返回 False"""
        from src.cli.validation import validate_args

        # 低于最小值 4
        args = self._make_args(window_size=3)
        assert validate_args(args) is False

        # 高于最大值 8
        args = self._make_args(window_size=10)
        assert validate_args(args) is False

        # 合法值 6 应通过
        args = self._make_args(window_size=6)
        assert validate_args(args) is True

    # ── 测试 2: sensitive_mode 参数解析 ─────────────────────────────────────
    def test_sensitive_mode_parameter(self, monkeypatch):
        """--sensitive-mode 参数解析正确，默认值为 masked"""
        # masked 模式
        monkeypatch.setattr(
            "sys.argv",
            ["cli.py", "-t", "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "--sensitive-mode", "masked"],
        )
        args = parse_args()
        assert args.sensitive_mode == "masked"

        # hash_only 模式
        monkeypatch.setattr(
            "sys.argv",
            ["cli.py", "-t", "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "--sensitive-mode", "hash_only"],
        )
        args = parse_args()
        assert args.sensitive_mode == "hash_only"

        # 未指定时默认 masked (v4.5.0: 安全优先，默认脱敏)
        monkeypatch.setattr("sys.argv", ["cli.py", "-t", "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"])
        args = parse_args()
        assert args.sensitive_mode == "masked"

    @staticmethod
    def _get_main_mod():
        """安全获取 src.cli.main 模块对象（与 TestLoadConfigWithValidation 相同惯例）"""
        import importlib
        import sys as _sys

        mod = _sys.modules.get("src.cli.main")
        if mod is None or not hasattr(mod, "_print_final_summary"):
            mod = importlib.import_module("src.cli.main")
        return mod

    # ── 测试 3: export_progress 集成 ─────────────────────────────────────────
    def test_export_progress_integration(self, monkeypatch, tmp_path, capsys):
        """_print_final_summary 在 args.export_progress 有值时调用 export_progress_data"""
        # _print_final_summary 在 stats_reporter 模块中，且 export_progress_data 也从该模块引用
        import src.cli.stats_reporter as stats_reporter_mod
        from src.cli.stats_reporter import _print_final_summary as print_summary

        # mock engine
        mock_stats = Mock()
        mock_stats.total_checked = 500
        mock_stats.elapsed = 5.0
        mock_stats.matches = []
        mock_stats.format_elapsed = lambda: "0:00:05"
        mock_stats.format_speed = lambda: "100 次/秒"

        mock_engine = Mock()
        mock_engine.get_stats.return_value = mock_stats

        # mock export_progress_data，追踪调用（需 patch stats_reporter 模块中的引用）
        called = []

        def fake_export_progress(stats, mode, engine_type, output_file, *args, **kwargs):
            called.append((engine_type, output_file))
            return True

        monkeypatch.setattr(stats_reporter_mod, "export_progress_data", fake_export_progress)

        export_file = str(tmp_path / "progress.json")
        args_obj = self._make_args()
        args_obj.export_progress = export_file
        args_obj.export_matches = None

        print_summary(mock_engine, "cpu", args_obj)

        assert len(called) == 1, "export_progress_data 应被调用一次"
        assert called[0][1] == export_file

    # ── 测试 4: export_matches 集成 ─────────────────────────────────────────
    def test_export_matches_integration(self, monkeypatch, tmp_path, capsys):
        """_print_final_summary 在 args.export_matches 有值时调用 export_matches"""
        import src.cli.stats_reporter as stats_reporter_mod
        from src.cli.stats_reporter import _print_final_summary as print_summary

        mock_stats = Mock()
        mock_stats.total_checked = 300
        mock_stats.elapsed = 3.0
        mock_stats.matches = []
        mock_stats.format_elapsed = lambda: "0:00:03"
        mock_stats.format_speed = lambda: "100 次/秒"

        mock_engine = Mock()
        mock_engine.get_stats.return_value = mock_stats

        # mock export_matches，追踪调用（需 patch stats_reporter 模块中的引用）
        called = []

        def fake_export_matches(matches, output_file, *args, **kwargs):
            called.append((matches, output_file))
            return True

        monkeypatch.setattr(stats_reporter_mod, "export_matches", fake_export_matches)

        export_file = str(tmp_path / "matches.json")
        args_obj = self._make_args()
        args_obj.export_progress = None
        args_obj.export_matches = export_file

        print_summary(mock_engine, "cpu", args_obj)

        assert len(called) == 1, "export_matches 应被调用一次"
        assert called[0][1] == export_file

    # ── 测试 5: 超大范围警告 ─────────────────────────────────────────────────
    def test_large_range_warning(self, capsys):
        """range 模式中搜索范围超过 2^64 时输出增强警告信息（含预估时间和建议）"""
        from src.cli.validation import validate_args

        # 构造一个范围超过 2^64 的 range 模式参数
        # start = 1, end = 1 + 2^64 + 1000（确保 total_range > 2^64）
        start_val = 1
        end_val = start_val + (2**64) + 1000
        args = self._make_args(
            mode="range",
            start=hex(start_val)[2:],
            end=hex(end_val)[2:],
        )
        result = validate_args(args)
        # validate_args 在超大范围时仍返回 True（只是警告，不拒绝）
        assert result is True

        captured = capsys.readouterr()
        combined = captured.out + captured.err
        # 应包含小时数预估
        assert "小时" in combined
        # 应包含 GPU 建议
        assert "GPU" in combined or "建议" in combined

    # ── 测试 6: hash_only 模式回调 ────────────────────────────────────────────
    def test_sensitive_mode_hash_only(self, capsys):
        """on_match_callback 工厂在 hash_only 模式下输出哈希前缀而非完整私钥"""
        import src.cli.engine_builder as eb

        # 通过工厂函数获取 hash_only 回调
        callback = eb.on_match_callback(sensitive_mode="hash_only")

        test_key = bytes.fromhex("0123456789abcdef" * 4)
        full_hex = test_key.hex()

        callback(test_key, "1TestAddress", "5JTestWIF12345678")

        captured = capsys.readouterr()
        # hash_only 模式不应出现完整私钥十六进制
        assert full_hex not in captured.out
        # 应包含 SHA256 哈希标识
        assert "SHA256" in captured.out
        # WIF 应被隐藏
        assert "已隐藏" in captured.out


class TestCLIOutput:
    """CLIOutput 输出管理器测试"""

    def setup_method(self):
        """每个测试前重置 CLIOutput 单例"""
        from src.cli.output import CLIOutput

        CLIOutput.reset_instance()
        from src.cli.log_window import reset_log_window_instance

        reset_log_window_instance()

    def teardown_method(self):
        """每个测试后重置单例"""
        from src.cli.output import CLIOutput

        CLIOutput.reset_instance()

    def test_output_rule_method(self, capsys):
        """rule 方法输出分隔线"""
        from src.cli.output import CLIOutput

        out = CLIOutput()
        out.rule("测试标题")
        captured = capsys.readouterr()
        assert "测试标题" in captured.out

    def test_output_header_method(self, capsys):
        """header 方法输出大标题分隔线"""
        from src.cli.output import CLIOutput

        out = CLIOutput()
        out.header("大标题")
        captured = capsys.readouterr()
        assert "大标题" in captured.out

    def test_output_startup_panel(self, capsys):
        """startup_panel 输出配置面板"""
        from src.cli.output import CLIOutput

        out = CLIOutput()
        out.startup_panel({"模式": "random", "目标": "1A1z..."})
        captured = capsys.readouterr()
        assert "random" in captured.out or "启动配置" in captured.out

    def test_output_final_summary(self, capsys):
        """final_summary 输出最终统计面板"""
        from src.cli.output import CLIOutput

        out = CLIOutput()
        out.final_summary("运行结果", {"总检查数": "1,000", "匹配数": "0"})
        captured = capsys.readouterr()
        assert "运行结果" in captured.out
        assert "总检查数" in captured.out

    def test_output_status_line(self, capsys):
        """status_line 输出单行状态"""
        from src.cli.output import CLIOutput

        out = CLIOutput()
        out.status_line("正在处理...")
        captured = capsys.readouterr()
        assert "正在处理" in captured.out

    def test_output_performance_status(self, capsys):
        """performance_status 输出性能状态"""
        from src.cli.output import CLIOutput

        out = CLIOutput()
        out.performance_status({
            "speed": 10000,
            "keys_total": 50000,
            "gpu_usage": 85,
            "memory_used": 2048,
        })
        captured = capsys.readouterr()
        assert "speed" in captured.out or "速度" in captured.out

    def test_output_quiet_mode_suppression(self, capsys):
        """quiet 模式下 info 不输出"""
        from src.cli.output import CLIOutput

        CLIOutput.reset_instance()
        out = CLIOutput.init(quiet=True)
        out.info("这条消息不应该出现")
        captured = capsys.readouterr()
        assert "不应该出现" not in captured.out

    def test_output_info_non_quiet(self, capsys):
        """非 quiet 模式下 info 正常输出"""
        from src.cli.output import CLIOutput

        CLIOutput.reset_instance()
        out = CLIOutput()
        out.info("信息消息")
        captured = capsys.readouterr()
        assert "信息消息" in captured.out
        assert "INFO" in captured.out

    def test_output_hint(self, capsys):
        """hint 方法输出提示信息"""
        from src.cli.output import CLIOutput

        CLIOutput.reset_instance()
        out = CLIOutput()
        out.hint("这是一条提示")
        captured = capsys.readouterr()
        assert "这是一条提示" in captured.out
        assert "HINT" in captured.out

    def test_output_warning_with_details(self, capsys):
        """warning 带 details 参数时输出详细信息"""
        from src.cli.output import CLIOutput

        CLIOutput.reset_instance()
        out = CLIOutput()
        out.warning("磁盘空间不足", details="剩余 100MB")
        captured = capsys.readouterr()
        assert "磁盘空间不足" in captured.out or "磁盘空间不足" in captured.err
        assert "剩余 100MB" in captured.out or "剩余 100MB" in captured.err

    def test_output_error_with_details(self, capsys):
        """error 带 details 参数时输出详细信息"""
        from src.cli.output import CLIOutput

        CLIOutput.reset_instance()
        out = CLIOutput()
        out.error("配置加载失败", details="JSON 语法错误")
        captured = capsys.readouterr()
        assert "配置加载失败" in captured.out or "配置加载失败" in captured.err
        assert "JSON 语法错误" in captured.out or "JSON 语法错误" in captured.err

    def test_output_print_always(self, capsys):
        """print_always 始终输出"""
        from src.cli.output import CLIOutput

        CLIOutput.reset_instance()
        out = CLIOutput()
        out.print_always("始终可见")
        captured = capsys.readouterr()
        assert "始终可见" in captured.out

    def test_output_startup_panel_quiet(self, capsys):
        """quiet 模式下 startup_panel 不输出"""
        from src.cli.output import CLIOutput

        CLIOutput.reset_instance()
        out = CLIOutput.init(quiet=True)
        out.startup_panel({"模式": "random"})
        captured = capsys.readouterr()
        assert "random" not in captured.out
        assert "启动配置" not in captured.out

    def test_output_stats_panel(self, capsys):
        """stats_panel 输出自定义统计面板"""
        from src.cli.output import CLIOutput

        CLIOutput.reset_instance()
        out = CLIOutput()
        out.stats_panel("性能统计", [
            ("速度", "10,000/s"),
            ("GPU 温度", "65°C", "yellow"),
        ])
        captured = capsys.readouterr()
        assert "性能统计" in captured.out
        assert "10,000/s" in captured.out
        assert "65°C" in captured.out

    def test_output_status_line_quiet(self, capsys):
        """quiet 模式下 status_line 不输出"""
        from src.cli.output import CLIOutput

        CLIOutput.reset_instance()
        out = CLIOutput.init(quiet=True)
        out.status_line("正在处理...")
        captured = capsys.readouterr()
        assert "正在处理" not in captured.out

    def test_output_performance_status_quiet(self, capsys):
        """quiet 模式下 performance_status 不输出"""
        from src.cli.output import CLIOutput

        CLIOutput.reset_instance()
        out = CLIOutput.init(quiet=True)
        out.performance_status({"speed": 5000, "keys_total": 100000})
        captured = capsys.readouterr()
        assert "性能状态" not in captured.out


class TestPagination:
    """PaginationManager 分页管理器测试"""

    def setup_method(self):
        """每个测试前重置 CLIOutput 单例"""
        from src.cli.output import CLIOutput

        CLIOutput.reset_instance()
        from src.cli.log_window import reset_log_window_instance

        reset_log_window_instance()

    def test_pagination_init(self):
        """初始化分页管理器，计算 total_pages"""
        from src.cli.pagination import PaginationManager

        pm = PaginationManager(list(range(25)), page_size=10)
        assert pm.current_page == 1
        assert pm.total_pages == 3
        assert pm.page_size == 10
        assert len(pm.items) == 25

    def test_pagination_init_empty(self):
        """空列表初始化 total_pages=0"""
        from src.cli.pagination import PaginationManager

        pm = PaginationManager([], page_size=10)
        assert pm.current_page == 1
        assert pm.total_pages == 0

    def test_pagination_get_current_page(self):
        """get_current_page_items 返回当前页数据"""
        from src.cli.pagination import PaginationManager

        pm = PaginationManager(list(range(25)), page_size=10)
        items = pm.get_current_page_items()
        assert items == list(range(10))

    def test_pagination_get_current_page_last(self):
        """最后一页数据量不足 page_size"""
        from src.cli.pagination import PaginationManager

        pm = PaginationManager(list(range(25)), page_size=10)
        pm.go_to_page(3)
        items = pm.get_current_page_items()
        assert items == list(range(20, 25))

    def test_pagination_next_page_success(self):
        """next_page 成功翻页"""
        from src.cli.pagination import PaginationManager

        pm = PaginationManager(list(range(25)), page_size=10)
        result = pm.next_page()
        assert result is True
        assert pm.current_page == 2

    def test_pagination_next_page_at_last(self):
        """最后一页时 next_page 返回 False"""
        from src.cli.pagination import PaginationManager

        pm = PaginationManager(list(range(25)), page_size=10)
        pm.go_to_page(3)
        result = pm.next_page()
        assert result is False
        assert pm.current_page == 3

    def test_pagination_previous_page_success(self):
        """previous_page 成功翻页"""
        from src.cli.pagination import PaginationManager

        pm = PaginationManager(list(range(25)), page_size=10)
        pm.go_to_page(2)
        result = pm.previous_page()
        assert result is True
        assert pm.current_page == 1

    def test_pagination_previous_page_at_first(self):
        """第一页时 previous_page 返回 False"""
        from src.cli.pagination import PaginationManager

        pm = PaginationManager(list(range(25)), page_size=10)
        result = pm.previous_page()
        assert result is False
        assert pm.current_page == 1

    def test_pagination_go_to_page_valid(self):
        """跳转到有效页"""
        from src.cli.pagination import PaginationManager

        pm = PaginationManager(list(range(25)), page_size=10)
        result = pm.go_to_page(2)
        assert result is True
        assert pm.current_page == 2

    def test_pagination_go_to_page_invalid_low(self):
        """跳转到第 0 页返回 False"""
        from src.cli.pagination import PaginationManager

        pm = PaginationManager(list(range(25)), page_size=10)
        result = pm.go_to_page(0)
        assert result is False
        assert pm.current_page == 1

    def test_pagination_go_to_page_invalid_high(self):
        """跳转到超出范围页返回 False"""
        from src.cli.pagination import PaginationManager

        pm = PaginationManager(list(range(25)), page_size=10)
        result = pm.go_to_page(999)
        assert result is False
        assert pm.current_page == 1

    def test_pagination_info(self):
        """get_pagination_info 返回完整分页信息"""
        from src.cli.pagination import PaginationManager

        pm = PaginationManager(list(range(25)), page_size=10)
        info = pm.get_pagination_info()
        assert info["current_page"] == 1
        assert info["total_pages"] == 3
        assert info["total_items"] == 25
        assert info["page_size"] == 10
        assert info["has_next"] is True
        assert info["has_previous"] is False

    def test_pagination_info_last_page(self):
        """最后一页时 has_next=False, has_previous=True"""
        from src.cli.pagination import PaginationManager

        pm = PaginationManager(list(range(25)), page_size=10)
        pm.go_to_page(3)
        info = pm.get_pagination_info()
        assert info["has_next"] is False
        assert info["has_previous"] is True

    def test_pagination_single_page(self):
        """单页数据验证 has_next/has_previous 均为 False"""
        from src.cli.pagination import PaginationManager

        pm = PaginationManager([1, 2, 3], page_size=10)
        info = pm.get_pagination_info()
        assert info["total_pages"] == 1
        assert info["has_next"] is False
        assert info["has_previous"] is False


class TestOptimizationCLI:
    """optimization_cli 优化设置命令行测试"""

    def setup_method(self):
        from src.cli.output import CLIOutput

        CLIOutput.reset_instance()
        from src.cli.log_window import reset_log_window_instance

        reset_log_window_instance()

    def test_print_settings(self, monkeypatch, capsys):
        """print_settings 输出当前优化设置"""
        from unittest.mock import Mock

        mock_config = Mock()
        mock_config.get_all.return_value = {
            "delta_stats_flush_interval": 30,
            "aggregator_interval": 10,
            "monitor_interval": 5,
        }
        monkeypatch.setattr(
            "src.cli.optimization_cli.get_optimization_config",
            lambda: mock_config,
        )
        monkeypatch.setattr(
            "src.cli.optimization_cli.is_feature_enabled",
            lambda f: {
                "delta_stats": True,
                "distributed_aggregator": False,
                "performance_monitor": True,
            }.get(f, False),
        )

        from src.cli.optimization_cli import print_settings

        print_settings()
        captured = capsys.readouterr()
        assert "优化设置" in captured.out
        assert "增量统计优化" in captured.out
        assert "30" in captured.out

    def test_main_default_shows_settings(self, monkeypatch, capsys):
        """main 默认运行 print_settings"""
        from unittest.mock import Mock

        mock_config = Mock()
        mock_config.get_all.return_value = {}
        monkeypatch.setattr(
            "src.cli.optimization_cli.get_optimization_config",
            lambda: mock_config,
        )
        monkeypatch.setattr(
            "src.cli.optimization_cli.is_feature_enabled",
            lambda f: False,
        )
        monkeypatch.setattr("sys.argv", ["optimization_cli.py"])

        from src.cli.optimization_cli import main

        main()
        captured = capsys.readouterr()
        assert "优化设置" in captured.out

    def test_main_enable_feature(self, monkeypatch, capsys):
        """main --enable 启用功能"""
        import src.cli.optimization_cli as opt_mod

        called = []

        def fake_enable(feature):
            called.append(feature)

        monkeypatch.setattr(opt_mod, "enable_feature", fake_enable)
        monkeypatch.setattr(opt_mod, "get_optimization_config", lambda: Mock(get_all=lambda: {}))
        monkeypatch.setattr(opt_mod, "is_feature_enabled", lambda f: False)
        monkeypatch.setattr("sys.argv", ["optimization_cli.py", "--enable", "delta_stats"])

        opt_mod.main()
        captured = capsys.readouterr()
        assert "已启用" in captured.out
        assert "delta_stats" in called

    def test_main_disable_feature(self, monkeypatch, capsys):
        """main --disable 禁用功能"""
        import src.cli.optimization_cli as opt_mod

        called = []

        def fake_disable(feature):
            called.append(feature)

        monkeypatch.setattr(opt_mod, "disable_feature", fake_disable)
        monkeypatch.setattr(opt_mod, "get_optimization_config", lambda: Mock(get_all=lambda: {}))
        monkeypatch.setattr(opt_mod, "is_feature_enabled", lambda f: False)
        monkeypatch.setattr("sys.argv", ["optimization_cli.py", "--disable", "performance_monitor"])

        opt_mod.main()
        captured = capsys.readouterr()
        assert "已禁用" in captured.out
        assert "performance_monitor" in called

    def test_main_list_features(self, monkeypatch, capsys):
        """main --list 列出可用功能"""
        import src.cli.optimization_cli as opt_mod

        monkeypatch.setattr(opt_mod, "get_optimization_config", lambda: Mock(get_all=lambda: {}))
        monkeypatch.setattr(opt_mod, "is_feature_enabled", lambda f: False)
        monkeypatch.setattr("sys.argv", ["optimization_cli.py", "--list"])

        opt_mod.main()
        captured = capsys.readouterr()
        assert "可用的优化功能" in captured.out
        assert "delta_stats" in captured.out


# ============================================================================
# _print_final_summary stats 异常测试
# ============================================================================


class TestPrintFinalSummaryException:
    """_print_final_summary else 分支 stats 获取异常 (L111-113) 测试"""

    def setup_method(self):
        from src.cli.output import CLIOutput
        CLIOutput.reset_instance()
        from src.cli.log_window import reset_log_window_instance
        reset_log_window_instance()

    def test_stats_get_exception_graceful(self, monkeypatch):
        """engine.get_stats() 抛异常 → 显示 '统计信息暂不可用'。"""
        from src.cli.stats_reporter import _print_final_summary
        from src.cli.output import CLIOutput

        engine = Mock()
        engine.get_stats.side_effect = RuntimeError("stats unavailable")

        args = Mock()
        args.export_progress = None
        args.export_matches = None

        # 确保 CLIOutput 可用
        CLIOutput.reset_instance()

        with patch("builtins.print"):
            _print_final_summary(engine, "cpu", args)
        # 不应抛出异常

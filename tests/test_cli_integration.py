#!/usr/bin/env python3
"""
CLI 集成测试

覆盖范围：
- TestCLIEndToEnd:         参数解析->验证->执行完整流
- TestGPUIntegration:      GPU引擎构建与降级
- TestPerformanceBenchmark: 关键路径性能基准
- TestEdgeCases:           边界条件与并发安全
- TestConfigMigration:     配置版本迁移工具
"""

import json
import os
import sys
import threading
import time
from io import StringIO
from unittest.mock import Mock, patch

import pytest

# 确保项目根目录在 sys.path
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.cli.advanced_features import (  # noqa: E402
    GPUErrorHandler,
    apply_template,
    export_progress_data,
)
from src.cli.config_migration import (  # noqa: E402
    backup_config,
    detect_config_version,
    migrate_config,
)
from src.cli.main import format_progress, load_targets, parse_args, validate_args  # noqa: E402
from src.collision.collision_stats import CollisionStats  # noqa: E402

# ─────────────────────────────────────────────────────────────────────────────
# 通用辅助函数
# ─────────────────────────────────────────────────────────────────────────────


def _make_full_args(**kwargs):
    """构造具有所有必填字段的 Args 对象"""

    class Args:
        pass

    a = Args()
    a.targets = kwargs.get("targets", ["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"])
    a.file = kwargs.get("file")
    a.mode = kwargs.get("mode", "random")
    a.start = kwargs.get("start")
    a.end = kwargs.get("end")
    a.workers = kwargs.get("workers", 4)
    a.duration = kwargs.get("duration", 60)
    a.health_check = kwargs.get("health_check", False)
    a.platform_check = kwargs.get("platform_check", False)
    a.cleanup = kwargs.get("cleanup", False)
    a.validate_addresses = kwargs.get("validate_addresses")
    a.examples = kwargs.get("examples", False)
    a.config_check = kwargs.get("config_check", False)
    a.quick_start = kwargs.get("quick_start", False)
    a.use_gpu = kwargs.get("use_gpu", False)
    a.multi_gpu = kwargs.get("multi_gpu", False)
    a.checkpoint = kwargs.get("checkpoint", False)
    a.checkpoint_interval = kwargs.get("checkpoint_interval", 30)
    a.dedup = kwargs.get("dedup", False)
    a.dedup_max_size = kwargs.get("dedup_max_size", 1_000_000)
    a.window_size = kwargs.get("window_size", 8)
    a.no_optimize = kwargs.get("no_optimize", False)
    a.no_simd = kwargs.get("no_simd", False)
    a.no_memory_pool = kwargs.get("no_memory_pool", False)
    a.sensitive_mode = kwargs.get("sensitive_mode", "full")
    a.export_progress = kwargs.get("export_progress")
    a.export_matches = kwargs.get("export_matches")
    return a


def _make_mock_stats(total_checked: int = 1000) -> Mock:
    """创建标准 mock stats 对象"""
    stats = Mock()
    stats.total_checked = total_checked
    stats.elapsed = 1.0
    stats.start_time = 1000.0
    stats.matches = []
    stats.format_elapsed = lambda: "0:00:01"
    stats.format_speed = lambda: "1,000 次/秒"
    return stats


def _make_mock_engine(stats: Mock = None) -> Mock:
    """创建标准 mock engine 对象"""
    engine = Mock()
    engine.is_running.side_effect = [True] + [False] * 100
    engine.get_stats.return_value = stats or _make_mock_stats()
    engine.start = Mock()
    engine.stop = Mock()
    return engine


# ─────────────────────────────────────────────────────────────────────────────
# TestCLIEndToEnd: 端到端流程测试
# ─────────────────────────────────────────────────────────────────────────────


class TestCLIEndToEnd:
    """参数解析 -> 验证 -> 执行的端到端集成流测试"""

    def setup_method(self):
        """每个测试前重置 CLIOutput、LogWindow 单例，并固定为中文语言。"""
        from src.cli.output import CLIOutput

        CLIOutput.reset_instance()
        from src.cli.log_window import reset_log_window_instance

        reset_log_window_instance()

        # 固定 i18n 语言为 zh_CN，确保中文断言在任意 locale 环境下一致
        from src.i18n import get_language, set_language

        self._saved_language = get_language()
        set_language("zh_CN")

    def teardown_method(self):
        """每个测试后恢复原始语言，避免跨测试污染。"""
        from src.i18n import set_language

        set_language(self._saved_language)

    def test_parse_validate_load_flow(self, tmp_path, monkeypatch):
        """参数解析->验证->目标加载完整流"""
        # 创建临时地址文件（放在项目内部 tests/data_logs 避免路径拦截）
        addr_file = tmp_path / "targets.txt"
        addr_file.write_text(
            "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa\n" "1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH\n",
            encoding="utf-8",
        )

        monkeypatch.setattr(
            "sys.argv",
            [
                "cli.py",
                "-f",
                str(addr_file),
                "-m",
                "random",
            ],
        )
        args = parse_args()
        assert args.file == str(addr_file)
        assert args.mode == "random"
        assert validate_args(args) is True

        # Mock validate_file_path 绕过项目目录限制（tmp_path 在系统临时目录）
        # Mock TargetResolver 确保不依赖真实文件 I/O
        with patch("src.cli.main.validate_file_path", return_value=True):
            with patch("src.collision.TargetResolver") as MockResolver:
                instance = MockResolver.return_value
                instance.load_from_file.return_value = {
                    "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
                    "1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH",
                }
                instance.resolve_multiple.return_value = set()
                targets = load_targets(args)
        assert len(targets) == 2

    def test_random_mode_full_cycle(self, monkeypatch, capsys):
        """随机模式完整生命周期（mock引擎）"""
        from src.cli.main import main

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
        stats = _make_mock_stats(total_checked=500)
        engine = _make_mock_engine(stats)

        _time_count = [0]

        def _mock_time():
            _time_count[0] += 1
            return 1000 if _time_count[0] == 1 else 2000

        with patch("src.cli.engine_runner.build_engine", return_value=(engine, "cpu")):
            with patch("time.sleep"):
                with patch("time.time", side_effect=_mock_time):
                    main()

        captured = capsys.readouterr()
        assert "开始对撞" in captured.out
        assert "对撞结束" in captured.out

    def test_range_mode_with_export(self, tmp_path, monkeypatch, capsys):
        """范围模式 + 导出进度"""
        from src.cli.main import main

        export_file = str(tmp_path / "progress_out.json")
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
                "FFFF",
                "--duration",
                "1",
                "--export-progress",
                export_file,
            ],
        )
        stats = _make_mock_stats(total_checked=100)
        engine = _make_mock_engine(stats)

        _time_count = [0]

        def _mock_time():
            _time_count[0] += 1
            return 1000 if _time_count[0] == 1 else 2000

        with patch("src.cli.engine_runner.build_engine", return_value=(engine, "cpu")):
            with patch("time.sleep"):
                with patch("time.time", side_effect=_mock_time):
                    main()

        captured = capsys.readouterr()
        assert "对撞结束" in captured.out

    def test_template_apply_then_run(self, tmp_path, monkeypatch):
        """模板应用 -> 配置加载 -> 验证配置正确"""
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"crypto": {}}), encoding="utf-8")

        # 应用 quick-test 模板
        result = apply_template("quick-test", str(config_file))
        assert result is True

        # 验证写入的配置包含 collision 段
        with open(config_file, encoding="utf-8") as f:
            config = json.load(f)
        assert "collision" in config

        # 用 load_config_with_validation 加载
        import importlib

        main_mod = importlib.import_module("src.cli.main")
        monkeypatch.setattr(main_mod, "_project_root", str(tmp_path))
        loaded = main_mod.load_config_with_validation()
        assert loaded is not None
        assert "collision" in loaded

    def test_quick_start_to_execution(self, monkeypatch):
        """quick-start 生成命令可被 parse_args 正常解析"""
        from unittest.mock import MagicMock

        from src.cli.commands import _cmd_quick_start

        # Windows 上 mock fcntl（Unix 文件锁），避免 No module named 'fcntl'
        mock_fcntl = MagicMock()
        monkeypatch.setitem(sys.modules, "fcntl", mock_fcntl)

        monkeypatch.setattr("sys.platform", "linux")
        import src.cli.commands as cmd_mod

        monkeypatch.setattr(cmd_mod.sys, "platform", "linux")

        # 模拟用户交互（单地址 -> random -> 不启用 checkpoint -> 不启用 dedup -> 0 -> CPU -> 不执行）
        inputs = iter(
            [
                "1",  # 单个地址
                "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",  # 输入地址
                "1",  # random 模式
                "n",  # 不启用 checkpoint
                "n",  # 不启用 dedup
                "1",  # duration=无限（1=无限，旧版用0）
                "1",  # CPU
                "n",  # 不执行
            ]
        )
        monkeypatch.setattr("builtins.input", lambda _="": next(inputs))

        buf = StringIO()
        monkeypatch.setattr("sys.stdout", buf)
        monkeypatch.setattr(cmd_mod.sys, "stdout", buf)
        _cmd_quick_start()

        output = buf.getvalue()
        assert "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa" in output
        # 生成的命令行含 -m random
        assert "-m random" in output


# ─────────────────────────────────────────────────────────────────────────────
# TestGPUIntegration: GPU 引擎集成测试
# ─────────────────────────────────────────────────────────────────────────────


class TestGPUIntegration:
    """GPU 引擎构建、降级和错误处理集成测试"""

    def setup_method(self):
        """每个测试前重置 CLIOutput 和 LogWindow 单例，确保测试隔离"""
        from src.cli.output import CLIOutput

        CLIOutput.reset_instance()
        from src.cli.log_window import reset_log_window_instance

        reset_log_window_instance()

    def test_single_gpu_engine_lifecycle(self, monkeypatch):
        """单 GPU 引擎构建 -> 运行 -> 统计"""
        import src.cli.engine_builder as eb

        mock_gpu_engine = Mock()
        mock_gpu_engine.is_running.side_effect = [True, False]
        mock_gpu_engine.get_stats.return_value = _make_mock_stats(200)
        mock_gpu_engine.start = Mock()
        mock_gpu_engine.stop = Mock()

        monkeypatch.setattr(eb, "GPU_AVAILABLE", True)
        with patch.dict(
            "sys.modules",
            {
                "src.collision.gpu_collision_engine": Mock(
                    GPUCollisionEngine=lambda **kw: mock_gpu_engine
                )
            },
        ):
            args = _make_full_args(
                use_gpu=True,
                checkpoint=False,
                checkpoint_interval=30,
                dedup=False,
                dedup_max_size=1_000_000,
            )
            targets = {"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"}
            engine, engine_type = eb.build_engine(args, targets)

            assert engine_type == "gpu"
            assert engine is mock_gpu_engine

    def test_multi_gpu_engine_lifecycle(self, monkeypatch):
        """多 GPU 引擎构建 -> 初始化成功"""
        import src.cli.engine_builder as eb

        mock_multi = Mock()
        mock_multi.initialize.return_value = True

        monkeypatch.setattr(eb, "GPU_AVAILABLE", True)
        with patch.dict(
            "sys.modules",
            {"src.gpu.multi_gpu_engine": Mock(MultiGPUCollisionEngine=lambda: mock_multi)},
        ):
            args = _make_full_args(multi_gpu=True)
            engine, engine_type = eb.build_engine(args, {"addr1"})

            assert engine_type == "multi_gpu"
            assert engine is mock_multi
            mock_multi.initialize.assert_called_once()

    def test_gpu_fallback_to_cpu(self, monkeypatch, capsys):
        """GPU 不可用时请求 GPU 应抛出 GPUNotAvailableError"""
        import src.cli.engine_builder as eb

        monkeypatch.setattr(eb, "GPU_AVAILABLE", False)

        args = _make_full_args(use_gpu=True)
        with pytest.raises(eb.GPUNotAvailableError):
            eb.build_engine(args, {"addr1"})

    def test_sensitive_mode_in_gpu_flow(self, monkeypatch, capsys):
        """GPU 流程中的脱敏模式集成 - masked 模式在非TTY环境下降级为hash_only"""
        import src.cli.engine_builder as eb

        callback = eb.on_match_callback(sensitive_mode="masked")
        test_key = bytes.fromhex("0123456789abcdef" * 4)
        with patch("sys.stdout.isatty", return_value=True):
            callback(test_key, "1TestAddress", "5JTestWIF12345678")

        captured = capsys.readouterr()
        full_hex = test_key.hex()
        assert full_hex not in captured.out
        assert full_hex[:8] in captured.out

    def test_gpu_error_handler_integration(self, capsys):
        """GPU 错误处理 -> 用户提示完整流"""
        # 测试 OOM 场景
        oom_err = Exception("Out of memory")
        result = GPUErrorHandler.handle_initialization_error(oom_err)
        assert result["type"] == "out_of_memory"
        assert result["recoverable"] is True
        assert "solution" in result

        # 测试 no_gpu 场景
        no_gpu_err = Exception("No platform found")
        result2 = GPUErrorHandler.handle_initialization_error(no_gpu_err)
        assert result2["type"] == "no_gpu"
        assert result2["recoverable"] is False

        # 测试 batch_size 调整建议
        new_size = GPUErrorHandler.suggest_batch_size_adjustment(65536, oom_err)
        assert new_size < 65536
        assert new_size >= 1024


# ─────────────────────────────────────────────────────────────────────────────
# TestPerformanceBenchmark: 性能基准测试
# ─────────────────────────────────────────────────────────────────────────────


class TestPerformanceBenchmark:
    """关键路径性能基准（宽松阈值，适应 CI 环境）"""

    def setup_method(self):
        """每个测试前重置 CLIOutput 和 LogWindow 单例，确保测试隔离"""
        from src.cli.output import CLIOutput

        CLIOutput.reset_instance()
        from src.cli.log_window import reset_log_window_instance

        reset_log_window_instance()

    def test_parse_args_performance(self, monkeypatch):
        """参数解析单次 < 200ms（100次平均）"""
        monkeypatch.setattr(
            "sys.argv",
            [
                "cli.py",
                "-t",
                "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
                "-m",
                "random",
            ],
        )

        # 预热
        parse_args()

        start = time.perf_counter()
        for _ in range(100):
            parse_args()
        elapsed_ms = (time.perf_counter() - start) * 1000 / 100

        assert elapsed_ms < 200, f"parse_args 平均耗时 {elapsed_ms:.2f}ms，超过 200ms 阈值"

    def test_validate_args_performance(self):
        """validate_args 单次 < 50ms（1000次平均）"""
        args = _make_full_args()

        # 预热
        validate_args(args)

        start = time.perf_counter()
        for _ in range(1000):
            validate_args(args)
        elapsed_ms = (time.perf_counter() - start) * 1000 / 1000

        assert elapsed_ms < 50, f"validate_args 平均耗时 {elapsed_ms:.2f}ms，超过 50ms 阈值"

    def test_format_progress_performance(self):
        """format_progress 单次 < 5ms（1000次平均）"""
        stats = CollisionStats()
        stats.total_checked = 100_000
        stats.start_time = time.time() - 10

        # 预热
        format_progress(stats, "random")

        start = time.perf_counter()
        for _ in range(1000):
            format_progress(stats, "random")
        elapsed_ms = (time.perf_counter() - start) * 1000 / 1000

        assert elapsed_ms < 5, f"format_progress 平均耗时 {elapsed_ms:.2f}ms，超过 5ms 阈值"

    def test_large_target_loading(self, tmp_path, monkeypatch):
        """10000+ 地址加载时间 < 5 秒"""
        addr_file = tmp_path / "large_targets.txt"
        # 生成 10000 个唯一占位地址（固定前缀 + 序号，确保集合不去重）
        lines = [f"1Address{i:09d}Placeholder" for i in range(10_000)]
        addr_file.write_text("\n".join(lines), encoding="utf-8")

        large_set = set(lines)

        with patch("src.cli.main.validate_file_path", return_value=True):
            with patch("src.collision.TargetResolver") as MockResolver:
                instance = MockResolver.return_value
                instance.load_from_file.return_value = large_set
                instance.resolve_multiple.return_value = set()

                args = _make_full_args(file=str(addr_file), targets=None)
                args.targets = None

                start = time.perf_counter()
                targets = load_targets(args)
                elapsed = time.perf_counter() - start

        assert elapsed < 5, f"加载 10000 地址耗时 {elapsed:.3f}s，超过 5s 阈值"
        assert len(targets) == 10_000


# ─────────────────────────────────────────────────────────────────────────────
# TestEdgeCases: 边界条件与并发安全
# ─────────────────────────────────────────────────────────────────────────────


class TestEdgeCases:
    """边界条件测试"""

    def setup_method(self):
        """每个测试前重置 CLIOutput 和 LogWindow 单例，确保测试隔离"""
        from src.cli.output import CLIOutput

        CLIOutput.reset_instance()
        from src.cli.log_window import reset_log_window_instance

        reset_log_window_instance()

    def test_max_range_2_256(self, monkeypatch, capsys):
        """超大范围 2^256 触发警告，validate_args 仍返回 True"""
        start_val = 1
        end_val = start_val + (2**64) + 10000
        args = _make_full_args(
            mode="range",
            start=hex(start_val)[2:],
            end=hex(end_val)[2:],
        )
        result = validate_args(args)
        assert result is True

        captured = capsys.readouterr()
        combined = captured.out + captured.err
        assert "小时" in combined
        assert "GPU" in combined or "建议" in combined

    def test_empty_target_file(self, tmp_path, monkeypatch):
        """空目标文件 -> load_targets 应 SystemExit（无有效地址）"""
        empty_file = tmp_path / "empty.txt"
        empty_file.write_text("", encoding="utf-8")

        # TargetResolver 返回空集合
        with patch("src.collision.TargetResolver") as MockResolver:
            instance = MockResolver.return_value
            instance.load_from_file.return_value = set()
            instance.resolve_multiple.return_value = set()

            args = _make_full_args(file=str(empty_file), targets=None)
            args.targets = None
            with pytest.raises(SystemExit):
                load_targets(args)

    def test_concurrent_export_calls(self, tmp_path):
        """多线程并发调用 export_progress_data/export_matches 不应抛出异常"""
        stats = _make_mock_stats(5000)
        errors = []

        def _do_export(idx: int):
            try:
                out = str(tmp_path / f"progress_{idx}.json")
                export_progress_data(stats, mode="random", engine_type="cpu", output_file=out)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=_do_export, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"并发导出出现异常: {errors}"

    def test_signal_handler_cleanup(self, monkeypatch):
        """信号处理配置可正常注册（不依赖真实 GPU）"""
        import signal as _signal

        from src.cli.main import main

        registered_signals = {}

        def _fake_signal(sig, handler):
            registered_signals[sig] = handler

        monkeypatch.setattr(_signal, "signal", _fake_signal)

        stats = _make_mock_stats(100)
        engine = _make_mock_engine(stats)

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

        _time_count = [0]

        def _mock_time():
            _time_count[0] += 1
            return 1000 if _time_count[0] == 1 else 2000

        with patch("src.cli.engine_runner.build_engine", return_value=(engine, "cpu")):
            with patch("time.sleep"):
                with patch("time.time", side_effect=_mock_time):
                    main()

        # SIGINT 应被注册
        assert _signal.SIGINT in registered_signals


# ─────────────────────────────────────────────────────────────────────────────
# TestConfigMigration: 配置版本迁移工具测试
# ─────────────────────────────────────────────────────────────────────────────


class TestConfigMigration:
    """配置版本迁移工具（src.cli.config_migration）测试"""

    def setup_method(self):
        """每个测试前重置 CLIOutput 和 LogWindow 单例，确保测试隔离"""
        from src.cli.output import CLIOutput

        CLIOutput.reset_instance()
        from src.cli.log_window import reset_log_window_instance

        reset_log_window_instance()

    def test_detect_config_version(self):
        """版本检测 - v2.x / v4.2.1 / v4.2.1"""
        v2_config = {
            "crypto": {"backend": "auto"},
            "collision": {"mode": "random"},
            "logging": {"level": "INFO"},
        }
        assert detect_config_version(v2_config) == "2.x"

        v3_config = {
            "crypto": {},
            "collision": {},
            "logging": {},
            "gpu": {"mode": "auto"},
            "monitoring": {"enabled": False},
        }
        assert detect_config_version(v3_config) == "3.0.0"

        v31_config = {
            "crypto": {},
            "collision": {},
            "logging": {},
            "gpu": {},
            "monitoring": {},
            "performance_monitoring": {"enabled": True},
        }
        assert detect_config_version(v31_config) == "3.1.0"

    def test_migrate_v2_to_v3(self):
        """v2 -> v4.2.1 迁移后必需段存在"""
        v2_config = {
            "crypto": {"backend": "auto"},
            "collision": {"mode": "random", "max_workers": 4},
            "logging": {"level": "INFO"},
        }
        migrated, changelog = migrate_config(v2_config)

        # 迁移后必须包含 gpu 和 monitoring 段
        assert "gpu" in migrated
        assert "monitoring" in migrated
        assert "performance_monitoring" in migrated

        # 变更日志不为空
        assert len(changelog) > 0
        # 应包含迁移规则标记
        assert any("2.x_to_3.0" in entry for entry in changelog)

    def test_backup_creation(self, tmp_path):
        """backup_config 创建备份文件"""
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"crypto": {}}), encoding="utf-8")

        backup_path = backup_config(str(config_file))

        assert os.path.exists(backup_path)
        assert backup_path != str(config_file)
        # 备份文件名包含 .bak.
        assert ".bak." in backup_path

        # 备份内容与原文件一致
        with open(backup_path, encoding="utf-8") as f:
            backup_data = json.load(f)
        assert backup_data == {"crypto": {}}

    def test_migrate_preserves_custom_values(self):
        """迁移过程保留用户自定义值，不覆盖已存在的字段"""
        v2_config = {
            "crypto": {"backend": "secp256k1"},
            "collision": {
                "mode": "range",
                "max_workers": 8,  # 用户自定义
                "use_performance_optimization": False,  # 用户已有
            },
            "logging": {"level": "DEBUG"},
        }
        migrated, changelog = migrate_config(v2_config)

        # 用户自定义值必须保留
        assert migrated["collision"]["max_workers"] == 8
        assert migrated["collision"]["use_performance_optimization"] is False
        assert migrated["crypto"]["backend"] == "secp256k1"
        assert migrated["logging"]["level"] == "DEBUG"

        # 缺失字段应被填充
        assert "gpu" in migrated
        assert "monitoring" in migrated

        # 变更日志应说明已存在的字段被保留
        preserved = [e for e in changelog if "保留用户值" in e or "字段已存在" in e]
        assert len(preserved) > 0


# ─────────────────────────────────────────────────────────────────────────────
# 运行入口
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

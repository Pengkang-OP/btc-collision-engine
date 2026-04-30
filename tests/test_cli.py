#!/usr/bin/env python3
"""CLI 基础功能测试"""
import pytest
import sys
import os
from unittest.mock import Mock, patch
from io import StringIO

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.cli.main import parse_args, validate_args, load_targets, format_progress, main
from src.collision.collision_stats import CollisionStats


class TestCLI:
    """CLI 测试类"""

    def setup_method(self):
        """每个测试前重置 CLIOutput 和 LogWindow 单例，确保测试隔离"""
        from src.cli.output import CLIOutput
        CLIOutput.reset_instance()
        from src.cli.log_window import reset_log_window_instance
        reset_log_window_instance()

    def test_parse_args(self):
        """测试命令行参数解析"""
        # 测试随机模式
        with patch('sys.argv', ['cli.py', '-t', '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa', '-m', 'random']):
            args = parse_args()
            assert args.targets == ['1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa']
            assert args.mode == 'random'
            assert args.checkpoint is False
            assert args.dedup is False

        # 测试范围模式
        with patch('sys.argv', ['cli.py', '-t', '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa', '-m', 'range', '--start', '1', '--end', 'FFFF']):
            args = parse_args()
            assert args.mode == 'range'
            assert args.start == '1'
            assert args.end == 'FFFF'

        # 测试暴力穷举模式
        with patch('sys.argv', ['cli.py', '-t', '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa', '-m', 'brute_force', '--start', '1']):
            args = parse_args()
            assert args.mode == 'brute_force'
            assert args.start == '1'

    def test_validate_args(self):
        """测试参数验证"""
        # 模拟参数对象
        class Args:
            def __init__(self, **kwargs):
                # 添加所有必需的属性（包括新增的工具命令属性）
                self.targets = kwargs.get('targets', None)
                self.file = kwargs.get('file', None)
                self.mode = kwargs.get('mode', 'random')
                self.start = kwargs.get('start', None)
                self.end = kwargs.get('end', None)
                self.workers = kwargs.get('workers', 4)
                self.duration = kwargs.get('duration', 60)
                # 新增工具命令属性
                self.health_check = kwargs.get('health_check', False)
                self.platform_check = kwargs.get('platform_check', False)
                self.cleanup = kwargs.get('cleanup', False)
                self.validate_addresses = kwargs.get('validate_addresses', None)

        # 测试有效参数
        args = Args(
            mode='random',
            targets=['1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa']
        )
        assert validate_args(args) is True

        # 测试范围模式缺少 start
        args = Args(
            mode='range',
            start=None,
            end='FFFF',
            workers=4,
            duration=60
        )
        assert validate_args(args) is False

        # 测试范围模式缺少 end
        args = Args(
            mode='range',
            start='1',
            end=None,
            workers=4,
            duration=60
        )
        assert validate_args(args) is False

        # 测试无效的 start 值
        args = Args(
            mode='range',
            start='invalid',
            end='FFFF',
            workers=4,
            duration=60
        )
        assert validate_args(args) is False

        # 测试 start >= end
        args = Args(
            mode='range',
            start='FFFF',
            end='1',
            workers=4,
            duration=60
        )
        assert validate_args(args) is False

        # 测试无效的 workers
        args = Args(
            mode='random',
            start=None,
            end=None,
            workers=0,
            duration=60
        )
        assert validate_args(args) is False

        # 测试无效的 duration
        args = Args(
            mode='random',
            start=None,
            end=None,
            workers=4,
            duration=-10
        )
        assert validate_args(args) is False

    def test_format_progress(self):
        """测试进度格式化"""
        stats = CollisionStats()
        stats.total_checked = 1000
        stats.start_time = 1000  # 模拟开始时间

        # 测试随机模式进度（新格式：[elapsed] | 1.0K | 速度: ... | ETA: -- | 匹配: 0）
        progress_str = format_progress(stats, 'random')
        assert '1.0K' in progress_str  # 已检查数量以缩写显示
        assert '速度:' in progress_str
        assert '匹配: 0' in progress_str

        # 测试范围模式进度（带进度条和百分比）
        progress_str = format_progress(stats, 'range', total_range=10000)
        assert '1.0K' in progress_str  # 已检查数量
        assert '10.0%' in progress_str  # 进度百分比

    def test_load_targets(self, tmp_path):
        """测试目标地址加载"""
        # 模拟 TargetResolver（延迟导入，需 patch collision 模块）
        with patch('src.collision.TargetResolver') as mock_resolver:
            mock_instance = Mock()
            mock_instance.load_from_file.return_value = {'1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa', '1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH'}
            mock_instance.resolve_multiple.return_value = {'1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'}
            mock_resolver.return_value = mock_instance

            # 模拟参数对象
            class Args:
                def __init__(self, **kwargs):
                    for key, value in kwargs.items():
                        setattr(self, key, value)

            # 测试从文件加载（同时 mock validate_file_path 跳过文件存在性检查）
            with patch('src.cli.main.validate_file_path', return_value=True):
                args = Args(file="test.txt", targets=None)
                targets = load_targets(args)
                assert len(targets) >= 2

            # 测试从命令行参数加载
            args = Args(file=None, targets=['1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'])
            targets = load_targets(args)
            assert len(targets) >= 1

    def test_main_random_mode(self, capsys, monkeypatch):
        """测试主程序随机模式"""
        # 模拟命令行参数
        monkeypatch.setattr('sys.argv', [
            'cli.py',
            '-t', '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa',
            '-m', 'random',
            '--duration', '1'
        ])

        # 创建 mock 引擎实例
        mock_instance = Mock()
        mock_instance.is_running.side_effect = [True, False]

        mock_stats = Mock()
        mock_stats.total_checked = 1000
        mock_stats.elapsed = 1.0
        mock_stats.start_time = 1000
        mock_stats.format_elapsed = lambda: '0:00:01'
        mock_stats.format_speed = lambda: '1,000 次/秒'
        mock_stats.matches = []

        mock_instance.get_stats.return_value = mock_stats
        mock_instance.start = Mock()
        mock_instance.stop = Mock()

        # 直接 patch build_engine，跳过实际引擎创建
        with patch('src.cli.engine_runner.build_engine', return_value=(mock_instance, 'cpu')):
            # 模拟 time.sleep
            with patch('time.sleep', return_value=None):
                # 模拟 time.time: 前1次返回1000，之后均返回2000（确保超时被触发）
                _time_call_count = [0]
                def _mock_time():
                    _time_call_count[0] += 1
                    return 1000 if _time_call_count[0] == 1 else 2000
                with patch('time.time', side_effect=_mock_time):
                    main()

        # 检查输出
        captured = capsys.readouterr()
        assert '开始对撞' in captured.out
        assert '对撞结束' in captured.out
        # Rich Panel 输出格式：「总检查数」后面是空格填充而非「  : 」
        assert '总检查数' in captured.out and '1,000' in captured.out

    def test_main_range_mode(self, capsys, monkeypatch):
        """测试主程序范围模式"""
        # 模拟命令行参数
        monkeypatch.setattr('sys.argv', [
            'cli.py',
            '-t', '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa',
            '-m', 'range',
            '--start', '1',
            '--end', '1000',
            '--duration', '1'
        ])

        # 创建 mock 引擎实例
        mock_instance = Mock()
        mock_instance.is_running.side_effect = [True, False]

        mock_stats = Mock()
        mock_stats.total_checked = 500
        mock_stats.elapsed = 1.0
        mock_stats.start_time = 1000
        mock_stats.format_elapsed = lambda: '0:00:01'
        mock_stats.format_speed = lambda: '500 次/秒'
        mock_stats.matches = []

        mock_instance.get_stats.return_value = mock_stats
        mock_instance.start = Mock()
        mock_instance.stop = Mock()

        # 直接 patch build_engine，跳过实际引擎创建
        with patch('src.cli.engine_runner.build_engine', return_value=(mock_instance, 'cpu')):
            with patch('time.sleep', return_value=None):
                _time_call_count = [0]
                def _mock_time():
                    _time_call_count[0] += 1
                    return 1000 if _time_call_count[0] == 1 else 2000
                with patch('time.time', side_effect=_mock_time):
                    main()

        # 检查输出
        captured = capsys.readouterr()
        assert '开始对撞' in captured.out
        assert '对撞结束' in captured.out
        # Rich Panel 输出格式：「总检查数」后面是空格填充而非「  : 」
        assert '总检查数' in captured.out and '500' in captured.out

    def test_main_brute_force_mode(self, capsys, monkeypatch):
        """测试主程序暴力穷举模式"""
        # 模拟命令行参数
        monkeypatch.setattr('sys.argv', [
            'cli.py',
            '-t', '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa',
            '-m', 'brute_force',
            '--start', '1',
            '--duration', '1'
        ])

        # 创建 mock 引擎实例
        mock_instance = Mock()
        mock_instance.is_running.side_effect = [True, False]

        mock_stats = Mock()
        mock_stats.total_checked = 2000
        mock_stats.elapsed = 1.0
        mock_stats.start_time = 1000
        mock_stats.format_elapsed = lambda: '0:00:01'
        mock_stats.format_speed = lambda: '2,000 次/秒'
        mock_stats.matches = []

        mock_instance.get_stats.return_value = mock_stats
        mock_instance.start = Mock()
        mock_instance.stop = Mock()

        # 直接 patch build_engine，跳过实际引擎创建
        with patch('src.cli.engine_runner.build_engine', return_value=(mock_instance, 'cpu')):
            with patch('time.sleep', return_value=None):
                _time_call_count = [0]
                def _mock_time():
                    _time_call_count[0] += 1
                    return 1000 if _time_call_count[0] == 1 else 2000
                with patch('time.time', side_effect=_mock_time):
                    main()

        # 检查输出
        captured = capsys.readouterr()
        assert '开始对撞' in captured.out
        assert '对撞结束' in captured.out
        # Rich Panel 输出格式：「总检查数」后面是空格填充而非「  : 」
        assert '总检查数' in captured.out and '2,000' in captured.out

    def test_validate_args_gpu_mutual_exclusion(self):
        """测试GPU参数互斥性：--use-gpu 和 --multi-gpu 由 argparse mutually_exclusive_group 处理"""
        # 现在互斥性由 argparse 的 mutually_exclusive_group 自动处理，
        # parse_args() 在遇到两者同时存在时会直接 sys.exit(2)。
        with patch('sys.argv', [
            'cli.py',
            '-t', '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa',
            '--use-gpu', '--multi-gpu'
        ]):
            with pytest.raises(SystemExit) as exc_info:
                parse_args()
            assert exc_info.value.code == 2

    def test_validate_args_checkpoint_interval_auto_enable(self):
        """测试 checkpoint-interval 非默认值时自动启用 checkpoint"""
        class Args:
            def __init__(self, **kwargs):
                self.targets = kwargs.get('targets', ['1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'])
                self.file = None
                self.mode = 'random'
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
                self.checkpoint = kwargs.get('checkpoint', False)
                self.checkpoint_interval = kwargs.get('checkpoint_interval', 30)
                self.dedup = kwargs.get('dedup', False)
                self.dedup_max_size = kwargs.get('dedup_max_size', 1000000)
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
                self.targets = kwargs.get('targets', ['1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'])
                self.file = None
                self.mode = 'random'
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
                self.dedup = kwargs.get('dedup', False)
                self.dedup_max_size = kwargs.get('dedup_max_size', 1000000)
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

        # 屏蔽 Windows 平台下 sys.stdout 被替换（避免 capsys 捕获失效）
        monkeypatch.setattr('sys.platform', 'linux')
        # 同时 mock 掉 src.cli.commands 模块内的 sys.platform
        monkeypatch.setattr('src.cli.commands.sys.platform', 'linux')

        # 模拟用户输入：选择单个地址、输入地址、选random模式、启用checkpoint(Y)、启用dedup(Y)、时长选无限(1)、GPU选CPU模式(1)、不执行(n)
        inputs = iter(['1', '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa', '1', 'Y', 'Y', '1', '1', 'n'])
        monkeypatch.setattr('builtins.input', lambda _='': next(inputs))

        # mock 掉 PlatformUtils.ensure_utf8_output，避免 StringIO 没有 buffer 属性报错
        monkeypatch.setattr('src.utils.platform_utils.PlatformUtils.ensure_utf8_output', staticmethod(lambda: None))
        # 使用 StringIO 手动捕获输出，避免 Windows 下 sys.stdout 被替换导致 capsys 失效
        buf = StringIO()
        monkeypatch.setattr('sys.stdout', buf)
        monkeypatch.setattr('src.cli.commands.sys.stdout', buf)
        _cmd_quick_start()
        output = buf.getvalue()
        assert '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa' in output
        assert '-m random' in output

    def test_import_compatibility(self):
        """确保拆分后的导入路径兼容"""
        # 旧路径（向后兼容）
        from src.cli.main import parse_args, validate_args, load_targets, format_progress, main
        # 新路径
        from src.cli.validation import validate_args as va
        from src.cli.commands import _cmd_examples
        from src.cli.engine_builder import build_engine
        from src.cli.progress import format_progress as fp
        from src.cli.constants import TAG_ERROR, TAG_TIP

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
        mod = _sys.modules.get('src.cli.config_loader')
        if mod is None:
            mod = importlib.import_module('src.cli.config_loader')
        return mod

    def test_config_not_found(self, tmp_path, monkeypatch):
        """config.json不存在时返回None"""
        import src.cli.config_loader as config_loader_mod
        mod = self._get_config_loader_module()
        monkeypatch.setattr(mod, '_project_root', str(tmp_path))
        result = mod.load_config_with_validation()
        assert result is None

    def test_config_invalid_json(self, tmp_path, monkeypatch):
        """config.json JSON格式错误时返回None"""
        mod = self._get_config_loader_module()
        config_file = tmp_path / "config.json"
        config_file.write_text("{invalid json", encoding='utf-8')
        monkeypatch.setattr(mod, '_project_root', str(tmp_path))
        result = mod.load_config_with_validation()
        assert result is None

    def test_config_valid(self, tmp_path, monkeypatch):
        """正常config.json成功加载"""
        import json
        mod = self._get_config_loader_module()
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"crypto": {}, "collision": {}}), encoding='utf-8')
        monkeypatch.setattr(mod, '_project_root', str(tmp_path))
        result = mod.load_config_with_validation()
        assert isinstance(result, dict)
        assert "crypto" in result

    def test_config_not_dict(self, tmp_path, monkeypatch):
        """config.json根节点不是dict时返回None"""
        mod = self._get_config_loader_module()
        config_file = tmp_path / "config.json"
        config_file.write_text('["not", "a", "dict"]', encoding='utf-8')
        monkeypatch.setattr(mod, '_project_root', str(tmp_path))
        result = mod.load_config_with_validation()
        assert result is None


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
        monkeypatch.setattr(eb, 'KeyCollisionEngine', lambda **kwargs: mock_engine)

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

        targets = {'1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'}
        engine, engine_type = eb.build_engine(MockArgs(), targets)
        assert engine_type == 'cpu'
        assert engine is mock_engine

    def test_build_gpu_when_unavailable(self, monkeypatch):
        """GPU不可用时请求GPU引擎应报错退出"""
        import src.cli.engine_builder as eb
        monkeypatch.setattr(eb, 'GPU_AVAILABLE', False)

        class MockArgs:
            use_gpu = True
            multi_gpu = False

        with pytest.raises(SystemExit):
            eb.build_engine(MockArgs(), {'addr1'})

    def test_build_multi_gpu_when_unavailable(self, monkeypatch):
        """GPU不可用时请求多GPU引擎应报错退出"""
        import src.cli.engine_builder as eb
        monkeypatch.setattr(eb, 'GPU_AVAILABLE', False)

        class MockArgs:
            use_gpu = False
            multi_gpu = True

        with pytest.raises(SystemExit):
            eb.build_engine(MockArgs(), {'addr1'})


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
        monkeypatch.setattr('sys.platform', 'linux')
        import src.cli.commands as cmd_mod
        monkeypatch.setattr(cmd_mod.sys, 'platform', 'linux')
        # mock 掉 ensure_utf8_output，避免 StringIO 没有 buffer 属性报错
        monkeypatch.setattr('src.utils.platform_utils.PlatformUtils.ensure_utf8_output', staticmethod(lambda: None))
        buf = StringIO()
        monkeypatch.setattr(cmd_mod.sys, 'stdout', buf)
        _cmd_examples()
        output = buf.getvalue()
        assert 'random' in output
        assert '-t' in output
        assert '--use-gpu' in output

    def test_config_check_missing(self, monkeypatch, tmp_path):
        """config.json不存在时config-check报告缺失"""
        from io import StringIO
        from src.cli.commands import _cmd_config_check
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr('sys.platform', 'linux')
        import src.cli.commands as cmd_mod
        monkeypatch.setattr(cmd_mod.sys, 'platform', 'linux')
        # mock 掉 ensure_utf8_output，避免 StringIO 没有 buffer 属性报错
        monkeypatch.setattr('src.utils.platform_utils.PlatformUtils.ensure_utf8_output', staticmethod(lambda: None))
        buf = StringIO()
        monkeypatch.setattr(cmd_mod.sys, 'stdout', buf)
        _cmd_config_check()
        output = buf.getvalue()
        # 不存在时输出含 ❌ 和 不存在
        assert '不存在' in output or 'config.json' in output

    def test_config_check_valid(self, monkeypatch, tmp_path):
        """config.json有效时config-check通过"""
        import json
        from io import StringIO
        from src.cli.commands import _cmd_config_check
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"crypto": {}, "collision": {}, "logging": {}}), encoding='utf-8')
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr('sys.platform', 'linux')
        import src.cli.commands as cmd_mod
        monkeypatch.setattr(cmd_mod.sys, 'platform', 'linux')
        # mock 掉 ensure_utf8_output，避免 StringIO 没有 buffer 属性报错
        monkeypatch.setattr('src.utils.platform_utils.PlatformUtils.ensure_utf8_output', staticmethod(lambda: None))
        buf = StringIO()
        monkeypatch.setattr(cmd_mod.sys, 'stdout', buf)
        _cmd_config_check()
        output = buf.getvalue()
        assert len(output) > 0
        assert 'config.json' in output

    def test_validate_addresses_file_not_found(self, monkeypatch, tmp_path):
        """验证不存在的地址文件时应触发 SystemExit"""
        from src.cli.commands import _cmd_validate_addresses
        from pathlib import Path
        # 使用 tmp_path 下不存在的路径（tmp_path 是真实绝对路径，且文件不存在）
        nonexistent = str(tmp_path / "nonexistent_test_addresses_xyz.txt")
        # validate_file_path 遇到不存在文件会返回 False，_cmd_validate_addresses 中
        # validate_file_path 返回 False 后直接 return，因此需要让文件通过路径检查但不存在
        # 方案: mock validate_file_path 返回 True，让代码走到文件不存在的分支抛 SystemExit
        with patch('src.cli.commands.validate_file_path', return_value=True):
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
        config_file.write_text(json.dumps({"crypto": {}}), encoding='utf-8')
        result = apply_template("quick-test", str(config_file))
        assert result is True
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        assert isinstance(config, dict)
        # quick-test 模板应写入 collision 段
        assert 'collision' in config

    def test_apply_template_invalid_name(self):
        """不存在的模板名返回False"""
        from src.cli.advanced_features import apply_template
        result = apply_template("nonexistent-template")
        assert result is False

    def test_recommend_parameters(self):
        """参数推荐返回正确结构"""
        from src.cli.advanced_features import recommend_parameters

        class MockArgs:
            targets = ['1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa']
            file = None
            mode = 'random'
            use_gpu = False
            multi_gpu = False
            start = None
            end = None

        result = recommend_parameters(MockArgs())
        assert 'recommendations' in result
        assert 'reasons' in result
        assert isinstance(result['recommendations'], list)
        assert isinstance(result['reasons'], list)

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
        mock_stats.format_elapsed = lambda: '0:00:10'
        mock_stats.format_speed = lambda: '100 次/秒'

        output_file = str(tmp_path / "progress.json")
        result = export_progress_data(mock_stats, 'random', 'cpu', output_file)
        assert result is True

        with open(output_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        assert data['total_checked'] == 1000

    def test_export_matches(self, tmp_path):
        """导出匹配结果"""
        import json
        from src.cli.advanced_features import export_matches

        matches = [
            {'address': '1A1z...', 'private_key': 'abc123', 'wif': '5J...'}
        ]
        output_file = str(tmp_path / "matches.json")
        result = export_matches(matches, output_file)
        assert result is True

        with open(output_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        assert len(data['matches']) == 1


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
        callback = eb.on_match_callback(sensitive_mode='masked')

        test_key = bytes.fromhex('0123456789abcdef' * 4)
        callback(test_key, '1TestAddress', '5JTestWIF12345678')

        captured = capsys.readouterr()
        full_hex = test_key.hex()
        # masked模式下不应包含完整私钥（中间部分被*替换）
        assert full_hex not in captured.out
        # 但应包含前8位
        assert full_hex[:8] in captured.out


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
            apply_template, recommend_parameters,
            export_progress_data, export_matches, GPUErrorHandler,
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
        a.targets = kwargs.get('targets', ['1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'])
        a.file = kwargs.get('file', None)
        a.mode = kwargs.get('mode', 'random')
        a.start = kwargs.get('start', None)
        a.end = kwargs.get('end', None)
        a.workers = kwargs.get('workers', 4)
        a.duration = kwargs.get('duration', 60)
        # 工具命令标志
        a.health_check = kwargs.get('health_check', False)
        a.platform_check = kwargs.get('platform_check', False)
        a.cleanup = kwargs.get('cleanup', False)
        a.validate_addresses = kwargs.get('validate_addresses', None)
        a.examples = kwargs.get('examples', False)
        a.config_check = kwargs.get('config_check', False)
        a.quick_start = kwargs.get('quick_start', False)
        # GPU 参数
        a.use_gpu = kwargs.get('use_gpu', False)
        a.multi_gpu = kwargs.get('multi_gpu', False)
        # 断点 / 去重
        a.checkpoint = kwargs.get('checkpoint', False)
        a.checkpoint_interval = kwargs.get('checkpoint_interval', 30)
        a.dedup = kwargs.get('dedup', False)
        a.dedup_max_size = kwargs.get('dedup_max_size', 1000000)
        # 性能优化
        a.window_size = kwargs.get('window_size', 8)
        a.no_optimize = kwargs.get('no_optimize', False)
        a.no_simd = kwargs.get('no_simd', False)
        a.no_memory_pool = kwargs.get('no_memory_pool', False)
        # 安全模式
        a.sensitive_mode = kwargs.get('sensitive_mode', 'full')
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
        """--sensitive-mode 参数解析正确，默认值为 full"""
        # masked 模式
        monkeypatch.setattr(
            'sys.argv',
            ['cli.py', '-t', '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa',
             '--sensitive-mode', 'masked']
        )
        args = parse_args()
        assert args.sensitive_mode == 'masked'

        # hash_only 模式
        monkeypatch.setattr(
            'sys.argv',
            ['cli.py', '-t', '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa',
             '--sensitive-mode', 'hash_only']
        )
        args = parse_args()
        assert args.sensitive_mode == 'hash_only'

        # 未指定时默认 full
        monkeypatch.setattr(
            'sys.argv',
            ['cli.py', '-t', '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa']
        )
        args = parse_args()
        assert args.sensitive_mode == 'full'

    @staticmethod
    def _get_main_mod():
        """安全获取 src.cli.main 模块对象（与 TestLoadConfigWithValidation 相同惯例）"""
        import importlib
        import sys as _sys
        mod = _sys.modules.get('src.cli.main')
        if mod is None or not hasattr(mod, '_print_final_summary'):
            mod = importlib.import_module('src.cli.main')
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
        mock_stats.format_elapsed = lambda: '0:00:05'
        mock_stats.format_speed = lambda: '100 次/秒'

        mock_engine = Mock()
        mock_engine.get_stats.return_value = mock_stats

        # mock export_progress_data，追踪调用（需 patch stats_reporter 模块中的引用）
        called = []
        def fake_export_progress(stats, mode, engine_type, output_file, *args, **kwargs):
            called.append((engine_type, output_file))
            return True

        monkeypatch.setattr(stats_reporter_mod, 'export_progress_data', fake_export_progress)

        export_file = str(tmp_path / 'progress.json')
        args_obj = self._make_args()
        args_obj.export_progress = export_file
        args_obj.export_matches = None

        print_summary(mock_engine, 'cpu', args_obj)

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
        mock_stats.format_elapsed = lambda: '0:00:03'
        mock_stats.format_speed = lambda: '100 次/秒'

        mock_engine = Mock()
        mock_engine.get_stats.return_value = mock_stats

        # mock export_matches，追踪调用（需 patch stats_reporter 模块中的引用）
        called = []
        def fake_export_matches(matches, output_file, *args, **kwargs):
            called.append((matches, output_file))
            return True

        monkeypatch.setattr(stats_reporter_mod, 'export_matches', fake_export_matches)

        export_file = str(tmp_path / 'matches.json')
        args_obj = self._make_args()
        args_obj.export_progress = None
        args_obj.export_matches = export_file

        print_summary(mock_engine, 'cpu', args_obj)

        assert len(called) == 1, "export_matches 应被调用一次"
        assert called[0][1] == export_file

    # ── 测试 5: 超大范围警告 ─────────────────────────────────────────────────
    def test_large_range_warning(self, capsys):
        """range 模式中搜索范围超过 2^64 时输出增强警告信息（含预估时间和建议）"""
        from src.cli.validation import validate_args

        # 构造一个范围超过 2^64 的 range 模式参数
        # start = 1, end = 1 + 2^64 + 1000（确保 total_range > 2^64）
        start_val = 1
        end_val = start_val + (2 ** 64) + 1000
        args = self._make_args(
            mode='range',
            start=hex(start_val)[2:],
            end=hex(end_val)[2:],
        )
        result = validate_args(args)
        # validate_args 在超大范围时仍返回 True（只是警告，不拒绝）
        assert result is True

        captured = capsys.readouterr()
        combined = captured.out + captured.err
        # 应包含小时数预估
        assert '小时' in combined
        # 应包含 GPU 建议
        assert 'GPU' in combined or '建议' in combined

    # ── 测试 6: hash_only 模式回调 ────────────────────────────────────────────
    def test_sensitive_mode_hash_only(self, capsys):
        """on_match_callback 工厂在 hash_only 模式下输出哈希前缀而非完整私钥"""
        import src.cli.engine_builder as eb

        # 通过工厂函数获取 hash_only 回调
        callback = eb.on_match_callback(sensitive_mode='hash_only')

        test_key = bytes.fromhex('0123456789abcdef' * 4)
        full_hex = test_key.hex()

        callback(test_key, '1TestAddress', '5JTestWIF12345678')

        captured = capsys.readouterr()
        # hash_only 模式不应出现完整私钥十六进制
        assert full_hex not in captured.out
        # 应包含 SHA256 哈希标识
        assert 'SHA256' in captured.out
        # WIF 应被隐藏
        assert '已隐藏' in captured.out

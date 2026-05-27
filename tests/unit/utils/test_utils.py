"""统一测试工具模块 - 提供通用的Mock工厂和测试辅助函数."""

import json
import os
import pathlib
import tempfile
import unittest
from contextlib import contextmanager
from typing import Any
from unittest.mock import Mock, patch


class TestUtils:
    """通用测试工具类."""

    # -------------------------------------------------------------------------
    # 临时文件工具
    # -------------------------------------------------------------------------

    @staticmethod
    @contextmanager
    def temp_file(content: str = "", suffix: str = ""):
        """创建临时文件上下文管理器."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False, encoding="utf-8") as f:
            f.write(content)
            temp_path = f.name

        try:
            yield temp_path
        finally:
            if pathlib.Path(temp_path).exists():
                pathlib.Path(temp_path).unlink()

    @staticmethod
    @contextmanager
    def temp_json_file(data: dict):
        """创建临时JSON文件上下文管理器."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            temp_path = f.name

        try:
            yield temp_path
        finally:
            if pathlib.Path(temp_path).exists():
                pathlib.Path(temp_path).unlink()

    @staticmethod
    @contextmanager
    def temp_directory():
        """创建临时目录上下文管理器."""
        temp_dir = tempfile.mkdtemp()

        try:
            yield temp_dir
        finally:
            import shutil

            shutil.rmtree(temp_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # Mock辅助函数
    # -------------------------------------------------------------------------

    @staticmethod
    def create_mock_with_attrs(attrs: dict[str, Any]) -> Mock:
        """创建带有指定属性的Mock对象."""
        mock = Mock()
        for key, value in attrs.items():
            setattr(mock, key, value)
        return mock

    @staticmethod
    def create_mock_with_methods(methods: dict[str, Any]) -> Mock:
        """创建带有指定方法的Mock对象."""
        mock = Mock()
        for method_name, return_value in methods.items():
            if callable(return_value):
                setattr(mock, method_name, return_value)
            else:
                setattr(mock, method_name, Mock(return_value=return_value))
        return mock

    @staticmethod
    @contextmanager
    def patch_multiple(patches: list[tuple[str, Any]]):
        """同时patch多个对象."""
        patch_objects = []
        try:
            for target, value in patches:
                p = patch(target, value)
                patch_objects.append(p)
                p.start()
            yield
        finally:
            for p in reversed(patch_objects):
                p.stop()

    # -------------------------------------------------------------------------
    # 断言辅助函数
    # -------------------------------------------------------------------------

    @staticmethod
    def assert_dict_contains_keys(d: dict, expected_keys: list[str]):
        """断言字典包含所有期望的键."""
        for key in expected_keys:
            assert key in d, f"字典缺少预期键: {key}"

    @staticmethod
    def assert_dict_equals_ignoring_keys(d1: dict, d2: dict, ignore_keys: list[str] = None):
        """比较两个字典，忽略指定的键."""
        if ignore_keys is None:
            ignore_keys = []

        d1_filtered = {k: v for k, v in d1.items() if k not in ignore_keys}
        d2_filtered = {k: v for k, v in d2.items() if k not in ignore_keys}

        assert d1_filtered == d2_filtered, (
            f"字典不相等（忽略键: {ignore_keys}）\n{d1_filtered}\n{d2_filtered}"
        )

    @staticmethod
    def assert_call_count(mock_obj, method_name: str, expected_count: int):
        """断言mock方法被调用的次数."""
        method = getattr(mock_obj, method_name, None)
        assert method is not None, f"对象没有方法: {method_name}"
        assert method.call_count == expected_count, (
            f"方法 {method_name} 调用次数不符: 预期 {expected_count}, 实际 {method.call_count}"
        )

    # -------------------------------------------------------------------------
    # 时间相关Mock
    # -------------------------------------------------------------------------

    @staticmethod
    @contextmanager
    def mock_time(fixed_time: float = 1234567890.0):
        """Mock time模块，返回固定时间."""
        with patch("time.time", return_value=fixed_time):
            yield fixed_time

    @staticmethod
    @contextmanager
    def mock_sleep():
        """Mock time.sleep，不实际等待."""
        with patch("time.sleep"):
            yield

    # -------------------------------------------------------------------------
    # 日志测试辅助
    # -------------------------------------------------------------------------

    @staticmethod
    @contextmanager
    def capture_logs(logger_name: str):
        """捕获指定logger的日志输出."""
        import logging

        logger = logging.getLogger(logger_name)
        original_level = logger.level

        logs = []

        class LogCaptureHandler(logging.Handler):
            def emit(self, record):
                logs.append(
                    {"level": record.levelname, "message": record.getMessage(), "name": record.name},
                )

        handler = LogCaptureHandler()
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        try:
            yield logs
        finally:
            logger.removeHandler(handler)
            logger.setLevel(original_level)

    # -------------------------------------------------------------------------
    # 性能测试辅助
    # -------------------------------------------------------------------------

    @staticmethod
    def measure_time(func, *args, **kwargs) -> tuple[float, Any]:
        """测量函数执行时间并返回结果."""
        import time

        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        return elapsed, result


class MockFactory:
    """统一Mock工厂 - 提供标准化的Mock对象."""

    # -------------------------------------------------------------------------
    # 通用Mock创建方法
    # -------------------------------------------------------------------------

    @staticmethod
    def create_simple_mock(**kwargs) -> Mock:
        """创建简单的Mock对象，设置属性."""
        mock = Mock()
        for key, value in kwargs.items():
            setattr(mock, key, value)
        return mock

    @staticmethod
    def create_callable_mock(return_value=None, side_effect=None) -> Mock:
        """创建可调用的Mock对象."""
        mock = Mock()
        if side_effect is not None:
            mock.side_effect = side_effect
        else:
            mock.return_value = return_value
        return mock

    @staticmethod
    def create_list_mock(items: list) -> Mock:
        """创建模拟列表的Mock对象."""
        mock = Mock()
        mock.__iter__.return_value = iter(items)
        mock.__len__.return_value = len(items)
        mock.__getitem__ = lambda idx: items[idx]
        return mock

    @staticmethod
    def create_dict_mock(data: dict) -> Mock:
        """创建模拟字典的Mock对象."""
        mock = Mock()
        mock.__getitem__ = lambda key: data[key]
        mock.get = lambda key, default=None: data.get(key, default)
        mock.__contains__ = lambda key: key in data
        mock.keys.return_value = data.keys()
        mock.values.return_value = data.values()
        mock.items.return_value = data.items()
        return mock

    # -------------------------------------------------------------------------
    # 特定场景Mock
    # -------------------------------------------------------------------------

    @staticmethod
    def create_success_result() -> Mock:
        """创建表示成功操作的Mock结果."""
        result = Mock()
        result.success = True
        result.error = None
        result.data = {}
        return result

    @staticmethod
    def create_failure_result(error_message: str = "操作失败") -> Mock:
        """创建表示失败操作的Mock结果."""
        result = Mock()
        result.success = False
        result.error = error_message
        result.data = None
        return result

    @staticmethod
    def create_progress_callback():
        """创建进度回调Mock."""
        return Mock()

    @staticmethod
    def create_event_loop():
        """创建事件循环Mock."""
        loop = Mock()
        loop.run_until_complete = Mock()
        loop.close = Mock()
        return loop

    # -------------------------------------------------------------------------
    # 上下文管理器Mock
    # -------------------------------------------------------------------------

    @staticmethod
    def create_context_manager_mock(enter_result=None):
        """创建模拟上下文管理器的Mock."""
        mock = Mock()
        mock.__enter__ = Mock(return_value=enter_result)
        mock.__exit__ = Mock(return_value=False)
        return mock


class TestCaseWithMocks:
    """增强的测试用例基类，提供常用Mock功能."""

    def setup_method(self, method):
        self.mock_factory = MockFactory()
        self.utils = TestUtils()
        self.patches = []

    def teardown_method(self, method):
        """清理所有patch."""
        for p in reversed(self.patches):
            p.stop()

    def add_patch(self, target: str, value=None):
        """添加patch并记录，在tearDown时自动清理."""
        p = patch(target) if value is None else patch(target, value)
        p.start()
        self.patches.append(p)
        return p

    def assert_mock_called_with(self, mock_obj, *args, **kwargs):
        """断言mock被调用时传入了指定参数."""
        mock_obj.assert_called_with(*args, **kwargs)

    def assert_mock_not_called(self, mock_obj):
        """断言mock没有被调用."""
        mock_obj.assert_not_called()

    def assert_mock_called_once(self, mock_obj):
        """断言mock被调用了一次."""
        mock_obj.assert_called_once()

    def create_temp_file(self, content: str = ""):
        """创建临时文件并返回路径."""
        fd, path = tempfile.mkstemp()
        try:
            os.write(fd, content.encode("utf-8"))
        finally:
            os.close(fd)
        return path

    def cleanup_temp_file(self, path: str):
        """清理临时文件."""
        if pathlib.Path(path).exists():
            pathlib.Path(path).unlink()


# -------------------------------------------------------------------------
# 常用装饰器
# -------------------------------------------------------------------------


def skip_if_no_pyopencl(func):
    """如果没有安装pyopencl则跳过测试."""
    try:
        import pyopencl  # noqa: F401
    except ImportError:
        return unittest.skip("pyopencl not installed")(func)
    return func


def skip_if_no_gpu(func):
    """如果没有GPU设备则跳过测试."""
    try:
        import pyopencl as cl

        platforms = cl.get_platforms()
        if not platforms:
            return unittest.skip("No OpenCL platforms available")(func)
        has_gpu = False
        for platform in platforms:
            for device in platform.get_devices():
                if device.type & cl.device_type.GPU:
                    has_gpu = True
                    break
            if has_gpu:
                break
        if not has_gpu:
            return unittest.skip("No GPU device available")(func)
        return func
    except ImportError:
        return unittest.skip("pyopencl not installed")(func)
    except Exception:
        return unittest.skip("OpenCL platform error (no GPU/OpenCL runtime)")(func)


def timeout(seconds: int):
    """测试超时装饰器."""
    import functools
    import signal

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            def handler(signum, frame):
                raise TimeoutError(f"测试超时（超过{seconds}秒）")

            signal.signal(signal.SIGALRM, handler)
            signal.alarm(seconds)
            try:
                return func(*args, **kwargs)
            finally:
                signal.alarm(0)

        return wrapper

    return decorator


# -------------------------------------------------------------------------
# 全局辅助变量
# -------------------------------------------------------------------------

# 常用测试数据
TEST_TARGET_ADDRESSES = [
    "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
    "1BitcoinEaterAddressDontSendf59kuE",
    "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy",
]

TEST_CONFIG = {
    "collision": {"max_workers": 4, "progress_interval": 1000, "checkpoint_interval": 30},
    "logging": {"level": "DEBUG", "enable_console": True},
    "gpu": {"use_gpu": False, "batch_size": 65536},
}

"""log_throttling.py 模块单元测试

测试 RateLimitedLogger 频率限制日志记录器 和 rate_limited_log 装饰器。
"""

import time
from unittest.mock import patch

from src.utils.log_throttling import (
    RateLimitedLogger,
    collision_logger,
    data_logger,
    gpu_logger,
    rate_limited_log,
)


class TestRateLimitedLoggerInit:
    """测试 RateLimitedLogger 初始化"""

    def test_init_default_cooldown(self):
        """默认冷却时间应为 60 秒"""
        rl = RateLimitedLogger("test")
        assert rl.default_cooldown == 60
        assert rl.logger.name == "test"

    def test_init_custom_cooldown(self):
        """自定义冷却时间"""
        rl = RateLimitedLogger("custom", default_cooldown=30)
        assert rl.default_cooldown == 30
        assert rl.logger.name == "custom"

    def test_init_empty_cache(self):
        """初始化后缓存应为空"""
        rl = RateLimitedLogger("test")
        assert rl._last_log_time == {}


class TestRateLimitedLoggerErrorLimited:
    """测试 error_limited 方法"""

    def test_first_call_logs(self):
        """第一次调用应记录日志"""
        rl = RateLimitedLogger("test")
        with patch.object(rl.logger, "error") as mock_error:
            rl.error_limited("test message")
            mock_error.assert_called_once_with("test message")

    def test_within_cooldown_suppressed(self):
        """冷却期内的重复调用应被抑制"""
        rl = RateLimitedLogger("test", default_cooldown=60)
        with patch.object(rl.logger, "error") as mock_error:
            rl.error_limited("test message")
            rl.error_limited("test message")
            # 只调用一次
            assert mock_error.call_count == 1

    def test_after_cooldown_logs_again(self):
        """冷却期后再次调用应记录日志"""
        rl = RateLimitedLogger("test", default_cooldown=1)
        with patch.object(rl.logger, "error") as mock_error:
            # 第一次: t=100 (> cooldown=1 → 记录)
            with patch.object(time, "time", return_value=100.0):
                rl.error_limited("test message")
            # 第二次: t=102 (delta=2 > cooldown=1 → 记录)
            with patch.object(time, "time", return_value=102.0):
                rl.error_limited("test message")
            assert mock_error.call_count == 2

    def test_custom_cooldown_used(self):
        """使用自定义冷却时间"""
        rl = RateLimitedLogger("test", default_cooldown=60)
        with patch.object(rl.logger, "error") as mock_error:
            # t=100 (> cooldown=10 → 记录)
            with patch.object(time, "time", return_value=100.0):
                rl.error_limited("msg", cooldown=10)
            # t=105 (delta=5 < cooldown=10 → 抑制)
            with patch.object(time, "time", return_value=105.0):
                rl.error_limited("msg", cooldown=10)
            assert mock_error.call_count == 1

    def test_different_messages_independent(self):
        """不同消息独立冷却"""
        rl = RateLimitedLogger("test", default_cooldown=60)
        with patch.object(rl.logger, "error") as mock_error:
            with patch.object(time, "time", return_value=100.0):
                rl.error_limited("message A")
                rl.error_limited("message B")
            assert mock_error.call_count == 2

    def test_passes_extra_args(self):
        """传递额外参数给底层 logger（cooldown 通过 kwarg 指定）"""
        rl = RateLimitedLogger("test")
        with patch.object(rl.logger, "error") as mock_error:
            # cooldown=0 保证每次都记录
            rl.error_limited("msg %s", 0, "extra", exc_info=True)
            mock_error.assert_called_once_with("msg %s", "extra", exc_info=True)


class TestRateLimitedLoggerWarningLimited:
    """测试 warning_limited 方法"""

    def test_first_call_warns(self):
        """第一次调用应记录警告"""
        rl = RateLimitedLogger("test")
        with patch.object(rl.logger, "warning") as mock_warn:
            rl.warning_limited("test warning")
            mock_warn.assert_called_once_with("test warning")

    def test_within_cooldown_suppressed(self):
        """冷却期内的重复调用应被抑制"""
        rl = RateLimitedLogger("test", default_cooldown=60)
        with patch.object(rl.logger, "warning") as mock_warn:
            rl.warning_limited("test warning")
            rl.warning_limited("test warning")
            assert mock_warn.call_count == 1

    def test_after_cooldown_warns_again(self):
        """冷却期后再次调用应记录警告"""
        rl = RateLimitedLogger("test", default_cooldown=1)
        with patch.object(rl.logger, "warning") as mock_warn:
            with patch.object(time, "time", return_value=100.0):
                rl.warning_limited("test warning")
            with patch.object(time, "time", return_value=102.0):
                rl.warning_limited("test warning")
            assert mock_warn.call_count == 2

    def test_custom_cooldown_used(self):
        """使用自定义冷却时间"""
        rl = RateLimitedLogger("test", default_cooldown=60)
        with patch.object(rl.logger, "warning") as mock_warn:
            with patch.object(time, "time", return_value=100.0):
                rl.warning_limited("warn", cooldown=30)
            with patch.object(time, "time", return_value=120.0):
                rl.warning_limited("warn", cooldown=30)
            assert mock_warn.call_count == 1


class TestRateLimitedLoggerClearCache:
    """测试 clear_cache 方法"""

    def test_clear_cache_allows_relog(self):
        """清除缓存后相同消息可再次记录"""
        rl = RateLimitedLogger("test", default_cooldown=3600)
        with patch.object(rl.logger, "error") as mock_error:
            # t=3700 (> cooldown=3600 → 记录)
            with patch.object(time, "time", return_value=3700.0):
                rl.error_limited("test message")
            rl.clear_cache()
            # 清除后 t=3701 (缓存已重置, delta=3701 > 3600 → 记录)
            with patch.object(time, "time", return_value=3701.0):
                rl.error_limited("test message")
            assert mock_error.call_count == 2

    def test_clear_cache_on_empty(self):
        """空缓存清除不报错"""
        rl = RateLimitedLogger("test")
        rl.clear_cache()
        assert rl._last_log_time == {}


class TestRateLimitedLogDecorator:
    """测试 rate_limited_log 装饰器"""

    def test_decorator_first_call_executes(self):
        """装饰器第一次调用应执行函数"""
        call_count = 0

        @rate_limited_log(cooldown=60, level="error")
        def my_func():
            nonlocal call_count
            call_count += 1
            return "done"

        result = my_func()
        assert result == "done"
        assert call_count == 1

    def test_decorator_within_cooldown_skips(self):
        """冷却期内的装饰器调用应跳过函数执行"""
        call_count = 0

        @rate_limited_log(cooldown=60, level="error")
        def my_func():
            nonlocal call_count
            call_count += 1
            return "done"

        # 第一次: t=100 (> cooldown=60 → 执行)
        with patch.object(time, "time", return_value=100.0):
            result1 = my_func()
        # 第二次: t=130 (delta=30 < cooldown=60 → 跳过)
        with patch.object(time, "time", return_value=130.0):
            result2 = my_func()

        assert result1 == "done"
        assert result2 is None
        assert call_count == 1

    def test_decorator_after_cooldown_executes(self):
        """冷却期后的装饰器调用应再次执行函数"""
        call_count = 0

        @rate_limited_log(cooldown=10, level="error")
        def my_func():
            nonlocal call_count
            call_count += 1
            return "done"

        with patch.object(time, "time", return_value=100.0):
            my_func()
        with patch.object(time, "time", return_value=111.0):
            my_func()

        assert call_count == 2

    def test_decorator_different_functions_independent(self):
        """不同函数的冷却独立"""
        call_a = 0
        call_b = 0

        @rate_limited_log(cooldown=60, level="error")
        def func_a():
            nonlocal call_a
            call_a += 1

        @rate_limited_log(cooldown=60, level="error")
        def func_b():
            nonlocal call_b
            call_b += 1

        with patch.object(time, "time", return_value=100.0):
            func_a()
            func_b()

        assert call_a == 1
        assert call_b == 1

    def test_decorator_preserves_function_metadata(self):
        """装饰器应保留函数元数据"""
        @rate_limited_log(cooldown=60, level="warning")
        def my_func():
            """Docstring here."""
            pass

        assert my_func.__name__ == "my_func"
        assert my_func.__doc__ == "Docstring here."

    def test_decorator_with_warning_level(self):
        """测试 warning 级别的装饰器"""
        @rate_limited_log(cooldown=60, level="warning")
        def my_func():
            return "warning_done"

        result = my_func()
        assert result == "warning_done"

    def test_decorator_with_info_level(self):
        """测试 info 级别的装饰器"""
        @rate_limited_log(cooldown=60, level="info")
        def my_func():
            return "info_done"

        result = my_func()
        assert result == "info_done"


class TestGlobalInstances:
    """测试全局日志实例"""

    def test_collision_logger_exists(self):
        """collision_logger 应有默认 cooldown=60"""
        assert isinstance(collision_logger, RateLimitedLogger)
        assert collision_logger.default_cooldown == 60

    def test_gpu_logger_exists(self):
        """gpu_logger 应有默认 cooldown=30"""
        assert isinstance(gpu_logger, RateLimitedLogger)
        assert gpu_logger.default_cooldown == 30

    def test_data_logger_exists(self):
        """data_logger 应有默认 cooldown=120"""
        assert isinstance(data_logger, RateLimitedLogger)
        assert data_logger.default_cooldown == 120

    def test_global_instances_independent(self):
        """全局实例应相互独立"""
        with patch.object(collision_logger.logger, "error") as coll_mock:
            with patch.object(data_logger.logger, "error") as data_mock:
                collision_logger.error_limited("collision msg")
                data_logger.error_limited("data msg")
                coll_mock.assert_called_once_with("collision msg")
                data_mock.assert_called_once_with("data msg")

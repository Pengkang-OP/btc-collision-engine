#!/usr/bin/env python3
"""测试辅助函数模块

提供Mock验证辅助函数,可在测试中使用
"""


class MockAssertions:
    """Mock断言辅助类

    提供常用的Mock验证方法,简化测试代码

    使用示例:
        from tests.test_helpers import MockAssertions

        def test_engine(self, mock_gpu_chain):
            mock_device, mock_context, mock_kernel = mock_gpu_chain
            # ... 测试代码 ...
            MockAssertions.assert_cleanup_called(mock_device, mock_context, mock_kernel)
    """

    @staticmethod
    def assert_cleanup_called(mock_device, mock_context, mock_kernel):
        """验证GPU资源清理是否正确调用"""
        mock_kernel.cleanup.assert_called_once()
        mock_context.cleanup.assert_called_once()
        mock_device.cleanup.assert_called_once()

    @staticmethod
    def assert_kernel_executed(mock_kernel, min_calls=1):
        """验证GPU内核执行批次调用

        Args:
            mock_kernel: GPU内核Mock
            min_calls: 最小调用次数

        """
        assert mock_kernel.run_batch.call_count >= min_calls, (
            f"GPU内核执行次数{mock_kernel.run_batch.call_count} < {min_calls}"
        )

    @staticmethod
    def assert_targets_set(mock_kernel, expected_count):
        """验证目标地址设置

        Args:
            mock_kernel: GPU内核Mock
            expected_count: 期望的目标地址数量

        """
        mock_kernel.set_targets.assert_called_once()
        call_args = mock_kernel.set_targets.call_args
        assert call_args[0][1] == expected_count, f"目标地址数量{call_args[0][1]} != {expected_count}"

    @staticmethod
    def assert_engine_running(engine):
        """验证引擎正在运行"""
        assert engine.is_running() is True

    @staticmethod
    def assert_engine_stopped(engine):
        """验证引擎已停止"""
        assert engine.is_running() is False

    @staticmethod
    def assert_batch_size_configured(mock_context, expected_batch_size):
        """验证batch_size配置

        Args:
            mock_context: GPU上下文Mock
            expected_batch_size: 期望的batch_size

        """
        mock_context.calculate_batch_size.assert_called()
        actual_batch_size = mock_context.calculate_batch_size.return_value
        assert actual_batch_size == expected_batch_size, (
            f"Batch size {actual_batch_size} != {expected_batch_size}"
        )

    @staticmethod
    def assert_gpu_initialized(mock_device):
        """验证GPU设备已初始化

        Args:
            mock_device: GPU设备Mock

        """
        mock_device.initialize.assert_called_once()

    @staticmethod
    def assert_gpu_cleaned(mock_device, mock_context, mock_kernel):
        """验证GPU资源已清理(同assert_cleanup_called)

        Args:
            mock_device: GPU设备Mock
            mock_context: GPU上下文Mock
            mock_kernel: GPU内核Mock

        """
        # 复用已有的方法
        MockAssertions.assert_cleanup_called(mock_device, mock_context, mock_kernel)

    @staticmethod
    def assert_no_collisions_found(mock_kernel):
        """验证未找到碰撞

        Args:
            mock_kernel: GPU内核Mock

        """
        # 验证run_batch返回空列表
        call_count = mock_kernel.run_batch.call_count
        if call_count > 0:
            for call in mock_kernel.run_batch.call_args_list:
                result = call[1].get("return_value") if call[1] else None
                if result is not None:
                    assert result == [], f"期望无碰撞,但找到: {result}"

    @staticmethod
    def assert_optimizer_called(mock_kernel):
        """验证GPU优化器被调用

        Args:
            mock_kernel: GPU内核Mock

        """
        mock_kernel.gpu_optimizer.analyze_and_adjust.assert_called()

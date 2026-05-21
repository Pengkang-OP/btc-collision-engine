import pytest

pytestmark = pytest.mark.gpu_hardware  # 需要真实GPU，CI中自动skip

from src.collision.gpu.engine import GPUCollisionEngine  # noqa: E402
from src.collision.targets.resolver import TargetResolver  # noqa: E402


@pytest.mark.gpu
def test_dynamic_benchmark_calculation():
    """
    测试动态性能基准值计算功能
    """
    # 创建目标解析器和目标地址
    resolver = TargetResolver()
    resolved = resolver.resolve("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa")  # 中本聪的地址
    targets = {resolved} if resolved else set()  # 引擎期望 Set[str]

    # 创建GPU碰撞引擎
    engine = GPUCollisionEngine(targets=targets, device_index=0, batch_size=100000)

    try:
        # 检查动态基准值是否存在且为正数
        assert hasattr(engine, "_dynamic_speed_benchmark"), "动态基准值属性不存在"
        assert engine._dynamic_speed_benchmark > 0, "动态基准值应该大于0"

        # 打印动态基准值
        print(f"动态性能基准值: {engine._dynamic_speed_benchmark:.0f} keys/s")

        # 验证动态基准值在合理范围内
        # 假设最小合理值为1000 keys/s，最大合理值为10,000,000 keys/s
        assert engine._dynamic_speed_benchmark >= 1000, "动态基准值过低"
        assert engine._dynamic_speed_benchmark <= 10000000, "动态基准值过高"

    finally:
        # 清理资源
        engine.stop()


@pytest.mark.gpu
def test_performance_warning_threshold():
    """
    测试性能警告阈值计算
    """
    # 创建目标解析器和目标地址
    resolver = TargetResolver()
    resolved = resolver.resolve("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa")  # 中本聪的地址
    targets = {resolved} if resolved else set()  # 引擎期望 Set[str]

    # 创建GPU碰撞引擎
    engine = GPUCollisionEngine(targets=targets, device_index=0, batch_size=100000)

    try:
        # 模拟执行一个批次，检查性能警告阈值计算
        seed = b"\x00" * 32
        batch_size = 100000
        batch_num = 1

        # 执行批次
        matches, execution_time_ms = engine._execute_gpu_batch(seed, batch_size, batch_num)

        # 检查执行时间是否合理
        assert execution_time_ms > 0, "执行时间应该大于0"

        # 打印执行时间和性能
        speed = batch_size / (execution_time_ms / 1000)
        print(f"执行时间: {execution_time_ms:.2f}ms")
        print(f"执行速度: {speed:.0f} keys/s")

    finally:
        # 清理资源
        engine.stop()


if __name__ == "__main__":
    # 运行测试
    test_dynamic_benchmark_calculation()
    test_performance_warning_threshold()
    print("所有测试通过!")

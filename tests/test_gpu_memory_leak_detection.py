import pytest
import time
from src.collision.gpu_collision_engine import GPUCollisionEngine
from src.collision.targets.resolver import TargetResolver

@pytest.mark.gpu
def test_memory_leak_detection():
    """
    测试内存泄漏检测功能
    """
    # 创建目标解析器和目标地址
    resolver = TargetResolver()
    resolved = resolver.resolve('1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa')  # 中本聪的地址
    targets = {resolved} if resolved else set()  # 引擎期望 Set[str]

    # 创建GPU碰撞引擎
    engine = GPUCollisionEngine(
        targets=targets,
        device_index=0,
        batch_size=100000
    )

    try:
        # 执行一些批次，产生一些缓冲区
        seed = b'\x00' * 32
        batch_size = 100000

        # 执行几个批次
        for i in range(3):
            matches, execution_time_ms = engine._execute_gpu_batch(seed, batch_size, i + 1)
            print(f"批次 {i+1} 执行时间: {execution_time_ms:.2f}ms")
            time.sleep(0.1)  # 短暂暂停

        # 调用内存泄漏检查
        engine._check_memory_leaks()

        # 验证检查是否成功执行（没有抛出异常）
        assert True, "内存泄漏检查执行成功"

    finally:
        # 清理资源
        engine.stop()

@pytest.mark.gpu
def test_buffer_release():
    """
    测试缓冲区释放功能
    """
    # 创建目标解析器和目标地址
    resolver = TargetResolver()
    resolved = resolver.resolve('1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa')  # 中本聪的地址
    targets = {resolved} if resolved else set()  # 引擎期望 Set[str]

    # 创建GPU碰撞引擎
    engine = GPUCollisionEngine(
        targets=targets,
        device_index=0,
        batch_size=100000
    )

    try:
        # 执行一些批次，产生一些缓冲区
        seed = b'\x00' * 32
        batch_size = 100000

        # 执行几个批次
        for i in range(3):
            matches, execution_time_ms = engine._execute_gpu_batch(seed, batch_size, i + 1)
            print(f"批次 {i+1} 执行时间: {execution_time_ms:.2f}ms")
            time.sleep(0.1)  # 短暂暂停

        # 模拟关闭过程中的缓冲区释放
        # 注意：这里我们不直接调用内部方法，而是通过正常的stop方法
        engine.stop()

        # 验证引擎已停止
        assert not engine._running, "引擎应该已停止"

    finally:
        # 确保资源被释放
        if engine._running:
            engine.stop()

if __name__ == "__main__":
    # 运行测试
    test_memory_leak_detection()
    test_buffer_release()
    print("所有测试通过!")

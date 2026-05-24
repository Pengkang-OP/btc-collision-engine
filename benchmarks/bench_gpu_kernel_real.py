"""
GPU 内核性能基准测试（真实硬件）
测试: 内核编译时间 + 批次执行时间 + 吞吐量
"""

import sys
import time

from src.collision.gpu.engine import GPUCollisionEngine


def test_kernel_compilation():
    """测试 GPU 内核编译时间"""
    print("=" * 60)
    print("1. GPU 内核编译时间")
    print("=" * 60)

    targets = {"12ib7dApVFvg82TXKycWBNpN8kFyiAN1dr"}

    # 首次初始化会触发内核编译
    t0 = time.perf_counter()
    engine = GPUCollisionEngine(
        targets=targets,
        device_index=-1,
        batch_size=65536,
        checkpoint_enabled=False,
        dedup_enabled=False,
        data_logging_enabled=False,
    )
    t1 = time.perf_counter()
    compile_time = t1 - t0

    dev_info = engine.get_device_info()
    print(f"  设备: {dev_info.get('name', 'Unknown')}")
    print(f"  内核编译 + 初始化: {compile_time:.3f}s")
    engine.start(mode="random")
    time.sleep(1)
    engine.stop()
    return compile_time


def test_batch_throughput(
    batch_sizes: list[int],
    duration: int = 3,
) -> list[tuple[int, int, float, float]]:
    """测试不同批次大小的吞吐量"""
    print("\n" + "=" * 60)
    print("2. 批次大小 vs 吞吐量")
    print("=" * 60)
    header = f"{'Batch Size':>12} | {'Keys':>12} | {'Time':>8} | {'Throughput':>14}"
    print(header)
    print("-" * 52)

    results = []
    for bs in batch_sizes:
        targets = {"12ib7dApVFvg82TXKycWBNpN8kFyiAN1dr"}
        engine = GPUCollisionEngine(
            targets=targets,
            device_index=-1,
            batch_size=bs,
            checkpoint_enabled=False,
            dedup_enabled=False,
            data_logging_enabled=False,
        )
        t0 = time.time()
        engine.start(mode="random")
        time.sleep(duration)
        engine.stop()
        elapsed = time.time() - t0

        # 从日志获取实际处理量（stats 通过回调）
        # 使用引擎内置统计
        try:
            stats = engine.get_stats()
            checked = stats.total_checked
        except Exception:
            checked = 0

        throughput = checked / elapsed if elapsed > 0 else 0
        results.append((bs, checked, elapsed, throughput))
        result_line = f"{bs:>12,} | {checked:>12,} | {elapsed:>7.2f}s | {throughput:>12,.0f} keys/s"
        print(result_line)

    print("-" * 52)
    best = max(results, key=lambda r: r[3])
    print(f"  最佳批次: {best[0]:>8,} | {best[3]:>12,.0f} keys/s")
    return results


def test_single_vendor_nvidia():
    """测试指定 NVIDIA 单卡性能"""
    print("\n" + "=" * 60)
    print("3. NVIDIA 单卡测试")
    print("=" * 60)

    import pyopencl as cl

    nvidia_devices = []
    for p in cl.get_platforms():
        if "nvidia" in p.name.lower():
            for d in p.get_devices():
                nvidia_devices.append((p.name, d.name))

    if not nvidia_devices:
        print("  [SKIP] NVIDIA GPU 未通过 OpenCL 可用")
        return

    print(f"  平台: {nvidia_devices[0][0]}")
    print(f"  设备: {nvidia_devices[0][1]}")

    targets = {"12ib7dApVFvg82TXKycWBNpN8kFyiAN1dr"}
    t0 = time.perf_counter()
    engine = GPUCollisionEngine(
        targets=targets,
        device_index=0,  # NVIDIA 是设备 0
        batch_size=65536,
        checkpoint_enabled=False,
        dedup_enabled=False,
        data_logging_enabled=False,
    )
    init_time = time.perf_counter() - t0
    print(f"  初始化时间: {init_time:.3f}s")

    engine.start(mode="random")
    time.sleep(5)
    engine.stop()
    print("  引擎运行: 5秒 (正常)")


def main():
    print("=" * 60)
    print("  GPU 内核性能基准测试（真实硬件）")
    print("=" * 60)

    # 1. 内核编译时间
    _ = test_kernel_compilation()

    # 2. 批次吞吐量
    batch_sizes = [65536, 262144, 1048576, 4194304]
    _ = test_batch_throughput(batch_sizes, duration=3)

    # 3. NVIDIA 单卡
    test_single_vendor_nvidia()

    print("\n" + "=" * 60)
    print("  基准测试完成")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())

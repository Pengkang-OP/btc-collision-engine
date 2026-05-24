"""GPU 性能基准测试 - 在本地 GPU 上运行"""
import time
import sys
import os
import json

# 设置 stdout 编码，避免 GBK 编码问题
if sys.stdout.encoding.lower() in ('gbk', 'gb2312', 'cp936'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

try:
    from src.collision.gpu.engine import GPUCollisionEngine, list_gpu_devices
except ImportError:
    try:
        from src.collision import GPUCollisionEngine

        def list_gpu_devices():
            return []
    except ImportError:
        print("[ERROR] 无法导入 GPUCollisionEngine")
        sys.exit(1)


def main():
    print("=" * 60)
    print("GPU 性能基准测试")
    print("=" * 60)

    # 检测 GPU 设备
    try:
        import pyopencl as cl
        devices = []
        for plat in cl.get_platforms():
            for dev in plat.get_devices():
                devices.append({"name": dev.name.strip(), "platform": plat.name.strip()})
        print("GPU 设备列表:")
        for i, d in enumerate(devices):
            print(f"  [{i}] {d['name']} ({d['platform']})")
    except Exception as e:
        print(f"pyopencl 检测失败: {e}")
        devices = []

    if not devices:
        print("未检测到 GPU 设备")
        sys.exit(1)

    # 选择 Intel Arc A770 (通常索引 1)
    target_idx = 1 if len(devices) > 1 else 0
    device_name = devices[target_idx]["name"]
    print(f"\n使用设备 [{target_idx}]: {device_name}")

    # 运行短时间 GPU 基准测试 (使用 benchmark_optimizations 中的测试)
    print("\n运行 GPU 性能基准测试...")
    print("  目标: 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa")
    print("  模式: random, batch_size=1,048,576\n")

    try:
        import warnings
        warnings.filterwarnings("ignore")

        engine = GPUCollisionEngine(
            targets={"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"},
            device_index=target_idx,
            batch_size=1048576,
        )

        engine.start()
        test_duration = 120  # 2 分钟
        print(f"  运行 {test_duration} 秒...")
        for remaining in range(test_duration, 0, -30):
            time.sleep(min(30, remaining))
            try:
                s = engine.stats
                if s and hasattr(s, 'speed') and s.speed:
                    print(f"    剩余 {remaining}s - 当前速度: {s.speed:,.0f} keys/s, 已检测: {s.total_checked:,}")
            except Exception:
                pass

        engine.stop()
        time.sleep(2)  # 等待引擎完全停止

        stats = getattr(engine, 'stats', None)
        if stats:
            total = getattr(stats, 'total_checked', 0)
            speed = getattr(stats, 'speed', 0)
            matches = len(getattr(stats, 'matches', []) or [])
            elapsed = getattr(stats, 'elapsed', test_duration)

            print(f"\n{'=' * 60}")
            print("GPU 性能测试结果")
            print(f"{'=' * 60}")
            print(f"  GPU 设备:      {device_name}")
            print(f"  运行时间:      {elapsed:.1f} 秒")
            print(f"  总检测数:      {total:,}")
            print(f"  平均速度:      {speed:,.0f} keys/s")
            print(f"  匹配数:        {matches}")
            print(f"{'=' * 60}")

            result = {
                "device": device_name,
                "runtime_seconds": elapsed,
                "total_checked": total,
                "avg_speed_keys_per_sec": speed,
                "matches": matches,
                "batch_size": 1048576,
                "test_type": "local_gpu_benchmark",
            }
            os.makedirs("test_results", exist_ok=True)
            with open("test_results/gpu_benchmark_result.json", "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print("结果保存至: test_results/gpu_benchmark_result.json")
        else:
            print("无法获取统计数据")

    except Exception as e:
        print(f"GPU 基准测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

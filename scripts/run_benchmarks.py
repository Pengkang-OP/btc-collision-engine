"""性能基准测试自动化工具

自动运行多项性能测试，汇总对比结果，生成基准报告。

用法:
    python scripts/run_benchmarks.py               # 运行所有基准测试
    python scripts/run_benchmarks.py --quick       # 快速模式（仅CPU）
    python scripts/run_benchmarks.py --json        # 以 JSON 格式输出
    python scripts/run_benchmarks.py --duration 30 # 每项测试 30 秒
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# 确保项目根目录在路径中
_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))


# ─────────────────────────────────────────────────────────────────────────────
# 基准测试项
# ─────────────────────────────────────────────────────────────────────────────


def bench_key_generation(duration: float = 10.0) -> dict[str, Any]:
    """基准测试: 私钥生成速度"""
    from src.core.key_generator import SecureKeyGenerator

    gen = SecureKeyGenerator()

    start = time.perf_counter()
    count = 0
    while time.perf_counter() - start < duration:
        gen.generate_secure_key()
        count += 1

    elapsed = time.perf_counter() - start
    return {
        "name": "私钥生成",
        "keys_per_sec": count / elapsed,
        "total_keys": count,
        "duration_sec": elapsed,
    }


def bench_address_conversion(duration: float = 10.0) -> dict[str, Any]:
    """基准测试: 私钥 → 地址转换速度"""
    from src.core.address_converter import AddressConverter
    from src.core.key_generator import SecureKeyGenerator

    gen = SecureKeyGenerator()
    conv = AddressConverter()
    key = gen.generate_secure_key()  # 预生成一个密钥

    start = time.perf_counter()
    count = 0
    while time.perf_counter() - start < duration:
        conv.private_key_to_address(key)
        count += 1

    elapsed = time.perf_counter() - start
    return {
        "name": "地址转换",
        "keys_per_sec": count / elapsed,
        "total_keys": count,
        "duration_sec": elapsed,
    }


def bench_address_lookup(duration: float = 10.0, target_count: int = 1000) -> dict[str, Any]:
    """基准测试: 地址哈希表查找速度"""
    from src.core.address_converter import AddressConverter
    from src.core.key_generator import SecureKeyGenerator
    from src.core.target_address_table import BitcoinTargetTable

    gen = SecureKeyGenerator()
    conv = AddressConverter()
    table = BitcoinTargetTable()

    # 构建目标表
    for _ in range(target_count):
        k = gen.generate_secure_key()
        a = conv.private_key_to_address(k)
        table.add_address(a)

    test_addr = conv.private_key_to_address(gen.generate_secure_key())

    start = time.perf_counter()
    count = 0
    while time.perf_counter() - start < duration:
        table.contains(test_addr)
        count += 1

    elapsed = time.perf_counter() - start
    return {
        "name": f"地址查找({target_count}目标)",
        "lookups_per_sec": count / elapsed,
        "total_lookups": count,
        "table_size": target_count,
        "duration_sec": elapsed,
    }


def bench_cpu_engine(duration: float = 15.0) -> dict[str, Any]:
    """基准测试: CPU 碰撞引擎吞吐量"""
    from src.collision.key_collision_engine import KeyCollisionEngine

    results = {"keys_checked": 0, "speed": 0.0, "error": None}

    try:
        engine = KeyCollisionEngine(
            targets={"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"},
            enable_optimization=True,
        )
        engine.start(mode="random")

        time.sleep(duration)

        stats = engine.get_stats()
        elapsed = stats.elapsed if stats.elapsed > 0 else duration
        results["keys_checked"] = stats.total_checked
        results["speed"] = stats.total_checked / elapsed

        engine.stop()
    except Exception as exc:
        results["error"] = str(exc)

    return {
        "name": "CPU 碰撞引擎",
        "keys_per_sec": results["speed"],
        "total_keys": results["keys_checked"],
        "duration_sec": duration,
        "error": results["error"],
    }


def bench_gpu_engine(duration: float = 15.0) -> dict[str, Any] | None:
    """基准测试: GPU 碰撞引擎吞吐量（需要 PyOpenCL）"""
    try:
        pass
    except ImportError:
        return None

    try:
        from src.collision.gpu_collision_engine import GPUCollisionEngine

        engine = GPUCollisionEngine(
            targets={"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"},
        )
        engine.start(mode="random")
        time.sleep(duration)
        stats = engine.get_stats()
        elapsed = stats.elapsed if stats.elapsed > 0 else duration
        speed = stats.total_checked / elapsed if elapsed > 0 else 0
        engine.stop()
        return {
            "name": "GPU 碰撞引擎",
            "keys_per_sec": speed,
            "total_keys": stats.total_checked,
            "duration_sec": duration,
            "error": None,
        }
    except Exception as exc:
        return {
            "name": "GPU 碰撞引擎",
            "keys_per_sec": 0,
            "total_keys": 0,
            "duration_sec": duration,
            "error": str(exc),
        }


# ─────────────────────────────────────────────────────────────────────────────
# 汇总与报告
# ─────────────────────────────────────────────────────────────────────────────


def _fmt_speed(speed: float) -> str:
    if speed >= 1_000_000:
        return f"{speed / 1_000_000:.2f} M/s"
    if speed >= 1_000:
        return f"{speed / 1_000:.1f} K/s"
    return f"{speed:.0f} /s"


def run_all(duration: float = 10.0, quick: bool = False) -> dict[str, Any]:
    """运行所有基准测试并汇总结果"""
    report: dict[str, Any] = {
        "timestamp": datetime.now().isoformat(),
        "platform": _get_platform_info(),
        "benchmarks": [],
    }

    tests = [
        ("私钥生成", lambda: bench_key_generation(duration)),
        ("地址转换", lambda: bench_address_conversion(duration)),
        ("地址查找", lambda: bench_address_lookup(duration)),
    ]
    if not quick:
        tests.append(("CPU引擎", lambda: bench_cpu_engine(duration * 1.5)))
        tests.append(("GPU引擎", lambda: bench_gpu_engine(duration * 1.5)))

    for name, fn in tests:
        print(f"  [运行中] {name}...", end="", flush=True)
        try:
            result = fn()
            if result is None:
                print(" [跳过]（未找到 GPU）")
                continue
            report["benchmarks"].append(result)
            speed_key = "keys_per_sec" if "keys_per_sec" in result else "lookups_per_sec"
            speed = result.get(speed_key, 0)
            err = result.get("error")
            if err:
                print(f" [!] {err[:60]}")
            else:
                print(f" {_fmt_speed(speed)}")
        except Exception as exc:
            print(f" [ERROR] {exc}")
            report["benchmarks"].append({"name": name, "error": str(exc)})

    return report


def _get_platform_info() -> dict[str, str]:
    import platform

    return {
        "os": platform.system(),
        "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "machine": platform.machine(),
    }


def print_report(report: dict[str, Any]):
    """打印人类可读的基准测试报告"""
    ts = report.get("timestamp", "N/A")
    plat = report.get("platform", {})
    benches = report.get("benchmarks", [])

    print("\n" + "=" * 65)
    print("  BTC 碰撞引擎 - 性能基准测试报告")
    print("=" * 65)
    print(f"  时间  : {ts}")
    print(f"  系统  : {plat.get('os', '?')} / Python {plat.get('python', '?')}")
    print("-" * 65)
    print(f"  {'测试项目':<24} {'速度':>15} {'总计':>14}")
    print("-" * 65)

    for b in benches:
        name = b.get("name", "?")
        err = b.get("error")
        if err:
            print(f"  {name:<24} [错误] {err[:30]}")
            continue
        speed_key = "keys_per_sec" if "keys_per_sec" in b else "lookups_per_sec"
        speed = b.get(speed_key, 0)
        total_key = "total_keys" if "total_keys" in b else "total_lookups"
        total = b.get(total_key, 0)
        print(f"  {name:<24} {_fmt_speed(speed):>15} {total:>12,}")

    # CPU vs GPU 对比
    cpu_speed = next((b["keys_per_sec"] for b in benches if "CPU" in b.get("name", "")), None)
    gpu_speed = next(
        (b["keys_per_sec"] for b in benches if "GPU" in b.get("name", "") and not b.get("error")),
        None,
    )
    if cpu_speed and gpu_speed and cpu_speed > 0:
        ratio = gpu_speed / cpu_speed
        print("-" * 65)
        print(f"  GPU 加速倍数: {ratio:.0f}x")

    print("=" * 65)


# ─────────────────────────────────────────────────────────────────────────────
# CLI 入口
# ─────────────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="BTC碰撞引擎 - 性能基准测试自动化")
    parser.add_argument("--quick", action="store_true", help="快速模式（跳过引擎测试）")
    parser.add_argument("--json", action="store_true", help="以 JSON 格式输出结果")
    parser.add_argument("--duration", type=float, default=10.0, help="每项测试时长（秒，默认: 10）")
    parser.add_argument("--save", metavar="FILE", help="保存报告到 JSON 文件")
    args = parser.parse_args()

    print("=" * 65)
    print("  BTC 碰撞引擎 - 性能基准测试")
    print("=" * 65)
    print(f"  每项测试时长: {args.duration} 秒")
    print(f"  测试模式    : {'快速' if args.quick else '完整'}")
    print("-" * 65)

    report = run_all(duration=args.duration, quick=args.quick)

    if args.json or args.save:
        output = json.dumps(report, ensure_ascii=False, indent=2)
        if args.json:
            print(output)
        if args.save:
            Path(args.save).write_text(output, encoding="utf-8")
            print(f"\n  报告已保存: {args.save}")
    else:
        print_report(report)


if __name__ == "__main__":
    main()

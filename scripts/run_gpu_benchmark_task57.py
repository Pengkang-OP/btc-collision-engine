# -*- coding: utf-8 -*-
"""
Task #57: GPU 性能基准测试
验证队列深度优化（queue_depth=4）+ 种子预生成线程的实际效果

对比基线：3.07M keys/s（GPU PRNG + 双缓冲）
预期目标：~3.4M keys/s（+10%）

用法：
    python run_gpu_benchmark_task57.py [--duration 30]
"""

import argparse
import json
import os
import sys
import time
import statistics
from datetime import datetime
from pathlib import Path

# 确保从项目根目录运行
_ROOT = Path(__file__).parent
sys.path.insert(0, str(_ROOT))

BASELINE_KEYS_PER_SEC = 3_070_000  # 3.07M keys/s 基线
TARGET_KEYS_PER_SEC = 3_400_000  # 3.40M keys/s 目标（+10%）


def load_config(config_path: str) -> dict:
    """加载配置文件"""
    with open(config_path, "r", encoding="utf-8") as f:
        raw = f.read()
    # 剥离 JSON5 风格注释（//...行）
    import re

    raw = re.sub(r"//[^\n]*", "", raw)
    return json.loads(raw)


def load_targets(path: str = "valid_addresses.txt") -> set:
    """从文件加载目标地址"""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"目标地址文件不存在: {path}")
    addresses = set()
    with open(p, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                addresses.add(line)
    return addresses


def run_benchmark(duration_sec: int = 30) -> dict:
    """
    运行 GPU 性能基准测试

    Returns:
        包含吞吐量等指标的结果字典
    """
    print("\n" + "=" * 70)
    print("  Task #57 GPU 性能基准测试")
    print("  验证：队列深度优化 + 种子预生成线程")
    print("=" * 70)
    print(f"  时间   : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  测试时长: {duration_sec} 秒")
    print(f"  基线   : {BASELINE_KEYS_PER_SEC/1e6:.2f}M keys/s")
    print(f"  目标   : {TARGET_KEYS_PER_SEC/1e6:.2f}M keys/s (+10%)")
    print("=" * 70 + "\n")

    # ── 1. 加载配置 ──────────────────────────────────────────
    config_file = _ROOT / "config.intel_arc.json"
    if not config_file.exists():
        config_file = _ROOT / "config.json"
    print(f"[1/5] 加载配置: {config_file.name}")
    config = load_config(str(config_file))

    gpu_cfg = config.get("gpu", {})
    batch_size = gpu_cfg.get("batch_size", 1_048_576)
    queue_depth = gpu_cfg.get("queue_depth", 4)
    seed_prefetch_size = gpu_cfg.get("seed_prefetch_size", 5)
    async_exec = gpu_cfg.get("async_execution", True)

    print(f"    batch_size       = {batch_size:,}")
    print(f"    queue_depth      = {queue_depth}")
    print(f"    seed_prefetch_size = {seed_prefetch_size}")
    print(f"    async_execution  = {async_exec}")

    # ── 2. 加载目标地址 ────────────────────────────────────
    print("\n[2/5] 加载目标地址...")
    targets = load_targets(str(_ROOT / "valid_addresses.txt"))
    print(f"    目标数量: {len(targets)}")

    # ── 3. 初始化引擎 ──────────────────────────────────────
    print("\n[3/5] 初始化 GPU 碰撞引擎...")
    try:
        from src.collision.gpu_collision_engine import GPUCollisionEngine
    except ImportError as e:
        print(f"    [ERROR] 无法导入 GPUCollisionEngine: {e}")
        return {"error": str(e), "success": False}

    speed_samples = []
    total_checked = 0
    start_time_ref = [None]

    def on_progress(stats):
        """进度回调：收集吞吐量采样"""
        speed = stats.speed if hasattr(stats, "speed") else getattr(stats, "keys_per_second", 0)
        if speed > 0:
            speed_samples.append(speed)
        # 获取 total_checked
        nonlocal total_checked
        total_checked = getattr(stats, "total_checked", 0)

    def on_match(private_key, address, wif):
        print(f"    [MATCH] 发现匹配! 地址: {address}")

    # 注意：GPUCollisionEngine 通过自动读取 config.intel_arc.json / config.json
    # 获取 queue_depth / seed_prefetch_size 等参数，不需要也不支持 config= 构造参数
    try:
        init_start = time.time()
        engine = GPUCollisionEngine(
            targets=targets,
            device_index=-1,
            batch_size=batch_size,
            on_progress=on_progress,
            on_match=on_match,
        )
        init_elapsed = time.time() - init_start
        print(f"    引擎初始化耗时: {init_elapsed:.2f}s")
    except Exception as e:
        print(f"    [ERROR] 引擎初始化失败: {e}")
        import traceback

        traceback.print_exc()
        return {"error": str(e), "success": False}

    # ── 4. 验证优化特性已加载 ────────────────────────────────
    print("\n[4/5] 验证优化特性...")
    # 检查 queue_depth
    async_executor = getattr(engine, "_async_executor", None)
    actual_queue_depth = (
        getattr(async_executor, "queue_depth", "N/A") if async_executor else "N/A（同步模式）"
    )
    print(f"    AsyncGPUExecutor.queue_depth = {actual_queue_depth}")

    # 检查种子预生成线程
    random_mode = getattr(engine, "_random_search_mode", None)
    seed_thread = getattr(random_mode, "_seed_thread", None)
    seed_thread_alive = seed_thread.is_alive() if seed_thread else False
    seed_prefetch_actual = (
        getattr(random_mode, "_seed_prefetch_size", "N/A") if random_mode else "N/A"
    )
    print(f"    SeedPrefetch 线程运行中 = {seed_thread_alive}")
    print(f"    SeedPrefetch 缓存深度   = {seed_prefetch_actual}")

    # 检查异步执行器
    async_exec_enabled = getattr(
        getattr(engine, "_gpu_device", None), "enable_async_execution", False
    )
    print(f"    异步执行已启用 = {async_exec_enabled}")

    # ── 5. 运行测试 ─────────────────────────────────────────
    print(f"\n[5/5] 运行 GPU 基准测试（{duration_sec}秒）...")
    print("-" * 70)
    print(f"  {'时间':>6}  {'速度':>14}  {'累计Keys':>14}  {'样本数':>6}")
    print("-" * 70)

    start_time_ref[0] = time.time()
    try:
        engine.start(mode="random")
    except Exception as e:
        print(f"    [ERROR] 引擎启动失败: {e}")
        import traceback

        traceback.print_exc()
        return {"error": str(e), "success": False}

    last_print_time = time.time()
    test_start = time.time()
    interval_speeds = []

    while time.time() - test_start < duration_sec:
        time.sleep(5)
        elapsed = time.time() - test_start

        # 取最近5秒的采样作为当前速度
        if speed_samples:
            recent_speed = speed_samples[-1]
            interval_speeds.append(recent_speed)
            print(
                f"  {elapsed:5.0f}s  {recent_speed/1e6:12.3f}M/s  {total_checked:>14,}  {len(speed_samples):>6}"
            )

    # 停止引擎
    try:
        engine.stop()
    except Exception as e:
        print(f"    [WARN] 停止引擎时异常: {e}")

    print("-" * 70)

    # ── 计算统计结果 ──────────────────────────────────────
    if len(speed_samples) < 2:
        print("\n[WARN] 采样数据不足，性能数据可能不准确")

    if speed_samples:
        avg_speed = statistics.mean(speed_samples)
        max_speed = max(speed_samples)
        min_speed = min(speed_samples)
        std_speed = statistics.stdev(speed_samples) if len(speed_samples) > 1 else 0.0

        # 去除前3个预热采样（如果足够多）
        warmup_skip = 3
        stable_samples = (
            speed_samples[warmup_skip:] if len(speed_samples) > warmup_skip + 2 else speed_samples
        )
        stable_avg = statistics.mean(stable_samples) if stable_samples else avg_speed
    else:
        avg_speed = max_speed = min_speed = std_speed = stable_avg = 0.0

    # 收集异步执行器统计
    executor_stats = {}
    if async_executor:
        try:
            executor_stats = async_executor.get_stats()
        except Exception:
            pass

    # ── 打印结果摘要 ──────────────────────────────────────
    print("\n" + "=" * 70)
    print("  性能测试结果")
    print("=" * 70)
    print(f"  测试时长       : {duration_sec}s")
    print(f"  采样次数       : {len(speed_samples)}")
    print(f"  最高速度       : {max_speed/1e6:.3f}M keys/s")
    print(f"  平均速度       : {avg_speed/1e6:.3f}M keys/s")
    print(f"  稳定平均速度   : {stable_avg/1e6:.3f}M keys/s（跳过前{warmup_skip}个预热采样）")
    print(f"  最低速度       : {min_speed/1e6:.3f}M keys/s")
    print(f"  速度标准差     : {std_speed/1e6:.3f}M keys/s")
    print(f"  总检查密钥数   : {total_checked:,}")

    print("\n  --- 优化特性验证 ---")
    print(f"  queue_depth      : {actual_queue_depth}")
    print(f"  seed_prefetch    : {seed_prefetch_actual} (线程运行={seed_thread_alive})")
    print(f"  异步执行         : {async_exec_enabled}")

    if executor_stats:
        print("\n  --- AsyncGPUExecutor 统计 ---")
        print(f"  异步执行批次     : {executor_stats.get('async_executions', 'N/A')}")
        print(f"  同步回退次数     : {executor_stats.get('sync_fallbacks', 'N/A')}")
        print(f"  异步执行率       : {executor_stats.get('async_rate_percent', 0):.1f}%")
        print(f"  queue_depth_hits : {executor_stats.get('queue_depth_hits', 'N/A')}")

    print("\n  --- 对比分析 ---")
    baseline = BASELINE_KEYS_PER_SEC
    target = TARGET_KEYS_PER_SEC
    delta_vs_baseline = (stable_avg - baseline) / baseline * 100 if baseline > 0 else 0
    delta_vs_target = (stable_avg - target) / target * 100 if target > 0 else 0

    print(f"  基线 (3.07M)   : {baseline/1e6:.2f}M keys/s")
    print(f"  目标 (+10%)    : {target/1e6:.2f}M keys/s")
    print(f"  实测稳定速度   : {stable_avg/1e6:.3f}M keys/s")
    print(f"  vs 基线        : {delta_vs_baseline:+.1f}%")
    print(f"  vs 目标        : {delta_vs_target:+.1f}%")

    if stable_avg >= target:
        print(f"\n  ✅ 性能目标达成！实测 {stable_avg/1e6:.3f}M >= 目标 {target/1e6:.2f}M keys/s")
    elif stable_avg >= baseline:
        print(f"\n  ⚠️  性能有所提升但未达目标（{stable_avg/1e6:.3f}M vs 目标 {target/1e6:.2f}M）")
    else:
        print(f"\n  ❌ 性能未提升（{stable_avg/1e6:.3f}M vs 基线 {baseline/1e6:.2f}M）")

    print("=" * 70 + "\n")

    # ── 保存结果到 JSON ──────────────────────────────────
    result = {
        "test_time": datetime.now().isoformat(timespec="seconds"),
        "config_file": str(config_file.name),
        "duration_sec": duration_sec,
        "batch_size": batch_size,
        "queue_depth_config": queue_depth,
        "queue_depth_actual": actual_queue_depth,
        "seed_prefetch_size": seed_prefetch_actual,
        "async_execution": async_exec_enabled,
        "total_checked": total_checked,
        "speed_samples_count": len(speed_samples),
        "max_speed": round(max_speed, 2),
        "avg_speed": round(avg_speed, 2),
        "stable_avg_speed": round(stable_avg, 2),
        "min_speed": round(min_speed, 2),
        "std_speed": round(std_speed, 2),
        "baseline_keys_per_sec": BASELINE_KEYS_PER_SEC,
        "target_keys_per_sec": TARGET_KEYS_PER_SEC,
        "delta_vs_baseline_pct": round(delta_vs_baseline, 2),
        "delta_vs_target_pct": round(delta_vs_target, 2),
        "target_achieved": stable_avg >= TARGET_KEYS_PER_SEC,
        "baseline_exceeded": stable_avg >= BASELINE_KEYS_PER_SEC,
        "executor_stats": executor_stats,
        "success": True,
    }

    out_dir = _ROOT / "test_results"
    out_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"task57_gpu_benchmark_{ts}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"  结果已保存: {out_path}")

    return result


def main():
    parser = argparse.ArgumentParser(description="Task #57: GPU 性能基准测试")
    parser.add_argument("--duration", type=int, default=60, help="测试时长（秒），默认60秒")
    args = parser.parse_args()

    result = run_benchmark(duration_sec=args.duration)
    if not result.get("success", False):
        print(f"\n[FAIL] 测试失败: {result.get('error', '未知错误')}")
        sys.exit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""诊断引擎速度为0的问题"""

import logging
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.collision import KeyCollisionEngine  # noqa: E402

# 设置日志级别为DEBUG
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


def diagnose_engine():
    """诊断引擎问题"""

    print("=" * 70)
    print("引擎诊断工具")
    print("=" * 70)
    print()

    # 创建引擎
    targets = {"1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"}

    print("1. 创建引擎...")
    engine = KeyCollisionEngine(
        targets=targets,
        on_progress=lambda stats: print(
            f"   📊 进度回调: {stats.total_checked:,} keys, {stats.speed:.2f} keys/s"
        ),
        on_match=lambda pk, addr, wif: print(f"   🎯 匹配: {addr}"),
        checkpoint_enabled=False,  # 禁用断点避免权限问题
        dedup_enabled=False,
        max_workers=4,
    )
    print("   OK 引擎创建成功")
    print()

    # 启动引擎
    print("2. 启动引擎 (random模式, 10秒)...")
    engine.start(mode="random")
    print("   OK 引擎已启动")
    print()

    # 监控10秒
    print("3. 监控引擎状态 (10秒)...")
    print()

    last_count = 0

    for i in range(10):
        time.sleep(1)

        stats = engine.get_stats()
        is_running = engine.is_running()

        # 检查线程状态
        thread_alive = engine._thread.is_alive() if engine._thread else False

        # 检查内部计数器
        live_count = engine._live_range_count if hasattr(engine, "_live_range_count") else 0

        print(
            f"   [{i + 1:2d}s] 运行={is_running}, 线程={thread_alive}, "
            f"已检查={stats.total_checked:,}, 速度={stats.speed:,.0f} keys/s, "
            f"live_count={live_count:,}"
        )

        # 检查计数是否增长
        if stats.total_checked > last_count:
            print(f"         OK 计数增长: +{stats.total_checked - last_count:,}")
        elif stats.total_checked == 0 and i > 2:
            print(f"         WARNING: 运行{i + 1}秒后仍为0")

        last_count = stats.total_checked

    print()

    # 停止引擎
    print("4. 停止引擎...")
    engine.stop()
    time.sleep(1)

    final_stats = engine.get_stats()
    print("   OK 引擎已停止")
    print()

    # 最终统计
    print("=" * 70)
    print("📊 诊断结果:")
    print("=" * 70)
    print(f"  总检查数: {final_stats.total_checked:,}")
    print(f"  运行时间: {final_stats.elapsed:.1f}秒")
    print(f"  平均速度: {final_stats.speed:,.0f} keys/s")
    print(f"  匹配数: {len(final_stats.matches)}")
    print()

    if final_stats.total_checked == 0:
        print("PROBLEM: 引擎速度确实为0")
        print()
        print("可能的原因:")
        print("  1. 工作线程未正常启动")
        print("  2. 工作线程阻塞在某个操作上")
        print("  3. 统计数据未正确更新")
        print("  4. SecureKeyManager或其他组件异常")
        print()
        print("建议:")
        print("  - 检查DEBUG日志查看工作线程是否启动")
        print("  - 检查是否有异常被捕获但未记录")
        print("  - 检查batch_size是否正确设置")
    else:
        print(f"OK 引擎正常工作，速度: {final_stats.speed:,.0f} keys/s")

    print("=" * 70)


if __name__ == "__main__":
    diagnose_engine()

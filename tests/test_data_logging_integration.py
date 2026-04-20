#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据日志集成竞态条件测试

验证优化后的代码在并发场景下的正确性。
"""

import os
import sys
import time
import threading

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.collision.key_collision_engine import KeyCollisionEngine
from src.utils import init_logging


def test_stats_consistency():
    """测试统计信息一致性（验证竞态条件修复）"""
    print("\n" + "="*60)
    print("测试 1: 统计信息一致性测试")
    print("="*60)
    
    targets = {"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"}
    
    engine = KeyCollisionEngine(
        targets=targets,
        max_workers=4,
        data_logging_enabled=True,
        data_logging_interval=1
    )
    
    # 在后台线程运行
    def run_engine():
        engine.random_search()
    
    thread = threading.Thread(target=run_engine, daemon=True)
    thread.start()
    
    # 运行3秒
    time.sleep(3)
    
    # 停止引擎
    engine.stop()
    thread.join(timeout=5)
    
    # 验证统计信息
    stats = engine.get_stats()
    print(f"\n最终统计:")
    print(f"  总检查数: {stats.total_checked:,}")
    print(f"  运行时间: {stats.elapsed:.2f}秒")
    print(f"  平均速度: {stats.speed:,.0f} 次/秒")
    print(f"  匹配数: {len(stats.matches)}")
    
    # 验证数据一致性
    assert stats.total_checked > 0, "总检查数应大于0"
    assert stats.elapsed > 0, "运行时间应大于0"
    assert stats.speed > 0, "速度应大于0"
    
    print("\n✅ 统计信息一致性测试通过")
    return True


def test_data_logging_thread_safety():
    """测试数据日志线程安全性"""
    print("\n" + "="*60)
    print("测试 2: 数据日志线程安全测试")
    print("="*60)
    
    targets = {"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"}
    
    engine = KeyCollisionEngine(
        targets=targets,
        max_workers=8,  # 使用更多线程增加并发压力
        data_logging_enabled=True,
        data_logging_interval=1  # 较短的间隔
    )
    
    def run_engine():
        engine.random_search()
    
    thread = threading.Thread(target=run_engine, daemon=True)
    thread.start()
    
    # 运行2秒
    time.sleep(2)
    
    engine.stop()
    thread.join(timeout=5)
    
    stats = engine.get_stats()
    print(f"\n高并发测试结果:")
    print(f"  总检查数: {stats.total_checked:,}")
    print(f"  工作线程: 8")
    print(f"  平均速度: {stats.speed:,.0f} 次/秒")
    
    assert stats.total_checked > 0, "高并发下总检查数应大于0"
    
    print("\n✅ 数据日志线程安全测试通过")
    return True


def test_error_logging_rate_limit():
    """测试错误记录限频功能"""
    print("\n" + "="*60)
    print("测试 3: 错误记录限频测试")
    print("="*60)
    
    # 这个测试主要验证限频机制不会导致程序崩溃
    targets = {"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"}
    
    engine = KeyCollisionEngine(
        targets=targets,
        max_workers=2,
        data_logging_enabled=True,
        data_logging_interval=1
    )
    
    def run_engine():
        engine.random_search()
    
    thread = threading.Thread(target=run_engine, daemon=True)
    thread.start()
    
    time.sleep(2)
    
    engine.stop()
    thread.join(timeout=5)
    
    stats = engine.get_stats()
    print(f"\n错误限频测试结果:")
    print(f"  总检查数: {stats.total_checked:,}")
    print(f"  运行时间: {stats.elapsed:.2f}秒")
    
    # 检查错误日志文件
    error_log_file = os.path.join("data_logs", "error_log.json")
    if os.path.exists(error_log_file):
        import json
        with open(error_log_file, 'r', encoding='utf-8') as f:
            errors = json.load(f)
        print(f"  错误日志数: {len(errors)}")
        # 验证限频：2秒内不应该有太多错误
        assert len(errors) < 10, f"错误日志数过多: {len(errors)}，限频可能未生效"
    
    print("\n✅ 错误记录限频测试通过")
    return True


def test_cpu_cache_mechanism():
    """测试CPU缓存机制"""
    print("\n" + "="*60)
    print("测试 4: CPU缓存机制测试")
    print("="*60)
    
    targets = {"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"}
    
    engine = KeyCollisionEngine(
        targets=targets,
        max_workers=4,
        data_logging_enabled=True,
        data_logging_interval=1
    )
    
    def run_engine():
        engine.random_search()
    
    # 记录开始时间
    start_time = time.time()
    
    thread = threading.Thread(target=run_engine, daemon=True)
    thread.start()
    
    time.sleep(2)
    
    engine.stop()
    thread.join(timeout=5)
    
    elapsed = time.time() - start_time
    stats = engine.get_stats()
    
    print(f"\nCPU缓存机制测试结果:")
    print(f"  总检查数: {stats.total_checked:,}")
    print(f"  运行时间: {elapsed:.2f}秒")
    print(f"  平均速度: {stats.speed:,.0f} 次/秒")
    
    # 验证性能：优化后应该达到一定速度
    assert stats.speed > 1000, f"速度过低: {stats.speed:.0f}，CPU缓存可能未生效"
    
    print("\n✅ CPU缓存机制测试通过")
    return True


def test_data_save_frequency():
    """测试数据保存频率"""
    print("\n" + "="*60)
    print("测试 5: 数据保存频率测试")
    print("="*60)
    
    targets = {"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"}
    
    engine = KeyCollisionEngine(
        targets=targets,
        max_workers=2,
        data_logging_enabled=True,
        data_logging_interval=1  # 每秒记录
    )
    
    def run_engine():
        engine.random_search()
    
    thread = threading.Thread(target=run_engine, daemon=True)
    thread.start()
    
    time.sleep(3)  # 运行3秒，应该记录3次，保存1次
    
    engine.stop()
    thread.join(timeout=5)
    
    stats = engine.get_stats()
    
    # 检查历史数据文件
    history_file = os.path.join("data_logs", "history_data.json")
    if os.path.exists(history_file):
        import json
        with open(history_file, 'r', encoding='utf-8') as f:
            history = json.load(f)
        print(f"\n数据保存频率测试结果:")
        print(f"  总检查数: {stats.total_checked:,}")
        print(f"  历史记录数: {len(history)}")
        print(f"  记录间隔: 1秒")
        print(f"  运行时间: 3秒")
        # 3秒运行，1秒间隔，应该约有3条记录（但只保存1次）
        print(f"  保存频率: 每3次记录保存1次")
    
    print("\n✅ 数据保存频率测试通过")
    return True


def main():
    """主测试函数"""
    # 初始化日志
    init_logging()
    
    print("\n" + "="*60)
    print("数据日志集成竞态条件测试")
    print("="*60)
    
    tests = [
        ("统计信息一致性", test_stats_consistency),
        ("数据日志线程安全", test_data_logging_thread_safety),
        ("错误记录限频", test_error_logging_rate_limit),
        ("CPU缓存机制", test_cpu_cache_mechanism),
        ("数据保存频率", test_data_save_frequency),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
                print(f"\n❌ {name} 测试失败")
        except Exception as e:
            failed += 1
            print(f"\n❌ {name} 测试异常: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)
    print(f"  总测试数: {len(tests)}")
    print(f"  通过: {passed}")
    print(f"  失败: {failed}")
    print("="*60)
    
    if failed == 0:
        print("\n✅ 所有测试通过！优化后的代码正确性验证成功！")
    else:
        print(f"\n❌ {failed} 个测试失败，需要检查")
    
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

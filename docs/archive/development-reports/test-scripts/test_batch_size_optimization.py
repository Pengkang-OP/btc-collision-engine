#!/usr/bin/env python3
"""测试batch_size优化效果"""

import sys
import json
from pathlib import Path
import time

sys.path.insert(0, str(Path(__file__).parent))

from src.collision import create_collision_engine


def test_batch_size_optimization():
    """测试batch_size优化"""

    print("=" * 80)
    print("  测试batch_size优化效果")
    print("=" * 80)
    print()

    # 读取配置文件
    config_file = Path(__file__).parent / 'config.intel_arc.json'
    print(f"【配置文件】{config_file}")

    if config_file.exists():
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)

        engine_batch_size = config.get('engine', {}).get('batch_size', 'N/A')
        gpu_batch_size = config.get('gpu', {}).get('batch_size', 'N/A')

        print(f"  engine.batch_size: {engine_batch_size if isinstance(engine_batch_size, str) else f'{engine_batch_size:,}'}")
        print(f"  gpu.batch_size: {gpu_batch_size if isinstance(gpu_batch_size, str) else f'{gpu_batch_size:,}'}")
    else:
        print("  ❌ 配置文件不存在")
        return

    print()

    # 测试1: 使用配置文件创建引擎(模拟GUI行为)
    print("【测试1】使用配置文件创建引擎(模拟GUI)")
    print("-" * 80)

    try:
        # 模拟GUI的配置读取逻辑
        gui_config = {}
        if 'gpu' in config:
            gui_config['gpu'] = config['gpu']
        if 'collision' in config and 'batch_size' in config['collision']:
            if 'gpu' not in gui_config:
                gui_config['gpu'] = {}
            gui_config['gpu']['batch_size'] = config['collision']['batch_size']

        print(f"  传递给引擎的配置:")
        print(f"    batch_size: {gui_config.get('gpu', {}).get('batch_size', 'N/A'):,}")

        # 创建引擎
        engine = create_collision_engine(
            targets=['1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'],
            mode='gpu',
            device_index=1,
            config=gui_config
        )

        # 检查实际batch_size
        actual_batch_size = engine.batch_size
        print(f"  ✅ 引擎实际batch_size: {actual_batch_size:,}")

        if actual_batch_size == 1000000:
            print(f"  ✅ batch_size优化成功! (从262k提升到1M)")
        else:
            print(f"  ⚠️ batch_size不是预期的1M")

        # 检查异步状态
        if hasattr(engine, '_gpu_device'):
            async_enabled = engine._gpu_device.enable_async_execution
            print(f"  异步执行: {'✅ 已启用' if async_enabled else '❌ 未启用'}")

            if async_enabled:
                has_executor = hasattr(engine, '_async_executor') and engine._async_executor is not None
                print(f"  异步执行器: {'✅ 已初始化' if has_executor else '❌ 未初始化'}")

        engine.stop()

    except Exception as e:
        print(f"  ❌ 错误: {e}")
        import traceback
        traceback.print_exc()

    print()

    # 测试2: 不使用配置(对比)
    print("【测试2】不使用配置(对比)")
    print("-" * 80)

    try:
        engine2 = create_collision_engine(
            targets=['1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'],
            mode='gpu',
            device_index=1
        )

        actual_batch_size2 = engine2.batch_size
        print(f"  引擎实际batch_size: {actual_batch_size2:,}")
        print(f"  (这是默认值,通常为262k)")

        engine2.stop()

    except Exception as e:
        print(f"  ❌ 错误: {e}")

    print()
    print("=" * 80)
    print("  测试完成")
    print("=" * 80)

    # 性能预期
    print()
    print("【性能预期】")
    print("  batch_size=262k:  ~47,000 keys/s (当前)")
    print("  batch_size=1M:    ~1,500,000 keys/s (预期)")
    print("  性能提升:         ~32倍")
    print()


if __name__ == "__main__":
    test_batch_size_optimization()

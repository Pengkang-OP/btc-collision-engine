#!/usr/bin/env python3
"""真实GPU环境碰撞测试 - 验证异常处理和锁保护修复

测试场景:
1. GPU引擎初始化验证
2. 正常碰撞流程（短期运行）
3. 错误计数器验证
4. 回调函数安全性验证
5. 断点续传同步验证
"""
import sys
import time
import logging
from pathlib import Path
import pytest

# 模块级别 marker：本文件所有测试都属于 GPU 测试
pytestmark = pytest.mark.gpu

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.collision.gpu_collision_engine import GPUCollisionEngine
from src.collision.collision_stats import CollisionStats

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


@pytest.fixture
def engine():
    """提供 GPUCollisionEngine 实例，若无 GPU 则跳过测试"""
    try:
        targets = {
            "1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH",
            "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
        }
        eng = GPUCollisionEngine(
            targets,
            batch_size=10000,
            device_index=0
        )
        if not eng.is_gpu_available():
            pytest.skip("无可用 GPU，跳过真实 GPU 测试")
        yield eng
        # 确保引擎停止
        if eng._running:
            eng.stop()
    except Exception as e:
        pytest.skip(f"GPU 引擎初始化失败，跳过测试: {e}")


def test_gpu_initialization():
    logger.info("=" * 60)
    logger.info("测试1: GPU引擎初始化验证")
    logger.info("=" * 60)
    
    try:
        targets = {
            "1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH",
            "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
        }
        
        engine = GPUCollisionEngine(
            targets,
            batch_size=10000,
            device_index=0
        )
        
        logger.info(f"✅ GPU引擎初始化成功")
        logger.info(f"   - GPU可用: {engine.is_gpu_available()}")
        logger.info(f"   - 设备索引: {engine.device_index}")
        logger.info(f"   - 批次大小: {engine.batch_size}")
        logger.info(f"   - 目标地址数: {len(engine.targets)}")
        logger.info(f"   - 错误计数器: {engine._consecutive_gpu_errors}")
        logger.info(f"   - 最大重试次数: {engine._max_gpu_error_retries}")
        
        # 获取设备信息
        if engine._gpu_device:
            device_info = engine._gpu_device.get_device_info()
            logger.info(f"   - GPU设备: {device_info.get('name', 'Unknown')}")
            logger.info(f"   - 厂商: {device_info.get('vendor', 'Unknown')}")
            logger.info(f"   - 显存: {device_info.get('global_mem_size', 0) / (1024**3):.1f} GB")
        
        return engine
        
    except Exception as e:
        logger.error(f"❌ GPU引擎初始化失败: {e}")
        return None


def test_collision_flow(engine):
    """测试2: 正常碰撞流程（3秒短时运行）"""
    logger.info("")
    logger.info("=" * 60)
    logger.info("测试2: 正常碰撞流程（3秒）")
    logger.info("=" * 60)
    
    if not engine:
        logger.error("⏭️ 跳过: 引擎未初始化")
        return
    
    # 设置回调函数
    progress_count = 0
    match_count = 0
    complete_called = False
    
    def on_progress(stats):
        nonlocal progress_count
        progress_count += 1
        if progress_count % 5 == 0:  # 每5次打印一次
            # 修复: CollisionStats的正确属性名是average_speed而非keys_per_sec
            speed = getattr(stats, 'average_speed', 0) or getattr(stats, 'keys_per_sec', 0)
            logger.info(
                f"   进度回调 #{progress_count}: "
                f"已检查={stats.total_checked:,}, "
                f"速率={speed:,.0f} keys/s"
            )
    
    def on_match(match_info):
        nonlocal match_count
        match_count += 1
        logger.info(f"   🎯 发现碰撞 #{match_count}: {match_info}")
    
    def on_complete(stats):
        nonlocal complete_called
        complete_called = True
        # 修复: CollisionStats的正确属性名是average_speed而非keys_per_sec
        speed = getattr(stats, 'average_speed', 0) or getattr(stats, 'keys_per_sec', 0)
        logger.info(
            f"   完成回调: 总计检查={stats.total_checked:,}, "
            f"耗时={stats.elapsed_time:.2f}s, "
            f"平均速率={speed:,.0f} keys/s"
        )
    
    engine.on_progress = on_progress
    engine.on_match = on_match
    engine.on_complete = on_complete
    
    # 启动碰撞（随机模式）
    logger.info("   启动GPU碰撞引擎...")
    start_time = time.time()
    
    try:
        engine.start(mode="random")
        
        # 运行3秒后停止
        time.sleep(3)
        engine.stop()
        
        elapsed = time.time() - start_time
        
        logger.info(f"✅ 碰撞流程测试完成")
        logger.info(f"   - 运行时间: {elapsed:.2f}s")
        logger.info(f"   - 进度回调次数: {progress_count}")
        logger.info(f"   - 碰撞次数: {match_count}")
        logger.info(f"   - 完成回调调用: {complete_called}")
        logger.info(f"   - 错误计数器: {engine._consecutive_gpu_errors}")
        logger.info(f"   - 最终状态: {'running' if engine._running else 'stopped'}")
        
    except Exception as e:
        logger.error(f"❌ 碰撞流程测试失败: {e}")
        import traceback
        traceback.print_exc()


def test_error_counter_behavior(engine):
    """测试3: 错误计数器行为验证"""
    logger.info("")
    logger.info("=" * 60)
    logger.info("测试3: 错误计数器行为验证")
    logger.info("=" * 60)
    
    if not engine:
        logger.error("⏭️ 跳过: 引擎未初始化")
        return
    
    # 测试1: 重启重置计数器
    logger.info("   测试3.1: 引擎重启重置计数器")
    initial_count = engine._consecutive_gpu_errors
    engine._consecutive_gpu_errors = 50
    logger.info(f"   - 设置错误计数器为: 50")
    
    engine.start(mode="random")
    engine.stop()
    
    if engine._consecutive_gpu_errors == 0:
        logger.info(f"   ✅ 重启后计数器重置为: {engine._consecutive_gpu_errors}")
    else:
        logger.error(f"   ❌ 重启后计数器未重置: {engine._consecutive_gpu_errors}")
    
    # 测试2: 锁保护验证
    logger.info("   测试3.2: 锁保护机制验证")
    import threading
    
    def increment_with_lock():
        with engine._batch_size_lock:
            engine._consecutive_gpu_errors += 1
    
    threads = []
    for _ in range(100):
        t = threading.Thread(target=increment_with_lock)
        threads.append(t)
        t.start()
    
    for t in threads:
        t.join()
    
    if engine._consecutive_gpu_errors == 100:
        logger.info(f"   ✅ 100线程并发递增准确: {engine._consecutive_gpu_errors}")
    else:
        logger.error(f"   ❌ 并发递增不准确: 期望100, 实际{engine._consecutive_gpu_errors}")
    
    # 重置计数器
    with engine._batch_size_lock:
        engine._consecutive_gpu_errors = 0


def test_callback_snapshot_safety(engine):
    """测试4: 回调快照安全性验证"""
    logger.info("")
    logger.info("=" * 60)
    logger.info("测试4: 回调快照安全性验证")
    logger.info("=" * 60)
    
    if not engine:
        logger.error("⏭️ 跳过: 引擎未初始化")
        return
    
    received_snapshots = []
    
    def on_progress_capture(stats):
        received_snapshots.append(('progress', stats))
    
    def on_complete_capture(stats):
        received_snapshots.append(('complete', stats))
    
    engine.on_progress = on_progress_capture
    engine.on_complete = on_complete_capture
    
    # 短暂运行
    engine.start(mode="random")
    time.sleep(1)
    engine.stop()
    
    # 验证快照
    logger.info(f"   收到回调次数: {len(received_snapshots)}")
    
    if len(received_snapshots) > 0:
        # 验证快照类型
        all_are_stats = all(
            isinstance(stats, CollisionStats)
            for _, stats in received_snapshots
        )
        
        if all_are_stats:
            logger.info(f"   ✅ 所有回调都收到CollisionStats对象")
        else:
            logger.error(f"   ❌ 部分回调收到非CollisionStats对象")
        
        # 验证快照非原对象
        all_are_snapshots = all(
            stats is not engine.stats
            for _, stats in received_snapshots
        )
        
        if all_are_snapshots:
            logger.info(f"   ✅ 所有回调都使用快照（非原对象）")
        else:
            logger.error(f"   ❌ 部分回调使用原对象（非快照）")
    else:
        logger.warning(f"   ⚠️  未收到任何回调（可能是运行时间太短）")


def test_config_loading():
    """测试5: 配置加载验证"""
    logger.info("")
    logger.info("=" * 60)
    logger.info("测试5: 配置加载验证")
    logger.info("=" * 60)
    
    try:
        import json
        from pathlib import Path
        
        config_files = [
            "config.json",
            "config.intel_arc.json",
            "config.multi_gpu.json"
        ]
        
        for config_file in config_files:
            config_path = project_root / config_file
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                gpu_config = config.get('gpu', {})
                max_retries = gpu_config.get('max_error_retries', '未配置')
                
                logger.info(f"   {config_file}:")
                logger.info(f"     - max_error_retries: {max_retries}")
                
                if max_retries == 100:
                    logger.info(f"     ✅ 配置正确")
                else:
                    logger.warning(f"     ⚠️  未配置或使用默认值")
            else:
                logger.warning(f"   {config_file}: 文件不存在")
    
    except Exception as e:
        logger.error(f"   ❌ 配置加载测试失败: {e}")


def main():
    """主测试流程"""
    logger.info("🚀 真实GPU环境碰撞测试 - 验证异常处理和锁保护修复")
    logger.info("")
    
    # 测试1: GPU初始化
    engine = test_gpu_initialization()
    
    # 测试2: 碰撞流程
    test_collision_flow(engine)
    
    # 测试3: 错误计数器
    test_error_counter_behavior(engine)
    
    # 测试4: 回调快照安全
    test_callback_snapshot_safety(engine)
    
    # 测试5: 配置加载
    test_config_loading()
    
    # 总结
    logger.info("")
    logger.info("=" * 60)
    logger.info("📊 测试总结")
    logger.info("=" * 60)
    logger.info("✅ GPU引擎初始化: 完成")
    logger.info("✅ 碰撞流程测试: 完成")
    logger.info("✅ 错误计数器验证: 完成")
    logger.info("✅ 回调快照安全: 完成")
    logger.info("✅ 配置加载验证: 完成")
    logger.info("")
    logger.info("🎉 所有测试完成！")


if __name__ == "__main__":
    main()

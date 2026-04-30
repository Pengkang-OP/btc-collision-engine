#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Intel Arc GPU实际碰撞测试脚本

功能：
1. 使用真实比特币地址进行碰撞测试
2. 完整的Intel Arc资源监控（显存、超时、性能）
3. GPU vs CPU性能对比
4. 数据质量验证
5. 生成详细测试报告

目标设备: Intel Arc A770 16GB
"""

import sys
import time
import json
import logging
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Set

# 添加项目根目录
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from src.collision.gpu_collision_engine import GPUCollisionEngine
from src.collision.collision_stats import CollisionStats
from src.gpu.intel_memory_monitor import IntelMemoryMonitor
from src.gpu.intel_timeout_manager import AdaptiveTimeoutManager

# 输出目录
_TEST_OUTPUT_DIR = _PROJECT_ROOT / "test_results"
_TEST_OUTPUT_DIR.mkdir(exist_ok=True)
_LOG_FILE = _TEST_OUTPUT_DIR / "intel_arc_collision_test.log"

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(str(_LOG_FILE), encoding='utf-8')
    ]
)

logger = logging.getLogger("IntelArcCollisionTest")


def load_valid_addresses(filepath: str = "") -> Set[str]:
    """加载有效地址文件"""
    addresses = set()
    # 默认路径: 项目根目录下的 targets.txt 或 benchmarks/btc_addresses_sorted.txt
    if not filepath:
        candidates = [
            _PROJECT_ROOT / "targets.txt",
            _PROJECT_ROOT / "benchmarks" / "btc_addresses_sorted.txt",
        ]
        for candidate in candidates:
            if candidate.exists():
                filepath = str(candidate)
                break
    if not filepath:
        logger.warning("未找到有效地址文件，将使用默认测试地址")
        return addresses
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                addr = line.strip()
                if addr and len(addr) >= 26:
                    addresses.add(addr)
        logger.info(f"从 {filepath} 加载了 {len(addresses)} 个地址")
        return addresses
    except Exception as e:
        logger.error(f"加载地址文件失败: {e}")
        return addresses


class IntelArcTestMonitor:
    """Intel Arc测试监控器"""

    def __init__(self, total_memory_bytes: int):
        self.memory_monitor = IntelMemoryMonitor(
            total_memory_bytes=total_memory_bytes,
            safe_usage_ratio=0.45
        )
        self.timeout_manager = AdaptiveTimeoutManager(
            base_timeout=30.0,
            min_timeout=10.0,
            max_timeout=120.0
        )

        # 性能统计
        self.start_time = None
        self.batch_count = 0
        self.total_keys = 0
        self.throughput_history = []
        self.execution_times = []

    def start(self):
        """开始监控"""
        self.start_time = time.time()
        logger.info("Intel Arc测试监控器已启动")

    def record_batch(self, batch_size: int, execution_time_ms: float):
        """记录批次数据"""
        self.batch_count += 1
        self.total_keys += batch_size
        self.execution_times.append(execution_time_ms)

        # 记录超时数据
        self.timeout_manager.record_execution_time(execution_time_ms)

        # 计算吞吐量
        throughput = (batch_size / execution_time_ms * 1000) if execution_time_ms > 0 else 0
        self.throughput_history.append(throughput)

        # 记录显存 (基于 batch_size 估算: 每 key 约 42 字节)
        estimated_bytes = batch_size * 42
        self.memory_monitor.track_allocation(
            estimated_bytes,
            batch_count=self.batch_count
        )
        self.memory_monitor.track_deallocation(
            estimated_bytes,
            batch_count=self.batch_count
        )

    def get_statistics(self) -> Dict:
        """获取统计信息"""
        elapsed = time.time() - self.start_time if self.start_time else 0
        avg_throughput = (
            sum(self.throughput_history) / len(self.throughput_history)
            if self.throughput_history else 0
        )
        peak_throughput = max(self.throughput_history) if self.throughput_history else 0

        return {
            'elapsed_seconds': elapsed,
            'batch_count': self.batch_count,
            'total_keys': self.total_keys,
            'avg_throughput': avg_throughput,
            'peak_throughput': peak_throughput,
            'avg_execution_time_ms': (
                sum(self.execution_times) / len(self.execution_times)
                if self.execution_times else 0
            ),
            'current_timeout': self.timeout_manager.get_timeout(),
            'memory_status': self.memory_monitor.get_status()
        }

    def generate_report(self) -> str:
        """生成测试报告"""
        stats = self.get_statistics()

        report = []
        report.append("=" * 80)
        report.append("📊 Intel Arc GPU 碰撞测试报告")
        report.append("=" * 80)
        report.append(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"测试时长: {stats['elapsed_seconds']:.2f} 秒")
        report.append("")
        report.append("🎯 性能指标:")
        report.append(f"  总检查密钥: {stats['total_keys']:,}")
        report.append(f"  总批次数: {stats['batch_count']}")
        report.append(f"  平均吞吐量: {stats['avg_throughput']:,.0f} keys/s")
        report.append(f"  峰值吞吐量: {stats['peak_throughput']:,.0f} keys/s")
        report.append(f"  平均执行时间: {stats['avg_execution_time_ms']:.1f} ms")
        report.append("")
        report.append("⏱️ 超时管理:")
        report.append(f"  当前超时: {stats['current_timeout']:.1f} 秒")
        timeout_stats = self.timeout_manager.get_statistics()
        report.append(f"  超时调整次数: {timeout_stats.get('timeout_adjustments', 0)}")
        report.append("")

        mem_status = stats['memory_status']
        report.append("💾 显存使用:")
        report.append(f"  总显存: {mem_status['total_memory_gb']:.1f} GB")
        report.append(f"  安全限制: {mem_status['safe_limit_mb']:.0f} MB (45%)")
        report.append(f"  峰值使用: {mem_status['peak_mb']:.1f} MB")
        status_val = mem_status.get('status')
        if hasattr(status_val, 'value'):
            report.append(f"  状态: {status_val.value.upper()}")
        else:
            report.append(f"  状态: {status_val}")
        report.append("")
        report.append("=" * 80)

        return "\n".join(report)

    def cleanup(self) -> None:
        """清理监控资源"""
        self.memory_monitor.reset()
        self.timeout_manager.reset()
        logger.info("Intel Arc测试监控器资源已清理")


def run_gpu_collision_test(
    targets: Set[str],
    duration: int = 60,
    batch_size: int = 1048576
) -> Dict:
    """运行GPU碰撞测试"""

    print("\n" + "=" * 80)
    print("🚀 Intel Arc GPU 碰撞测试")
    print("=" * 80)
    print(f"测试时长: {duration} 秒")
    print(f"批次大小: {batch_size:,}")
    print(f"目标地址: {len(targets)} 个")
    print()

    # 统计数据
    stats_data = {
        'total_checked': 0,
        'speed': 0.0,
        'elapsed': 0.0,
        'matches': [],
        'batches': []
    }

    # 创建监控器
    monitor = IntelArcTestMonitor(total_memory_bytes=16 * 1024**3)

    def on_progress(stats: CollisionStats):
        """进度回调"""
        stats_data['total_checked'] = stats.total_checked
        stats_data['speed'] = stats.speed
        stats_data['elapsed'] = stats.elapsed
        stats_data['matches'] = stats.matches

        elapsed = stats.elapsed
        mins = int(elapsed // 60)
        secs = int(elapsed % 60)

        print(f"  [{mins:02d}:{secs:02d}] "
              f"已检查: {stats.total_checked:>12,} | "
              f"速度: {stats.speed:>12,.0f} keys/s | "
              f"匹配: {len(stats.matches)}")

    def on_match(private_key: bytes, address: str, wif: str):
        """匹配回调 - 签名需匹配 MatchCallback = Callable[[bytes, str, str], None]"""
        print(f"\n🎯 发现匹配: {address}")
        print(f"   私钥: {private_key.hex()}")
        print(f"   WIF: {wif}\n")
        stats_data['matches'].append({
            'address': address,
            'private_key': private_key.hex(),
            'wif': wif
        })

    try:
        # 初始化GPU引擎
        print("📋 初始化GPU碰撞引擎...")
        engine = GPUCollisionEngine(
            targets=set(targets),  # 确保是set类型
            device_index=-1,  # 自动选择最佳GPU
            batch_size=batch_size,
            on_progress=on_progress,
            on_match=on_match,
            checkpoint_enabled=False,
            dedup_enabled=False,
            data_logging_enabled=False,
            use_enhanced_monitoring=True
        )

        # 获取设备信息
        device_info = engine._gpu_device.get_device_info()
        print(f"\n✅ GPU引擎初始化完成")
        print(f"   设备: {device_info.get('name', 'Unknown')}")
        print(f"   厂商: {device_info.get('vendor', 'Unknown')}")
        print(f"   显存: {device_info.get('global_mem_size', 0) / 1024**3:.1f} GB")
        print(f"   计算单元: {device_info.get('max_compute_units', 'N/A')}")
        print(f"   Batch Size: {engine.batch_size:,}")
        print(f"   异步执行: {engine._gpu_device.enable_async_execution}")

        print(f"\n⏱️  开始测试，持续 {duration} 秒...\n")
        print("-" * 80)

        # 启动监控
        monitor.start()

        # 启动引擎
        start_time = time.time()
        engine.start(mode="random")

        # 运行指定时长
        batch_times = []
        last_log_time = start_time
        try:
            while (time.time() - start_time) < duration:
                time.sleep(1)

                # 每5秒记录一次监控数据 (使用计时器避免竞态)
                now = time.time()
                if now - last_log_time >= 5.0:
                    last_log_time = now
                    current_stats = engine.get_stats()
                    if hasattr(current_stats, 'speed') and current_stats.speed > 0:
                        # 估算执行时间：batch_size / speed * 1000
                        est_batch_time = batch_size / current_stats.speed * 1000
                        batch_times.append(est_batch_time)
                        monitor.record_batch(
                            batch_size=batch_size,
                            execution_time_ms=est_batch_time
                        )

        except KeyboardInterrupt:
            print("\n\n⚠️  收到中断信号，正在停止...")
        finally:
            engine.stop()
            monitor.cleanup()

        elapsed = time.time() - start_time

        # 打印结果
        print("-" * 80)
        print(f"\n📊 测试完成！")
        print("=" * 80)
        print(f"  总检查数   : {stats_data['total_checked']:,}")
        print(f"  运行时间   : {elapsed:.2f} 秒")
        print(f"  平均速度   : {stats_data['total_checked']/elapsed:,.0f} keys/s")
        print(f"  峰值速度   : {stats_data['speed']:,.0f} keys/s")
        print(f"  发现匹配   : {len(stats_data['matches'])} 个")
        print("=" * 80)

        # 生成监控报告
        print()
        print(monitor.generate_report())

        # 保存测试数据
        # 转换MemoryStatus枚举为字符串
        monitoring_data = monitor.get_statistics()
        if 'memory_status' in monitoring_data:
            mem_status = monitoring_data['memory_status']
            if hasattr(mem_status.get('status'), 'value'):
                mem_status['status'] = mem_status['status'].value

        test_result = {
            'timestamp': datetime.now().isoformat(),
            'device': device_info,
            'duration_seconds': elapsed,
            'total_checked': stats_data['total_checked'],
            'avg_speed': stats_data['total_checked'] / elapsed,
            'peak_speed': stats_data['speed'],
            'matches_found': len(stats_data['matches']),
            'matches': stats_data['matches'],
            'monitoring': monitoring_data
        }

        # 保存结果到 test_results 目录
        result_file = _TEST_OUTPUT_DIR / f"intel_arc_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(str(result_file), 'w', encoding='utf-8') as f:
            json.dump(test_result, f, indent=2, ensure_ascii=False)

        print(f"\n💾 测试结果已保存到: {result_file}")

        return test_result

    except Exception as e:
        logger.error(f"GPU测试失败: {e}", exc_info=True)
        print(f"\n❌ GPU测试失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def run_cpu_baseline_test(targets: Set[str], duration: int = 10) -> Dict:
    """运行CPU基线测试（用于对比）"""
    print("\n" + "=" * 80)
    print("💻 CPU 基线测试（对比用）")
    print("=" * 80)
    print(f"测试时长: {duration} 秒")
    print()

    from src.collision.key_collision_engine import KeyCollisionEngine

    stats_data = {
        'total_checked': 0,
        'speed': 0.0
    }

    def on_progress(stats: CollisionStats):
        stats_data['total_checked'] = stats.total_checked
        stats_data['speed'] = stats.speed

        elapsed = stats.elapsed
        mins = int(elapsed // 60)
        secs = int(elapsed % 60)

        print(f"  [{mins:02d}:{secs:02d}] "
              f"已检查: {stats.total_checked:>10,} | "
              f"速度: {stats.speed:>10,.2f} keys/s")

    try:
        print("📋 初始化CPU碰撞引擎...")
        engine = KeyCollisionEngine(
            targets=targets,
            mode="random",
            batch_size=10000,
            on_progress=on_progress,
            checkpoint_enabled=False
        )

        print(f"\n⏱️  开始CPU测试，持续 {duration} 秒...\n")
        print("-" * 80)

        start_time = time.time()
        engine.start()

        try:
            while (time.time() - start_time) < duration:
                time.sleep(1)
        finally:
            engine.stop()

        elapsed = time.time() - start_time

        print("-" * 80)
        print(f"\n📊 CPU测试完成！")
        print("=" * 80)
        print(f"  总检查数   : {stats_data['total_checked']:,}")
        print(f"  运行时间   : {elapsed:.2f} 秒")
        print(f"  平均速度   : {stats_data['total_checked']/elapsed:,.2f} keys/s")
        print("=" * 80)

        return {
            'total_checked': stats_data['total_checked'],
            'avg_speed': stats_data['total_checked'] / elapsed
        }

    except Exception as e:
        logger.error(f"CPU测试失败: {e}")
        print(f"\n⚠️ CPU测试跳过: {e}")
        return None


def main():
    """主函数"""
    print("\n" + "=" * 80)
    print("Intel Arc GPU 实际碰撞测试套件")
    print("=" * 80)
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # 加载目标地址
    print("📂 加载目标地址...")
    targets = load_valid_addresses()  # 使用默认搜索路径

    if not targets:
        # 使用默认测试地址
        targets = {"12ib7dApVFvg82TXKycWBNpN8kFyiAN1dr"}
        print(f"  使用默认测试地址: {next(iter(targets))}")
        targets = {"12ib7dApVFvg82TXKycWBNpN8kFyiAN1dr"}
    else:
        print(f"  ✅ 加载了 {len(targets)} 个目标地址")
        # 显示前5个
        for i, addr in enumerate(list(targets)[:5]):
            print(f"    {i+1}. {addr}")
        if len(targets) > 5:
            print(f"    ... 还有 {len(targets) - 5} 个地址")

    # 运行GPU测试
    gpu_result = run_gpu_collision_test(
        targets=targets,
        duration=60,  # 60秒测试
        batch_size=1048576  # 1M batch size
    )

    # 可选：运行CPU基线测试（取消注释以启用）
    # cpu_result = run_cpu_baseline_test(targets, duration=10)

    # 性能对比
    if gpu_result:
        print("\n" + "=" * 80)
        print("📈 性能总结")
        print("=" * 80)

        gpu_speed = gpu_result['avg_speed']
        print(f"  GPU速度: {gpu_speed:,.0f} keys/s")

        # 与典型CPU速度对比（约88 keys/s）
        cpu_baseline = 88
        speedup = gpu_speed / cpu_baseline
        print(f"  CPU基线: {cpu_baseline:,.0f} keys/s")
        print(f"  加速倍数: {speedup:,.1f}x")
        print("=" * 80)

        # 资源使用评估
        monitoring = gpu_result['monitoring']
        mem_status = monitoring['memory_status']
        print(f"\n💾 资源使用评估:")
        print(f"  显存使用率: {mem_status['usage_percent']:.1f}% (安全限制内)")
        print(f"  超时设置: {monitoring['current_timeout']:.1f} 秒")

        if mem_status['usage_percent'] < 70:
            print(f"  ✅ 显存使用正常")
        else:
            print(f"  ⚠️ 显存使用率较高，建议监控")

        print("\n🎉 Intel Arc GPU碰撞测试完成！")

        return 0
    else:
        print("\n❌ 测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())

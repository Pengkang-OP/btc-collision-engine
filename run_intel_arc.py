#!/usr/bin/env python3
"""
Intel Arc A770 快速启动脚本

立即使用优化后的配置启动碰撞引擎，获得最大GPU利用率！
"""

import hashlib
import logging
import os
import sys
import time

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# 安装日志安全过滤器（防止私钥泄露到日志文件）
try:
    from src.utils.logging_config import _setup_security_filter
    _setup_security_filter()
except Exception:
    pass  # 安全过滤器初始化失败不阻止运行

logger = logging.getLogger(__name__)


def main():
    print("=" * 70)
    print("  BTC Collision Engine - Intel Arc A770 优化版")
    print("=" * 70)
    print()

    # 导入引擎
    try:
        from src.collision.gpu.engine import GPUCollisionEngine
        from src.monitoring.gpu_performance_monitor import GPUPerformanceMonitor
    except ImportError as e:
        logger.error(f"导入失败: {e}")
        logger.error("请确保在项目根目录运行此脚本")
        return 1

    # 解析命令行参数
    targets_file = "targets.txt"
    if len(sys.argv) > 1:
        targets_file = sys.argv[1]

    # 检查目标文件
    if not os.path.exists(targets_file):
        logger.error(f"目标文件不存在: {targets_file}")
        print(f"\n使用方法: {sys.argv[0]} [目标文件]")
        print("\n或者创建一个简单的 targets.txt:")
        print("  1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa")
        return 1

    # 使用 TargetResolver 读取并解析目标地址
    # 支持 P2PKH地址、WIF私钥、压缩/非压缩公钥、Hash160、P2WPKH Bech32
    # 自动跳过密码学上无法匹配的格式 (P2SH/P2WSH/Taproot)
    try:
        from src.collision.targets.resolver import TargetResolver

        resolver = TargetResolver()
        targets = resolver.load_from_file(targets_file)

        # 报告不支持的类型
        unsupported = resolver.get_unsupported_types()
        if unsupported:
            unsupported_summary = ", ".join(
                f"{k}={v}" for k, v in sorted(unsupported.items())
            )
            logger.warning(
                f"密码学上不支持匹配的输入已跳过: {unsupported_summary}. "
                f"这些格式因密码学路径不同无法通过私钥碰撞匹配。"
            )
    except Exception as e:
        logger.error(f"读取目标文件失败: {e}")
        return 1

    if not targets:
        logger.error("目标文件为空")
        return 1

    print(f"✓ 已加载 {len(targets)} 个目标地址")
    print()

    # 创建引擎 - Intel Arc A770 优化配置
    logger.info("正在初始化GPU引擎 (Intel Arc A770 优化)...")

    try:
        engine = GPUCollisionEngine(
            targets=targets,
            batch_size=1048576,   # 100万初始批次
            device=1,             # GPU 1 (Intel Arc A770)
            use_async_execution=True,  # 异步执行
            use_double_buffering=True,  # 双缓冲
        )

        # 创建性能监控
        monitor = GPUPerformanceMonitor(engine=engine)

        logger.info("✓ GPU引擎初始化成功")
        print()

        # 显示配置
        print("-" * 70)
        print("  配置信息")
        print("-" * 70)
        print(f"  GPU设备: Intel(R) Arc(TM) A770")
        print(f"  批次大小: {engine.batch_size:,}")
        print(f"  异步执行: 已启用")
        print(f"  双缓冲: 已启用")
        print(f"  队列深度: 12")
        print("-" * 70)
        print()

        # 启动监控
        monitor.start()
        logger.info("✓ 性能监控已启动")

        # 定义匹配回调
        def on_match(private_key, address, wif):
            key_hash = hashlib.sha256(private_key).hexdigest()[:16]

            # 始终记录脱敏审计日志
            logger.info(
                "匹配发现: address=%s, key_hash=KEY_HASH:%s",
                address, key_hash
            )

            # 交互式终端：显示完整私钥（带安全警告）
            if sys.stdout.isatty():
                print()
                print("=" * 70)
                print("  🎊 找到匹配！")
                print("=" * 70)
                print(f"  地址: {address}")
                print(f"  WIF: {wif}")
                print(f"  私钥(hex): {private_key.hex()}")
                print("=" * 70)
                print("  ⚠ 安全警告: 请勿分享、截图或在网络上传输以上私钥信息！")
                print()
            else:
                # 非交互环境：仅输出脱敏信息
                print(f"\n[MATCH] address={address}, key_hash=KEY_HASH:{key_hash}\n")

            # 保存到文件（设置严格权限防止私钥泄漏）
            key_file = "found_keys.txt"
            try:
                with open(key_file, "a") as f:
                    f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"  Address: {address}\n")
                    f.write(f"  WIF: {wif}\n")
                    f.write(f"  Private Key: {private_key.hex()}\n\n")
                os.chmod(key_file, 0o600)
            except Exception as e:
                logger.error(f"保存匹配失败: {e}")

        engine.on_match = on_match

        # 启动搜索
        print("\n🚀 开始搜索...")
        print("按 Ctrl+C 停止\n")

        # 显示实时性能
        def show_performance():
            stats = monitor.get_stats()

            print("\033[2J\033[H", end='')  # 清屏
            print("=" * 70)
            print("  BTC Collision Engine - Intel Arc A770")
            print("=" * 70)
            print()
            print("  [GPU 状态]")
            print(f"  ├─ 利用率: {stats['avg_gpu_utilization'] * 100:.1f}%")
            print(f"  ├─ 温度: {stats['avg_temperature']:.1f}°C")
            print(f"  ├─ 显存: {stats['avg_memory_used_mb']:.0f}/{stats['memory_usage'].get('total_mb', 16384):.0f} MB")
            print(f"  └─ 功耗: {stats['avg_power_usage_w']:.1f} W")
            print()
            print("  [性能]")
            print(f"  ├─ 吞吐量: {stats['current_throughput']:,.0f} keys/s")
            print(f"  ├─ 平均吞吐量: {stats['avg_throughput']:,.0f} keys/s")
            print(f"  ├─ 已检查: {stats['total_keys_processed']:,}")
            print(f"  └─ 批次: {stats['total_batches']:,}")
            print()
            print("=" * 70)
            print("  按 Ctrl+C 停止")
            print("=" * 70)

        # 启动搜索
        engine.start(mode="random")

        # 性能显示循环
        last_update = time.time()
        try:
            while engine.is_running():
                time.sleep(2)

                # 定期显示性能
                if time.time() - last_update > 2:
                    show_performance()
                    last_update = time.time()

        except KeyboardInterrupt:
            print("\n\n正在停止...")

        finally:
            # 停止引擎和监控
            engine.stop()
            monitor.stop()

            # 显示最终统计
            print()
            print("=" * 70)
            print("  最终统计")
            print("=" * 70)
            final_stats = monitor.get_stats()
            print(f"  总检查: {final_stats['total_keys_processed']:,} 密钥")
            print(f"  总批次: {final_stats['total_batches']:,}")
            print(f"  平均吞吐量: {final_stats['avg_throughput']:,.0f} keys/s")
            print("=" * 70)
            print()

    except Exception as e:
        logger.exception(f"运行失败: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

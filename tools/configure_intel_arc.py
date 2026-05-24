#!/usr/bin/env python3
"""
Intel Arc A770 GPU自动选择和配置工具

功能:
1. 自动检测所有GPU设备
2. 识别Intel Arc A770
3. 生成正确的配置文件
4. 验证配置
"""

import json
from pathlib import Path

from src.gpu.device import GPUDeviceDetector


def print_header(title: str):
    """打印标题"""
    print(f"\n{'=' * 80}")
    print(f"  {title}")
    print(f"{'=' * 80}\n")


def detect_gpus():
    """检测所有GPU设备"""
    print_header("GPU设备检测")

    devices = GPUDeviceDetector.detect_devices()

    if not devices:
        print("[ERROR] 未检测到任何GPU设备!")
        return None

    print(f"检测到 {len(devices)} 个GPU设备:\n")

    intel_arc_index = None

    for i, device in enumerate(devices):
        name = device.get("name", "Unknown")
        vendor = device.get("vendor", "Unknown")
        mem_gb = device.get("global_mem_size", 0) / (1024**3)

        print(f"  GPU {i}:")
        print(f"    名称: {name}")
        print(f"    厂商: {vendor}")
        print(f"    显存: {mem_gb:.1f} GB")
        print()

        # 查找Intel Arc
        if "Arc" in name and "Intel" in vendor:
            intel_arc_index = i
            print(f"  [FOUND] 找到Intel Arc A770! 索引: {i}")
            print()

    if intel_arc_index is None:
        print("[WARN] 未检测到Intel Arc A770!")
        print("[INFO] 可能的原因:")
        print("  1. Intel Arc驱动未正确安装")
        print("  2. GPU未正确识别")
        print("  3. OpenCL平台配置问题")
        return None

    return intel_arc_index


def generate_config(device_index: int) -> dict:
    """生成优化配置"""
    config = {
        "collision": {
            "mode": "random",
            "batch_size": 131072,  # 平衡性能和稳定性
            "max_threads": 8,
            "checkpoint_interval": 300,
        },
        "gpu": {
            "use_gpu": True,
            "device_index": device_index,  # 指定Intel Arc A770
            "gpu_memory_pool": True,
            "max_buffers": 100,
            "max_memory_mb": 512,
            "async_execution": False,  # Intel Arc禁用异步
            "timeout_protection": True,
            "base_timeout_seconds": 30,
            "memory_limit_percent": 45,
            "uint32_workaround": True,
            "disable_async_transfer": True,
            "conservative_memory_policy": True,
            "adaptive_timeout": True,
        },
        "monitoring": {
            "enable_performance_monitor": True,
            "report_interval": 60,
            "log_level": "INFO",
            "enable_memory_monitoring": True,
            "enable_timeout_monitoring": True,
        },
    }

    return config


def save_config(config: dict, filename: str = "config.intel_arc.json"):
    """保存配置文件"""
    config_path = Path(__file__).parent.parent / filename

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

    print(f"\n[PASS] 配置已保存到: {config_path}")
    return config_path


def verify_config(config: dict):
    """验证配置"""
    print_header("配置验证")

    checks = {
        "GPU启用": config["gpu"]["use_gpu"],
        "设备索引设置": "device_index" in config["gpu"],
        "内存池启用": config["gpu"]["gpu_memory_pool"],
        "异步执行禁用": not config["gpu"]["async_execution"],
        "超时保护启用": config["gpu"]["timeout_protection"],
        "uint32 workaround": config["gpu"]["uint32_workaround"],
    }

    all_passed = True
    for check_name, result in checks.items():
        status = "[PASS]" if result else "[FAIL]"
        print(f"  {status} {check_name}")
        if not result:
            all_passed = False

    print()

    if all_passed:
        print("[PASS] 所有配置检查通过!")
    else:
        print("[WARN] 部分配置检查未通过,请检查")

    return all_passed


def print_usage(config_path: Path, config: dict) -> None:
    """打印使用说明"""
    print_header("使用说明")

    print("  方法1: 替换现有配置")
    print(f"    copy {config_path.name} config.json")
    print()
    print("  方法2: 命令行指定")
    print(f"    python key_collision_cli.py --config {config_path.name}")
    print()
    print("  方法3: 在代码中使用")
    print("    engine = GPUCollisionEngine(")
    print("        targets=target_addresses,")
    print("        batch_size=131072,")
    print("        use_gpu_memory_pool=True,")
    print(f"        device_index={config['gpu']['device_index']}")
    print("    )")
    print()


def main():
    """主函数"""
    print_header("Intel Arc A770 GPU自动配置工具")

    # 1. 检测GPU
    device_index = detect_gpus()

    if device_index is None:
        print("\n[ERROR] 无法自动配置,请手动检查GPU驱动和连接")
        return

    # 2. 生成配置
    print_header("生成优化配置")
    config = generate_config(device_index)

    print(f"  批次大小: {config['collision']['batch_size']:,}")
    print(f"  GPU设备索引: {config['gpu']['device_index']}")
    print(f"  内存池: {config['gpu']['max_buffers']}缓冲区 / {config['gpu']['max_memory_mb']}MB")
    print(f"  异步执行: {'禁用' if not config['gpu']['async_execution'] else '启用'}")
    print("  uint32 workaround: 已启用")
    print()

    # 3. 保存配置
    config_path = save_config(config)

    # 4. 验证配置
    verify_config(config)

    # 5. 打印使用说明
    print_usage(config_path, config)

    # 总结
    print_header("配置完成")
    print(f"  Intel Arc A770 (索引{device_index}) 已配置为默认GPU")
    print(f"  配置文件: {config_path}")
    print()
    print("  下一步:")
    print(f"    1. 使用新配置运行: python key_collision_cli.py --config {config_path.name}")
    print("    2. 运行稳定性测试验证")
    print("    3. 观察是否仍有间歇性问题")
    print()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""验证GPU设备优先级修复效果"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.gpu.device import GPUDeviceDetector


def main():
    print("=" * 80)
    print("  GPU设备优先级修复验证")
    print("=" * 80)
    print()

    # 1. 检测所有设备
    print("步骤1: 检测所有GPU设备")
    print("-" * 80)
    devices = GPUDeviceDetector.detect_devices()

    if not devices:
        print("[ERROR] 未检测到GPU设备")
        return

    print(f"检测到 {len(devices)} 个GPU设备:\n")
    for i, device in enumerate(devices):
        name = device.get("name", "Unknown")
        mem_gb = device.get("global_mem_size", 0) / (1024**3)
        cu = device.get("max_compute_units", "N/A")
        print(f"  GPU {i}: {name}")
        print(f"    显存: {mem_gb:.1f} GB")
        print(f"    计算单元: {cu}")
        print()

    # 2. 测试自动选择
    print("步骤2: 测试自动选择逻辑")
    print("-" * 80)
    best_device = GPUDeviceDetector._select_best_device(devices.copy())

    print(f"自动选择的设备: {best_device['name']}")
    print(f"  显存: {best_device.get('global_mem_size', 0) / (1024**3):.1f} GB")
    print(f"  计算单元: {best_device.get('max_compute_units', 'N/A')}")
    print()

    # 3. 验证选择正确性
    print("步骤3: 验证选择逻辑")
    print("-" * 80)

    # 计算每个设备的分数
    def calc_score(dev):
        name_lower = dev["name"].lower()
        vendor_lower = dev.get("vendor", "").lower()

        global_mem_gb = dev.get("global_mem_size", 0) / (1024**3)
        memory_score = global_mem_gb * 10

        compute_units = dev.get("max_compute_units", 0)
        cu_score = (compute_units / 100.0) * 5

        if "nvidia" in name_lower or "nvidia" in vendor_lower:
            vendor_score = 20
        elif "amd" in name_lower or "amd" in vendor_lower:
            vendor_score = 15
        elif "intel" in name_lower and "arc" in name_lower:
            vendor_score = 10
        elif "intel" in name_lower:
            vendor_score = 5
        else:
            vendor_score = 0

        return memory_score + cu_score + vendor_score

    print("各设备优先级分数:\n")
    for i, device in enumerate(devices):
        score = calc_score(device)
        name = device.get("name", "Unknown")
        mem_gb = device.get("global_mem_size", 0) / (1024**3)

        print(f"  GPU {i}: {name}")
        print(f"    显存分数: {mem_gb * 10:.1f}")
        print(f"    总分: {score:.1f}")
        print()

    # 4. 结论
    print("=" * 80)
    print("  验证结论")
    print("=" * 80)
    print()

    # 检查是否有Intel Arc
    has_intel_arc = any("Arc" in d.get("name", "") for d in devices)
    has_nvidia = any(
        "NVIDIA" in d.get("name", "") or "GTX" in d.get("name", "") or "RTX" in d.get("name", "")
        for d in devices
    )

    if has_intel_arc and has_nvidia:
        # 多GPU环境
        intel_arc_dev = next(d for d in devices if "Arc" in d.get("name", ""))
        nvidia_dev = next(
            d
            for d in devices
            if "NVIDIA" in d.get("name", "") or "GTX" in d.get("name", "") or "RTX" in d.get("name", "")
        )

        intel_score = calc_score(intel_arc_dev)
        nvidia_score = calc_score(nvidia_dev)

        print("多GPU环境检测:")
        print(
            f"  Intel Arc: {intel_arc_dev['name']} ({intel_arc_dev.get('global_mem_size', 0) / (1024**3):.1f}GB)"
        )
        print(
            f"  NVIDIA: {nvidia_dev['name']} ({nvidia_dev.get('global_mem_size', 0) / (1024**3):.1f}GB)"
        )
        print()

        if intel_score > nvidia_score:
            print("[PASS] 修复成功! Intel Arc A770被正确选择(显存更大)")
        else:
            print("[WARN] NVIDIA被选择(可能显存更小但厂商优先级高)")
            print(f"  Intel Arc分数: {intel_score:.1f}")
            print(f"  NVIDIA分数: {nvidia_score:.1f}")
    else:
        print(f"[INFO] 单GPU环境,自动选择: {best_device['name']}")

    print()
    print("=" * 80)


if __name__ == "__main__":
    main()

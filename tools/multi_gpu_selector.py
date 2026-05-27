#!/usr/bin/env python3
"""多GPU环境选择工具.

功能:
- 检测所有可用GPU设备
- 显示每个GPU的详细信息
- 智能推荐最佳GPU
- 生成配置文件

使用方法:
    python tools/multi_gpu_selector.py
"""

import json
from pathlib import Path


def detect_all_gpus():
    """检测所有GPU设备."""
    try:
        import pyopencl as cl

        print("🔍 正在检测GPU设备...\n")

        # 获取所有平台
        platforms = cl.get_platforms()
        all_devices = []

        for platform_idx, platform in enumerate(platforms):
            platform_name = platform.get_info(cl.platform_info.NAME)
            platform_vendor = platform.get_info(cl.platform_info.VENDOR)

            print(f"📦 平台 {platform_idx}: {platform_name} ({platform_vendor})")
            print("-" * 80)

            try:
                devices = platform.get_devices(device_type=cl.device_type.GPU)

                for device_idx, device in enumerate(devices):
                    device_name = device.get_info(cl.device_info.NAME)
                    device_vendor = device.get_info(cl.device_info.VENDOR)
                    global_mem = device.get_info(cl.device_info.GLOBAL_MEM_SIZE)
                    max_compute_units = device.get_info(cl.device_info.MAX_COMPUTE_UNITS)
                    max_work_group_size = device.get_info(cl.device_info.MAX_WORK_GROUP_SIZE)
                    global_mem_cache_size = device.get_info(cl.device_info.GLOBAL_MEM_CACHE_SIZE)
                    local_mem_size = device.get_info(cl.device_info.LOCAL_MEM_SIZE)

                    device_info = {
                        "platform_index": platform_idx,
                        "device_index": device_idx,
                        "global_index": len(all_devices),
                        "name": device_name,
                        "vendor": device_vendor,
                        "global_mem_gb": global_mem / (1024**3),
                        "global_mem_bytes": global_mem,
                        "max_compute_units": max_compute_units,
                        "max_work_group_size": max_work_group_size,
                        "global_mem_cache_kb": global_mem_cache_size / 1024,
                        "local_mem_kb": local_mem_size / 1024,
                        "device": device,
                        "platform": platform,
                    }

                    all_devices.append(device_info)

                    # 打印设备信息
                    print(f"\n  🎮 GPU {len(all_devices) - 1}: {device_name}")
                    print(f"     厂商: {device_vendor}")
                    print(f"     显存: {global_mem / (1024**3):.2f} GB")
                    print(f"     计算单元: {max_compute_units}")
                    print(f"     最大工作组: {max_work_group_size:,}")
                    print(f"     全局缓存: {global_mem_cache_size / 1024:.0f} KB")
                    print(f"     本地内存: {local_mem_size / 1024:.0f} KB")

            except Exception as e:
                print(f"  ⚠️  获取设备失败: {e}")

            print()

        return all_devices

    except ImportError:
        print("❌ pyopencl未安装")
        return []
    except Exception as e:
        print(f"❌ GPU检测失败: {e}")
        return []


def calculate_priority_score(device_info):
    """计算GPU优先级分数.

    评分标准:
    - 显存大小: 10分/GB (最重要)
    - 计算单元: 0.05分/CU
    - 厂商偏好: NVIDIA=20, AMD=15, Intel Arc=10, 其他=0
    """
    name_lower = device_info["name"].lower()
    vendor_lower = device_info["vendor"].lower()

    # 显存分数 (每GB 10分)
    memory_score = device_info["global_mem_gb"] * 10

    # 计算单元分数
    cu_score = device_info["max_compute_units"] * 0.05

    # 厂商基础分
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

    total_score = memory_score + cu_score + vendor_score

    return {
        "memory_score": memory_score,
        "cu_score": cu_score,
        "vendor_score": vendor_score,
        "total_score": total_score,
    }


def recommend_gpu(devices):
    """推荐最佳GPU."""
    if not devices:
        return None, "未检测到GPU设备"

    # 计算每个设备的分数
    scored_devices = []
    for device in devices:
        scores = calculate_priority_score(device)
        device["scores"] = scores
        scored_devices.append((device, scores["total_score"]))

    # 按分数排序
    scored_devices.sort(key=lambda x: x[1], reverse=True)
    best_device, best_score = scored_devices[0]

    return best_device, f"推荐指数: {best_score:.1f}"


def generate_config(device, devices, output_file="config.multi_gpu.json"):
    """生成多GPU配置文件."""
    config = {
        "gpu": {
            "enabled": True,
            "device_index": device["global_index"],
            "batch_size": 10000,
            "use_memory_pool": True,
            "enable_async": True,
            "description": f"使用 {device['name']} ({device['global_mem_gb']:.1f}GB)",
        },
        "multi_gpu": {
            "all_devices": [
                {
                    "index": d["global_index"],
                    "name": d["name"],
                    "vendor": d["vendor"],
                    "memory_gb": d["global_mem_gb"],
                }
                for d in devices
            ],
            "recommended_index": device["global_index"],
        },
    }

    output_path = Path(output_file)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    return output_path


def print_summary(devices, recommended, recommendation_text):
    """打印总结."""
    print("\n" + "=" * 80)
    print("📊 GPU检测总结")
    print("=" * 80)

    print(f"\n🔢 检测到GPU数量: {len(devices)}")

    if devices:
        print("\n📋 所有GPU设备:")
        for i, device in enumerate(devices):
            scores = device["scores"]
            recommended_marker = "⭐" if device == recommended else "  "
            print(f"  {recommended_marker} GPU {i}: {device['name']}")
            print(f"      显存: {device['global_mem_gb']:.2f} GB | 分数: {scores['total_score']:.1f}")

        print("\n🏆 推荐GPU:")
        print(f"  {recommended['name']}")
        print(f"  全局索引: {recommended['global_index']}")
        print(f"  {recommendation_text}")
        print(f"  显存: {recommended['global_mem_gb']:.2f} GB")
        print("  评分详情:")
        print(f"    - 显存得分: {recommended['scores']['memory_score']:.1f}")
        print(f"    - 计算单元得分: {recommended['scores']['cu_score']:.1f}")
        print(f"    - 厂商得分: {recommended['scores']['vendor_score']:.1f}")

        print("\n💡 使用方式:")
        print("  方式1: 修改config.json")
        print(f'    "gpu_device_index": {recommended["global_index"]}')
        print()
        print("  方式2: 生成新配置文件")
        print("    python tools/multi_gpu_selector.py --generate-config")
        print()
        print("  方式3: 命令行参数")
        print(f"    python key_collision_cli.py --gpu-device {recommended['global_index']}")


def main():
    """主函数."""
    import argparse

    parser = argparse.ArgumentParser(description="多GPU环境选择工具")
    parser.add_argument("--generate-config", action="store_true", help="生成多GPU配置文件")
    parser.add_argument("--output", default="config.multi_gpu.json", help="配置文件输出路径")

    args = parser.parse_args()

    print("=" * 80)
    print("🎮 多GPU环境检测与选择工具")
    print("=" * 80)
    print()

    # 检测GPU
    devices = detect_all_gpus()

    if not devices:
        print("\n❌ 未检测到GPU设备")
        print("请检查:")
        print("  1. 是否正确安装GPU驱动")
        print("  2. 是否安装pyopencl: pip install pyopencl")
        print("  3. GPU是否支持OpenCL")
        return

    # 推荐GPU
    recommended, recommendation_text = recommend_gpu(devices)

    # 打印总结
    print_summary(devices, recommended, recommendation_text)

    # 生成配置文件
    if args.generate_config:
        print("\n📝 生成配置文件...")
        config_path = generate_config(recommended, devices, args.output)
        print(f"✅ 配置文件已生成: {config_path}")
        print(f"   使用方式: python key_collision_cli.py --config {config_path}")


if __name__ == "__main__":
    main()

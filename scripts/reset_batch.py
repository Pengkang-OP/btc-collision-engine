#!/usr/bin/env python3
"""
Intel Arc A770 Batch Size 重置工具

当 GPU 性能持续下降时，使用此脚本重置 batch_size 到初始值。

使用方法:
    python reset_batch.py
    python reset_batch.py --batch 1572864
"""

import argparse


def reset_batch_size(target_batch: int = 1572864):
    """
    重置 batch_size 配置

    Args:
        target_batch: 目标 batch_size 值
    """
    import json
    import os

    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json"
    )

    # 读取配置
    with open(config_path, encoding="utf-8") as f:
        config = json.load(f)

    # 检查当前值
    current = config.get("gpu", {}).get("per_device_config", {}).get("1", {})
    current_batch = current.get("batch_size", "未设置")

    print(f"当前 batch_size: {current_batch}")
    print(f"目标 batch_size: {target_batch}")

    # 更新配置
    if "gpu" not in config:
        config["gpu"] = {}
    if "per_device_config" not in config["gpu"]:
        config["gpu"]["per_device_config"] = {}
    if "1" not in config["gpu"]["per_device_config"]:
        config["gpu"]["per_device_config"]["1"] = {}

    config["gpu"]["per_device_config"]["1"]["batch_size"] = target_batch

    # 原子写回配置（先写临时文件再 rename，防止中断截断）
    tmp_path = config_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)
    os.replace(tmp_path, config_path)

    print(f"[OK] batch_size reset to: {target_batch}")
    print("请重启程序以应用新配置")


def main():
    parser = argparse.ArgumentParser(description="Intel Arc A770 Batch Size 重置工具")
    parser.add_argument(
        "--batch", "-b", type=int, default=1572864, help="目标 batch_size 值 (默认: 1572864)"
    )

    args = parser.parse_args()
    reset_batch_size(args.batch)


if __name__ == "__main__":
    main()

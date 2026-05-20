"""基础碰撞示例 - Basic Collision Example

演示最简单的比特币私钥碰撞使用方式。

用法:
    python examples/basic_collision.py

功能说明:
    - 随机生成比特币私钥
    - 计算对应的公钥和地址
    - 检查是否与目标地址匹配
    - 运行 10 秒后自动停止
"""

import os
import sys
import time

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.address_converter import AddressConverter
from src.core.base58 import Base58
from src.core.key_generator import SecureKeyGenerator

# ─────────────────────────────────────────────────────────────────────────────
# 目标地址（示例：比特币创世区块地址，余额 > 50 BTC）
# ─────────────────────────────────────────────────────────────────────────────
TARGET_ADDRESSES = [
    "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",  # 创世区块地址
    "1HLoD9E4SDFFPDiYfNYnkBLQ85Y51J3Zb1",  # 早期挖矿地址
]

# 运行时长（秒）
RUN_DURATION = 10


def main():
    print("=" * 60)
    print("  BTC 碰撞引擎 - 基础碰撞示例")
    print("=" * 60)
    print(f"  目标地址数: {len(TARGET_ADDRESSES)}")
    print(f"  运行时长  : {RUN_DURATION} 秒")
    print("  碰撞模式  : 随机（CPU）")
    print("-" * 60)

    # 初始化组件
    key_gen = SecureKeyGenerator()
    converter = AddressConverter()

    # 将目标地址转为 Hash160 集合以实现 O(1) 匹配
    target_hash160_set = set()
    for addr in TARGET_ADDRESSES:
        try:
            # Base58Check 解码: 版本字节(1) + Hash160(20) + 校验和(4)
            _, payload = Base58.check_decode(addr)
            h160 = payload  # payload 即 Hash160
            target_hash160_set.add(bytes(h160))
        except Exception as e:
            print(f"  [WARN] 无法解码目标地址 {addr}: {e}")
    print(f"  已加载 {len(target_hash160_set)} 个目标 Hash160")

    # 开始碰撞
    start_time = time.time()
    checked = 0
    matches = []

    print("\n  开始碰撞...")
    try:
        while time.time() - start_time < RUN_DURATION:
            # 生成随机私钥（generate_single 返回 bytes）
            private_key = key_gen.generate_single()

            # 计算地址信息（含 Hash160）
            result = converter.private_key_to_address(private_key, compressed=True)
            address = result['address']
            hash160 = bytes.fromhex(result['hash160'])

            checked += 1

            # 检查是否匹配
            if hash160 in target_hash160_set:
                elapsed = time.time() - start_time
                matches.append({
                    "private_key": private_key.hex(),
                    "address": address,
                    "elapsed": elapsed,
                    "checked_count": checked,
                })
                print(f"\n  [!!] 发现匹配！地址: {address}")
                print(f"       私钥: {private_key.hex()}")

            # 每 100000 次打印进度
            if checked % 100_000 == 0:
                elapsed = time.time() - start_time
                speed = checked / elapsed if elapsed > 0 else 0
                print(
                    f"  [{elapsed:.1f}s] 已检查: {checked:,} | "
                    f"速度: {speed/1000:.1f}K/s | 匹配: {len(matches)}"
                )

    except KeyboardInterrupt:
        print("\n  [用户中断]")

    # 最终统计
    elapsed = time.time() - start_time
    speed = checked / elapsed if elapsed > 0 else 0

    print("\n" + "=" * 60)
    print("  运行结束")
    print("-" * 60)
    print(f"  总检查数: {checked:,}")
    print(f"  运行时间: {elapsed:.2f} 秒")
    print(f"  平均速度: {speed/1000:.1f}K/s")
    print(f"  发现匹配: {len(matches)} 个")
    print("=" * 60)

    if matches:
        print("\n  匹配详情:")
        for m in matches:
            print(f"    地址    : {m['address']}")
            print(f"    私钥    : {m['private_key']}")
            print(f"    发现时刻: {m['elapsed']:.2f}s")


if __name__ == "__main__":
    main()

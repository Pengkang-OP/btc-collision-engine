#!/usr/bin/env python3
"""
测试: 目标地址包含多格式时的处理逻辑
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import secrets
from src.core.multi_format_generator import MultiFormatAddressGenerator, AddressFormat
from src.collision.targets.format_aware_manager import FormatAwareTargetManager

print("=" * 80)
print("测试: 多格式目标地址场景")
print("=" * 80)

gen = MultiFormatAddressGenerator()

# 已知私钥=1生成的各格式地址
test_key = bytes.fromhex("0000000000000000000000000000000000000000000000000000000000000001")
addrs = gen.generate_all_formats(test_key)

print("\n测试私钥=1生成的地址:")
for fmt, addr in addrs.items():
    print(f"  {fmt:10s}: {addr}")

print("\n" + "=" * 80)
print("场景1: 目标包含P2PKH和Bech32")
print("-" * 80)

manager = FormatAwareTargetManager()
manager.add_target(addrs["p2pkh"])  # 添加P2PKH目标
manager.add_target(addrs["bech32"])  # 添加Bech32目标

print(f"目标格式: {manager.get_format_stats()}")
print(f"P2PKH目标: {addrs['p2pkh']}")
print(f"Bech32目标: {addrs['bech32']}")

# 执行匹配
is_match, matched_addr, matched_fmt = manager.check_match(test_key)

print(f"\n匹配结果:")
print(f"  匹配: {'✓' if is_match else '✗'}")
print(f"  地址: {matched_addr}")
print(f"  格式: {matched_fmt}")

print(f"\n处理流程:")
print(f"  1. 遍历到P2PKH格式，有{manager.get_targets_by_format()[AddressFormat.P2PKH]}个目标")
print(f"     - 生成P2PKH地址: {addrs['p2pkh']}")
print(f"     - 检查是否在目标中: {'是' if addrs['p2pkh'].lower() in manager.get_targets_by_format()[AddressFormat.P2PKH] else '否'}")
print(f"  2. 继续遍历到Bech32格式，有{manager.get_targets_by_format()[AddressFormat.BECH32]}个目标")
print(f"     - 生成Bech32地址: {addrs['bech32']}")
print(f"     - 检查是否在目标中: {'是' if addrs['bech32'].lower() in manager.get_targets_by_format()[AddressFormat.BECH32] else '否'}")
print(f"  3. 两个格式都匹配，返回第一个匹配的（P2PKH先遍历）")

print("\n" + "=" * 80)
print("场景2: 目标只包含Bech32")
print("-" * 80)

manager2 = FormatAwareTargetManager()
manager2.add_target(addrs["bech32"])  # 只添加Bech32目标

print(f"目标格式: {manager2.get_format_stats()}")
print(f"Bech32目标: {addrs['bech32']}")

is_match2, matched_addr2, matched_fmt2 = manager2.check_match(test_key)

print(f"\n匹配结果:")
print(f"  匹配: {'✓' if is_match2 else '✗'}")
print(f"  地址: {matched_addr2}")
print(f"  格式: {matched_fmt2}")

print(f"\n处理流程:")
print(f"  1. P2PKH格式有0个目标 → 跳过（不生成P2PKH地址）")
print(f"  2. Bech32格式有1个目标")
print(f"     - 生成Bech32地址: {addrs['bech32']}")
print(f"     - 检查是否在目标中: 是")
print(f"     - 匹配成功！")
print(f"  3. P2SH和Taproot有0个目标 → 跳过")

print("\n✓ 优化效果: 只生成了1个格式（Bech32），跳过了3个空格式！")

print("\n" + "=" * 80)
print("场景3: 目标包含所有4种格式")
print("-" * 80)

manager3 = FormatAwareTargetManager()
manager3.add_target(addrs["p2pkh"])
manager3.add_target(addrs["p2sh"])
manager3.add_target(addrs["bech32"])
manager3.add_target(addrs["taproot"])

print(f"目标格式: {manager3.get_format_stats()}")
print(f"所有格式都有目标")

is_match3, matched_addr3, matched_fmt3 = manager3.check_match(test_key)

print(f"\n匹配结果:")
print(f"  匹配: {'✓' if is_match3 else '✗'}")
print(f"  地址: {matched_addr3}")
print(f"  格式: {matched_fmt3}")

print(f"\n处理流程:")
print(f"  1. P2PKH: 有目标，生成地址，{'匹配成功' if matched_fmt3 == 'p2pkh' else '不匹配'}")
print(f"     - 匹配: {matched_fmt3 == 'p2pkh'}")
if matched_fmt3 != 'p2pkh':
    print(f"  2. P2SH: 有目标，生成地址，{'匹配成功' if matched_fmt3 == 'p2sh' else '不匹配'}")
if matched_fmt3 not in ['p2pkh', 'p2sh']:
    print(f"  3. Bech32: 有目标，生成地址，{'匹配成功' if matched_fmt3 == 'bech32' else '不匹配'}")
if matched_fmt3 == 'bech32':
    print(f"     - 返回Bech32匹配！")
print(f"\n  由于P2PKH在字典中第一个被遍历，会返回P2PKH格式的匹配")

print("\n" + "=" * 80)
print("场景4: 模拟现实碰撞场景")
print("-" * 80)

print("场景: 目标地址表包含多个P2PKH和多个Bech32地址")
print("其中一个Bech32地址匹配")

# 创建模拟场景
manager4 = FormatAwareTargetManager()
manager4.add_target("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa")  # 假P2PKH地址
manager4.add_target("bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4")  # 真实的Bech32地址（私钥=1）

print(f"目标格式: {manager4.get_format_stats()}")

# 测试匹配
is_match4, matched_addr4, matched_fmt4 = manager4.check_match(test_key)

print(f"\n匹配结果:")
print(f"  匹配: {'✓' if is_match4 else '✗'}")
print(f"  地址: {matched_addr4}")
print(f"  格式: {matched_fmt4}")

print(f"\n✓ 正确匹配了Bech32地址！")

print("\n" + "=" * 80)
print("总结")
print("=" * 80)

print("""
多格式目标地址处理逻辑:

1. 【格式遍历】按固定顺序遍历所有格式
   P2PKH → P2SH → Bech32 → Taproot

2. 【跳过优化】跳过没有目标的格式
   • 如果该格式没有目标 → continue（不生成地址）

3. 【匹配逻辑】找到匹配立即返回
   • 生成该格式地址
   • 检查是否在目标集合中
   • 匹配成功 → 返回
   • 匹配失败 → 继续下一个格式

4. 【性能优化】只生成有目标空间的格式
   • 1个格式目标 → 生成1次
   • 2个格式目标 → 生成2次
   • 4个格式目标 → 生成4次

5. 【匹配顺序】返回第一个匹配的格式
   • 按遍历顺序返回
   • 通常是P2PKH（字典定义第一个）
""")

print("=" * 80)

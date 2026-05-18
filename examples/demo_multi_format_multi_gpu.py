#!/usr/bin/env python3
"""
快速演示: 使用多格式多GPU引擎
"""

import sys
sys.path.insert(0, 'src')

print("=" * 80)
print("快速演示: 多格式多GPU引擎")
print("=" * 80)

# 1. 导入并创建引擎
print("\n1. 创建多格式多GPU引擎...")
from src.gpu.multi_format_multi_gpu_engine import create_engine
engine = create_engine()
print("   ✅ 引擎创建成功!")

# 2. 添加多种格式的目标地址
print("\n2. 添加多种格式的目标地址...")
targets = [
    # P2PKH格式
    "1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH",
    "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",  # Satoshi的地址
    
    # Bech32格式
    "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4",
    
    # Taproot格式
    "bc1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vqzk5jj0",
]

for addr in targets:
    engine.add_target(addr)
print(f"   ✅ 已添加 {len(targets)} 个目标地址")

# 3. 显示格式统计
print("\n3. 格式统计...")
stats = engine.get_format_stats()
print("   格式统计:")
for fmt, count in stats.items():
    print(f"     • {fmt.upper()}: {count} 个地址")

# 4. 测试已知私钥 (私钥=1)
print("\n4. 测试已知私钥 (私钥=1)...")
from src.core.multi_format_generator import MultiFormatAddressGenerator
gen = MultiFormatAddressGenerator()

known_private_key = b"\x00" * 31 + b"\x01"
print("   私钥: 1")

is_match, matches = engine.check_match_all(known_private_key)

if is_match:
    print(f"\n   🎉 找到 {len(matches)} 个匹配!")
    for addr, fmt in matches:
        print(f"      ✅ {fmt.upper()}: {addr}")
else:
    print(f"\n   没有找到匹配 (应该找到的，让我检查一下...)")
    
    # 单独测试生成
    print("\n   验证地址生成:")
    all_addresses = gen.generate_all_formats(known_private_key)
    for fmt, addr in all_addresses.items():
        in_targets = addr in engine._format_manager.get_all_targets()
        print(f"      {fmt}: {addr} {'✅ 在目标中' if in_targets else '❌ 不在目标中'}")

# 5. 测试随机私钥
print("\n5. 测试随机私钥...")
import secrets
for i in range(3):
    test_key = secrets.token_bytes(32)
    is_match, matches = engine.check_match_all(test_key)
    
    if is_match:
        print(f"   私钥 {i+1}: 🎉 找到匹配!")
        for addr, fmt in matches:
            print(f"      {fmt}: {addr}")
    else:
        print(f"   私钥 {i+1}: 无匹配 (正常)")

# 6. 清理
print("\n6. 清理...")
engine.cleanup()
print("   ✅ 清理完成")

print("\n" + "=" * 80)
print("🎉 演示完成!")
print("=" * 80)
print("\n📋 使用示例:")
print("""
# 基本使用
from src.gpu.multi_format_multi_gpu_engine import create_engine

# 创建引擎
engine = create_engine()

# 添加多格式目标
engine.add_target("1BgGZ...")  # P2PKH
engine.add_target("bc1q...")   # Bech32

# 检查匹配
is_match, addr, fmt = engine.check_match(private_key)

# 完整检查
is_match, matches = engine.check_match_all(private_key)

# 清理
engine.cleanup()
""")

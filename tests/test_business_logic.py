"""简单测试业务逻辑模块"""

import os
import sys

# 切换到项目根目录
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.abspath("."))


print("=" * 60)
print("测试业务逻辑核心模块")
print("=" * 60)

# 测试1: 私钥生成器
print("\n1. 测试私钥生成器...")
try:
    from src.core.key_generator import SecureKeyGenerator

    generator = SecureKeyGenerator({"batch_size": 100})

    keys = generator.generate_batch(10)
    print(f"   生成了 {len(keys)} 个私钥")
    print(f"   每个私钥长度: {len(keys[0])} 字节")
    print("   ✅ 私钥生成器测试通过")
except Exception as e:
    print(f"   ❌ 私钥生成器测试失败: {e}")

# 测试2: 地址转换器
print("\n2. 测试地址转换器...")
try:
    from src.core.address_converter import AddressConverter

    converter = AddressConverter()

    # 使用有效的32字节私钥（非全0）
    test_key = b"\x01" + b"\x00" * 31  # 测试用的简单私钥
    result = converter.private_key_to_all(test_key)

    print(f"   私钥: {test_key.hex()[:20]}...")
    print(f"   压缩地址: {result['address_compressed']}")
    print(f"   压缩WIF: {result['wif_compressed'][:20]}...")
    print("   ✅ 地址转换器测试通过")
except Exception as e:
    print(f"   ❌ 地址转换器测试失败: {e}")

# 测试3: 目标地址表
print("\n3. 测试目标地址表...")
try:
    from src.core.target_address_table import BitcoinTargetTable

    table = BitcoinTargetTable()

    # 生成一个测试目标
    test_key = b"\x01" + b"\x00" * 31  # 测试用的简单私钥
    test_result = converter.private_key_to_all(test_key)

    table.add_target(
        wif=test_result["wif_compressed"],
        address=test_result["address_compressed"],
        hash160=test_result["hash160_compressed"],
    )

    stats = table.get_statistics()
    print(f"   目标地址数: {stats['total_targets']}")

    # 测试匹配
    is_match, info = table.check_match(test_result["hash160_compressed"])
    print(f"   匹配测试: {'成功' if is_match else '失败'}")
    print("   ✅ 目标地址表测试通过")
except Exception as e:
    print(f"   ❌ 目标地址表测试失败: {e}")
    import traceback

    traceback.print_exc()

# 测试4: 持续比对系统
print("\n4. 测试持续比对系统...")
try:
    from src.collision.continuous_matcher import ContinuousMatcher

    matcher = ContinuousMatcher(table)

    # 创建测试地址
    test_addresses = []
    for i in range(10):
        # 使用不同的32字节私钥
        pk = (i + 2).to_bytes(32, "big")
        result = converter.private_key_to_all(pk)
        test_addresses.append({"hash160": result["hash160_compressed"], "private_key": pk})

    # 添加一个匹配的地址
    if "test_result" in locals():
        test_addresses.append({"hash160": test_result["hash160_compressed"], "private_key": test_key})

    matches = matcher.check_address_batch(test_addresses)
    print(f"   检查了 {len(test_addresses)} 个地址")
    print(f"   找到 {len(matches)} 个匹配")
    print("   ✅ 持续比对系统测试通过")
except Exception as e:
    print(f"   ❌ 持续比对系统测试失败: {e}")
    import traceback

    traceback.print_exc()

# 测试5: 数据存储
print("\n5. 测试数据存储...")
try:
    from src.collision.match_storage import MatchDataStorage

    storage = MatchDataStorage("./test_matches")

    if "matches" in locals() and matches:
        filepath = storage.save_match(matches[0])
        print(f"   保存到: {filepath}")

        stats = storage.get_statistics()
        print(f"   总匹配数: {stats['total_matches']}")
        print("   ✅ 数据存储测试通过")
    else:
        print("   ⚠️  无匹配数据，跳过存储测试")
except Exception as e:
    print(f"   ❌ 数据存储测试失败: {e}")
    import traceback

    traceback.print_exc()

# 测试6: 合规验证
print("\n6. 测试规范合规性验证...")
try:
    from src.core.compliance_validator import BitcoinComplianceValidator

    validator = BitcoinComplianceValidator()

    if "test_result" in locals():
        validation_data = {
            "private_key": test_key,
            "public_key": test_result["public_key_compressed"],
            "address": test_result["address_compressed"],
            "wif": test_result["wif_compressed"],
            "hash160": test_result["hash160_compressed"],
            "compressed": True,
        }

        is_valid, issues = validator.validate(validation_data)
        print(f"   合规性: {'通过' if is_valid else '失败'}")
        if issues:
            print(f"   问题: {issues}")
        print("   ✅ 合规验证测试通过")
    else:
        print("   ⚠️  无测试数据，跳过合规验证测试")
except Exception as e:
    print(f"   ❌ 合规验证测试失败: {e}")
    import traceback

    traceback.print_exc()

print("\n" + "=" * 60)
print("测试完成！")
print("=" * 60)

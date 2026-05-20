"""
业务逻辑核心模块使用示例

演示如何使用BTC碰撞引擎的业务逻辑模块：
1. 比特币目标地址表
2. 安全私钥生成器
3. 地址转换器
4. 持续比对系统
5. 匹配数据存储
6. 规范合规性验证
"""
import os

# 确保在项目根目录运行
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# H-NEW2修复: 使用正确的包路径导入模块（扁平导入已失效）
from src.collision.continuous_matcher import ContinuousMatcher
from src.collision.match_storage import MatchDataStorage
from src.core.address_converter import AddressConverter
from src.core.compliance_validator import BitcoinComplianceValidator
from src.core.key_generator import SecureKeyGenerator
from src.core.target_address_table import BitcoinTargetTable


def example_1_target_table():
    """示例1: 比特币目标地址表"""
    print("=" * 60)
    print("示例1: 比特币目标地址表")
    print("=" * 60)

    # 创建目标地址表
    table = BitcoinTargetTable(max_size=1000000)

    # 从WIF列表加载目标地址
    # ⚠️ 安全: 运行时动态生成演示私钥，不硬编码WIF
    import secrets as _secrets
    _demo_key = _secrets.token_bytes(32)
    from src.core.wif import WIF
    [
        WIF.encode(_demo_key, compressed=True),  # 动态生成演示WIF
        # 可以添加更多WIF地址
    ]

    # 注意：这里的WIF是示例，实际使用时应替换为真实的目标地址
    # loaded_count = table.load_from_wif_list(wif_list)
    # print(f"加载了 {loaded_count} 个目标地址")

    # 查看统计信息
    stats = table.get_statistics()
    print(f"目标地址表统计: {stats}")

    print()


def example_2_key_generator():
    """示例2: 安全私钥生成器"""
    print("=" * 60)
    print("示例2: 安全私钥生成器")
    print("=" * 60)

    # 创建私钥生成器
    config = {
        'batch_size': 1000,
        'rate_limit': 0,  # 无限制
        'key_format': 'both'
    }

    generator = SecureKeyGenerator(config)

    # 批量生成私钥
    private_keys = generator.generate_batch(100)
    print(f"生成了 {len(private_keys)} 个私钥")

    # 查看统计信息
    stats = generator.get_statistics()
    print(f"生成统计: {stats}")

    print()


def example_3_address_converter():
    """示例3: 地址转换器"""
    print("=" * 60)
    print("示例3: 地址转换器")
    print("=" * 60)

    import secrets

    # 创建地址转换器
    converter = AddressConverter()

    # 生成随机私钥
    private_key = secrets.token_bytes(32)

    # 完整转换
    result = converter.private_key_to_all(private_key)

    print(f"私钥: {private_key.hex()}")
    print(f"压缩地址: {result['address_compressed']}")
    print(f"非压缩地址: {result['address_uncompressed']}")
    print(f"压缩WIF: {result['wif_compressed']}")
    print(f"非压缩WIF: {result['wif_uncompressed']}")

    print()


def example_4_continuous_matcher():
    """示例4: 持续比对系统"""
    print("=" * 60)
    print("示例4: 持续比对系统")
    print("=" * 60)

    # 创建目标地址表
    table = BitcoinTargetTable()

    # 创建比对系统
    matcher = ContinuousMatcher(table)

    # 模拟地址列表
    import secrets
    addresses = []
    for _ in range(100):
        private_key = secrets.token_bytes(32)
        addresses.append({
            'hash160': secrets.token_bytes(20),  # 随机Hash160
            'private_key': private_key
        })

    # 批量比对
    matches = matcher.check_address_batch(addresses)
    print(f"检查了 {len(addresses)} 个地址，找到 {len(matches)} 个匹配")

    # 查看统计信息
    stats = matcher.get_statistics()
    print(f"比对统计: {stats}")

    print()


def example_5_match_storage():
    """示例5: 匹配数据存储"""
    print("=" * 60)
    print("示例5: 匹配数据存储")
    print("=" * 60)

    # 创建存储
    storage = MatchDataStorage('./test_matches')

    # 模拟匹配数据 — 使用动态生成的占位WIF
    import secrets as _secrets

    from src.core.wif import WIF
    _demo_pk = _secrets.token_bytes(32)
    _demo_wif_c = WIF.encode(_demo_pk, compressed=True)
    _demo_wif_u = WIF.encode(_demo_pk, compressed=False)
    {
        'found_at': '2026-04-22T10:30:45.123456',
        'hash160': _secrets.token_bytes(20).hex(),
        'generated': {
            'private_key': _demo_pk,
            'wif_compressed': _demo_wif_c,
            'wif_uncompressed': _demo_wif_u,
            'public_key_compressed': _secrets.token_bytes(33),
            'public_key_uncompressed': _secrets.token_bytes(65),
            'address_compressed': '1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2',  # 公开测试地址
            'address_uncompressed': '1EHNa6Q4Jz2uvNExL497mE43ikXhwF6kZm',  # 公开测试地址
            'hash160_compressed': _secrets.token_bytes(20),
            'hash160_uncompressed': _secrets.token_bytes(20)
        },
        'target': {
            'address': '1EHNa6Q4Jz2uvNExL497mE43ikXhwF6kZm',
            'type': 'uncompressed'
        }
    }

    # 保存匹配数据
    # filepath = storage.save_match(match_data)
    # print(f"匹配数据已保存: {filepath}")

    # 查看统计信息
    stats = storage.get_statistics()
    print(f"存储统计: {stats}")

    print()


def example_6_compliance_validator():
    """示例6: 规范合规性验证"""
    print("=" * 60)
    print("示例6: 规范合规性验证")
    print("=" * 60)

    import secrets

    from src.core.address_converter import AddressConverter

    # 创建验证器
    validator = BitcoinComplianceValidator()

    # 创建地址转换器
    converter = AddressConverter()

    # 生成私钥和地址
    private_key = secrets.token_bytes(32)
    result = converter.private_key_to_all(private_key)

    # 构建验证数据
    validation_data = {
        'private_key': private_key,
        'public_key': result['public_key_compressed'],
        'address': result['address_compressed'],
        'wif': result['wif_compressed'],
        'hash160': result['hash160_compressed'],
        'compressed': True
    }

    # 验证合规性
    is_valid, issues = validator.validate(validation_data)

    print(f"合规性验证: {'通过' if is_valid else '失败'}")
    if issues:
        print(f"问题: {issues}")
    else:
        print("所有检查项均通过")

    print()


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("BTC碰撞引擎 - 业务逻辑核心模块示例")
    print("=" * 60 + "\n")

    # 运行所有示例
    try:
        example_1_target_table()
        example_2_key_generator()
        example_3_address_converter()
        example_4_continuous_matcher()
        example_5_match_storage()
        example_6_compliance_validator()

        print("=" * 60)
        print("所有示例运行完成！")
        print("=" * 60)

    except Exception as e:
        print(f"\n运行示例时出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()

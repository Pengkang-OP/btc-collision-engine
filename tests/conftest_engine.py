"""KeyCollisionEngine 测试共享辅助函数 (MAINT-1)"""

from src.core.address_generator import P2PKHAddressGenerator


def get_known_target() -> tuple:
    """获取一个已知私钥对应的地址（用于匹配测试）"""
    # 私钥 = 1
    pk = (1).to_bytes(32, "big")
    gen = P2PKHAddressGenerator()
    addr, _, _ = gen.generate_address(pk)
    return pk, addr

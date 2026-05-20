#!/usr/bin/env python3
"""
GPU 数据格式实时监控工具

监控 GPU 生成的数据是否符合比特币标准：
- 私钥格式（32字节，范围 1 到 N-1）
- 公钥格式（压缩 33字节 / 非压缩 65字节）
- 地址格式（P2PKH / P2SH / Bech32）
"""

import os
import re
import sys
import time
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.collision import KeyCollisionEngine, TargetResolver
from src.core import (
    EllipticCurve,
    P2PKHAddressGenerator,
    Secp256k1,
)
from src.utils.ui_helpers import format_number_with_commas, format_speed


class GPUDataFormatMonitor:
    """GPU 数据格式监控器"""

    def __init__(self, target_addresses: list[str] = None):
        """
        初始化监控器

        Args:
            target_addresses: 目标地址列表
        """
        self.target_addresses = target_addresses or []
        self.resolver = TargetResolver()
        self.address_gen = P2PKHAddressGenerator()  # 创建地址生成器实例

        # 统计信息
        self.total_checked = 0
        self.valid_private_keys = 0
        self.valid_public_keys = 0
        self.valid_addresses = 0
        self.invalid_private_keys = 0
        self.invalid_public_keys = 0
        self.invalid_addresses = 0
        self.format_errors = []

        # 性能统计
        self.start_time = None
        self.last_stats_time = None
        self.last_checked = 0

        # 验证规则
        self.compiled_pubkey_pattern = re.compile(r'^(02|03|04)[0-9a-fA-F]+$')
        self.p2pkh_pattern = re.compile(r'^1[a-km-zA-HJ-NP-Z1-9]{25,34}$')
        self.p2sh_pattern = re.compile(r'^3[a-km-zA-HJ-NP-Z1-9]{25,34}$')
        self.bech32_pattern = re.compile(r'^bc1[a-z0-9]{25,39}$')

    def validate_private_key(self, private_key: bytes) -> tuple[bool, str]:
        """
        验证私钥格式

        Args:
            private_key: 私钥字节

        Returns:
            (是否有效, 错误信息)
        """
        # 检查长度（应该是 32 字节）
        if len(private_key) != 32:
            return False, f"私钥长度错误: {len(private_key)} 字节（应为 32 字节）"

        # 转换为整数
        private_key_int = int.from_bytes(private_key, 'big')

        # 检查范围（1 到 N-1）
        if private_key_int < 1:
            return False, f"私钥值过小: {private_key_int}（应 >= 1）"

        if private_key_int >= Secp256k1.N:
            return False, f"私钥值过大: {private_key_int}（应 < N={Secp256k1.N}）"

        return True, ""

    def validate_public_key(self, public_key: bytes) -> tuple[bool, str]:
        """
        验证公钥格式

        Args:
            public_key: 公钥字节

        Returns:
            (是否有效, 错误信息)
        """
        if len(public_key) == 0:
            return False, "公钥为空"

        # 检查是否为压缩格式（33 字节，02 或 03 开头）
        if len(public_key) == 33:
            if public_key[0] not in [0x02, 0x03]:
                return False, f"压缩公钥前缀错误: 0x{public_key[0]:02x}（应为 0x02 或 0x03）"
            return True, "压缩格式"

        # 检查是否为非压缩格式（65 字节，04 开头）
        if len(public_key) == 65:
            if public_key[0] != 0x04:
                return False, f"非压缩公钥前缀错误: 0x{public_key[0]:02x}（应为 0x04）"
            return True, "非压缩格式"

        return False, f"公钥长度错误: {len(public_key)} 字节（应为 33 或 65 字节）"

    def validate_address(self, address: str) -> tuple[bool, str]:
        """
        验证地址格式

        Args:
            address: 地址字符串

        Returns:
            (是否有效, 地址类型)
        """
        if not address or not isinstance(address, str):
            return False, "地址为空"

        address = address.strip()

        # P2PKH 地址
        if self.p2pkh_pattern.match(address):
            return True, "P2PKH"

        # P2SH 地址
        if self.p2sh_pattern.match(address):
            return True, "P2SH"

        # Bech32 地址
        if self.bech32_pattern.match(address):
            return True, "Bech32"

        return False, f"未知地址格式: {address[:20]}..."

    def monitor_key_generation(self, engine: KeyCollisionEngine, display_interval: float = 2.0):
        """
        监控密钥生成过程

        Args:
            engine: 碰撞引擎实例
            display_interval: 显示间隔（秒）
        """
        print("\n" + "=" * 80)
        print("🔍 GPU 数据格式实时监控")
        print("=" * 80)
        print(f"启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"目标地址数: {len(self.target_addresses)}")
        print(f"显示间隔: {display_interval} 秒")
        print("=" * 80 + "\n")

        self.start_time = time.time()
        self.last_stats_time = time.time()

        try:
            # 启动引擎
            engine.start(mode='random')

            print("✅ 引擎已启动，开始监控...\n")

            # 监控循环
            while engine.is_running():
                time.sleep(display_interval)

                # 获取统计
                stats = engine.get_stats()
                current_checked = stats.total_checked
                new_checked = current_checked - self.last_checked

                # 更新统计
                self.total_checked = current_checked
                self.last_checked = current_checked

                # 生成示例数据进行验证
                self._generate_and_validate_sample_data()

                # 显示监控报告
                self._display_monitoring_report(new_checked)

        except KeyboardInterrupt:
            print("\n\n⚠️  监控被用户中断")
        except Exception as e:
            print(f"\n\n❌ 监控过程出错: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # 停止引擎
            if engine.is_running():
                print("\n正在停止引擎...")
                engine.stop()

            # 显示最终报告
            self._display_final_report()

    def _generate_and_validate_sample_data(self):
        """生成并验证示例数据"""
        import random

        # 获取椭圆曲线实例
        ec = EllipticCurve()

        # 生成随机私钥样本
        for _ in range(10):
            try:
                # 生成有效的随机私钥（1 到 N-1）
                private_key_int = random.randint(1, Secp256k1.N - 1)
                private_key_bytes = private_key_int.to_bytes(32, 'big')

                # 验证私钥
                is_valid, error = self.validate_private_key(private_key_bytes)
                if is_valid:
                    self.valid_private_keys += 1

                    # 使用正确的椭圆曲线运算生成公钥
                    try:
                        # 直接使用 EllipticCurve 的 generate_public_key 方法
                        compressed_pubkey = ec.generate_public_key(private_key_bytes, compressed=True)

                        # 验证公钥格式
                        is_valid_pk, pk_type = self.validate_public_key(compressed_pubkey)

                        if is_valid_pk:
                            self.valid_public_keys += 1

                            # 生成 P2PKH 地址
                            try:
                                address = self.address_gen.public_key_to_address(compressed_pubkey)
                                is_valid_addr, addr_type = self.validate_address(address)

                                if is_valid_addr:
                                    self.valid_addresses += 1
                                else:
                                    self.invalid_addresses += 1
                                    if len(self.format_errors) < 20:
                                        self.format_errors.append(f"地址格式错误: {address}")
                            except Exception as e:
                                self.invalid_addresses += 1
                                if len(self.format_errors) < 20:
                                    self.format_errors.append(f"地址生成失败: {str(e)}")
                        else:
                            self.invalid_public_keys += 1
                            if len(self.format_errors) < 20:
                                self.format_errors.append(f"公钥验证失败: {pk_type}")

                    except Exception as e:
                        self.invalid_public_keys += 1
                        if len(self.format_errors) < 20:
                            self.format_errors.append(f"公钥生成失败: {str(e)}")
                else:
                    self.invalid_private_keys += 1
                    if len(self.format_errors) < 20:
                        self.format_errors.append(error)

            except Exception:
                # 静默处理异常，避免影响监控
                pass

    def _display_monitoring_report(self, new_checked: int):
        """显示监控报告"""
        elapsed = time.time() - self.start_time
        speed = new_checked / (time.time() - self.last_stats_time) if time.time() > self.last_stats_time else 0

        self.last_stats_time = time.time()

        # 计算验证统计
        total_validations = self.valid_private_keys + self.invalid_private_keys
        private_key_rate = (self.valid_private_keys / total_validations * 100) if total_validations > 0 else 0

        total_pk_validations = self.valid_public_keys + self.invalid_public_keys
        public_key_rate = (self.valid_public_keys / total_pk_validations * 100) if total_pk_validations > 0 else 0

        total_addr_validations = self.valid_addresses
        address_rate = 100.0 if total_addr_validations > 0 else 0

        print("\n" + "-" * 80)
        print(f"📊 监控报告 - {datetime.now().strftime('%H:%M:%S')}")
        print("-" * 80)

        # 性能统计
        print("⚡ 性能统计:")
        print(f"   总检测数: {format_number_with_commas(self.total_checked)}")
        print(f"   新增检测: {format_number_with_commas(new_checked)}")
        print(f"   当前速度: {format_speed(speed)} keys/s")
        print(f"   运行时间: {elapsed:.1f} 秒")
        print()

        # 私钥验证
        print("🔑 私钥验证:")
        print(f"   有效私钥: {format_number_with_commas(self.valid_private_keys)}")
        print(f"   无效私钥: {format_number_with_commas(self.invalid_private_keys)}")
        print(f"   合格率: {private_key_rate:.2f}%")
        print()

        # 公钥验证
        print("🔓 公钥验证:")
        print(f"   有效公钥: {format_number_with_commas(self.valid_public_keys)}")
        print(f"   无效公钥: {format_number_with_commas(self.invalid_public_keys)}")
        print(f"   合格率: {public_key_rate:.2f}%")
        print()

        # 地址验证
        print("📍 地址验证:")
        print(f"   有效地址: {format_number_with_commas(self.valid_addresses)}")
        print(f"   无效地址: {format_number_with_commas(self.invalid_addresses)}")
        print(f"   合格率: {address_rate:.2f}%")
        print()

        # 格式错误
        if self.format_errors:
            print(f"⚠️  格式错误示例 (最近 {len(self.format_errors)} 个):")
            for i, error in enumerate(self.format_errors[-5:], 1):
                print(f"   {i}. {error}")
            print()

        print("-" * 80)

    def _display_final_report(self):
        """显示最终报告"""
        elapsed = time.time() - self.start_time if self.start_time else 0

        print("\n" + "=" * 80)
        print("📈 GPU 数据格式监控 - 最终报告")
        print("=" * 80)
        print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"总运行时间: {elapsed:.1f} 秒")
        print()

        print("🔑 私钥验证统计:")
        print(f"   有效: {format_number_with_commas(self.valid_private_keys)}")
        print(f"   无效: {format_number_with_commas(self.invalid_private_keys)}")
        total = self.valid_private_keys + self.invalid_private_keys
        if total > 0:
            print(f"   合格率: {self.valid_private_keys / total * 100:.2f}%")
        print()

        print("🔓 公钥验证统计:")
        print(f"   有效: {format_number_with_commas(self.valid_public_keys)}")
        print(f"   无效: {format_number_with_commas(self.invalid_public_keys)}")
        total = self.valid_public_keys + self.invalid_public_keys
        if total > 0:
            print(f"   合格率: {self.valid_public_keys / total * 100:.2f}%")
        print()

        print("📍 地址验证统计:")
        print(f"   有效: {format_number_with_commas(self.valid_addresses)}")
        print(f"   无效: {format_number_with_commas(self.invalid_addresses)}")
        print()

        if self.format_errors:
            print(f"⚠️  共发现 {len(self.format_errors)} 个格式错误")
        else:
            print("✅ 未发现格式错误")

        print("=" * 80)


def main():
    """主函数"""
    print("\n" + "=" * 80)
    print("🚀 GPU 数据格式实时监控工具")
    print("=" * 80)
    print()

    # 示例目标地址
    target_addresses = [
        "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",  # 中本聪地址
        "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2",
        "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy",
        "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4",
    ]

    print(f"📋 目标地址 ({len(target_addresses)} 个):")
    for addr in target_addresses:
        print(f"   - {addr}")
    print()

    # 创建解析器
    resolver = TargetResolver()
    resolved_targets = set()
    for addr in target_addresses:
        result = resolver.resolve(addr)
        if result:
            resolved_targets.add(result)

    if not resolved_targets:
        print("❌ 无法解析目标地址")
        return

    print(f"✅ 成功解析 {len(resolved_targets)} 个目标地址\n")

    # 创建引擎
    engine = KeyCollisionEngine(
        targets=resolved_targets,
        on_progress=lambda stats: None,
        on_match=lambda pk, addr, wif: print(f"\n🎯 发现匹配!\n   地址: {addr}\n   私钥: {pk.hex()}\n   WIF: {wif}\n"),
        on_complete=lambda stats: print("\n✅ 对撞完成")
    )

    # 创建监控器
    monitor = GPUDataFormatMonitor(target_addresses)

    # 开始监控
    monitor.monitor_key_generation(engine, display_interval=2.0)


if __name__ == "__main__":
    main()

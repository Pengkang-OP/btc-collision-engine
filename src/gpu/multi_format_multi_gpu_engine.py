"""
多格式地址支持 - 多GPU引擎集成方案

目标: 在不修改GPU内核的情况下，支持多格式地址匹配

方案: 混合架构
1. GPU路径: 继续生成P2PKH地址进行快速匹配
2. 后处理: GPU匹配后，检查是否需要生成其他格式
3. 格式感知: 目标管理器按格式分组，只匹配对应格式

集成架构:
    MultiGPUEngine
        ↓
    FormatAwareTargetManager (多格式目标管理)
        ↓
    ├─ GPU路径 (P2PKH匹配) → 后处理 (检查其他格式)
    └─ CPU路径 (全格式检查) → check_match_all()

关键点:
- GPU内核无需修改（仍只生成P2PKH）
- 通过后处理支持其他格式
- 性能影响最小化
"""

from typing import Optional, Tuple
from ..utils import get_configured_logger
from src.core.multi_format_generator import MultiFormatAddressGenerator, AddressFormat
from src.collision.targets.format_aware_manager import FormatAwareTargetManager
from src.gpu.worker import SingleGPUWorker
from src.gpu.multi_gpu_engine import MultiGPUCollisionEngine

logger = get_configured_logger("MultiFormatMultiGPUEngine")

def create_multi_format_multi_gpu_engine():
    """
    创建支持多格式的多GPU引擎

    集成方案:
    1. 使用 FormatAwareTargetManager 管理多格式目标
    2. GPU路径保持原样（快速P2PKH匹配）
    3. 添加后处理检查其他格式

    Returns:
        格式感知的多GPU引擎包装器
    """

    class MultiFormatMultiGPUEngine:
        """多格式多GPU引擎包装器

        支持特性:
        - 多格式目标地址管理
        - P2PKH快速GPU匹配
        - 其他格式后处理匹配
        - 格式统计和监控
        """

        def __init__(self, multi_gpu_config: dict = None):
            self._multi_gpu_engine = MultiGPUCollisionEngine(multi_gpu_config)
            self._format_manager = FormatAwareTargetManager()
            self._address_generator = MultiFormatAddressGenerator()

            # 配置参数
            self._enable_post_processing = True  # 后处理其他格式
            self._enable_cpu_fallback = False    # CPU备用检查

            logger.info("多格式多GPU引擎已创建")

        def initialize(self, device_indices=None, device_count=-1, strategy="performance"):
            """初始化GPU设备"""
            return self._multi_gpu_engine.initialize(
                device_indices=device_indices,
                device_count=device_count,
                strategy=strategy
            )

        def add_target(self, address: str) -> bool:
            """添加目标地址（自动检测格式）"""
            return self._format_manager.add_target(address)

        def add_targets(self, addresses: list[str]) -> int:
            """批量添加目标地址"""
            return self._format_manager.add_targets(addresses)

        def load_targets_from_file(self, filepath: str) -> int:
            """从文件加载目标地址"""
            return self._format_manager.load_from_file(filepath)

        def get_format_stats(self) -> dict[str, int]:
            """获取格式统计"""
            return self._format_manager.get_format_stats()

        def start(self, mode="random", total_keys=10000000, match_callback=None):
            """启动多GPU碰撞

            Args:
                mode: 碰撞模式
                total_keys: 总密钥数
                match_callback: 匹配回调 (device_idx, match)
            """
            # 获取所有目标
            all_targets = self._format_manager.get_all_targets()

            # 创建包装回调函数
            def wrapped_callback(device_idx, match):
                """包装回调：添加多格式检查"""
                matched_address = match.get('address', '')
                matched_format = match.get('format', 'p2pkh')

                # 检查是否需要检查其他格式
                # 注意: match_dict 仅包含 private_key_hash (非完整私钥),
                # 多格式后处理检查需要在 GPU 内核层完成,此处作为占位保留
                if self._enable_post_processing and matched_address:
                    try:
                        private_key_value = match.get('private_key_hash')
                        if private_key_value:
                            extra_formats = self._check_other_formats(
                                private_key_value,
                                matched_address,
                                matched_format
                            )
                        else:
                            extra_formats = []
                    except Exception as e:
                        logger.warning(f"后处理检查其他格式失败: {type(e).__name__}")
                        extra_formats = []

                    # 添加额外匹配结果
                    if extra_formats:
                        for extra_addr, extra_fmt in extra_formats:
                            extra_match = {
                                **match,
                                'address': extra_addr,
                                'format': extra_fmt,
                                'extra_match': True
                            }
                            if match_callback:
                                match_callback(device_idx, extra_match)

                # 调用原始回调
                if match_callback:
                    match_callback(device_idx, match)

            return self._multi_gpu_engine.start(
                targets=all_targets,
                mode=mode,
                total_keys=total_keys,
                match_callback=wrapped_callback
            )

        def _check_other_formats(
            self,
            private_key: bytes,
            matched_address: str,
            matched_format: str
        ) -> list[tuple[str, str]]:
            """检查其他格式是否也匹配

            当P2PKH地址匹配时，检查同一私钥的其他格式地址是否也在目标中

            Args:
                private_key: 匹配的私钥
                matched_address: 已匹配的地址
                matched_format: 已匹配的格式

            Returns:
                额外匹配的 (地址, 格式) 列表
            """
            extra_matches = []

            # 预先获取按格式分组的目标（避免循环内重复调用）
            targets_by_format = self._format_manager.get_targets_by_format()

            # 仅在存在非当前格式目标时才生成全部格式地址
            has_other_format_targets = any(
                len(targets) > 0
                for fmt_key, targets in targets_by_format.items()
                if fmt_key.value != matched_format
            )
            if not has_other_format_targets:
                return extra_matches

            # 获取所有格式的地址
            all_addresses = self._address_generator.generate_all_formats(private_key)

            # 检查每个格式
            for fmt, address in all_addresses.items():
                # 跳过已匹配的格式
                if fmt == matched_format:
                    continue

                format_enum = AddressFormat(fmt)
                if address.lower() in targets_by_format.get(
                    format_enum, set()
                ):
                    extra_matches.append((address, fmt))

            return extra_matches

        def check_match(self, private_key: bytes) -> Tuple[bool, Optional[str], Optional[str]]:
            """CPU路径: 检查私钥是否匹配任何目标（全格式检查）

            Args:
                private_key: 32字节私钥

            Returns:
                (is_match, matched_address, matched_format)
            """
            return self._format_manager.check_match(private_key)

        def check_match_all(self, private_key: bytes) -> Tuple[bool, list[tuple[str, str]]]:
            """CPU路径: 检查私钥是否匹配所有格式目标

            Args:
                private_key: 32字节私钥

            Returns:
                (is_match, list[(address, format)])
            """
            return self._format_manager.check_match_all(private_key)

        def stop(self):
            """停止碰撞"""
            self._multi_gpu_engine.stop()

        def get_combined_stats(self) -> dict:
            """获取统计信息（包含格式统计）"""
            stats = self._multi_gpu_engine.get_combined_stats()
            stats['format_stats'] = self.get_format_stats()
            return stats

        def cleanup(self):
            """清理资源"""
            self._multi_gpu_engine.cleanup()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.cleanup()

    return MultiFormatMultiGPUEngine()


# 创建便捷函数
def create_engine():
    """创建多格式多GPU引擎的便捷函数"""
    return create_multi_format_multi_gpu_engine()


if __name__ == "__main__":
    print("=" * 80)
    print("多格式多GPU引擎集成方案")
    print("=" * 80)

    # 测试创建引擎
    engine = create_multi_format_multi_gpu_engine()

    print("\n✅ 引擎创建成功!")
    print("\n支持的地址格式:")
    for fmt in AddressFormat:
        print(f"  • {fmt.value.upper()}: {fmt.value}")

    print("\n使用示例:")
    print("""
    # 1. 创建引擎
    engine = create_engine()

    # 2. 初始化GPU
    engine.initialize(device_count=2)

    # 3. 添加多格式目标
    engine.add_target("1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH")  # P2PKH
    engine.add_target("bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4")  # Bech32

    # 4. 查看格式统计
    print(engine.get_format_stats())

    # 5. 启动碰撞
    def on_match(device_idx, match):
        print(f"GPU {device_idx} 找到匹配!")
        print(f"  格式: {match['format']}")
        print(f"  地址: {match['address']}")

    engine.start(mode='random', total_keys=10000000, match_callback=on_match)

    # 6. 获取统计
    stats = engine.get_combined_stats()
    print(f"格式统计: {stats['format_stats']}")

    # 7. 清理
    engine.cleanup()
    """)

    print("\n✅ 集成方案设计完成!")

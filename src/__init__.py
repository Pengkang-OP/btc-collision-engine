"""比特币私钥对撞工具包"""

__version__ = "4.4.0"  # v4.4.0: 安全修复增强(安全清零/侧信道防护/敏感数据脱敏/线程安全), 文档一致性整理
__author__ = "BTC Collision Team"

# 多格式地址支持模块（v4.3.0 新增）
from .collision.targets.format_aware_manager import FormatAwareTargetManager
from .core.multi_format_generator import AddressFormat, MultiFormatAddressGenerator
from .gpu.multi_format_multi_gpu_engine import create_engine, create_multi_format_multi_gpu_engine

__all__ = [
    "MultiFormatAddressGenerator",
    "AddressFormat",
    "FormatAwareTargetManager",
    "create_engine",
    "create_multi_format_multi_gpu_engine",
]

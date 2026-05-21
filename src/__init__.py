"""比特币私钥对撞工具包"""

__version__ = "4.5.1"  # v4.5.1: 全面审核修复：死代码清理、线程安全增强、配置对齐、文档修正
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

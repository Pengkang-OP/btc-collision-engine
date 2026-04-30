"""目标地址管理模块

提供完整的比特币地址管理功能:
- 地址解析和格式检测 (resolver)
- 地址缓存管理 (cache)
- 批量地址验证 (validator)
- 高效地址匹配 (matcher)
- 地址持久化存储 (storage)

示例:
    >>> from src.collision.targets import TargetResolver, AddressMatcher
    >>> resolver = TargetResolver(enable_cache=True)
    >>> address = resolver.resolve('5KJvsngHeMpm884wtkJNzQGaCErckhHJBGFsvd3VyK5qMZXj3hS')
    >>> matcher = AddressMatcher(strategy='hash_set', targets={address})
"""

from .resolver import TargetResolver
from .cache import AddressCache
from .validator import AddressBatchValidator, ValidationResult
from .matcher import AddressMatcher
from .storage import AddressStorage

__all__ = [
    "TargetResolver",
    "AddressCache",
    "AddressBatchValidator",
    "ValidationResult",
    "AddressMatcher",
    "AddressStorage",
]

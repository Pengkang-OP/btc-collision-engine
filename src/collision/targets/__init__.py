"""目标地址管理模块

提供完整的比特币地址管理功能:
- 地址解析和格式检测 (resolver)
- 地址缓存管理 (cache)
- 批量地址验证 (validator)
- 高效地址匹配 (matcher)
- 地址持久化存储 (storage)

Example:
    >>> from src.collision.targets import TargetResolver, AddressMatcher
    >>> resolver = TargetResolver(enable_cache=True)
    >>> address = resolver.resolve('1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa')
    >>> matcher = AddressMatcher(strategy='hash_set', targets={address})

"""

from .cache import AddressCache
from .matcher import AddressMatcher
from .resolver import TargetResolver
from .storage import AddressStorage
from .validator import AddressBatchValidator, ValidationResult

__all__ = [
    "AddressBatchValidator",
    "AddressCache",
    "AddressMatcher",
    "AddressStorage",
    "TargetResolver",
    "ValidationResult",
]

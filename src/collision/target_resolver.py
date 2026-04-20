"""目标地址解析器 - 向后兼容模块

⚠️  弃用警告: 此模块已迁移到 targets.resolver,请使用新路径。

📅 移除计划:
    - 此模块将在 v2.0 版本中移除（计划时间: 2026-Q3）
    - 建议所有用户尽快迁移到新路径
    - 迁移后可消除 DeprecationWarning

✅ 新用法（推荐）:
    from src.collision.targets.resolver import TargetResolver
    # 或
    from src.collision import TargetResolver
    # 或
    from src.collision.targets import TargetResolver

❌ 旧用法（已弃用，将在v2.0移除）:
    from src.collision.target_resolver import TargetResolver

📚 迁移指南:
    1. 搜索代码中所有使用旧路径的地方
    2. 替换为新的导入路径（推荐第一种新用法）
    3. 运行测试验证功能正常
    4. 确认不再有 DeprecationWarning

📖 相关文档:
    - docs/import-path-optimization-report.md
    - docs/bech32-p2sh-support.md
"""
import warnings

# 发出弃用警告
warnings.warn(
    "target_resolver已迁移到targets.resolver,请使用 'from src.collision.targets.resolver import TargetResolver'",
    DeprecationWarning,
    stacklevel=2
)

# 从新模块导入
from .targets.resolver import TargetResolver

__all__ = ['TargetResolver']

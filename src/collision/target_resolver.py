"""目标地址解析器 - 向后兼容模块

⚠️  DEPRECATION WARNING (弃用警告): 此模块已迁移到 targets.resolver

================================================================================
迁移时间表 (Migration Timeline):
--------------------------------------------------------------------------------
  ⚠️  v4.2.1–v4.5.x: 发出 DeprecationWarning（当前状态）
  📅  v5.0.0: 计划移除此模块
  ⚠️  移除后: 旧导入路径将导致 ImportError
  📋  跟踪: 在 GitHub Issues 中搜索标签 'deprecation/target-resolver'
================================================================================

✅ 推荐的新导入方式（按优先级排序）:
--------------------------------------------------------------------------------
    # 方式1: 直接导入（推荐）
    from src.collision.targets.resolver import TargetResolver

    # 方式2: 通过 collision 包导入
    from src.collision import TargetResolver

    # 方式3: 通过 targets 子包导入
    from src.collision.targets import TargetResolver

❌ 旧导入方式（已弃用）:
--------------------------------------------------------------------------------
    from src.collision.target_resolver import TargetResolver  # ⚠️ 将在2026-Q3移除

📋 迁移步骤 (Migration Steps):
--------------------------------------------------------------------------------
    1. 在代码库中搜索: "from src.collision.target_resolver"
    2. 替换为: "from src.collision.targets.resolver import TargetResolver"
    3. 运行测试套件验证功能正常
    4. 确认不再有 DeprecationWarning 输出

🔧 迁移工具:
--------------------------------------------------------------------------------
    项目提供了迁移辅助脚本:
    $ python scripts/check_import_paths.py --fix target_resolver

📖 相关文档:
--------------------------------------------------------------------------------
    - docs/address-import-feature.md
    - docs/architecture_separation_design.md
"""

import warnings

warnings.warn(
    """
    ================================================================
    DEPRECATION WARNING: 'src.collision.target_resolver' 已弃用
    ================================================================
    此模块已迁移到 'src.collision.targets.resolver'

    迁移建议:
    - 将: from src.collision.target_resolver import TargetResolver
    - 替换为: from src.collision.targets.resolver import TargetResolver

    移除时间线:
    - 当前版本 v4.x: 发出警告
    - 计划移除: v5.0.0
    - 跟踪标签: 'deprecation/target-resolver'

    迁移辅助: python scripts/check_import_paths.py --fix target_resolver
    ================================================================
    """,
    DeprecationWarning,
    stacklevel=2,
)

from .targets.resolver import TargetResolver  # noqa: E402

__all__ = ["TargetResolver"]

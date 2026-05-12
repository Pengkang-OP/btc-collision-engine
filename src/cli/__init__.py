"""比特币私钥对撞工具 - 命令行界面"""

# 核心API
# 高级功能
from src.cli.advanced_features import (
    GPUErrorHandler,
    apply_template,
    export_matches,
    export_progress_data,
    recommend_parameters,
)

# 配置迁移
from src.cli.config_migration import migrate_config_file

# 引擎构建
from src.cli.engine_builder import GPU_AVAILABLE, build_engine, on_match_callback
from src.cli.main import load_targets, main, parse_args
from src.cli.progress import format_progress

# 验证和进度
from src.cli.validation import validate_args, validate_file_path

__all__ = [
    # 核心
    "main",
    "parse_args",
    "load_targets",
    # 验证
    "validate_args",
    "validate_file_path",
    # 进度
    "format_progress",
    # 引擎
    "build_engine",
    "on_match_callback",
    "GPU_AVAILABLE",
    # 高级功能
    "apply_template",
    "recommend_parameters",
    "export_progress_data",
    "export_matches",
    "GPUErrorHandler",
    # 配置迁移
    "migrate_config_file",
]

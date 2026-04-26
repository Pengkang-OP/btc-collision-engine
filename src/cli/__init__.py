"""比特币私钥对撞工具 - 命令行界面"""

# 核心API
from src.cli.main import main, parse_args, load_targets

# 验证和进度
from src.cli.validation import validate_args, validate_file_path
from src.cli.progress import format_progress

# 引擎构建
from src.cli.engine_builder import build_engine, on_match_callback, GPU_AVAILABLE

# 高级功能
from src.cli.advanced_features import (
    apply_template,
    recommend_parameters,
    export_progress_data,
    export_matches,
    GPUErrorHandler,
)

# 配置迁移
from src.cli.config_migration import migrate_config_file

__all__ = [
    # 核心
    'main', 'parse_args', 'load_targets',
    # 验证
    'validate_args', 'validate_file_path',
    # 进度
    'format_progress',
    # 引擎
    'build_engine', 'on_match_callback', 'GPU_AVAILABLE',
    # 高级功能
    'apply_template', 'recommend_parameters',
    'export_progress_data', 'export_matches', 'GPUErrorHandler',
    # 配置迁移
    'migrate_config_file',
]

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CLI常量定义"""

# 进度条配置
PROGRESS_BAR_LENGTH: int = 20
PROGRESS_BAR_FILLED: str = "█"
PROGRESS_BAR_EMPTY: str = "░"

# 数值单位阈值
UNIT_BILLION: int = 1_000_000_000
UNIT_MILLION: int = 1_000_000
UNIT_THOUSAND: int = 1_000

# 标签前缀
TAG_ERROR: str = "[Error]"
TAG_TIP: str = "[Tip]"
TAG_INFO: str = "[Info]"
TAG_OK: str = "[OK]"
TAG_WARN: str = "[Warn]"

# 配置段名称
REQUIRED_CONFIG_SECTIONS: list = ["crypto", "collision", "logging"]
REQUIRED_DIRECTORIES: list = ["logs", "data_logs"]

# 默认值
DEFAULT_CHECKPOINT_INTERVAL: int = 30
DEFAULT_DEDUP_MAX_SIZE: int = 1_000_000
DEFAULT_PROGRESS_INTERVAL: float = 5.0
DEFAULT_WINDOW_SIZE: int = 8
DEFAULT_GPU_DEVICE: int = -1
DEFAULT_GPU_COUNT: int = -1

# 分界线常量
# DEPRECATED: 以下常量已被 CLIOutput.rule() / CLIOutput.header() 替代，保留以避免外部引用报错
SEPARATOR_EQUAL: str = "=" * 70
SEPARATOR_DASHED: str = "-" * 70
SEPARATOR_DASHED_SHORT: str = "-" * 60

# 时间阈值
INIT_CHECK_THRESHOLD: int = 15
ETA_MINUTE_THRESHOLD: int = 60
ETA_HOUR_THRESHOLD: int = 3600

# 文件路径常量
CONFIG_FILE_NAME: str = "config.json"
CONFIG_EXAMPLE_FILE: str = "config.example.json"
WIZARD_MARKER_PATH: str = "data_logs/.wizard_completed"

# 私钥输出模式
SENSITIVE_OUTPUT_MODE: str = "full"  # "full", "masked", "hash_only"

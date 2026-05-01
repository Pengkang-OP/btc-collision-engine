# -*- coding: utf-8 -*-
"""GPU碰撞引擎配置管理器

CODE-1修复: 从gpu_collision_engine.py提取配置管理逻辑，降低主类复杂度。
负责GPU配置读取、合并、验证和应用。
"""

import logging
import json
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

logger = logging.getLogger(__name__)


class GPUConfigManager:
    """GPU配置管理器

    职责:
    1. 读取配置（构造函数参数 > 配置文件 > 默认值）
    2. 合并配置（AutoConfig + ProfileLoader）
    3. 验证配置有效性
    4. 应用配置到GPU设备

    设计模式: 策略模式 + 责任链模式
    """

    def __init__(self) -> None:
        """初始化配置管理器"""
        self._config_cache: Dict[str, Any] = {}
        logger.debug("GPUConfigManager已初始化")

    def read_async_config(
        self,
        constructor_config: Optional[Dict[str, Any]] = None,
        config_files: Optional[List[Path]] = None,
    ) -> Tuple[bool, str]:
        """读取异步执行配置（按优先级）

        CODE-3修复: 添加完整类型注解

        Args:
            constructor_config: 构造函数传入的配置
            config_files: 配置文件路径列表

        Returns:
            (enable_async: bool, config_source: str) 元组
        """
        enable_async = False
        config_source = "默认"

        # 记录配置读取优先级
        logger.debug("配置读取优先级: 1.构造函数参数 > 2.配置文件 > 3.默认值")

        # 优先级1: 构造函数传入的配置
        if constructor_config:
            gpu_config = constructor_config.get("gpu", {})
            if "async_execution" in gpu_config:
                enable_async = gpu_config["async_execution"]
                config_source = "构造参数"
                logger.info(f"✅ 从构造参数读取异步设置: {enable_async} (优先级1)")
                return enable_async, config_source

        # 优先级2: 自动读取配置文件
        if config_files is None:
            # 默认配置文件路径
            project_root = Path(__file__).parent.parent.parent
            config_files = [
                project_root / "config.intel_arc.json",
                project_root / "config.json",
            ]

        for cfg_file in config_files:
            if cfg_file.exists():
                try:
                    with open(cfg_file, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                        if cfg.get("gpu", {}).get("async_execution", False):
                            enable_async = True
                            config_source = f"配置文件 {cfg_file.name}"
                            logger.info(f"✅ 从{config_source}读取异步设置 (优先级2)")
                            return enable_async, config_source
                except json.JSONDecodeError as e:
                    logger.warning(f"配置文件 {cfg_file} JSON格式错误: {e}")
                except PermissionError:
                    logger.warning(f"无法读取 {cfg_file}: 权限不足")
                except Exception as e:
                    logger.debug(f"读取配置文件 {cfg_file} 失败(非关键): {e}")

        # 优先级3: 默认值（已在performance_optimizer中设置为True）
        logger.debug(f"使用默认异步设置: {enable_async} (优先级3)")
        return enable_async, config_source

    def merge_gpu_configs(
        self, auto_config: Dict[str, Any], profile_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """合并AutoConfig和ProfileLoader的配置

        CODE-3修复: 添加完整类型注解

        Args:
            auto_config: GPUAutoConfigurator生成的配置
            profile_config: GPUProfileLoader加载的配置（可选）

        Returns:
            合并后的配置字典
        """
        merged = auto_config.copy()

        if profile_config:
            # ProfileLoader的配置覆盖AutoConfig
            for key in [
                "batch_size",
                "work_group_size",
                "memory_usage_ratio",
                "enable_async",
                "use_uint32_workaround",
            ]:
                if key in profile_config:
                    value = profile_config[key]
                    # 验证值的有效性
                    if self._validate_config_value(key, value):
                        merged[key] = value
                        logger.debug(f"配置覆盖: {key} = {value}")
                    else:
                        logger.warning(f"配置值无效: {key}={value}，使用默认值")

        # 验证合并后的配置
        self._validate_merged_config(merged)

        logger.info(
            "GPU配置合并完成: "
            f"batch_size={merged.get('batch_size', 'N/A')}, "
            f"work_group={merged.get('work_group_size', 'N/A')}, "
            f"mem_ratio={merged.get('memory_usage_ratio', 'N/A')}"
        )
        return merged

    def _validate_config_value(self, key: str, value: Any) -> bool:
        """验证配置值的有效性

        CODE-3修复: 添加完整类型注解

        Args:
            key: 配置键名
            value: 配置值

        Returns:
            是否有效
        """
        if key == "batch_size":
            # P1-2: batch_size must be < UINT32_MAX to prevent GPU gid overflow
            from .gpu_collision_engine import GPU_MAX_BATCH_SIZE

            return isinstance(value, int) and 1024 <= value < GPU_MAX_BATCH_SIZE
        elif key == "work_group_size":
            return isinstance(value, int) and 64 <= value <= 2048
        elif key == "memory_usage_ratio":
            return isinstance(value, (int, float)) and 0 < value <= 1.0
        elif key in ["enable_async", "use_uint32_workaround", "use_fast_math"]:
            return isinstance(value, bool)
        return True

    def _validate_merged_config(self, config: Dict[str, Any]) -> None:
        """验证合并后的配置

        CODE-3修复: 添加完整类型注解（返回None）

        Args:
            config: 合并后的配置字典
        """
        if "batch_size" in config:
            batch_size = config["batch_size"]
            if batch_size is not None:
                if batch_size < 1024:
                    logger.warning(f"batch_size过小({batch_size})，可能导致性能差")
                elif batch_size >= 33554432:
                    # P1-2: 超过33M可能显存不足（上限为UINT32_MAX）
                    logger.warning(f"batch_size过大({batch_size})，可能导致显存不足")

        if "memory_usage_ratio" in config:
            ratio = config["memory_usage_ratio"]
            if ratio is not None:
                if ratio > 0.85:
                    logger.warning(f"显存使用率过高({ratio:.0%})，可能导致不稳定")
                elif ratio < 0.3:
                    logger.warning(f"显存使用率过低({ratio:.0%})，性能可能不佳")

    def get_config_summary(self, config: Dict[str, Any]) -> str:
        """获取配置摘要信息

        CODE-3修复: 添加完整类型注解

        Args:
            config: 配置字典

        Returns:
            配置摘要字符串
        """
        return (
            "GPU配置摘要:\n"
            f"  - batch_size: {config.get('batch_size', 'N/A')}\n"
            f"  - work_group_size: {config.get('work_group_size', 'N/A')}\n"
            f"  - memory_usage_ratio: {config.get('memory_usage_ratio', 'N/A')}\n"
            f"  - enable_async: {config.get('enable_async', False)}\n"
            f"  - use_uint32_workaround: {config.get('use_uint32_workaround', False)}\n"
            f"  - use_fast_math: {config.get('use_fast_math', False)}"
        )

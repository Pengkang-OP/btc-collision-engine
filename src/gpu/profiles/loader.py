"""GPU型号数据库加载器.

负责加载和管理GPU型号配置数据库。
"""

import json
import os
import pathlib
from typing import Any

# 统一日志获取
from src.utils import get_configured_logger

logger = get_configured_logger("GPUProfileLoader")


class GPUProfileLoader:
    """GPU型号配置加载器."""

    __slots__ = ("profile_file", "profiles")

    def __init__(self, profile_file: str | None = None) -> None:
        """初始化加载器.

        Args:
            profile_file: JSON配置文件路径,None则使用默认路径

        """
        if profile_file is None:
            # 使用当前文件同目录下的gpu_profiles.json
            profile_file = os.path.join(os.path.dirname(__file__), "gpu_profiles.json")

        self.profile_file = profile_file
        self.profiles: dict[str, Any] = {}
        self._load_profiles()

    def _load_profiles(self) -> None:
        """加载JSON配置文件."""
        try:
            if not pathlib.Path(self.profile_file).exists():
                logger.warning(f"GPU配置文件不存在: {self.profile_file}")
                self.profiles = {}
                return

            with pathlib.Path(self.profile_file).open(encoding="utf-8") as f:
                data = json.load(f)

            # 版本检查
            version = data.get("_version", "1.0")
            if version != "1.0":
                logger.warning(
                    "不支持的配置文件版本: %s, 当前支持1.0。可能导致配置加载错误",
                    version,
                )

            self.profiles = data

            vendor_count = len([k for k in self.profiles if not k.startswith("_")])
            logger.info("GPU型号数据库加载成功: %s 个厂商 (版本 %s)", vendor_count, version)

        except json.JSONDecodeError as e:
            logger.error("GPU配置文件JSON格式错误: %s", e)
            self.profiles = {}
        except Exception as e:
            logger.error("加载GPU配置文件失败: %s", e)
            self.profiles = {}

    def get_profile(self, vendor: str, model_name: str) -> dict[str, Any] | None:
        """根据厂商和型号获取配置.

        Args:
            vendor: 厂商名称(nvidia/amd/intel)
            model_name: GPU型号名称(如"RTX 3080")

        Returns:
            配置字典,如果未找到则返回None

        """
        vendor = vendor.lower()

        if vendor not in self.profiles:
            logger.debug("未知厂商: %s", vendor)
            return None

        vendor_data = self.profiles[vendor]

        # 遍历所有架构世代,查找匹配的型号
        for arch_name, arch_data in vendor_data.items():
            # 跳过元数据字段和default配置
            if arch_name.startswith("_") or arch_name == "default":
                continue

            # 确保arch_data是字典（架构层级）
            if not isinstance(arch_data, dict):
                logger.warning(
                    f"跳过无效的架构配置 {vendor}/{arch_name}: 期望dict, 得到{type(arch_data).__name__}",
                )
                continue

            # 遍历该架构下的所有系列
            for series_name, series_data in arch_data.items():
                if series_name.startswith("_"):
                    continue

                # 确保series_data是字典
                if not isinstance(series_data, dict):
                    _type_name = type(series_data).__name__
                    logger.warning(
                        "跳过无效系列配置 %s/%s/%s: 期望dict, 得%s",
                        vendor,
                        arch_name,
                        series_name,
                        _type_name,
                    )
                    continue

                # 验证配置合法性
                if not self._validate_profile(series_data, f"{vendor}/{arch_name}/{series_name}"):
                    logger.warning("配置验证失败: %s/%s/%s", vendor, arch_name, series_name)
                    continue

                # 检查型号是否在列表中
                models = series_data.get("models", [])
                if self._match_model(model_name, models):
                    logger.info(
                        "匹配GPU型号: %s -> %s/%s/%s",
                        model_name,
                        vendor,
                        arch_name,
                        series_name,
                    )
                    return series_data

        # 未找到具体型号,返回厂商默认配置
        logger.warning("未找到型号 %s 的配置,使用厂商默认配置", model_name)
        return self.get_default_profile(vendor)

    def _match_model(self, model_name: str, model_list: list[str]) -> bool:
        """模糊匹配型号名称.

        Args:
            model_name: 要匹配的型号名称
            model_list: 型号列表

        Returns:
            是否匹配成功

        """
        model_lower = model_name.lower()

        for candidate in model_list:
            candidate_lower = candidate.lower()

            # 完全匹配
            if model_lower == candidate_lower:
                return True

            # 包含匹配(避免误匹配,要求至少包含主要关键词)
            if model_lower in candidate_lower or candidate_lower in model_lower:
                return True

            # 部分匹配(提取关键部分,如"RTX 3080"匹配"GeForce RTX 3080")
            # 移除常见前缀
            cleaned_model = self._clean_model_name(model_lower)
            cleaned_candidate = self._clean_model_name(candidate_lower)

            if cleaned_model in cleaned_candidate or cleaned_candidate in cleaned_model:
                return True

        return False

    # ---- 合法优化项枚举 ----
    _VALID_OPTIMIZATIONS: set[str] = {
        "async_transfer",
        "persistent_buffers",
        "shared_memory_optimization",
        "uint32_workaround",
        "timeout_protection",
        "conservative_memory",
        "memory_coalescing",
        "hbm_optimization",
        "compute_unit_optimization",
        "infinity_cache",
        "chiplet_architecture",
        "large_page_support",
        "shader_execution_reordering",
        "pro_driver_optimization",
        "tensor_core_ready",
    }

    # ---- 合法已知问题枚举 ----
    _VALID_KNOWN_ISSUES: set[str] = {
        "global_char_hang_bug",
    }

    # ---- 驱动版本正则 (major.minor[.patch[.build]]) ----
    # NVIDIA: X.Y (450.00); AMD/Intel: X.Y.Z[.W] (31.0.101.0)
    _DRIVER_VERSION_RE = r"^\d+\.\d+(?:\.\d+){0,2}$"

    @staticmethod
    def _validate_profile_models(profile: dict[str, Any], errors: list[str]) -> None:
        """验证 models 字段."""
        if not isinstance(profile["models"], list):
            errors.append("models必须为列表")
        elif len(profile["models"]) == 0:
            errors.append("models列表不能为空")
        elif not all(isinstance(m, str) for m in profile["models"]):
            errors.append("models列表中的元素必须为字符串")

    @staticmethod
    def _validate_profile_batch_sizes(profile: dict[str, Any], errors: list[str]) -> None:
        """验证 batch_size 字段."""
        for key in ["recommended_batch_size", "max_batch_size"]:
            value = profile[key]
            if not isinstance(value, (int, float)):
                errors.append(f"{key}类型错误: 期望int/float, 得到{type(value).__name__}")
            elif value <= 0:
                errors.append(f"{key}必须为正数")

        rec_batch = profile.get("recommended_batch_size")
        max_batch = profile.get("max_batch_size")
        if (
            isinstance(rec_batch, (int, float))
            and isinstance(max_batch, (int, float))
            and max_batch < rec_batch
        ):
            errors.append(f"max_batch_size ({max_batch}) < recommended_batch_size ({rec_batch})")

    def _validate_profile_optimizations(
        self,
        profile: dict[str, Any],
        errors: list[str],
        warnings: list[str],
    ) -> None:
        """验证 optimizations 字段（如果存在）."""
        if "optimizations" not in profile:
            return
        if not isinstance(profile["optimizations"], list):
            errors.append("optimizations必须为列表")
            return
        if not all(isinstance(opt, str) for opt in profile["optimizations"]):
            errors.append("optimizations列表中的元素必须为字符串")
            return

        invalid_opts = set(profile["optimizations"]) - self._VALID_OPTIMIZATIONS
        if invalid_opts:
            warnings.append(f"未知的优化项: {invalid_opts}")

    @staticmethod
    def _validate_profile_optional_fields(
        profile: dict[str, Any],
        errors: list[str],
        warnings: list[str],
    ) -> None:
        """验证可选字段：compute_capability, memory_efficiency."""
        if "compute_capability" in profile:
            cc = profile["compute_capability"]
            if not isinstance(cc, (str, int, float)):
                errors.append(
                    f"compute_capability类型错误: 期望str/int/float, 得到{type(cc).__name__}",
                )

        if "memory_efficiency" in profile:
            eff = profile["memory_efficiency"]
            if not isinstance(eff, (int, float)):
                errors.append(f"memory_efficiency类型错误: 期望int/float, 得到{type(eff).__name__}")
            elif not (0.0 < eff <= 1.0):
                warnings.append(f"memory_efficiency ({eff}) 不在合理范围 (0.0, 1.0]")

    @staticmethod
    def _validate_profile_queue_depth(
        profile: dict[str, Any],
        errors: list[str],
    ) -> None:
        """验证 queue_depth 可选字段."""
        if "queue_depth" not in profile:
            return
        qd = profile["queue_depth"]
        if not isinstance(qd, int) or isinstance(qd, bool):
            errors.append(f"queue_depth类型错误: 期望int, 得到{type(qd).__name__}")
        elif not (1 <= qd <= 64):
            errors.append(f"queue_depth ({qd}) 超出合理范围 [1, 64]")

    @staticmethod
    def _validate_profile_timeout(
        profile: dict[str, Any],
        errors: list[str],
    ) -> None:
        """验证 timeout_seconds 可选字段."""
        if "timeout_seconds" not in profile:
            return
        ts = profile["timeout_seconds"]
        if not isinstance(ts, (int, float)) or isinstance(ts, bool):
            errors.append(f"timeout_seconds类型错误: 期望int/float, 得到{type(ts).__name__}")
        elif ts <= 0:
            errors.append(f"timeout_seconds ({ts}) 必须为正数")

    @staticmethod
    def _validate_profile_known_issues(
        profile: dict[str, Any],
        errors: list[str],
        warnings: list[str],
    ) -> None:
        """验证 known_issues 可选字段."""
        if "known_issues" not in profile:
            return
        ki = profile["known_issues"]
        if not isinstance(ki, list):
            errors.append(f"known_issues类型错误: 期望list, 得到{type(ki).__name__}")
            return
        if not all(isinstance(issue, str) for issue in ki):
            errors.append("known_issues列表中的元素必须为字符串")
            return

        invalid_issues = set(ki) - GPUProfileLoader._VALID_KNOWN_ISSUES
        if invalid_issues:
            warnings.append(f"未知的已知问题: {invalid_issues}")

    @staticmethod
    def _validate_profile_driver_versions(
        profile: dict[str, Any],
        errors: list[str],
        warnings: list[str],
    ) -> None:
        """验证 min_driver_version / recommended_driver_version 可选字段."""
        import re

        def _check_drv(key: str) -> str | None:
            value = profile.get(key)
            if value is None:
                return None
            if not isinstance(value, str):
                errors.append(f"{key}类型错误: 期望str, 得到{type(value).__name__}")
                return None
            if not re.match(GPUProfileLoader._DRIVER_VERSION_RE, value):
                errors.append(
                    f"{key}格式无效: '{value}' (期望 X.Y.Z[.W] 如 '31.0.101.0')",
                )
                return None
            return value

        min_ver = _check_drv("min_driver_version")
        rec_ver = _check_drv("recommended_driver_version")

        # 跨字段依赖: recommended >= min
        if min_ver is not None and rec_ver is not None:
            try:
                min_parts = [int(x) for x in min_ver.split(".")]
                rec_parts = [int(x) for x in rec_ver.split(".")]
                max_len = max(len(min_parts), len(rec_parts))
                min_parts += [0] * (max_len - len(min_parts))
                rec_parts += [0] * (max_len - len(rec_parts))
                if rec_parts < min_parts:
                    errors.append(
                        f"recommended_driver_version ({rec_ver}) < min_driver_version ({min_ver})",
                    )
            except (ValueError, TypeError):
                pass  # 格式错误已由 _check_drv 报告

    def _validate_profile(self, profile: dict[str, Any], profile_path: str) -> bool:
        """验证GPU配置文件的合法性.

        验证内容包括:
        - 必需字段存在性 (models, recommended_batch_size, max_batch_size)
        - 字段类型正确性
        - 数值关系合法性 (max_batch_size >= recommended_batch_size)
        - optimizations枚举值有效性
        - memory_efficiency范围合理性
        - queue_depth范围合理性 [1, 64]
        - timeout_seconds正数检查
        - known_issues枚举白名单验证
        - driver_version格式与版本比较验证

        Args:
            profile: 配置字典
            profile_path: 配置路径(用于日志)，格式: "vendor/arch/series"

        Returns:
            bool: 配置是否合法

        Note:
            - 验证失败时会记录ERROR级别日志
            - 发现问题时会记录WARNING级别日志
            - 该方法会收集所有错误后统一报告，而非快速失败

        """
        errors: list[str] = []
        warnings: list[str] = []

        for key in ["models", "recommended_batch_size", "max_batch_size"]:
            if key not in profile:
                errors.append(f"缺少必需字段: {key}")

        if errors:
            for error in errors:
                logger.error("配置 %s: %s", profile_path, error)
            return False

        self._validate_profile_models(profile, errors)
        self._validate_profile_batch_sizes(profile, errors)
        self._validate_profile_optimizations(profile, errors, warnings)
        self._validate_profile_optional_fields(profile, errors, warnings)
        self._validate_profile_queue_depth(profile, errors)
        self._validate_profile_timeout(profile, errors)
        self._validate_profile_known_issues(profile, errors, warnings)
        self._validate_profile_driver_versions(profile, errors, warnings)

        if errors:
            for error in errors:
                logger.error("配置 %s: %s", profile_path, error)
            return False

        if warnings:
            for warning in warnings:
                logger.warning("配置 %s: %s", profile_path, warning)

        return True

    def _clean_model_name(self, name: str) -> str:
        """清理型号名称,移除常见前缀和后缀."""
        # 移除常见前缀
        prefixes = ["nvidia ", "amd ", "intel ", "geforce ", "radeon ", "arc "]
        for prefix in prefixes:
            name = name.removeprefix(prefix)

        # 移除常见后缀
        suffixes = [" graphics", " gpu"]
        for suffix in suffixes:
            name = name.removesuffix(suffix)

        return name.strip()

    def get_default_profile(self, vendor: str) -> dict[str, Any] | None:
        """获取厂商的默认配置.

        Args:
            vendor: 厂商名称

        Returns:
            默认配置字典

        """
        vendor = vendor.lower()

        if vendor not in self.profiles:
            return None

        vendor_data = self.profiles[vendor]

        # 查找"default"配置
        if "default" in vendor_data:
            return vendor_data["default"]

        return None

    def get_all_vendors(self) -> list[str]:
        """获取所有支持的厂商列表."""
        return [k for k in self.profiles if not k.startswith("_")]

    def get_vendor_architectures(self, vendor: str) -> list[str]:
        """获取厂商的所有架构世代.

        Args:
            vendor: 厂商名称

        Returns:
            架构名称列表

        """
        vendor = vendor.lower()

        if vendor not in self.profiles:
            return []

        vendor_data = self.profiles[vendor]
        return [k for k in vendor_data if not k.startswith("_") and k != "default"]

    def reload(self) -> None:
        """重新加载配置文件."""
        logger.info("重新加载GPU型号数据库...")
        self._load_profiles()

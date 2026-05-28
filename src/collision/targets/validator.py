"""批量地址验证器.

提供高效的地址批量验证功能:
- 并行验证多个地址
- 详细的验证结果和错误报告
- 支持多种地址格式验证
- 数据类型兼容性和错误处理
"""

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

# 导入日志配置
from src.utils import get_configured_logger

# v4.2.1修复: Python的logging.Logger本身是线程安全的，无需ThreadSafeLogger包装
logger = get_configured_logger("AddressValidator")


@dataclass
class ValidationResult:
    """地址验证结果.

    Fields:
        address: 被验证的比特币地址
        valid: 验证结果（True=通过，False=失败或未验证）
        validated: 是否实际进行了验证
            - True: 已对该地址进行了某种形式的验证（类型检查、格式验证等）
            - False: 未对该地址进行任何验证（批量中止导致）
        format_type: 地址格式类型（p2pkh, p2sh, bech32, unknown）
        error: 错误信息（验证失败或未验证时的原因）

    状态组合示例:
        - valid=True, validated=True: 验证通过 [OK]
        - valid=False, validated=True: 验证失败（格式错误、校验和失败等） [ERR]
        - valid=False, validated=False: 未验证（批量中止、未处理等） [PAUSE]

    使用示例:
        >>> result = ValidationResult(
        ...     address='1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa',
        ...     valid=True,
        ...     format_type='p2pkh'
        ... )
        >>> if result.valid:
        ...     print(f"地址 {result.address} 验证通过")
        >>> if not result.validated:
        ...     print(f"地址 {result.address} 未验证")
    """

    address: str
    valid: bool
    validated: bool = True  # 是否实际进行了验证（用于区分"验证失败"和"未验证"）
    format_type: str = "unknown"
    error: str | None = None

    def __repr__(self) -> str:
        """返回验证结果的字符串表示。."""
        if self.valid:
            return f"ValidationResult({self.address[:10]}..., valid=True, format={self.format_type})"
        if not self.validated:
            return (
                f"ValidationResult({self.address[:10]}..., "
                f"valid=False, validated=False, error={self.error})"
            )
        return f"ValidationResult({self.address[:10]}..., valid=False, error={self.error})"


class AddressBatchValidator:
    """批量地址验证器.

    使用线程池并行验证多个比特币地址,提供详细的验证结果。

    Example:
        >>> validator = AddressBatchValidator(max_workers=4)
        >>> results = validator.validate_batch(['1A1z...', 'invalid'])
        >>> for addr, result in results.items():
        ...     print(f"{addr}: {'valid' if result.valid else 'invalid'}")

    """

    def __init__(self, max_workers: int = 4) -> None:
        """初始化批量地址验证器.

        Args:
            max_workers: 最大工作线程数,默认4

        """
        self.max_workers = max_workers
        self._lock = threading.Lock()
        self.total_validated = 0
        self.total_valid = 0
        self.total_invalid = 0

        logger.info("AddressBatchValidator 初始化: max_workers=%s", max_workers)

    # ── validate_batch 辅助方法（降低 C901） ──────────────────────

    @staticmethod
    def _normalize_addresses(
        addresses: list[str | Any],
        strict_mode: bool,
        on_type_error: str,
    ) -> tuple[list[str], int, dict[str, ValidationResult] | None]:
        """将输入地址列表规范化为纯字符串列表。.

        Returns:
            (str_addresses, skipped_count, abort_results):
            - abort_results 非 None 表示严格模式 abort 策略触发中止。

        """
        str_addresses: list[str] = []
        skipped_count = 0

        for addr in addresses:
            if isinstance(addr, str):
                stripped = addr.strip()
                if stripped:
                    str_addresses.append(stripped)
                else:
                    logger.debug("地址为空字符串，跳过 [原始字符串]")
                    skipped_count += 1
            elif strict_mode:
                addr_str = str(addr) if addr is not None else "None"
                if on_type_error == "abort":
                    error_msg = f"期望字符串类型，实际: {type(addr).__name__}"
                    logger.error(error_msg)
                    results = {}
                    for valid_addr in str_addresses:
                        results[valid_addr] = ValidationResult(
                            address=valid_addr,
                            valid=False,
                            validated=False,
                            error="批量验证因严格模式中止",
                        )
                    results[addr_str] = ValidationResult(
                        address=addr_str,
                        valid=False,
                        validated=True,
                        error=error_msg,
                    )
                    logger.info(
                        f"严格模式验证中止: 已收集{len(str_addresses)}个有效地址（未验证），"
                        f"遇到非字符串类型: {type(addr).__name__}",
                    )
                    return str_addresses, skipped_count, results
                if on_type_error == "skip":
                    logger.info(f"跳过非字符串类型: {type(addr).__name__}")
                    skipped_count += 1
                elif on_type_error == "convert":
                    safe_types = (int, float, Decimal)
                    if isinstance(addr, safe_types):
                        try:
                            str_addr = str(addr).strip()
                            if str_addr:
                                str_addresses.append(str_addr)
                                logger.debug(f"类型转换成功: {type(addr).__name__} -> str")
                            else:
                                skipped_count += 1
                        except Exception as e:
                            logger.error(
                                f"地址类型转换失败: {type(addr).__name__} -> str, 错误={e}",
                            )
                            skipped_count += 1
                    else:
                        logger.debug(f"不支持的类型转换: {type(addr).__name__}, 跳过")
                        skipped_count += 1
            else:
                try:
                    str_addr = str(addr).strip()
                    if str_addr:
                        str_addresses.append(str_addr)
                    else:
                        skipped_count += 1
                except Exception as e:
                    logger.error(f"地址类型转换失败: {type(addr).__name__}, 错误={e}")
                    skipped_count += 1

        return str_addresses, skipped_count, None

    @staticmethod
    def _log_validation_summary(results: dict) -> None:
        """记录批量验证结果摘要。."""
        valid_count = sum(1 for r in results.values() if r.valid)
        invalid_count = len(results) - valid_count
        pct = (valid_count / len(results) * 100) if len(results) > 0 else 0
        logger.info(
            f"批量验证完成: 总数={len(results)}, 有效={valid_count}, "
            f"无效={invalid_count}, 有效率={pct:.1f}%",
        )

    def validate_batch(
        self,
        addresses: list[str | Any],
        strict_mode: bool = False,
        on_type_error: str = "abort",
    ) -> dict[str, ValidationResult]:
        """批量验证地址。."""
        valid_strategies = {"abort", "skip", "convert"}
        if on_type_error not in valid_strategies:
            raise ValueError(f"无效的策略 '{on_type_error}',必须是 {valid_strategies} 之一")

        str_addresses, skipped_count, abort_results = self._normalize_addresses(
            addresses,
            strict_mode,
            on_type_error,
        )
        if abort_results is not None:
            return abort_results

        if skipped_count > 0:
            logger.info(
                f"数据类型转换: 总数={len(addresses)}, 有效={len(str_addresses)}, 跳过={skipped_count}",
            )

        logger.info(f"开始批量验证: 总数={len(str_addresses)}, 工作线程={self.max_workers}")

        results: dict[str, ValidationResult] = {}
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(self._validate_single, addr): addr for addr in str_addresses}
            for future in as_completed(futures):
                addr = futures[future]
                try:
                    result = future.result()
                    results[addr] = result
                    with self._lock:
                        self.total_validated += 1
                        if result.valid:
                            self.total_valid += 1
                        else:
                            self.total_invalid += 1
                except Exception as e:
                    logger.error("地址验证异常: %s, 错误=%s", addr, e)
                    results[addr] = ValidationResult(address=addr, valid=False, error=str(e))

        self._log_validation_summary(results)
        return results

    def _validate_single(self, address: str) -> ValidationResult:
        """验证单个地址.

        Args:
            address: 待验证的地址

        Returns:
            验证结果

        """
        try:
            from src.core.base58 import Base58

            # 检测地址格式
            if address.startswith("1"):
                format_type = "P2PKH"
                version, payload = Base58.check_decode(address)
                if version == 0x00 and len(payload) == 20:
                    logger.debug(f"地址验证成功: {address[:8]}... (P2PKH)")
                    return ValidationResult(address=address, valid=True, format_type=format_type)
                logger.debug(
                    f"地址验证失败: {address[:8]}... (P2PKH, version=0x{version:02x})",
                )
                return ValidationResult(
                    address=address,
                    valid=False,
                    format_type=format_type,
                    error=f"Invalid version: 0x{version:02x}",
                )

            if address.startswith("3"):
                format_type = "P2SH"
                version, payload = Base58.check_decode(address)
                if version == 0x05 and len(payload) == 20:
                    logger.debug(f"地址验证成功: {address[:8]}... (P2SH)")
                    return ValidationResult(address=address, valid=True, format_type=format_type)
                logger.debug(f"地址验证失败: {address[:8]}... (P2SH, version=0x{version:02x})")
                return ValidationResult(
                    address=address,
                    valid=False,
                    format_type=format_type,
                    error=f"Invalid version: 0x{version:02x}",
                )

            if address.lower().startswith("bc1p"):
                format_type = "Bech32m"
                if 62 <= len(address) <= 74:
                    logger.debug(f"Bech32m地址基本验证通过: {address[:8]}...")
                    return ValidationResult(address=address, valid=True, format_type=format_type)
                return ValidationResult(
                    address=address,
                    valid=False,
                    format_type=format_type,
                    error="Invalid length (Bech32m: 62-74)",
                )

            if address.lower().startswith("bc1"):
                format_type = "Bech32"
                if 42 <= len(address) <= 62:
                    logger.debug(f"Bech32地址基本验证通过: {address[:8]}...")
                    return ValidationResult(address=address, valid=True, format_type=format_type)
                return ValidationResult(
                    address=address,
                    valid=False,
                    format_type=format_type,
                    error="Invalid length (Bech32: 42-62)",
                )

            return ValidationResult(
                address=address,
                valid=False,
                format_type="unknown",
                error="Unknown address format",
            )

        except Exception as e:
            logger.error(f"地址验证异常: {address[:8]}..., 错误={e}")
            return ValidationResult(address=address, valid=False, error=str(e))

    def filter_valid(self, addresses: list[str | Any]) -> list[str]:
        """过滤出有效地址.

        Args:
            addresses: 待过滤的地址列表

        Returns:
            有效地址列表

        """
        logger.debug(f"开始过滤有效地址: 输入数={len(addresses)}")

        results = self.validate_batch(addresses)
        valid_addresses = [addr for addr, result in results.items() if result.valid]

        logger.debug(f"过滤完成: 输入={len(addresses)}, 输出={len(valid_addresses)}")

        return valid_addresses

    def get_summary(self) -> dict[str, float | int]:
        """获取验证统计摘要.

        Returns:
            统计信息字典

        """
        with self._lock:
            summary = {
                "total_validated": self.total_validated,
                "total_valid": self.total_valid,
                "total_invalid": self.total_invalid,
                "success_rate": (
                    self.total_valid / self.total_validated * 100 if self.total_validated > 0 else 0
                ),
            }

            logger.debug("验证统计摘要: %s", summary)
            return summary

    def get_validation_summary(self, results: dict[str, ValidationResult]) -> dict[str, Any]:
        """获取验证结果摘要(别名方法,保持向后兼容).

        Args:
            results: validate_batch返回的结果字典

        Returns:
            摘要字典

        """
        valid_count = sum(1 for r in results.values() if r.valid)
        invalid_count = len(results) - valid_count

        summary = {
            "total": len(results),
            "valid": valid_count,
            "invalid": invalid_count,
            "success_rate": (valid_count / len(results) * 100) if len(results) > 0 else 0,
        }

        logger.debug("验证结果摘要: %s", summary)
        return summary

    def get_validation_coverage(self, results: dict[str, ValidationResult]) -> dict[str, Any]:
        """获取验证覆盖率统计.

        用于分析批量验证的执行情况,特别是在严格模式下区分
        "已验证"和"未验证"的地址。

        Args:
            results: validate_batch 返回的验证结果字典

        Returns:
            包含覆盖率统计的字典:
            - total: 总地址数
            - validated: 已验证地址数(无论成功或失败)
            - unvalidated: 未验证地址数(因中止等原因未执行验证)
            - coverage: 验证覆盖率百分比 (validated/total*100)
            - valid: 验证成功的地址数
            - invalid: 已验证但失败的地址数（注意：不包括未验证的地址）

        Example:
            >>> results = validator.validate_batch(addresses, strict_mode=True)
            >>> coverage = validator.get_validation_coverage(results)
            >>> print(f"验证覆盖率: {coverage['coverage']:.1f}%")
            >>> print(f"验证失败: {coverage['invalid']} (已验证但失败)")

        """
        total = len(results)

        if total == 0:
            return {
                "total": 0,
                "validated": 0,
                "unvalidated": 0,
                "coverage": 0.0,
                "valid": 0,
                "invalid": 0,  # 已验证但失败的地址数
            }

        validated = sum(1 for r in results.values() if r.validated)
        unvalidated = total - validated
        valid = sum(1 for r in results.values() if r.valid)
        invalid = validated - valid  # 已验证但失败的地址数（不包括未验证的）

        coverage_stats = {
            "total": total,
            "validated": validated,
            "unvalidated": unvalidated,
            "coverage": (validated / total * 100),
            "valid": valid,
            "invalid": invalid,
        }

        logger.debug(
            f"验证覆盖率统计: 总数={total}, "
            f"已验证={validated}, 未验证={unvalidated}, "
            f"覆盖率={coverage_stats['coverage']:.1f}%",
        )

        return coverage_stats

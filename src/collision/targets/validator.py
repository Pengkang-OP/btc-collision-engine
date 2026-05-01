"""批量地址验证器

提供高效的地址批量验证功能:
- 并行验证多个地址
- 详细的验证结果和错误报告
- 支持多种地址格式验证
- 数据类型兼容性和错误处理
"""

import threading
from decimal import Decimal
from typing import List, Dict, Optional, Union, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

# 导入日志配置
from ...utils import init_logging, get_configured_logger

# 初始化日志系统
init_logging()
# v2.2.1修复: Python的logging.Logger本身是线程安全的，无需ThreadSafeLogger包装
logger = get_configured_logger("AddressValidator", thread_safe=False)


@dataclass
class ValidationResult:
    """地址验证结果

    字段说明:
        address: 被验证的比特币地址
        valid: 验证结果（True=通过，False=失败或未验证）
        validated: 是否实际进行了验证
            - True: 已对该地址进行了某种形式的验证（类型检查、格式验证等）
            - False: 未对该地址进行任何验证（批量中止导致）
        format_type: 地址格式类型（p2pkh, p2sh, bech32, unknown）
        error: 错误信息（验证失败或未验证时的原因）

    状态组合示例:
        - valid=True, validated=True: 验证通过 ✅
        - valid=False, validated=True: 验证失败（格式错误、校验和失败等） ❌
        - valid=False, validated=False: 未验证（批量中止、未处理等） ⏸️

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
    error: Optional[str] = None

    def __repr__(self) -> str:
        if self.valid:
            return (
                f"ValidationResult({self.address[:10]}..., valid=True, format={self.format_type})"
            )
        elif not self.validated:
            return f"ValidationResult({self.address[:10]}..., valid=False, validated=False, error={self.error})"  # noqa: E501
        else:
            return f"ValidationResult({self.address[:10]}..., valid=False, error={self.error})"


class AddressBatchValidator:
    """批量地址验证器

    使用线程池并行验证多个比特币地址,提供详细的验证结果。

    示例:
        >>> validator = AddressBatchValidator(max_workers=4)
        >>> results = validator.validate_batch(['1A1z...', 'invalid'])
        >>> for addr, result in results.items():
        ...     print(f"{addr}: {'valid' if result.valid else 'invalid'}")
    """

    def __init__(self, max_workers: int = 4) -> None:
        """
        初始化批量地址验证器

        参数:
            max_workers: 最大工作线程数,默认4
        """
        self.max_workers = max_workers
        self._lock = threading.Lock()
        self.total_validated = 0
        self.total_valid = 0
        self.total_invalid = 0

        logger.info(f"AddressBatchValidator 初始化: max_workers={max_workers}")

    def validate_batch(
        self,
        addresses: List[Union[str, Any]],
        strict_mode: bool = False,
        on_type_error: str = "abort",
    ) -> Dict[str, ValidationResult]:
        """
        批量验证地址

        参数:
            addresses: 待验证的地址列表（支持字符串和其他类型）
            strict_mode: 严格模式，如果为True则只接受字符串类型，默认False
            on_type_error: 严格模式下遇到非字符串类型的处理策略
                - 'abort': 立即中止验证(默认),返回部分结果
                - 'skip': 跳过非字符串类型,继续验证其他地址
                - 'convert': 尝试将非字符串类型转换为字符串

        返回:
            字典 {地址: 验证结果}

        示例:
            >>> # 默认行为: 遇到非字符串立即中止
            >>> results = validator.validate_batch(addresses, strict_mode=True)

            >>> # 跳过非字符串类型
            >>> results = validator.validate_batch(addresses, strict_mode=True, on_type_error='skip')  # noqa: E501

            >>> # 尝试转换类型
            >>> results = validator.validate_batch(addresses, strict_mode=True, on_type_error='convert')  # noqa: E501
        """
        # 验证策略参数
        valid_strategies = {"abort", "skip", "convert"}
        if on_type_error not in valid_strategies:
            raise ValueError(f"无效的策略 '{on_type_error}',必须是 {valid_strategies} 之一")

        # 数据类型兼容性处理
        str_addresses = []
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
                # 严格模式：根据策略处理非字符串类型
                addr_str = str(addr) if addr is not None else "None"

                if on_type_error == "abort":
                    # 策略1: 立即中止(默认行为)
                    error_msg = f"期望字符串类型，实际: {type(addr).__name__}"
                    logger.error(error_msg)

                    # 已收集的地址标记为"未验证"
                    # 使用validated=False明确区分"验证失败"和"未验证"
                    results = {}
                    for valid_addr in str_addresses:
                        results[valid_addr] = ValidationResult(
                            address=valid_addr,
                            valid=False,
                            validated=False,  # 明确标记未验证
                            error="批量验证因严格模式中止",
                        )

                    # 添加导致失败的地址
                    results[addr_str] = ValidationResult(
                        address=addr_str,
                        valid=False,
                        validated=True,  # 这个地址确实验证了（类型检查失败）
                        error=error_msg,
                    )

                    logger.info(
                        f"严格模式验证中止: 已收集{len(str_addresses)}个有效地址（未验证），"
                        f"遇到非字符串类型: {type(addr).__name__}"
                    )
                    return results

                elif on_type_error == "skip":
                    # 策略2: 跳过非字符串类型,继续验证
                    logger.info(f"跳过非字符串类型: {type(addr).__name__}")
                    skipped_count += 1

                elif on_type_error == "convert":
                    # 策略3: 尝试转换为字符串（仅允许安全类型）
                    # 类型白名单：int, float, Decimal（移除bytes/bytearray，因为str()会产生"b'...'"格式）
                    safe_types = (int, float, Decimal)
                    if isinstance(addr, safe_types):
                        try:
                            str_addr = str(addr).strip()
                            if str_addr:
                                str_addresses.append(str_addr)
                                logger.debug(f"类型转换成功: {type(addr).__name__} -> str")
                            else:
                                logger.debug("地址转换为空字符串，跳过 [convert策略]")
                                skipped_count += 1
                        except Exception as e:
                            logger.error(
                                f"地址类型转换失败: {type(addr).__name__} -> str, " f"错误={e}"
                            )
                            skipped_count += 1
                    else:
                        logger.debug(f"不支持的类型转换: {type(addr).__name__}, 跳过")
                        skipped_count += 1

            else:
                # 宽松模式：尝试转换为字符串
                try:
                    str_addr = str(addr).strip()
                    if str_addr:
                        str_addresses.append(str_addr)
                    else:
                        logger.debug("地址转换为空字符串，跳过 [宽松模式]")
                        skipped_count += 1
                except Exception as e:
                    logger.error(f"地址类型转换失败: {type(addr).__name__}, " f"错误={e}")
                    skipped_count += 1

        if skipped_count > 0:
            logger.info(
                f"数据类型转换: 总数={len(addresses)}, 有效={len(str_addresses)}, 跳过={skipped_count}"
            )

        logger.info(f"开始批量验证: 总数={len(str_addresses)}, 工作线程={self.max_workers}")

        results = {}

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有验证任务
            futures = {executor.submit(self._validate_single, addr): addr for addr in str_addresses}

            # 收集结果
            for future in as_completed(futures):
                addr = futures[future]
                try:
                    result = future.result()
                    results[addr] = result

                    # 更新统计
                    with self._lock:
                        self.total_validated += 1
                        if result.valid:
                            self.total_valid += 1
                        else:
                            self.total_invalid += 1

                except Exception as e:
                    logger.error(f"地址验证异常: {addr}, 错误={e}")
                    results[addr] = ValidationResult(address=addr, valid=False, error=str(e))

        # 统计结果
        valid_count = sum(1 for r in results.values() if r.valid)
        invalid_count = len(results) - valid_count

        logger.info(
            f"批量验证完成: 总数={len(results)}, 有效={valid_count}, "
            f"无效={invalid_count}, 有效率={(valid_count / len(results) * 100) if len(results) > 0 else 0:.1f}%"  # noqa: E501
        )

        return results

    def _validate_single(self, address: str) -> ValidationResult:
        """
        验证单个地址

        参数:
            address: 待验证的地址

        返回:
            验证结果
        """
        try:
            from ...core.base58 import Base58

            # 检测地址格式
            if address.startswith("1"):
                format_type = "P2PKH"
                version, payload = Base58.check_decode(address)
                if version == 0x00 and len(payload) == 20:
                    logger.debug(f"地址验证成功: {address[:15]}... (P2PKH)")
                    return ValidationResult(address=address, valid=True, format_type=format_type)
                else:
                    logger.debug(
                        f"地址验证失败: {address[:15]}... (P2PKH, version=0x{version:02x})"
                    )
                    return ValidationResult(
                        address=address,
                        valid=False,
                        format_type=format_type,
                        error=f"Invalid version: 0x{version:02x}",
                    )

            elif address.startswith("3"):
                format_type = "P2SH"
                version, payload = Base58.check_decode(address)
                if version == 0x05 and len(payload) == 20:
                    logger.debug(f"地址验证成功: {address[:15]}... (P2SH)")
                    return ValidationResult(address=address, valid=True, format_type=format_type)
                else:
                    logger.debug(f"地址验证失败: {address[:15]}... (P2SH, version=0x{version:02x})")
                    return ValidationResult(
                        address=address,
                        valid=False,
                        format_type=format_type,
                        error=f"Invalid version: 0x{version:02x}",
                    )

            elif address.lower().startswith("bc1"):
                format_type = "Bech32"
                # Bech32验证需要专门的库,这里只做基本检查
                if 14 <= len(address) <= 74:
                    logger.debug(f"Bech32地址基本验证通过: {address[:15]}...")
                    return ValidationResult(address=address, valid=True, format_type=format_type)
                else:
                    return ValidationResult(
                        address=address,
                        valid=False,
                        format_type=format_type,
                        error="Invalid length",
                    )

            else:
                return ValidationResult(
                    address=address,
                    valid=False,
                    format_type="unknown",
                    error="Unknown address format",
                )

        except Exception as e:
            logger.error(f"地址验证异常: {address[:15]}..., 错误={e}")
            return ValidationResult(address=address, valid=False, error=str(e))

    def filter_valid(self, addresses: List[Union[str, Any]]) -> List[str]:
        """
        过滤出有效地址

        参数:
            addresses: 待过滤的地址列表

        返回:
            有效地址列表
        """
        logger.debug(f"开始过滤有效地址: 输入数={len(addresses)}")

        results = self.validate_batch(addresses)
        valid_addresses = [addr for addr, result in results.items() if result.valid]

        logger.debug(f"过滤完成: 输入={len(addresses)}, 输出={len(valid_addresses)}")

        return valid_addresses

    def get_summary(self) -> Dict[str, Union[float, int]]:
        """
        获取验证统计摘要

        返回:
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

            logger.debug(f"验证统计摘要: {summary}")
            return summary

    def get_validation_summary(self, results: Dict[str, ValidationResult]) -> Dict[str, Any]:
        """
        获取验证结果摘要(别名方法,保持向后兼容)

        参数:
            results: validate_batch返回的结果字典

        返回:
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

        logger.debug(f"验证结果摘要: {summary}")
        return summary

    def get_validation_coverage(self, results: Dict[str, ValidationResult]) -> Dict[str, Any]:
        """获取验证覆盖率统计

        用于分析批量验证的执行情况,特别是在严格模式下区分
        "已验证"和"未验证"的地址。

        参数:
            results: validate_batch 返回的验证结果字典

        返回:
            包含覆盖率统计的字典:
            - total: 总地址数
            - validated: 已验证地址数(无论成功或失败)
            - unvalidated: 未验证地址数(因中止等原因未执行验证)
            - coverage: 验证覆盖率百分比 (validated/total*100)
            - valid: 验证成功的地址数
            - invalid: 已验证但失败的地址数（注意：不包括未验证的地址）

        示例:
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
            f"覆盖率={coverage_stats['coverage']:.1f}%"
        )

        return coverage_stats

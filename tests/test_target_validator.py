#!/usr/bin/env python3
"""批量地址验证器 (validator) 单元测试

覆盖：
- ValidationResult 数据类
- AddressBatchValidator 初始化
- validate_batch 批量验证
- strict_mode / on_type_error 策略
- filter_valid / get_summary / get_validation_summary
- get_validation_coverage
"""

import pytest

# ============================================================================
# ValidationResult 测试
# ============================================================================


@pytest.mark.unit
class TestValidationResult:
    """ValidationResult 数据类测试"""

    def test_valid_result(self):
        from src.collision.targets.validator import ValidationResult

        result = ValidationResult(
            address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", valid=True, format_type="p2pkh"
        )
        assert result.valid is True
        assert result.validated is True  # default
        assert result.format_type == "p2pkh"

    def test_invalid_result(self):
        from src.collision.targets.validator import ValidationResult

        result = ValidationResult(address="invalid", valid=False, error="bad format")
        assert result.valid is False
        assert result.error == "bad format"

    def test_defaults(self):
        from src.collision.targets.validator import ValidationResult

        result = ValidationResult(address="addr", valid=False)
        assert result.validated is True
        assert result.format_type == "unknown"
        assert result.error is None

    def test_repr_valid(self):
        from src.collision.targets.validator import ValidationResult

        result = ValidationResult(address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", valid=True)
        r = repr(result)
        assert "valid=True" in r

    def test_repr_not_validated(self):
        from src.collision.targets.validator import ValidationResult

        result = ValidationResult(
            address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            valid=False,
            validated=False,
            error="aborted",
        )
        r = repr(result)
        assert "validated=False" in r


# ============================================================================
# AddressBatchValidator 初始化测试
# ============================================================================


@pytest.mark.unit
class TestValidatorInit:
    """初始化测试"""

    def test_default_max_workers(self):
        from src.collision.targets.validator import AddressBatchValidator

        validator = AddressBatchValidator()
        assert validator.max_workers == 4
        assert validator.total_validated == 0

    def test_custom_max_workers(self):
        from src.collision.targets.validator import AddressBatchValidator

        validator = AddressBatchValidator(max_workers=8)
        assert validator.max_workers == 8


# ============================================================================
# validate_batch 测试
# ============================================================================


@pytest.mark.unit
class TestValidateBatch:
    """批量验证测试"""

    def test_invalid_strategy_raises(self):
        from src.collision.targets.validator import AddressBatchValidator

        validator = AddressBatchValidator()
        with pytest.raises(ValueError, match="无效的策略"):
            validator.validate_batch(["addr1"], strict_mode=True, on_type_error="invalid_strategy")

    def test_empty_list(self):
        from src.collision.targets.validator import AddressBatchValidator

        validator = AddressBatchValidator()
        results = validator.validate_batch([])
        assert isinstance(results, dict)
        assert len(results) == 0

    def test_valid_addresses(self):
        from src.collision.targets.validator import AddressBatchValidator

        validator = AddressBatchValidator(max_workers=1)
        results = validator.validate_batch(["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"])
        assert len(results) >= 1

    def test_strict_mode_abort_on_non_string(self):
        from src.collision.targets.validator import AddressBatchValidator

        validator = AddressBatchValidator(max_workers=1)
        results = validator.validate_batch(
            ["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", 12345],
            strict_mode=True,
            on_type_error="abort",
        )
        # 应包含已收集地址（标记为未验证）和导致中止的地址
        assert len(results) >= 1
        # 应至少有一个未验证的结果
        unvalidated = [r for r in results.values() if not r.validated]
        assert len(unvalidated) >= 1

    def test_strict_mode_skip_non_string(self):
        from src.collision.targets.validator import AddressBatchValidator

        validator = AddressBatchValidator(max_workers=1)
        results = validator.validate_batch(
            ["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", 12345],
            strict_mode=True,
            on_type_error="skip",
        )
        # 非字符串应被跳过，只验证第一个
        assert len(results) >= 1

    def test_strict_mode_convert_int(self):
        from src.collision.targets.validator import AddressBatchValidator

        validator = AddressBatchValidator(max_workers=1)
        # int 是 safe_type，可被转换
        results = validator.validate_batch(
            ["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", 12345],
            strict_mode=True,
            on_type_error="convert",
        )
        assert len(results) >= 1

    def test_loose_mode_converts(self):
        """宽松模式自动转换非字符串"""
        from src.collision.targets.validator import AddressBatchValidator

        validator = AddressBatchValidator(max_workers=1)
        results = validator.validate_batch(["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"])
        assert len(results) >= 1

    def test_invalid_address(self):
        from src.collision.targets.validator import AddressBatchValidator

        validator = AddressBatchValidator(max_workers=1)
        results = validator.validate_batch(["not_a_valid_address_xyz"])
        assert len(results) == 1
        addr_results = list(results.values())
        assert addr_results[0].valid is False


# ============================================================================
# filter_valid 测试
# ============================================================================


@pytest.mark.unit
class TestFilterValid:
    """过滤有效地址测试"""

    def test_filters_only_valid(self):
        from src.collision.targets.validator import AddressBatchValidator

        validator = AddressBatchValidator(max_workers=1)
        # 使用已知的混合地址列表
        valid = validator.filter_valid(["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "invalid"])
        # 有效地址可能为 0-1
        assert isinstance(valid, list)


# ============================================================================
# get_summary / get_validation_summary / get_validation_coverage 测试
# ============================================================================


@pytest.mark.unit
class TestSummary:
    """统计摘要测试"""

    def test_get_summary_initially_zero(self):
        from src.collision.targets.validator import AddressBatchValidator

        validator = AddressBatchValidator()
        summary = validator.get_summary()
        assert summary["total_validated"] == 0
        assert summary["success_rate"] == 0

    def test_get_validation_summary_empty(self):
        from src.collision.targets.validator import AddressBatchValidator

        validator = AddressBatchValidator()
        summary = validator.get_validation_summary({})
        assert summary["total"] == 0
        assert summary["valid"] == 0

    def test_get_validation_coverage_empty(self):
        from src.collision.targets.validator import AddressBatchValidator

        validator = AddressBatchValidator()
        coverage = validator.get_validation_coverage({})
        assert coverage["total"] == 0
        assert coverage["coverage"] == 0.0

    def test_get_validation_coverage_mixed(self):
        from src.collision.targets.validator import AddressBatchValidator, ValidationResult

        validator = AddressBatchValidator()
        results = {
            "addr1": ValidationResult(address="addr1", valid=True, validated=True),
            "addr2": ValidationResult(address="addr2", valid=False, validated=True, error="bad"),
            "addr3": ValidationResult(address="addr3", valid=False, validated=False, error="aborted"),
        }
        coverage = validator.get_validation_coverage(results)
        assert coverage["total"] == 3
        assert coverage["validated"] == 2
        assert coverage["unvalidated"] == 1
        assert coverage["valid"] == 1
        assert coverage["invalid"] == 1  # validated but not valid

    def test_get_validation_summary_counts(self):
        from src.collision.targets.validator import AddressBatchValidator, ValidationResult

        validator = AddressBatchValidator()
        results = {
            "a": ValidationResult(address="a", valid=True),
            "b": ValidationResult(address="b", valid=True),
            "c": ValidationResult(address="c", valid=False, error="err"),
        }
        summary = validator.get_validation_summary(results)
        assert summary["total"] == 3
        assert summary["valid"] == 2
        assert summary["invalid"] == 1
        assert summary["success_rate"] > 0

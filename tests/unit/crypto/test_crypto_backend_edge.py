"""crypto_backend.py 全覆盖测试

覆盖: PurePythonBackend(const_time), OpenSSLBackend, CoincurveBackend,
      ECDSABackend, CryptoBackendManager 边界, 便捷函数
"""

import logging
from unittest.mock import patch

import pytest

import unittest

from src.core.crypto_backend import (
    BackendType,
    CoincurveBackend,
    CryptoBackendManager,
    ECDSABackend,
    OpenSSLBackend,
    PurePythonBackend,
    crypto_manager,
    generate_public_key,
    get_available_backends,
    get_crypto_backend,
    set_crypto_backend,
)

PK = b"\x01" * 32  # 测试用私钥


# ===========================================================================
# Group 1: PurePythonBackend const_time 路径 (lines 119-120, 129-132, 137)
# ===========================================================================


class TestPurePythonConstantTime:
    """PurePythonBackend use_const_time=True"""

    def setup_method(self, method):
        self.backend = PurePythonBackend(use_const_time=True)

    def test_name_with_const_time(self):
        """const_time 后端名 → line 112"""
        assert "Constant Time" in self.backend.name

    def test_is_available(self):
        """始终可用"""
        assert self.backend.is_available

    def test_generate_public_key_const_time(self):
        """const_time 路径 → lines 119-120"""
        result = self.backend.generate_public_key(PK, compressed=True)
        assert len(result) == 33

    def test_generate_public_key_uncompressed(self):
        """普通路径非压缩 → line 122"""
        backend = PurePythonBackend(use_const_time=False)
        result = backend.generate_public_key(PK, compressed=False)
        assert len(result) == 65

    def test_scalar_multiply_const_time(self):
        """const_time scalar_multiply → lines 129-132"""
        from src.core.secp256k1 import Secp256k1

        result = self.backend.scalar_multiply(5, Secp256k1.Gx, Secp256k1.Gy)
        assert len(result) == 2
        assert isinstance(result[0], int)
        assert isinstance(result[1], int)

    def test_scalar_multiply_non_const_time(self):
        """非 const_time scalar_multiply → line 132"""
        from src.core.secp256k1 import Secp256k1

        backend = PurePythonBackend(use_const_time=False)
        result = backend.scalar_multiply(5, Secp256k1.Gx, Secp256k1.Gy)
        assert len(result) == 2

    def test_is_constant_time_true(self):
        """use_const_time=True → line 137"""
        assert self.backend.is_constant_time()

    def test_is_constant_time_false(self):
        """v4.2.2后始终为 True（所有路径使用恒定时间实现）"""
        backend = PurePythonBackend(use_const_time=False)
        assert backend.is_constant_time()


# ===========================================================================
# Group 2: OpenSSLBackend (lines 146-151, 157, 163, 170-196, 203-222, 233)
# ===========================================================================


class TestOpenSSLBackend:
    """OpenSSLBackend 全路径（PyO3 仅初始化一次，通过 mock 测试）"""

    def setup_method(self, method):
        # cryptography 的 PyO3 绑定在 crypto_manager 初始化时已加载，
        # 无法在测试中再次 import。使用 crypto_manager 中的已有实例，
        # 并通过 mock 测试不可用分支。
        self.backend = crypto_manager._backends[BackendType.OPENSSL]

    @pytest.mark.skipif(
        not crypto_manager._backends[BackendType.OPENSSL].is_available,
        reason="OpenSSL backend not available in test environment",
    )
    def test_name(self):
        """名称 → line 163"""
        assert self.backend.name == "OpenSSL (cryptography)"

    @pytest.mark.skipif(
        not crypto_manager._backends[BackendType.OPENSSL].is_available,
        reason="OpenSSL backend not available",
    )
    def test_is_available(self):
        assert self.backend.is_available

    @pytest.mark.skipif(
        not crypto_manager._backends[BackendType.OPENSSL].is_available,
        reason="OpenSSL backend not available",
    )
    def test_generate_public_key_compressed(self):
        """压缩公钥 → lines 170-192"""
        result = self.backend.generate_public_key(PK, compressed=True)
        assert len(result) == 33
        assert result[0] in (2, 3)

    @pytest.mark.skipif(
        not crypto_manager._backends[BackendType.OPENSSL].is_available,
        reason="OpenSSL backend not available",
    )
    def test_generate_public_key_uncompressed(self):
        """非压缩公钥 → lines 193-196"""
        result = self.backend.generate_public_key(PK, compressed=False)
        assert len(result) == 65
        assert result[0] == 0x04

    def test_generate_public_key_not_available(self):
        """不可用时 RuntimeError → line 171"""
        backend = OpenSSLBackend()
        backend._available = False
        with pytest.raises(RuntimeError) as ctx:
            backend.generate_public_key(PK)
        assert "not available" in str(ctx.value)

    def test_scalar_multiply_not_available(self):
        """不可用时 RuntimeError → line 204"""
        backend = OpenSSLBackend()
        backend._available = False
        with pytest.raises(RuntimeError) as ctx:
            backend.scalar_multiply(5, 0, 0)
        assert "not available" in str(ctx.value)

    @pytest.mark.skipif(
        not crypto_manager._backends[BackendType.OPENSSL].is_available,
        reason="OpenSSL backend not available",
    )
    def test_scalar_multiply_fallback(self):
        """回退到纯 Python → lines 217-222"""
        from src.core.secp256k1 import Secp256k1

        result = self.backend.scalar_multiply(5, Secp256k1.Gx, Secp256k1.Gy)
        assert len(result) == 2

    @pytest.mark.skipif(
        not crypto_manager._backends[BackendType.OPENSSL].is_available,
        reason="OpenSSL backend not available",
    )
    def test_is_constant_time(self):
        """返回 False → line 233"""
        assert not self.backend.is_constant_time()


# ===========================================================================
# Group 3: CoincurveBackend (lines 247-248, 260, 274-304, 308)
# ===========================================================================


class TestCoincurveBackend:
    """CoincurveBackend 全路径"""

    @pytest.mark.skipif(
        not CoincurveBackend().is_available,
        reason="Coincurve backend not available in test environment",
    )
    def setup_method(self, method):
        self.backend = CoincurveBackend()

    @pytest.mark.skipif(
        not CoincurveBackend().is_available,
        reason="Coincurve backend not available in test environment",
    )
    def test_name(self):
        """名称"""
        assert "coincurve" in self.backend.name

    @pytest.mark.skipif(
        not CoincurveBackend().is_available,
        reason="Coincurve backend not available in test environment",
    )
    def test_is_available(self):
        """后端可用"""
        assert self.backend.is_available

    @pytest.mark.skipif(
        not CoincurveBackend().is_available,
        reason="Coincurve backend not available in test environment",
    )
    def test_generate_public_key_compressed(self):
        """压缩公钥 → lines 258-266"""
        result = self.backend.generate_public_key(PK, compressed=True)
        assert len(result) == 33

    @pytest.mark.skipif(
        not CoincurveBackend().is_available,
        reason="Coincurve backend not available in test environment",
    )
    def test_generate_public_key_uncompressed(self):
        """非压缩公钥"""
        result = self.backend.generate_public_key(PK, compressed=False)
        assert len(result) == 65

    def test_generate_public_key_not_available(self):
        """不可用时 RuntimeError → line 260"""
        backend = CoincurveBackend()
        backend._available = False
        with pytest.raises(RuntimeError) as ctx:
            backend.generate_public_key(PK)
        assert "not available" in str(ctx.value)

    @pytest.mark.skipif(
        not CoincurveBackend().is_available,
        reason="Coincurve backend not available in test environment",
    )
    def test_scalar_multiply(self):
        """标量乘法 → lines 274-294"""
        from src.core.secp256k1 import Secp256k1

        result = self.backend.scalar_multiply(5, Secp256k1.Gx, Secp256k1.Gy)
        assert len(result) == 2

    def test_scalar_multiply_not_available(self):
        """不可用时 RuntimeError → line 275"""
        backend = CoincurveBackend()
        backend._available = False
        with pytest.raises(RuntimeError) as ctx:
            backend.scalar_multiply(5, 0, 0)
        assert "not available" in str(ctx.value)

    @pytest.mark.skipif(
        not CoincurveBackend().is_available,
        reason="Coincurve backend not available in test environment",
    )
    def test_is_constant_time(self):
        """恒时 → line 308"""
        assert self.backend.is_constant_time()

    def test_check_availability_import_error(self):
        """Coincurve 不可用 → 返回 False → lines 247-248"""
        with patch.dict("sys.modules", {"coincurve": None}):
            backend = CoincurveBackend()
            assert not backend._available
            assert not backend.is_available

    @pytest.mark.skipif(
        not CoincurveBackend().is_available,
        reason="Coincurve backend not available in test environment",
    )
    def test_scalar_multiply_fallback(self):
        """Multiply 抛异常时的回退 → lines 295-304"""
        from unittest.mock import MagicMock

        from src.core.secp256k1 import Secp256k1

        # 创建一个 coincurve.PublicKey mock 使 multiply 抛异常
        with patch("coincurve.PublicKey") as mock_pk:
            mock_instance = MagicMock()
            mock_instance.multiply.side_effect = AttributeError("no multiply")
            mock_pk.return_value = mock_instance
            result = self.backend.scalar_multiply(5, Secp256k1.Gx, Secp256k1.Gy)
        assert len(result) == 2


# ===========================================================================
# Group 4: ECDSABackend (lines 328-329, 333, 340-350, 358-362, 366)
# ===========================================================================


class TestECDSABackend:
    """ECDSABackend 全路径"""

    @pytest.mark.skipif(
        not ECDSABackend().is_available,
        reason="ECDSA backend not available in test environment",
    )
    def setup_method(self, method):
        self.backend = ECDSABackend()

    @pytest.mark.skipif(
        not ECDSABackend().is_available,
        reason="ECDSA backend not available in test environment",
    )
    def test_name(self):
        """名称 → line 333"""
        assert self.backend.name == "ecdsa"

    @pytest.mark.skipif(
        not ECDSABackend().is_available,
        reason="ECDSA backend not available in test environment",
    )
    def test_is_available(self):
        assert self.backend.is_available

    @pytest.mark.skipif(
        not ECDSABackend().is_available,
        reason="ECDSA backend not available in test environment",
    )
    def test_generate_public_key_compressed(self):
        """压缩公钥 → lines 340-348"""
        result = self.backend.generate_public_key(PK, compressed=True)
        assert len(result) == 33

    @pytest.mark.skipif(
        not ECDSABackend().is_available,
        reason="ECDSA backend not available in test environment",
    )
    def test_generate_public_key_uncompressed(self):
        """非压缩公钥 → lines 349-350"""
        result = self.backend.generate_public_key(PK, compressed=False)
        assert len(result) == 65
        assert result[0] == 0x04

    def test_generate_public_key_not_available(self):
        """不可用时 RuntimeError → line 341"""
        backend = ECDSABackend()
        backend._available = False
        with pytest.raises(RuntimeError) as ctx:
            backend.generate_public_key(PK)
        assert "not available" in str(ctx.value)

    @pytest.mark.skipif(
        not ECDSABackend().is_available,
        reason="ECDSA backend not available in test environment",
    )
    def test_scalar_multiply(self):
        """回退标量乘法 → lines 358-362"""
        from src.core.secp256k1 import Secp256k1

        result = self.backend.scalar_multiply(5, Secp256k1.Gx, Secp256k1.Gy)
        assert len(result) == 2

    @pytest.mark.skipif(
        not ECDSABackend().is_available,
        reason="ECDSA backend not available in test environment",
    )
    def test_is_constant_time(self):
        """非恒时 → line 366"""
        assert not self.backend.is_constant_time()

    def test_check_availability_import_error(self):
        """Ecdsa 不可用 → 返回 False → lines 328-329"""
        with patch.dict("sys.modules", {"ecdsa": None}):
            backend = ECDSABackend()
            assert not backend._available
            assert not backend.is_available


# ===========================================================================
# Group 5: CryptoBackendManager 边界
# ===========================================================================


class TestCryptoBackendManagerEdge:
    """CryptoBackendManager 边界路径"""

    def setup_method(self, method):
        # 保存当前状态
        self._saved = crypto_manager._current_backend
        crypto_manager.reset_to_best_backend()

    def teardown_method(self, method):
        crypto_manager._current_backend = self._saved

    def test_current_backend_not_none(self):
        """current_backend 不为空"""
        backend = crypto_manager.current_backend
        assert backend is not None

    def test_is_constant_time(self):
        """is_constant_time 委托 → lines 529-530"""
        result = crypto_manager.is_constant_time()
        assert isinstance(result, bool)

    def test_set_backend_pure_python_const_time(self):
        """set_backend PURE_PYTHON with kwargs → lines 469-494"""
        result = crypto_manager.set_backend(BackendType.PURE_PYTHON, use_const_time=True)
        assert result
        assert crypto_manager.is_constant_time()
        # restore
        crypto_manager.set_backend(BackendType.PURE_PYTHON, use_const_time=False)

    def test_set_backend_coincurve(self):
        """set_backend COINCURVE"""
        original = crypto_manager.current_backend
        result = crypto_manager.set_backend(BackendType.COINCURVE)
        assert result
        assert "coincurve" in crypto_manager.current_backend.name
        # restore
        crypto_manager._current_backend = original

    def test_set_backend_nonexistent_raises(self):
        """未知后端 → ValueError → line 483"""
        # 从 _backends 中临时移除 COINCURVE 来触发 None 检查
        saved = crypto_manager._backends.pop(BackendType.COINCURVE, None)
        try:
            with pytest.raises(ValueError):
                crypto_manager.set_backend(BackendType.COINCURVE)
        finally:
            if saved is not None:
                crypto_manager._backends[BackendType.COINCURVE] = saved

    def test_get_available_backends(self):
        """列出可用后端 → lines 498-500"""
        backends = crypto_manager.get_available_backends()
        assert len(backends) > 0
        assert isinstance(backends, list)
        for bt, name in backends:
            assert isinstance(bt, BackendType)
            assert isinstance(name, str)

    def test_reset_to_best_backend(self):
        """Reset → line 441"""
        crypto_manager.reset_to_best_backend()
        assert crypto_manager.current_backend is not None

    def test_generate_public_key_perf_log(self):
        """带性能日志的 generate_public_key → lines 519-523"""
        # 需要 DEBUG 级别
        with patch.object(logging.getLogger("CryptoBackend"), "isEnabledFor", return_value=True):
            result = crypto_manager.generate_public_key(PK, compressed=True)
            assert len(result) == 33

    def test_current_backend_none_raises(self):
        """current_backend 为 None → RuntimeError → line 453"""
        saved = crypto_manager._current_backend
        try:
            crypto_manager._current_backend = None
            with pytest.raises(RuntimeError) as ctx:
                _ = crypto_manager.current_backend
            assert "No crypto backend" in str(ctx.value)
        finally:
            crypto_manager._current_backend = saved

    def test_set_backend_not_available_raises(self):
        """后端不可用 → RuntimeError → lines 486-487"""
        coincurve = crypto_manager._backends.get(BackendType.COINCURVE)
        if coincurve:
            saved_avail = coincurve._available
            try:
                coincurve._available = False
                with pytest.raises(RuntimeError) as ctx:
                    crypto_manager.set_backend(BackendType.COINCURVE)
                assert "not available" in str(ctx.value)
            finally:
                coincurve._available = saved_avail

    def test_set_backend_pure_python_new_instance(self):
        """PURE_PYTHON 不存在时创建新实例 → line 478"""
        saved = crypto_manager._backends.pop(BackendType.PURE_PYTHON, None)
        try:
            result = crypto_manager.set_backend(BackendType.PURE_PYTHON, use_const_time=False)
            assert result
        finally:
            if saved is not None:
                crypto_manager._backends[BackendType.PURE_PYTHON] = saved


# ===========================================================================
# Group 6: 便捷函数 (lines 544, 559, 573, 578)
# ===========================================================================


class TestConvenienceFunctions:
    """模块级便捷函数"""

    def setup_method(self, method):
        self._saved = crypto_manager._current_backend
        crypto_manager.reset_to_best_backend()

    def teardown_method(self, method):
        crypto_manager._current_backend = self._saved

    def test_get_crypto_backend(self):
        """返回 CryptoBackendManager → line 544"""
        result = get_crypto_backend()
        assert isinstance(result, CryptoBackendManager)
        assert result is crypto_manager

    def test_generate_public_key_conv(self):
        """便捷函数 → line 559"""
        result = generate_public_key(PK, compressed=True)
        assert len(result) == 33

    def test_set_crypto_backend(self):
        """set_crypto_backend → line 573"""
        result = set_crypto_backend(BackendType.PURE_PYTHON)
        assert result

    def test_get_available_backends(self):
        """get_available_backends → line 578"""
        backends = get_available_backends()
        assert len(backends) > 0


if __name__ == "__main__":
    unittest.main(verbosity=2)

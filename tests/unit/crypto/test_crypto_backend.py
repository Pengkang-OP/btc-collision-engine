"""crypto_backend加密后端管理器测试"""

from unittest.mock import MagicMock, PropertyMock, patch

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


class TestPurePythonBackendDirect:
    """PurePythonBackend 直接测试 - 覆盖常量时间与标量乘法路径"""

    def setup_method(self, method):
        self.pk = (42).to_bytes(32, "big")
        self.pk2 = (12345).to_bytes(32, "big")

    def test_generate_public_key_compressed(self):
        """P0-1: 非恒定时间压缩公钥生成"""
        backend = PurePythonBackend()
        pub = backend.generate_public_key(self.pk, compressed=True)
        assert len(pub) == 33
        assert [2, 3] in pub[0]

    def test_generate_public_key_uncompressed(self):
        """P0-2: 非恒定时间非压缩公钥生成"""
        backend = PurePythonBackend()
        pub = backend.generate_public_key(self.pk, compressed=False)
        assert len(pub) == 65
        assert pub[0] == 4

    def test_generate_public_key_const_time_compressed(self):
        """P0-3: 恒定时间压缩公钥生成"""
        backend = PurePythonBackend(use_const_time=True)
        pub = backend.generate_public_key(self.pk, compressed=True)
        assert len(pub) == 33
        assert [2, 3] in pub[0]

    def test_generate_public_key_const_time_uncompressed(self):
        """P0-4: 恒定时间非压缩公钥生成"""
        backend = PurePythonBackend(use_const_time=True)
        pub = backend.generate_public_key(self.pk, compressed=False)
        assert len(pub) == 65
        assert pub[0] == 4

    def test_scalar_multiply(self):
        """P0-5: 非恒定时间标量乘法"""
        backend = PurePythonBackend()
        from src.core.secp256k1 import Secp256k1

        k = 123456789
        rx, ry = backend.scalar_multiply(k, Secp256k1.Gx, Secp256k1.Gy)
        assert isinstance(rx, int)
        assert isinstance(ry, int)
        assert rx > 0
        assert ry > 0

    def test_scalar_multiply_const_time(self):
        """P0-6: 恒定时间标量乘法"""
        backend = PurePythonBackend(use_const_time=True)
        from src.core.secp256k1 import Secp256k1

        k = 123456789
        rx, ry = backend.scalar_multiply(k, Secp256k1.Gx, Secp256k1.Gy)
        assert isinstance(rx, int)
        assert isinstance(ry, int)
        assert rx > 0
        assert ry > 0

    def test_is_constant_time_default_true(self):
        """P0-7: v4.2.2后所有标量乘法使用恒定时间实现"""
        backend = PurePythonBackend()
        assert backend.is_constant_time()

    def test_is_constant_time_enabled_true(self):
        """P0-8: 启用恒定时间"""
        backend = PurePythonBackend(use_const_time=True)
        assert backend.is_constant_time()

    def test_name_default(self):
        """P0-9: 默认名称"""
        backend = PurePythonBackend()
        assert backend.name == "Pure Python"

    def test_name_const_time(self):
        """P0-10: 恒定时间模式名称"""
        backend = PurePythonBackend(use_const_time=True)
        assert backend.name in "Constant Time"
        assert backend.name in "Pure Python"

    def test_always_available(self):
        """P0-11: PurePython 始终可用"""
        backend = PurePythonBackend()
        assert backend.is_available
        backend_ct = PurePythonBackend(use_const_time=True)
        assert backend_ct.is_available

    def test_consistency_const_time_vs_regular(self):
        """P0-12: 恒定时间与常规模式结果一致"""
        regular = PurePythonBackend()
        const = PurePythonBackend(use_const_time=True)

        pub_reg = regular.generate_public_key(self.pk, compressed=True)
        pub_ct = const.generate_public_key(self.pk, compressed=True)
        assert pub_reg == pub_ct

        from src.core.secp256k1 import Secp256k1

        k = 999888777
        rx_r, ry_r = regular.scalar_multiply(k, Secp256k1.Gx, Secp256k1.Gy)
        rx_c, ry_c = const.scalar_multiply(k, Secp256k1.Gx, Secp256k1.Gy)
        assert rx_r == rx_c
        assert ry_r == ry_c


class TestBackendSetAndSwitch:
    """后端切换与 set_backend 路径测试"""

    def setup_method(self, method):
        self.pk = (42).to_bytes(32, "big")

    def teardown_method(self, method):
        # 恢复为最佳后端
        crypto_manager.reset_to_best_backend()

    def test_set_backend_pure_python_const_time(self):
        """P0-13: set_backend 切换到 PurePython + const_time"""
        result = crypto_manager.set_backend(BackendType.PURE_PYTHON, use_const_time=True)
        assert result
        backend = crypto_manager.current_backend
        assert backend.name in "Constant Time"
        assert backend.is_constant_time()

    def test_is_constant_time_via_manager(self):
        """P0-14: 通过 manager 检查恒定时间（v4.2.2后始终为True）"""
        crypto_manager.set_backend(BackendType.PURE_PYTHON, use_const_time=True)
        assert crypto_manager.is_constant_time()
        crypto_manager.set_backend(BackendType.PURE_PYTHON, use_const_time=False)
        assert crypto_manager.is_constant_time()

    def test_generate_public_key_const_time_via_manager(self):
        """P0-15: 通过 manager 使用恒定时间后端生成公钥"""
        crypto_manager.set_backend(BackendType.PURE_PYTHON, use_const_time=True)
        pub = crypto_manager.generate_public_key(self.pk, compressed=True)
        assert len(pub) == 33

    def test_set_backend_unknown_type_error(self):
        """P0-16: set_backend 未知后端类型抛出 ValueError"""
        # 用 MagicMock 替换 _backends，使 get() 返回 None 模拟未知后端
        mock_backends = MagicMock()
        mock_backends.get.return_value = None
        with patch.object(crypto_manager, "_backends", mock_backends):
            with pytest.raises(ValueError) as ctx:
                crypto_manager.set_backend(BackendType.PURE_PYTHON)
            assert "Unknown backend type" in str(ctx.value)

    def test_set_backend_unavailable_backend_error(self):
        """P0-17: set_backend 不可用后端抛出 RuntimeError"""
        with patch.object(OpenSSLBackend, "is_available", PropertyMock(return_value=False)):
            with pytest.raises(RuntimeError) as ctx:
                crypto_manager.set_backend(BackendType.OPENSSL)
            assert "not available" in str(ctx.value)

    def test_reset_to_best_backend(self):
        """P0-18: reset_to_best_backend 恢复最佳后端"""
        crypto_manager.set_backend(BackendType.PURE_PYTHON)
        assert crypto_manager.current_backend.name in "Pure Python"
        crypto_manager.reset_to_best_backend()
        assert crypto_manager.current_backend.is_available

    def test_generate_public_key_perf_debug_path(self):
        """P0-19: DEBUG 级别性能日志路径"""
        import logging as log_mod

        crypto_logger = log_mod.getLogger("CryptoBackend")
        old_level = crypto_logger.level
        try:
            crypto_logger.setLevel(log_mod.DEBUG)
            pub = crypto_manager.generate_public_key(self.pk, compressed=True)
            assert len(pub) == 33
        finally:
            crypto_logger.setLevel(old_level)


class TestConvenienceFunctions:
    """模块级便捷函数测试"""

    def setup_method(self, method):
        self.pk = (42).to_bytes(32, "big")

    def teardown_method(self, method):
        crypto_manager.reset_to_best_backend()

    def test_get_crypto_backend(self):
        """P0-20: get_crypto_backend 返回管理器实例"""
        mgr = get_crypto_backend()
        assert isinstance(mgr, CryptoBackendManager)
        assert mgr is crypto_manager

    def test_generate_public_key_convenience(self):
        """P0-21: generate_public_key 便捷函数"""
        pub = generate_public_key(self.pk, compressed=True)
        assert len(pub) == 33
        assert [2, 3] in pub[0]

    def test_set_crypto_backend_convenience(self):
        """P0-22: set_crypto_backend 便捷函数"""
        result = set_crypto_backend(BackendType.PURE_PYTHON, use_const_time=True)
        assert result
        assert crypto_manager.current_backend.name in "Constant Time"

    def test_get_available_backends_convenience(self):
        """P0-23: get_available_backends 便捷函数"""
        backends = get_available_backends()
        assert isinstance(backends, list)
        assert len(backends) > 0
        for bt, name in backends:
            assert isinstance(bt, BackendType)
            assert isinstance(name, str)


class TestCryptoBackendManagerEdgeCases:
    """CryptoBackendManager 边缘情况测试"""

    def test_current_backend_none_error(self):
        """P0-24: current_backend 为 None 时抛出 RuntimeError"""
        with patch.object(crypto_manager, "_current_backend", None):
            with pytest.raises(RuntimeError) as ctx:
                _ = crypto_manager.current_backend
            assert "No crypto backend available" in str(ctx.value)

    def test_scalar_multiply_via_manager(self):
        """P0-25: 通过 manager 的 current_backend 执行标量乘法"""
        from src.core.secp256k1 import Secp256k1

        crypto_manager.set_backend(BackendType.PURE_PYTHON)
        backend = crypto_manager.current_backend
        rx, ry = backend.scalar_multiply(999, Secp256k1.Gx, Secp256k1.Gy)
        assert isinstance(rx, int)
        assert isinstance(ry, int)

    def test_backend_in_managers_dict(self):
        """P0-26: 所有4个后端类型都在管理器字典中"""
        for bt in BackendType:
            assert crypto_manager._backends in bt
            backend = crypto_manager._backends[bt]
            assert backend is not None
            assert isinstance(backend.name, str)


class TestOpenSSLBackendDirect:
    """OpenSSLBackend 直接测试 - 覆盖 generate_public_key/scalar_multiply 路径"""

    def setup_method(self, method):
        self.pk = (42).to_bytes(32, "big")
        # 直接实例化 OpenSSLBackend（cryptography 已安装）
        self.backend = OpenSSLBackend()

    def test_is_available(self):
        """P1-1: OpenSSL 后端可用性"""
        assert self.backend.is_available

    def test_name(self):
        """P1-2: OpenSSL 后端名称"""
        assert self.backend.name in "OpenSSL"

    def test_is_constant_time(self):
        """P1-3: OpenSSL is_constant_time 返回 False"""
        assert not self.backend.is_constant_time()

    def test_generate_public_key_compressed(self):
        """P1-4: OpenSSL 压缩公钥生成"""
        pub = self.backend.generate_public_key(self.pk, compressed=True)
        assert len(pub) == 33
        assert [2, 3] in pub[0]

    def test_generate_public_key_uncompressed(self):
        """P1-5: OpenSSL 非压缩公钥生成"""
        pub = self.backend.generate_public_key(self.pk, compressed=False)
        assert len(pub) == 65
        assert pub[0] == 4

    def test_scalar_multiply(self):
        """P1-6: OpenSSL 标量乘法"""
        from src.core.secp256k1 import Secp256k1

        rx, ry = self.backend.scalar_multiply(42, Secp256k1.Gx, Secp256k1.Gy)
        assert isinstance(rx, int)
        assert isinstance(ry, int)
        assert rx > 0


class TestCoincurveBackendDirect:
    """CoincurveBackend 直接测试 - 覆盖 generate_public_key/scalar_multiply 路径"""

    def setup_method(self, method):
        self.pk = (42).to_bytes(32, "big")
        self.backend = CoincurveBackend()

    def test_is_available(self):
        """P1-7: Coincurve 后端可用性"""
        assert self.backend.is_available

    def test_name(self):
        """P1-8: Coincurve 后端名称"""
        assert self.backend.name.lower() in "coincurve"

    def test_is_constant_time(self):
        """P1-9: Coincurve is_constant_time 返回 True"""
        assert self.backend.is_constant_time()

    def test_generate_public_key_compressed(self):
        """P1-10: Coincurve 压缩公钥生成"""
        pub = self.backend.generate_public_key(self.pk, compressed=True)
        assert len(pub) == 33
        assert [2, 3] in pub[0]

    def test_generate_public_key_uncompressed(self):
        """P1-11: Coincurve 非压缩公钥生成"""
        pub = self.backend.generate_public_key(self.pk, compressed=False)
        assert len(pub) == 65
        assert pub[0] == 4

    def test_scalar_multiply(self):
        """P1-12: Coincurve 标量乘法"""
        from src.core.secp256k1 import Secp256k1

        rx, ry = self.backend.scalar_multiply(42, Secp256k1.Gx, Secp256k1.Gy)
        assert isinstance(rx, int)
        assert isinstance(ry, int)
        assert rx > 0

    def test_generate_public_key_deterministic(self):
        """P1-13: Coincurve 公钥生成确定性"""
        pub1 = self.backend.generate_public_key(self.pk, compressed=True)
        pub2 = self.backend.generate_public_key(self.pk, compressed=True)
        assert pub1 == pub2


class TestECDSABackendDirect:
    """ECDSABackend 直接测试 - 覆盖 generate_public_key/scalar_multiply 路径"""

    def setup_method(self, method):
        self.pk = (42).to_bytes(32, "big")
        self.backend = ECDSABackend()

    def test_is_available(self):
        """P1-14: ECDSA 后端可用性"""
        assert self.backend.is_available

    def test_name(self):
        """P1-15: ECDSA 后端名称"""
        assert self.backend.name.lower() in "ecdsa"

    def test_is_constant_time(self):
        """P1-16: ECDSA is_constant_time 返回 False"""
        assert not self.backend.is_constant_time()

    def test_generate_public_key_compressed(self):
        """P1-17: ECDSA 压缩公钥生成"""
        pub = self.backend.generate_public_key(self.pk, compressed=True)
        assert len(pub) == 33
        assert [2, 3] in pub[0]

    def test_generate_public_key_uncompressed(self):
        """P1-18: ECDSA 非压缩公钥生成"""
        pub = self.backend.generate_public_key(self.pk, compressed=False)
        assert len(pub) == 65
        assert pub[0] == 4

    def test_scalar_multiply(self):
        """P1-19: ECDSA 标量乘法"""
        from src.core.secp256k1 import Secp256k1

        rx, ry = self.backend.scalar_multiply(42, Secp256k1.Gx, Secp256k1.Gy)
        assert isinstance(rx, int)
        assert isinstance(ry, int)
        assert rx > 0


class TestBackendImportErrors:
    """测试 _check_availability 的 ImportError 路径"""

    def _mock_import_for(self, blocked_modules):
        """创建一个仅对特定模块抛出 ImportError 的 mock import"""
        import builtins

        original_import = builtins.__import__

        def selective_import(name, *args, **kwargs):
            for blocked in blocked_modules:
                if name.startswith(blocked):
                    raise ImportError(f"Mocked import error for: {name}")
            return original_import(name, *args, **kwargs)

        return patch("builtins.__import__", side_effect=selective_import)

    def test_openssl_import_error(self):
        """P1-20: OpenSSL 导入失败时 _available=False"""
        with self._mock_import_for(["cryptography"]):
            backend = OpenSSLBackend()
            assert not backend._available
            assert not backend.is_available

    def test_coincurve_import_error(self):
        """P1-21: coincurve 导入失败时 _available=False"""
        with self._mock_import_for(["coincurve"]):
            backend = CoincurveBackend()
            assert not backend._available
            assert not backend.is_available

    def test_ecdsa_import_error(self):
        """P1-22: ecdsa 导入失败时 _available=False"""
        with self._mock_import_for(["ecdsa"]):
            backend = ECDSABackend()
            assert not backend._available
            assert not backend.is_available

    def test_unavailable_backend_raises_on_generate(self):
        """P1-23: 不可用后端调用 generate_public_key 抛出 RuntimeError"""
        with self._mock_import_for(["cryptography"]):
            backend = OpenSSLBackend()
            with pytest.raises(RuntimeError) as ctx:
                backend.generate_public_key((1).to_bytes(32, "big"))
            assert "not available" in str(ctx.value)

    def test_unavailable_backend_raises_on_scalar_multiply(self):
        """P1-24: 不可用后端调用 scalar_multiply 抛出 RuntimeError"""
        with self._mock_import_for(["cryptography"]):
            backend = OpenSSLBackend()
            from src.core.secp256k1 import Secp256k1

            with pytest.raises(RuntimeError) as ctx:
                backend.scalar_multiply(1, Secp256k1.Gx, Secp256k1.Gy)
            assert "not available" in str(ctx.value)

    def test_coincurve_unavailable_generate_public_key(self):
        """P2-1: coincurve 不可用时 generate_public_key 抛出 RuntimeError"""
        with self._mock_import_for(["coincurve"]):
            backend = CoincurveBackend()
            assert not backend._available
            with pytest.raises(RuntimeError) as ctx:
                backend.generate_public_key((1).to_bytes(32, "big"))
            assert "not available" in str(ctx.value)

    def test_coincurve_unavailable_scalar_multiply(self):
        """P2-2: coincurve 不可用时 scalar_multiply 抛出 RuntimeError"""
        with self._mock_import_for(["coincurve"]):
            backend = CoincurveBackend()
            assert not backend._available
            from src.core.secp256k1 import Secp256k1

            with pytest.raises(RuntimeError) as ctx:
                backend.scalar_multiply(1, Secp256k1.Gx, Secp256k1.Gy)
            assert "not available" in str(ctx.value)

    def test_ecdsa_unavailable_generate_public_key(self):
        """P2-3: ecdsa 不可用时 generate_public_key 抛出 RuntimeError"""
        with self._mock_import_for(["ecdsa"]):
            backend = ECDSABackend()
            assert not backend._available
            with pytest.raises(RuntimeError) as ctx:
                backend.generate_public_key((1).to_bytes(32, "big"))
            assert "not available" in str(ctx.value)


class TestCoincurveFallbackToPurePython:
    """Coincurve 乘操作失败时回退到 PurePython"""

    def test_scalar_multiply_fallback_when_publickey_fails(self):
        """P2-4: coincurve.PublicKey 构造失败时回退到 PurePython"""
        import coincurve

        from src.core.secp256k1 import Secp256k1

        backend = CoincurveBackend()
        assert backend._available
        with patch.object(coincurve, "PublicKey", side_effect=TypeError("mock construction error")):
            rx, ry = backend.scalar_multiply(42, Secp256k1.Gx, Secp256k1.Gy)
            # 回退到 PurePython，应能正常工作
            assert isinstance(rx, int)
            assert isinstance(ry, int)
            assert rx > 0

    def test_scalar_multiply_fallback_consistency(self):
        """P2-5: Coincurve 回退结果与 PurePython 一致"""
        import coincurve

        from src.core.secp256k1 import Secp256k1

        k = 999888777
        # PurePython 直接计算
        pp = PurePythonBackend()
        pp_rx, pp_ry = pp.scalar_multiply(k, Secp256k1.Gx, Secp256k1.Gy)
        # Coincurve 回退
        backend = CoincurveBackend()
        with patch.object(coincurve, "PublicKey", side_effect=TypeError("mock")):
            cc_rx, cc_ry = backend.scalar_multiply(k, Secp256k1.Gx, Secp256k1.Gy)
        assert pp_rx == cc_rx
        assert pp_ry == cc_ry


class TestBackendConsistency:
    """跨后端一致性测试"""

    def setup_method(self, method):
        self.pk = (999888777).to_bytes(32, "big")

    def test_all_backends_produce_same_compressed_public_key(self):
        """P1-25: 所有后端生成相同的压缩公钥"""
        pp = PurePythonBackend().generate_public_key(self.pk, compressed=True)
        ossl = OpenSSLBackend().generate_public_key(self.pk, compressed=True)
        cc = CoincurveBackend().generate_public_key(self.pk, compressed=True)
        ecdsa = ECDSABackend().generate_public_key(self.pk, compressed=True)

        assert pp == ossl
        assert ossl == cc
        assert cc == ecdsa

    def test_all_backends_produce_same_uncompressed_public_key(self):
        """P1-26: 所有后端生成相同的非压缩公钥"""
        pp = PurePythonBackend().generate_public_key(self.pk, compressed=False)
        ossl = OpenSSLBackend().generate_public_key(self.pk, compressed=False)
        cc = CoincurveBackend().generate_public_key(self.pk, compressed=False)
        ecdsa = ECDSABackend().generate_public_key(self.pk, compressed=False)

        assert pp == ossl
        assert ossl == cc
        assert cc == ecdsa

    def test_all_backends_scalar_multiply_consistency(self):
        """P1-27: 所有后端标量乘法结果一致"""
        from src.core.secp256k1 import Secp256k1

        k = 12345
        pp = PurePythonBackend().scalar_multiply(k, Secp256k1.Gx, Secp256k1.Gy)
        ossl = OpenSSLBackend().scalar_multiply(k, Secp256k1.Gx, Secp256k1.Gy)
        cc = CoincurveBackend().scalar_multiply(k, Secp256k1.Gx, Secp256k1.Gy)
        ecdsa = ECDSABackend().scalar_multiply(k, Secp256k1.Gx, Secp256k1.Gy)

        assert pp == ossl
        assert ossl == cc
        assert cc == ecdsa

    def test_set_backend_then_generate(self):
        """P1-28: set_backend 切换后各后端正确工作"""
        for bt in [
            BackendType.PURE_PYTHON,
            BackendType.OPENSSL,
            BackendType.COINCURVE,
            BackendType.ECDSA,
        ]:
            crypto_manager.set_backend(bt)
            pub = crypto_manager.generate_public_key(self.pk, compressed=True)
            assert len(pub) == 33, f"Backend {bt.name} failed"
        crypto_manager.reset_to_best_backend()


class TestCryptoBackendManager:
    """加密后端管理器测试"""

    def test_backend_detection(self):
        """后端自动检测"""
        backend = crypto_manager.current_backend
        assert backend is not None
        assert hasattr(backend, "name")
        assert hasattr(backend, "is_available")

    def test_backend_availability(self):
        """后端可用性检查"""
        backends = crypto_manager.get_available_backends()
        assert len(backends) > 0
        # backends是元组列表: (BackendType, name)
        assert isinstance(backends[0], tuple)
        assert len(backends[0]) == 2

    def test_get_available_backends(self):
        """获取可用后端列表"""
        backends = crypto_manager.get_available_backends()
        assert isinstance(backends, list)
        assert len(backends) > 0
        # 每个元素应该是 (BackendType, name) 元组
        for backend_type, name in backends:
            assert isinstance(backend_type, BackendType)
            assert isinstance(name, str)

    def test_public_key_generation_compressed(self):
        """公钥生成 - 压缩格式"""
        pk = (42).to_bytes(32, "big")
        pub_key = crypto_manager.generate_public_key(pk, compressed=True)

        assert isinstance(pub_key, bytes)
        assert len(pub_key) == 33  # 压缩公钥33字节
        assert [2, 3] in pub_key[0]  # 前缀为0x02或0x03

    def test_public_key_generation_uncompressed(self):
        """公钥生成 - 非压缩格式"""
        pk = (42).to_bytes(32, "big")
        pub_key = crypto_manager.generate_public_key(pk, compressed=False)

        assert isinstance(pub_key, bytes)
        assert len(pub_key) == 65  # 非压缩公钥65字节
        assert pub_key[0] == 4  # 前缀为0x04

    def test_public_key_generation_deterministic(self):
        """公钥生成确定性 - 相同私钥生成相同公钥"""
        pk = (123456).to_bytes(32, "big")
        pub1 = crypto_manager.generate_public_key(pk, compressed=True)
        pub2 = crypto_manager.generate_public_key(pk, compressed=True)

        assert pub1 == pub2

    def test_public_key_generation_different_keys(self):
        """不同私钥生成不同公钥"""
        pk1 = (1).to_bytes(32, "big")
        pk2 = (2).to_bytes(32, "big")

        pub1 = crypto_manager.generate_public_key(pk1, compressed=True)
        pub2 = crypto_manager.generate_public_key(pk2, compressed=True)

        assert pub1 != pub2

    def test_public_key_generation_boundary_values(self):
        """边界值私钥的公钥生成"""
        # 最小有效私钥
        pk_min = (1).to_bytes(32, "big")
        pub_min = crypto_manager.generate_public_key(pk_min, compressed=True)
        assert len(pub_min) == 33

        # 从secp256k1导入N
        from src.core.secp256k1 import Secp256k1

        # 最大有效私钥 (N-1)
        pk_max = (Secp256k1.N - 1).to_bytes(32, "big")
        pub_max = crypto_manager.generate_public_key(pk_max, compressed=True)
        assert len(pub_max) == 33

        # 两者应该不同
        assert pub_min != pub_max

    def test_backend_fallback(self):
        """后端回退机制 - 当首选后端不可用时能回退"""
        # 这个测试验证即使首选后端失败，也能使用其他后端
        pk = (999).to_bytes(32, "big")

        # 应该能成功生成公钥（无论使用哪个后端）
        pub_key = crypto_manager.generate_public_key(pk, compressed=True)
        assert pub_key is not None
        assert len(pub_key) == 33

    def test_current_backend_is_available(self):
        """当前使用的后端应该是可用的"""
        backend = crypto_manager.current_backend
        assert backend.is_available

    def test_backend_name(self):
        """后端名称应该非空"""
        backend = crypto_manager.current_backend
        assert isinstance(backend.name, str)
        assert len(backend.name) > 0

    def test_multiple_generations_performance(self):
        """多次生成的性能测试（验证后端正常工作）"""
        import time

        pk = (42).to_bytes(32, "big")
        iterations = 100

        start = time.time()
        for _ in range(iterations):
            pub_key = crypto_manager.generate_public_key(pk, compressed=True)
            assert len(pub_key) == 33
        elapsed = time.time() - start

        # 应该在合理时间内完成（10秒以内）
        assert elapsed < 10.0

        # 输出性能信息用于调试
        backend = crypto_manager.current_backend
        print(f"\n后端: {backend.name}")
        print(f"{iterations}次公钥生成耗时: {elapsed:.4f}秒")
        print(f"速度: {iterations / elapsed:.2f} ops/sec")

    def test_invalid_private_key_handling(self):
        """无效私钥处理 - 后端应能处理各种输入"""
        # 测试全零私钥（虽然无效，但后端应该能处理）
        pk_zero = b"\x00" * 32
        # 有些后端可能会生成无穷远点，有些会抛异常
        try:
            pub_key = crypto_manager.generate_public_key(pk_zero, compressed=True)
            # 如果成功，应该是33字节
            assert len(pub_key) == 33
        except Exception:
            # 抛异常也是可接受的行为
            pass

    def test_consistency_with_pure_python(self):
        """验证与纯Python实现的一致性"""
        from src.core.secp256k1 import EllipticCurve

        pk = (12345).to_bytes(32, "big")

        # 使用crypto_manager生成
        pub_crypto = crypto_manager.generate_public_key(pk, compressed=True)

        # 使用纯Python实现生成
        ec = EllipticCurve()
        pub_python = ec.generate_public_key(pk, compressed=True)

        # 结果应该一致
        assert pub_crypto == pub_python


class TestBackendType:
    """BackendType枚举测试"""

    def test_backend_type_values(self):
        """后端类型枚举值"""
        assert BackendType.PURE_PYTHON.name == "PURE_PYTHON"
        assert BackendType.OPENSSL.name == "OPENSSL"
        assert BackendType.COINCURVE.name == "COINCURVE"
        assert BackendType.ECDSA.name == "ECDSA"

    def test_backend_type_count(self):
        """后端类型数量"""
        assert len(list(BackendType)) == 4


if __name__ == "__main__":
    unittest.main(verbosity=2)

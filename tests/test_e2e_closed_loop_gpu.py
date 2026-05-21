"""端到端闭环测试（GPU 引擎）

闭环(Closed-Loop)概念: 使用已知密钥对, 通过 GPU 引擎的内部
回调机制验证 Match → WIF/地址 的完整闭环。

GPU 引擎测试策略:
- 使用 Mock 的 GPUDeviceManager 完全绕过真实 OpenCL 初始化
- 直接调用引擎内部的 _safe_invoke_match_callback 测试回调闭环
- 验证引擎生命周期 start/stop 闭环
- 验证统计/设备信息在 stop 后仍可访问

注意: GPU 引擎的匹配检测在 GPU 内核中执行(pyopencl C扩展),
无法 Mock。本测试专注于 Python 层的回调闭环和生命周期闭环。
"""

import os
import time
from unittest.mock import Mock, patch

import pytest

# GPU 引擎
from src.collision.gpu.engine import GPUCollisionEngine

# 使用独立的地址生成器（与引擎内部解耦，验证引擎的真实输出）
from src.core.address_generator import P2PKHAddressGenerator
from src.core.wif import WIF

# ============================================================================
# 已知密钥对常量（动态推导，避免硬编码风险）
# ============================================================================

def _derive_known_keypair(k: int):
    """从整数 k 推导完整密钥对 (private_key, address, wif)"""
    private_key = k.to_bytes(32, "big")
    gen = P2PKHAddressGenerator()
    address, _, _ = gen.generate_address(private_key)
    wif = WIF.encode(private_key, compressed=True)
    return private_key, address, wif


_K1_PK, _K1_ADDR, _K1_WIF = _derive_known_keypair(1)
_K2_PK, _K2_ADDR, _K2_WIF = _derive_known_keypair(2)


# ============================================================================
# Fixture: Mock GPU 引擎（绕过真实 OpenCL 初始化）
# ============================================================================

@pytest.fixture
def mock_gpu_engine():
    """创建预配置的 GPU 引擎，使用 Mock 的 GPUDeviceManager
    完全绕过真实 OpenCL 初始化。

    Yields:
        tuple: (engine, mock_device_manager)
    """
    with (
        patch("src.collision.gpu.engine.GPUDeviceManager") as MockDeviceManager,
        patch("src.collision.gpu.engine.PYOPENCL_AVAILABLE", True),
    ):
        # 创建 Mock 设备管理器
        mock_mgr = Mock()
        mock_mgr.initialize = Mock()
        mock_mgr.device = Mock()
        mock_mgr.device.name = "Mock GPU"
        mock_mgr.device.vendor = "NVIDIA Corporation"
        mock_mgr.context = Mock()
        mock_mgr.kernel = Mock()
        mock_mgr.async_executor = None  # 不使用异步执行器
        mock_mgr.memory_pool = Mock()
        mock_mgr.get_device_info = Mock(return_value={
            "name": "Mock GPU",
            "vendor": "NVIDIA Corporation",
            "type": "GPU",
            "device_index": 0,
            "batch_size": 65536,
        })
        mock_mgr.cleanup = Mock()
        MockDeviceManager.return_value = mock_mgr

        yield mock_mgr


@pytest.fixture
def gpu_engine_no_targets(mock_gpu_engine):
    """创建无目标地址的 GPU 引擎"""
    engine = GPUCollisionEngine(
        targets=set(),
        device_index=0,
        data_logging_enabled=False,
        use_enhanced_monitoring=False,
    )
    yield engine
    if engine.is_running():
        engine.stop()


@pytest.fixture
def gpu_engine_with_targets(mock_gpu_engine):
    """创建有已知目标地址的 GPU 引擎"""
    engine = GPUCollisionEngine(
        targets={_K1_ADDR},
        device_index=0,
        data_logging_enabled=False,
        use_enhanced_monitoring=False,
    )
    yield engine
    if engine.is_running():
        engine.stop()


# ============================================================================
# Task 11: TestGPUEngineInitClosedLoop - GPU 引擎初始化闭环
# ============================================================================

@pytest.mark.gpu
class TestGPUEngineInitClosedLoop:
    """GPU 引擎初始化闭环测试"""

    def test_gpu_engine_init_with_known_targets(self, gpu_engine_with_targets):
        """使用已知地址初始化 → 验证 targets 正确加载"""
        engine = gpu_engine_with_targets
        assert engine is not None
        assert _K1_ADDR in engine.targets, (
            f"已知地址应在 targets 中，实际: {engine.targets}"
        )

    def test_gpu_engine_init_with_empty_targets(self, gpu_engine_no_targets):
        """无目标地址初始化 → 验证 targets 为空"""
        engine = gpu_engine_no_targets
        assert engine is not None
        assert len(engine.targets) == 0

    def test_gpu_engine_device_info(self, gpu_engine_with_targets):
        """验证 get_device_info() 返回 GPU 类型"""
        engine = gpu_engine_with_targets
        info = engine.get_device_info()

        assert isinstance(info, dict)
        assert info["type"] == "GPU"
        assert "name" in info
        assert "vendor" in info
        assert "device_index" in info
        assert "batch_size" in info

    def test_gpu_engine_stats_initial(self, gpu_engine_with_targets):
        """初始 stats 状态正确"""
        engine = gpu_engine_with_targets
        stats = engine.get_stats()

        assert stats is not None
        assert stats.total_checked == 0
        assert len(stats.matches) == 0

    def test_gpu_engine_context_manager(self, mock_gpu_engine):
        """with 语句自动 stop"""
        with GPUCollisionEngine(
            targets=set(),
            device_index=0,
            data_logging_enabled=False,
            use_enhanced_monitoring=False,
        ) as engine:
            assert engine is not None

        # 退出 with 块后应已停止
        assert not engine.is_running()

    def test_gpu_engine_batch_size_property(self, gpu_engine_with_targets):
        """batch_size 属性可读写"""
        engine = gpu_engine_with_targets
        bs = engine.batch_size
        assert isinstance(bs, int)
        assert bs > 0

        # 设置新的 batch_size
        engine.batch_size = 100000
        assert engine.batch_size == 100000


# ============================================================================
# Task 12: TestGPUEngineMatchCallbackClosedLoop - GPU 匹配回调闭环
# ============================================================================

@pytest.mark.gpu
class TestGPUEngineMatchCallbackClosedLoop:
    """GPU 匹配回调闭环测试"""

    def test_gpu_safe_invoke_match_callback(self, mock_gpu_engine):
        """直接调用 _safe_invoke_match_callback → 验证 on_match 被调用"""
        callback_results = []

        def on_match(pk, addr, wif):
            callback_results.append({"pk": pk, "addr": addr, "wif": wif})

        engine = GPUCollisionEngine(
            targets={_K1_ADDR},
            on_match=on_match,
            device_index=0,
            data_logging_enabled=False,
            use_enhanced_monitoring=False,
        )

        # 直接调用内部回调方法
        result = engine._safe_invoke_match_callback(_K1_PK, _K1_ADDR, _K1_WIF)
        assert result is True, "_safe_invoke_match_callback 应返回 True"

        assert len(callback_results) == 1
        assert callback_results[0]["pk"] == _K1_PK
        assert callback_results[0]["addr"] == _K1_ADDR
        assert callback_results[0]["wif"] == _K1_WIF

    def test_gpu_match_callback_wif_roundtrip(self, mock_gpu_engine):
        """回调中的 WIF → decode → 相同 private_key → 相同地址"""
        callback_data = {}

        def on_match(pk, addr, wif):
            callback_data["pk"] = pk
            callback_data["addr"] = addr
            callback_data["wif"] = wif

        engine = GPUCollisionEngine(
            targets={_K2_ADDR},
            on_match=on_match,
            device_index=0,
            data_logging_enabled=False,
            use_enhanced_monitoring=False,
        )

        engine._safe_invoke_match_callback(_K2_PK, _K2_ADDR, _K2_WIF)

        # WIF 往返验证
        decoded_pk, is_compressed = WIF.decode(callback_data["wif"])
        assert decoded_pk == callback_data["pk"]
        assert is_compressed is True

        # 重新推导地址
        gen = P2PKHAddressGenerator()
        re_addr, _, _ = gen.generate_address(decoded_pk)
        assert re_addr == callback_data["addr"]

    def test_gpu_match_callback_timeout_handling(self, mock_gpu_engine):
        """超时回调不崩溃（Windows 线程超时）"""
        if os.name != "nt":
            pytest.skip("超时测试仅适用于 Windows (os.name == 'nt')")

        def slow_callback(pk, addr, wif):
            time.sleep(10)  # 远超 5 秒超时

        engine = GPUCollisionEngine(
            targets={_K1_ADDR},
            on_match=slow_callback,
            device_index=0,
            data_logging_enabled=False,
            use_enhanced_monitoring=False,
        )

        # 应返回 False（超时）
        result = engine._safe_invoke_match_callback(_K1_PK, _K1_ADDR, _K1_WIF)
        assert result is False, "超时的回调应返回 False"

    def test_gpu_match_callback_without_on_match(self, mock_gpu_engine):
        """没有 on_match 回调时返回 True"""
        engine = GPUCollisionEngine(
            targets={_K1_ADDR},
            device_index=0,
            data_logging_enabled=False,
            use_enhanced_monitoring=False,
        )

        # on_match 未设置，应返回 True
        result = engine._safe_invoke_match_callback(_K1_PK, _K1_ADDR, _K1_WIF)
        assert result is True

    def test_gpu_match_callback_data_integrity(self, mock_gpu_engine):
        """回调参数 (pk, addr, wif) 三元组完整性"""
        results = []

        def on_match(pk, addr, wif):
            results.append({
                "pk_len": len(pk),
                "addr_start": addr[0],
                "wif_start": wif[0],
            })

        engine = GPUCollisionEngine(
            targets={_K1_ADDR},
            on_match=on_match,
            device_index=0,
            data_logging_enabled=False,
            use_enhanced_monitoring=False,
        )

        engine._safe_invoke_match_callback(_K1_PK, _K1_ADDR, _K1_WIF)

        assert len(results) == 1
        r = results[0]
        assert r["pk_len"] == 32, "私钥应 32 字节"
        assert r["addr_start"] == "1", "P2PKH 地址以 '1' 开头"
        assert r["wif_start"] in ("K", "L"), "压缩 WIF 以 K 或 L 开头"

    def test_gpu_match_callback_exception_handling(self, mock_gpu_engine):
        """回调抛出异常时不应崩溃，返回 False"""
        def failing_callback(pk, addr, wif):
            raise RuntimeError("模拟回调异常")

        engine = GPUCollisionEngine(
            targets={_K1_ADDR},
            on_match=failing_callback,
            device_index=0,
            data_logging_enabled=False,
            use_enhanced_monitoring=False,
        )

        result = engine._safe_invoke_match_callback(_K1_PK, _K1_ADDR, _K1_WIF)
        assert result is False, "异常回调应返回 False"


# ============================================================================
# Task 13: TestGPUEngineLifecycleClosedLoop - GPU 生命周期闭环
# ============================================================================

@pytest.mark.gpu
class TestGPUEngineLifecycleClosedLoop:
    """GPU 引擎生命周期闭环测试"""

    def test_gpu_start_stop_lifecycle(self, gpu_engine_no_targets):
        """start(random) → is_running() → stop → is_running() False"""
        engine = gpu_engine_no_targets

        assert not engine.is_running()

        engine.start(mode="random")
        # 给后台线程一点时间
        time.sleep(0.3)
        assert engine.is_running(), "start 后应 running"

        engine.stop()
        time.sleep(0.3)
        assert not engine.is_running(), "stop 后应 not running"

    def test_gpu_double_stop_idempotent(self, gpu_engine_no_targets):
        """stop() 两次不崩溃（幂等性）"""
        engine = gpu_engine_no_targets

        engine.start(mode="random")
        time.sleep(0.3)

        # 第一次 stop
        engine.stop()
        # 第二次 stop（应安全跳过）
        engine.stop()

        assert not engine.is_running()

    def test_gpu_stats_persist_after_stop(self, gpu_engine_no_targets):
        """stop 后 get_stats() 仍可访问"""
        engine = gpu_engine_no_targets

        engine.start(mode="random")
        time.sleep(0.3)
        engine.stop()

        stats = engine.get_stats()
        assert stats is not None

    def test_gpu_engine_get_stats_during_run(self, gpu_engine_no_targets):
        """运行中 get_stats() 可访问"""
        engine = gpu_engine_no_targets

        engine.start(mode="random")
        time.sleep(0.3)

        stats = engine.get_stats()
        assert stats is not None

        engine.stop()

    def test_gpu_engine_device_info_after_stop(self, gpu_engine_no_targets):
        """stop 后 get_device_info() 仍可访问"""
        engine = gpu_engine_no_targets

        engine.start(mode="random")
        time.sleep(0.3)
        engine.stop()

        info = engine.get_device_info()
        assert isinstance(info, dict)
        assert info["type"] == "GPU"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

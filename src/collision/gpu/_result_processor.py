"""GPU 碰撞结果处理器.

从 GPUCollisionEngine 中提取匹配结果处理逻辑，
负责将 GPU 计算出的匹配结果安全地分发给用户回调。

职责:
- 安全调用匹配回调（超时控制、异常隔离）
- 处理 GPU 匹配结果（常规模式：完整私钥数组）
- 处理 GPU 匹配结果（PRNG 模式：种子+索引推导私钥）

版本: v1.1.0 (CALL-1 - 超时保护工具集成)
创建日期: 2026-05-20
"""

from typing import TYPE_CHECKING

from src.utils import get_configured_logger
from src.utils.timeout import invoke_with_timeout

from ..events import EngineMatchEvent

# 回调类型

if TYPE_CHECKING:
    from .engine import GPUCollisionEngine

logger = get_configured_logger(__name__)

__all__ = ["GPUResultProcessor"]


class GPUResultProcessor:
    """GPU 碰撞结果处理器.

    封装匹配结果的验证、去重和回调分发逻辑。
    通过 engine 引用访问所有引擎状态，不复制状态。
    """

    def __init__(self, engine: "GPUCollisionEngine") -> None:
        """初始化结果处理器.

        Args:
            engine: GPUCollisionEngine 实例引用

        """
        self._engine = engine

    # ========== 匹配回调安全调用 ==========

    def safe_invoke_match_callback(self, private_key: bytes, address: str, wif: str) -> bool:
        """安全调用匹配回调函数，提供超时控制与异常隔离.

        使用统一的 invoke_with_timeout 工具实现跨平台超时保护。

        Args:
            private_key: 私钥字节串
            address: 匹配的比特币地址
            wif: WIF 格式私钥

        Returns:
            True 表示回调执行成功，False 表示超时或异常

        """
        engine = self._engine
        on_match = engine.on_match
        if not on_match:
            return True
        try:
            timeout = getattr(engine, "_match_callback_timeout", 5)
            return invoke_with_timeout(
                on_match,
                args=(private_key, address, wif),
                timeout=timeout,
                callback_name="on_match",
            )
        except Exception as e:
            logger.error("匹配回调调用失败: %s", e, exc_info=True)
            return False

    # ========== 匹配结果处理 ==========

    def process_matches(self, private_keys: bytes, matches: list[dict[str, int]]) -> None:
        """处理 GPU 匹配结果（常规模式：完整私钥数组）.

        从 GPUCollisionEngine._process_gpu_matches 提取。

        对每个匹配执行：
        1. 从私钥数组中提取对应私钥
        2. 去重过滤
        3. 编码 WIF 并记录统计
        4. 发布事件总线事件
        5. 调用用户匹配回调

        Args:
            private_keys: 私钥字节数组（完整 batch 的私钥数据）
            matches: GPU 返回的匹配列表 [{key_index, target_index}, ...]

        """
        engine = self._engine
        from src.core.wif import WIF

        for match in matches:
            key_idx = match["key_index"]
            # S-2修复: 添加边界检查，防止越界访问
            if key_idx * 32 + 32 > len(private_keys):
                logger.warning(
                    f"私钥索引越界: key_idx={key_idx}, private_keys长度={len(private_keys)}",
                )
                continue
            private_key = private_keys[key_idx * 32 : (key_idx + 1) * 32]
            if engine.dedup_filter is not None and not engine.dedup_filter.check_and_add(
                private_key,
            ):
                continue
            target_idx = match["target_index"]
            # G1修复: 检查目标索引是否越界
            if target_idx >= len(engine._device_manager.target_list):
                logger.warning(
                    f"目标索引越界: {target_idx} >= {len(engine._device_manager.target_list)}，跳过匹配",
                )
                continue
            address = engine._device_manager.target_list[target_idx]
            wif = WIF.encode(private_key, compressed=True)
            if engine.stats is not None:
                engine.stats.add_match(private_key, address)

            # v3.2.0: 发布匹配事件
            match_event = EngineMatchEvent(  # type: ignore[call-arg]
                private_key=private_key,
                address=address,
                wif=wif,
                target_address=address,
                source="gpu_collision_engine",
            )
            engine.event_bus.publish(match_event)

            # 向后兼容: 调用传统回调
            if not self.safe_invoke_match_callback(private_key, address, wif):
                logger.warning("GPU匹配回调处理失败，跳过地址: [MASKED_ADDRESS]")

    def process_matches_prng(self, seed: bytes, matches: list[dict[str, int]]) -> None:
        """处理 GPU 匹配结果（PRNG 模式：种子+索引推导私钥）.

        从 GPUCollisionEngine._process_gpu_matches_prng 提取。

        PRNG 模式下，GPU 内核使用 seed + key_index 计算私钥，
        因此 CPU 侧从 seed 和 key_index 即可重建私钥。

        C-4修复: 添加索引越界检查，防止 IndexError 崩溃和潜在的越界访问。

        Args:
            seed: 32 字节随机种子
            matches: GPU 返回的匹配列表 [{key_index, target_index}, ...]

        """
        engine = self._engine
        from src.core.secp256k1 import Secp256k1
        from src.core.wif import WIF

        seed_int = int.from_bytes(seed, "big")
        for match in matches:
            key_idx = match["key_index"]
            # C-4修复: 检查 key_idx 是否可能导致整数溢出或越界
            try:
                key_int = (seed_int + key_idx) % (2**256)
            except (OverflowError, ValueError):
                logger.warning("PRNG模式key_idx计算失败: key_idx=%s, 跳过匹配", key_idx)
                continue
            # P1-3修复: 验证私钥范围 (1 <= k < N)，与 GPU 内核一致
            # GPU 内核在 batch_check.cl:1240 中拒绝 k==0 或 k>=N 的私钥，
            # 如果 GPU 端的验证被跳过，重建的私钥也应该是无效的，不应继续处理。
            if key_int == 0 or key_int >= Secp256k1.N:
                logger.warning(
                    "PRNG模式恢复的私钥超出secp256k1有效范围: key_idx=%s, 跳过匹配",
                    key_idx,
                )
                continue
            private_key = key_int.to_bytes(32, "big")
            if engine.dedup_filter is not None and not engine.dedup_filter.check_and_add(
                private_key,
            ):
                continue
            target_idx = match["target_index"]
            # G1修复: 检查目标索引是否越界
            if target_idx >= len(engine._device_manager.target_list):
                logger.warning(
                    f"目标索引越界: {target_idx} >= {len(engine._device_manager.target_list)}，跳过匹配",
                )
                continue
            address = engine._device_manager.target_list[target_idx]
            wif = WIF.encode(private_key, compressed=True)
            if engine.stats is not None:
                engine.stats.add_match(private_key, address)

            # v3.2.0: 发布匹配事件 (PRNG模式)
            match_event = EngineMatchEvent(  # type: ignore[call-arg]
                private_key=private_key,
                address=address,
                wif=wif,
                target_address=address,
                source="gpu_collision_engine",
            )
            engine.event_bus.publish(match_event)

            # 向后兼容: 调用传统回调
            if not self.safe_invoke_match_callback(private_key, address, wif):
                logger.warning("GPU匹配回调处理失败，跳过地址: [MASKED_ADDRESS]")

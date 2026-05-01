"""示例碰撞插件"""

import time
import threading
import secrets
from typing import Set, Optional

# P3-3: 统一回调类型别名
from ..types import ProgressCallback, MatchCallback, CompleteCallback
from src.collision.plugins.base_plugin import CollisionPlugin
from src.collision.collision_stats import CollisionStats
from src.core.address_generator import P2PKHAddressGenerator

# v2.2.1迁移: 使用crypto_backend替代secp256k1.py
# Secp256k1.N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
SECP256K1_N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141


class ExamplePlugin(CollisionPlugin):
    """示例碰撞插件 - 实现随机碰撞策略"""

    @property
    def name(self) -> str:
        """插件名称"""
        return "example"

    @property
    def description(self) -> str:
        """插件描述"""
        return "示例碰撞插件，实现随机碰撞策略"

    def initialize(self, targets: Set[str], **kwargs) -> None:
        """
        初始化插件

        参数:
            targets: 目标地址集合
            kwargs: 其他参数
        """
        self.targets = targets
        self.generator = P2PKHAddressGenerator()
        self.stats = CollisionStats()
        self._stop_event = threading.Event()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self.progress_interval = kwargs.get("progress_interval", 1000)

    def start(
        self,
        on_progress: Optional[ProgressCallback] = None,
        on_match: Optional[MatchCallback] = None,
        on_complete: Optional[CompleteCallback] = None,
    ) -> None:
        """
        开始碰撞

        参数:
            on_progress: 进度回调
            on_match: 匹配回调
            on_complete: 完成回调
        """
        if self._running:
            return

        self.on_progress = on_progress
        self.on_match = on_match
        self.on_complete = on_complete
        self._stop_event.clear()
        self._running = True
        self.stats = CollisionStats()
        self.stats.start_time = time.time()

        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        """运行碰撞逻辑"""
        count = 0

        while not self._stop_event.is_set():
            # 生成随机私钥
            private_key = secrets.token_bytes(32)
            k = int.from_bytes(private_key, "big")
            # v2.2.1迁移: 使用曲线阶数常量（原Secp256k1.N）
            if k < 1 or k >= SECP256K1_N:
                continue

            # 生成地址
            address, compressed_pub, _ = self.generator.generate_address(private_key)
            count += 1

            # 检查匹配
            if address in self.targets:
                from src.core.wif import WIF

                wif = WIF.encode(private_key, compressed=True)
                self.stats.add_match(private_key, address)
                if self.on_match:
                    self.on_match(private_key, address, wif)
                # 找到匹配后停止
                self._stop_event.set()

            # 进度回调
            if count % self.progress_interval == 0:
                self.stats.update(count)
                if self.on_progress:
                    self.on_progress(self.stats)

        self.stats.update(count)
        if self.on_complete:
            self.on_complete(self.stats)
        self._running = False

    def stop(self) -> None:
        """停止碰撞"""
        self._stop_event.set()
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def is_running(self) -> bool:
        """是否正在运行"""
        return self._running and self._thread is not None and self._thread.is_alive()

    def get_stats(self) -> CollisionStats:
        """获取统计数据"""
        return self.stats

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
比特币私钥碰撞引擎 - 向后兼容模块

v5.0.0: 已移除 _LegacyTargetResolver 回退路径和 CollisionCLI 旧版 CLI。
请使用 key_collision_cli.py 或 start_menu.py 启动程序。

此文件仍保留以下类和常量的向后兼容导出：
- TargetResolver, CollisionStats, CheckpointManager
- DeduplicationFilter, KeyCollisionEngine
- GPUCollisionEngine, MultiGPUCollisionEngine

作者: BTC Project
版本: v5.0.0
"""

import os
import time
import secrets
import threading
import logging
import json
import hashlib
from datetime import datetime
from typing import Set, List, Dict, Optional, Callable, Tuple

# 尝试导入coincurve以提升性能
try:
    import coincurve
    COINCURVE_AVAILABLE = True
    logging.debug("coincurve库已加载，将使用高性能加密后端")
except ImportError:
    COINCURVE_AVAILABLE = False
    logging.debug("coincurve库未安装，将使用纯Python实现")

# 尝试导入 p2pkh_simulator（旧版第一方模拟器，可选）
try:
    from p2pkh_simulator import (
        Secp256k1, ECPoint, EllipticCurve, HashUtils, Base58, WIF,
        P2PKHAddressGenerator,
    )
    P2PKH_SIMULATOR_AVAILABLE = True
except ImportError:
    P2PKH_SIMULATOR_AVAILABLE = False
    # 定义占位符，避免后续代码指向这些类型时出错
    Secp256k1 = ECPoint = EllipticCurve = HashUtils = Base58 = WIF = None
    P2PKHAddressGenerator = None
    logging.warning(
        "p2pkh_simulator 模块未找到，key_collision.py 的 KeyCollisionEngine 不可用。"
        "请使用 key_collision_cli.py 运行命令行模式。"
    )

# 导入监控系统
try:
    from src.monitoring import MonitoringSystem
    MONITORING_AVAILABLE = True
except ImportError:
    MONITORING_AVAILABLE = False
    MonitoringSystem = None

# 条件导入新GPU引擎
try:
    from src.collision.gpu.engine import GPUCollisionEngine as _GPUCollisionEngine
    GPU_ENGINE_AVAILABLE = True
except ImportError:
    GPU_ENGINE_AVAILABLE = False
    _GPUCollisionEngine = None

# 条件导入多GPU引擎
try:
    from src.gpu.multi_gpu_engine import MultiGPUCollisionEngine as _MultiGPUCollisionEngine
    MULTI_GPU_ENGINE_AVAILABLE = True
except ImportError:
    MULTI_GPU_ENGINE_AVAILABLE = False
    _MultiGPUCollisionEngine = None


# =============================================================================
# TargetResolver 类 - 目标地址解析器
# =============================================================================
# v5.0.0: 已移除 _LegacyTargetResolver 回退路径，
# key_collision.py 现在要求 src/ 模块必须可用。
from src.collision import TargetResolver as _SrcTargetResolver


class TargetResolver:
    """解析多种格式的目标，统一转换为 P2PKH 地址集合

    v5.0.0: 只使用 src.collision.TargetResolver 统一实现。
    """

    def __init__(self):
        self._impl = _SrcTargetResolver()

    @staticmethod
    def detect_format(input_str: str) -> str:
        """自动检测输入格式，返回: 'address', 'wif', 'pubkey_compressed', 'pubkey_uncompressed', 'unknown'"""
        return _SrcTargetResolver.detect_format(input_str)

    @staticmethod
    def analyze_target_formats(targets: set[str]) -> dict[str, int]:
        """分析目标地址格式分布"""
        return _SrcTargetResolver.analyze_target_formats(targets)

    def resolve(self, input_str: str) -> Optional[str]:
        """将任意格式输入解析为 P2PKH 地址，解析失败返回 None"""
        return self._impl.resolve(input_str)

    def resolve_multiple(self, inputs: List[str]) -> Set[str]:
        """解析多个输入，返回地址集合"""
        return self._impl.resolve_multiple(inputs)

    def load_from_file(self, filepath: str) -> Set[str]:
        """从文件逐行加载并解析，跳过空行和#注释"""
        return self._impl.load_from_file(filepath)


# =============================================================================
# CollisionStats 类 - 统计数据容器
# =============================================================================
class CollisionStats:
    """对撞统计数据"""

    def __init__(self):
        self.total_checked: int = 0       # 已检测总数
        self.speed: float = 0.0           # 每秒检测速率
        self.elapsed: float = 0.0         # 已运行时间(秒)
        self.start_time: float = 0.0      # 开始时间戳
        self.matches: List[Dict] = []     # 匹配结果列表
        self._progress_percent: float = 0.0  # 进度百分比(范围扫描模式)
        # 每个match: {"private_key_hash": str, "address": str, "timestamp": float}

    def update(self, checked_count: int):
        """更新统计数据"""
        self.total_checked = checked_count
        self.elapsed = time.time() - self.start_time
        self.speed = self.total_checked / self.elapsed if self.elapsed > 0 else 0

    def add_match(self, private_key: bytes, address: str):
        """记录一个匹配结果（安全：仅存储私钥哈希，不存储明文私钥）"""
        private_key_hash = hashlib.sha256(private_key).hexdigest()
        match_info = {
            "private_key_hash": private_key_hash,
            "address": address,
            "timestamp": time.time()
        }
        self.matches.append(match_info)

    def format_elapsed(self) -> str:
        """格式化已运行时间为 HH:MM:SS"""
        hours = int(self.elapsed // 3600)
        minutes = int((self.elapsed % 3600) // 60)
        seconds = int(self.elapsed % 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def format_speed(self) -> str:
        """格式化速度（带单位）"""
        if self.speed >= 1_000_000:
            return f"{self.speed / 1_000_000:.2f}M/s"
        elif self.speed >= 1_000:
            return f"{self.speed / 1_000:.2f}K/s"
        else:
            return f"{self.speed:.2f}/s"


# =============================================================================
# CheckpointManager 类 - 断点管理器
# =============================================================================
class CheckpointManager:
    """断点管理器 - 保存和恢复对撞进度"""

    DEFAULT_FILE = "collision_checkpoint.json"

    def __init__(self, filepath: str = None, auto_save_interval: int = 30):
        self.filepath = filepath or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), self.DEFAULT_FILE
        )
        self.auto_save_interval = auto_save_interval
        self._last_save_time = 0.0

    @staticmethod
    def _sanitize_matches(matches: list) -> list:
        """脱敏匹配结果：仅保留地址和时间戳，移除私钥信息"""
        sanitized = []
        for m in matches:
            safe = {
                "address": m.get("address", ""),
                "timestamp": m.get("timestamp", 0),
            }
            if "private_key_hash" in m:
                safe["private_key_hash"] = m["private_key_hash"]
            sanitized.append(safe)
        return sanitized

    def save(self, mode: str, targets: set, current_position: int,
             total_checked: int, matches: list,
             range_start: int = None, range_end: int = None):
        """保存断点到 JSON 文件

        安全说明: 私钥信息不会保存到断点文件，仅保存地址和时间戳用于统计。
        """
        data = {
            "version": 1,
            "timestamp": datetime.now().isoformat(),
            "mode": mode,
            "targets": list(targets),
            "current_position": current_position,
            "total_checked": total_checked,
            "matches": self._sanitize_matches(matches),
            "range_start": range_start,
            "range_end": range_end
        }
        try:
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self._last_save_time = time.time()
            logging.info(f"断点已保存: {self.filepath}")
        except Exception as e:
            logging.error(f"保存断点失败: {e}")

    def load(self) -> Optional[Dict]:
        """从文件加载断点，文件不存在或格式错误返回 None"""
        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if data.get("version") != 1:
                logging.warning("断点文件版本不兼容")
                return None
            logging.info(f"断点已加载: {self.filepath}")
            return data
        except FileNotFoundError:
            return None
        except (json.JSONDecodeError, Exception) as e:
            logging.error(f"加载断点失败: {e}")
            return None

    def delete(self):
        """删除断点文件"""
        try:
            if os.path.exists(self.filepath):
                os.remove(self.filepath)
                logging.info(f"断点文件已删除: {self.filepath}")
        except Exception as e:
            logging.error(f"删除断点文件失败: {e}")

    def exists(self) -> bool:
        """检查断点文件是否存在"""
        return os.path.exists(self.filepath)

    def should_auto_save(self) -> bool:
        """检查是否该自动保存（基于时间间隔）"""
        return (time.time() - self._last_save_time) >= self.auto_save_interval


# =============================================================================
# DeduplicationFilter 类 - 私钥去重过滤器
# =============================================================================
class DeduplicationFilter:
    """私钥去重过滤器 - 防止重复检测相同私钥

    设计说明：
    比特币私钥空间为 2^256，内存无法存储所有已检测的键。
    本实现采用有界哈希集合策略：
    - 保留最近 max_size 个私钥的哈希指纹（8字节截断SHA256）
    - 当集合达到上限时清空重置
    - 仅对 random_search 模式有意义（range/brute_force 天然无重复）
    """

    def __init__(self, max_size: int = 1_000_000, enabled: bool = True):
        self._seen: set = set()
        self.max_size = max_size
        self.enabled = enabled
        self.duplicates_found: int = 0
        self.resets: int = 0

    def _fingerprint(self, private_key: bytes) -> bytes:
        """计算私钥的8字节指纹"""
        return hashlib.sha256(private_key).digest()[:8]

    def check_and_add(self, private_key: bytes) -> bool:
        """检查是否重复。不重复返回True，重复返回False。禁用时始终返回True。"""
        if not self.enabled:
            return True
        fp = self._fingerprint(private_key)
        if fp in self._seen:
            self.duplicates_found += 1
            return False
        self._seen.add(fp)
        if len(self._seen) >= self.max_size:
            self._seen.clear()
            self.resets += 1
        return True

    def get_stats(self) -> Dict:
        """返回去重统计"""
        return {
            "tracked": len(self._seen),
            "duplicates_found": self.duplicates_found,
            "resets": self.resets,
            "max_size": self.max_size
        }

    def reset(self):
        """重置过滤器"""
        self._seen.clear()
        self.duplicates_found = 0
        self.resets = 0


# =============================================================================
# KeyCollisionEngine 类 - 对撞核心引擎
# =============================================================================
class KeyCollisionEngine:
    """比特币私钥对撞引擎"""

    def __init__(self, targets: Set[str],
                 on_progress: Optional[Callable] = None,
                 on_match: Optional[Callable] = None,
                 on_complete: Optional[Callable] = None,
                 checkpoint_enabled: bool = False,
                 dedup_enabled: bool = False,
                 dedup_max_size: int = 1_000_000,
                 checkpoint_interval: int = 30,
                 monitoring_enabled: bool = True):
        """
        Args:
            targets: 目标地址集合 (set, O(1)查找)
            on_progress: 进度回调 fn(stats: CollisionStats)
            on_match: 匹配回调 fn(private_key: bytes, address: str, wif: str)
            on_complete: 完成回调 fn(stats: CollisionStats)
            checkpoint_enabled: 是否启用断点续传
            dedup_enabled: 是否启用去重过滤
            dedup_max_size: 去重过滤器最大容量
            checkpoint_interval: 断点自动保存间隔(秒)
            monitoring_enabled: 是否启用监控系统
        """
        self.targets = targets
        self.on_progress = on_progress
        self.on_match = on_match
        self.on_complete = on_complete

        # 检查关键依赖是否可用（避免后续 None 调用崩溃）
        if not P2PKH_SIMULATOR_AVAILABLE or P2PKHAddressGenerator is None:
            raise RuntimeError(
                "p2pkh_simulator 模块不可用，KeyCollisionEngine 无法运行。"
                "请使用 key_collision_cli.py 启动命令行模式。"
            )

        self.generator = P2PKHAddressGenerator()
        self.stats = CollisionStats()
        self._stop_event = threading.Event()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self.progress_interval = 1000  # 每N次检测触发一次进度回调
        self.logger = logging.getLogger("KeyCollisionEngine")
        # 断点管理器
        self.checkpoint_mgr = (
            CheckpointManager(auto_save_interval=checkpoint_interval)
            if checkpoint_enabled else None
        )
        # 去重过滤器
        self.dedup_filter = DeduplicationFilter(max_size=dedup_max_size, enabled=dedup_enabled)
        # 当前位置（用于断点保存）
        self._current_position = 0
        self._current_mode = ""
        self._range_start = None
        self._range_end = None
        # 监控系统
        self.monitoring_enabled = monitoring_enabled and MONITORING_AVAILABLE
        self.monitoring_system = None
        if self.monitoring_enabled:
            self.monitoring_system = MonitoringSystem(self)
            self.logger.info("监控系统已初始化")

    def _generate_address(self, private_key: bytes) -> str:
        """从私钥生成 P2PKH 地址

        coincurve 优先以提升性能，失败时回退到纯 Python 实现。
        """
        if COINCURVE_AVAILABLE:
            try:
                public_key = coincurve.PrivateKey(private_key).public_key.format(compressed=True)
                hash160 = hashlib.new('ripemd160', hashlib.sha256(public_key).digest()).digest()
                return Base58.check_encode(0x00, hash160)
            except Exception:
                pass
        address, _, _ = self.generator.generate_address(private_key)
        return address

    def _generate_and_check(self) -> Optional[Tuple[bytes, str]]:
        """生成一个随机私钥并检查是否匹配目标。
        使用 secrets.token_bytes(32) 生成加密安全随机私钥。
        验证 1 <= k < N。
        返回 (private_key, address) 如果匹配，否则 None。"""
        # 生成随机私钥
        private_key = secrets.token_bytes(32)
        k = int.from_bytes(private_key, 'big')

        # 验证范围
        if k < 1 or k >= Secp256k1.N:
            return None

        # 生成地址并检查匹配
        address = self._generate_address(private_key)
        if address in self.targets:
            return (private_key, address)

        return None

    def _save_checkpoint(self, count: int):
        """辅助方法：保存当前断点（私钥信息经 CheckpointManager 脱敏后写入）"""
        if self.checkpoint_mgr and self.checkpoint_mgr.should_auto_save():
            matches_list = [
                {"address": m["address"], "timestamp": m["timestamp"]}
                for m in self.stats.matches
            ] if hasattr(self.stats, 'matches') else []
            self.checkpoint_mgr.save(
                mode=self._current_mode,
                targets=self.targets,
                current_position=self._current_position,
                total_checked=count,
                matches=matches_list,
                range_start=self._range_start,
                range_end=self._range_end
            )

    def random_search(self):
        """随机碰撞模式 - 使用 secrets 模块随机生成私钥并比对"""
        self._current_mode = "random"
        self._current_position = 0
        self._range_start = None
        self._range_end = None
        self.stats = CollisionStats()
        self.stats.start_time = time.time()
        count = 0

        while not self._stop_event.is_set():
            # 生成随机私钥
            private_key = secrets.token_bytes(32)
            k = int.from_bytes(private_key, 'big')
            if k < 1 or k >= Secp256k1.N:
                continue

            # 去重检查（在范围验证之后，生成地址之前）
            if not self.dedup_filter.check_and_add(private_key):
                continue

            # 生成地址
            address = self._generate_address(private_key)
            count += 1

            # 检查匹配
            if address in self.targets:
                wif = WIF.encode(private_key, compressed=True)
                self.stats.add_match(private_key, address)
                if self.on_match:
                    self.on_match(private_key, address, wif)
                # 如果没有on_match回调，找到匹配后停止
                else:
                    self._stop_event.set()

            # 进度回调
            if count % self.progress_interval == 0:
                self.stats.update(count)
                if self.on_progress:
                    self.on_progress(self.stats)
                # 断点自动保存
                self._save_checkpoint(count)

        self.stats.update(count)
        if self.on_complete:
            self.on_complete(self.stats)

    def range_scan(self, start: int, end: int):
        """范围扫描模式 - 在指定私钥范围 [start, end] 内顺序扫描"""
        self._current_mode = "range"
        self._range_start = start
        self._range_end = end
        self.stats = CollisionStats()
        self.stats.start_time = time.time()
        count = 0
        total_range = end - start + 1

        for k in range(start, end + 1):
            if self._stop_event.is_set():
                break

            # 更新当前位置
            self._current_position = k

            # 验证范围
            if k < 1 or k >= Secp256k1.N:
                continue

            # 生成私钥
            private_key = k.to_bytes(32, 'big')

            # 生成地址
            address = self._generate_address(private_key)
            count += 1

            # 检查匹配
            if address in self.targets:
                wif = WIF.encode(private_key, compressed=True)
                self.stats.add_match(private_key, address)
                if self.on_match:
                    self.on_match(private_key, address, wif)
                # 如果没有on_match回调，找到匹配后停止
                else:
                    self._stop_event.set()

            # 进度回调
            if count % self.progress_interval == 0:
                self.stats.update(count)
                if self.on_progress:
                    self.stats._progress_percent = (k - start) / total_range * 100
                    self.on_progress(self.stats)
                # 断点自动保存
                self._save_checkpoint(count)

        self.stats.update(count)
        if self.on_complete:
            self.on_complete(self.stats)

    def brute_force(self, start: int = 1):
        """暴力穷举模式 - 从指定起点开始顺序递增"""
        self._current_mode = "brute_force"
        self._range_start = start
        self._range_end = None
        self.stats = CollisionStats()
        self.stats.start_time = time.time()
        count = 0
        k = start

        while not self._stop_event.is_set():
            # 更新当前位置
            self._current_position = k

            # 验证范围
            if k < 1 or k >= Secp256k1.N:
                k += 1
                continue

            # 生成私钥
            private_key = k.to_bytes(32, 'big')

            # 生成地址
            address = self._generate_address(private_key)
            count += 1

            # 检查匹配
            if address in self.targets:
                wif = WIF.encode(private_key, compressed=True)
                self.stats.add_match(private_key, address)
                if self.on_match:
                    self.on_match(private_key, address, wif)
                # 如果没有on_match回调，找到匹配后停止
                else:
                    self._stop_event.set()

            # 进度回调
            if count % self.progress_interval == 0:
                self.stats.update(count)
                if self.on_progress:
                    self.on_progress(self.stats)
                # 断点自动保存
                self._save_checkpoint(count)

            k += 1

        self.stats.update(count)
        # 最终断点保存
        if self.checkpoint_mgr:
            matches_list = [
                {"address": m["address"], "timestamp": m["timestamp"]}
                for m in self.stats.matches
            ] if hasattr(self.stats, 'matches') else []
            self.checkpoint_mgr.save(
                mode=self._current_mode,
                targets=self.targets,
                current_position=self._current_position,
                total_checked=self.stats.total_checked,
                matches=matches_list,
                range_start=self._range_start,
                range_end=self._range_end
            )
        if self.on_complete:
            self.on_complete(self.stats)

    def resume_from_checkpoint(self) -> Optional[Dict]:
        """从断点恢复，返回断点数据（包含mode等信息），无断点返回 None"""
        if not self.checkpoint_mgr or not self.checkpoint_mgr.exists():
            return None
        data = self.checkpoint_mgr.load()
        if not data:
            return None

        # 恢复统计数据
        self.stats.total_checked = data.get('total_checked', 0)
        self.stats.matches = data.get('matches', [])

        # 恢复目标（如果当前没有目标）
        if not self.targets and data.get('targets'):
            self.targets = set(data['targets'])

        return data

    def start_from_checkpoint(self, data: Dict):
        """根据断点数据启动对撞"""
        mode = data.get('mode', 'random')
        if mode == 'range':
            self.start(
                mode='range',
                start=data.get('current_position', 1),
                end=data.get('range_end', 2 ** 32),
            )
        elif mode == 'brute_force':
            self.start(
                mode='brute_force',
                start=data.get('current_position', 1),
            )
        elif mode == 'random':
            self.start(mode='random')

    def start(self, mode: str = "random", resume: bool = False, **kwargs):
        """在后台线程启动对撞
        Args:
            mode: "random", "range", "brute_force"
            resume: 是否从断点恢复
            kwargs: range模式需要 start, end; brute_force需要 start
        """
        if self._running:
            return

        # 断点恢复逻辑
        if resume and self.checkpoint_mgr:
            checkpoint = self.checkpoint_mgr.load()
            if checkpoint:
                # 恢复目标地址
                if checkpoint.get("targets"):
                    self.targets = set(checkpoint["targets"])
                # 根据断点中的 mode 字段恢复对应模式
                checkpoint_mode = checkpoint.get("mode", mode)
                if checkpoint_mode == "range":
                    # 从断点继续范围扫描
                    range_start = checkpoint.get("current_position", kwargs.get('start', 1))
                    range_end = checkpoint.get("range_end", kwargs.get('end', 2**32))
                    kwargs['start'] = range_start
                    kwargs['end'] = range_end
                    mode = "range"
                elif checkpoint_mode == "brute_force":
                    # 从断点继续暴力穷举
                    start_pos = checkpoint.get("current_position", kwargs.get('start', 1))
                    kwargs['start'] = start_pos
                    mode = "brute_force"
                elif checkpoint_mode == "random":
                    # 随机模式直接启动，恢复统计数据
                    mode = "random"

        self._stop_event.clear()
        self._running = True

        # 启动监控系统
        if self.monitoring_enabled and self.monitoring_system:
            self.monitoring_system.start()

        if mode == "random":
            target_fn = self.random_search
        elif mode == "range":
            def _range_scan_target():
                return self.range_scan(
                    kwargs.get('start', 1), kwargs.get('end', 2 ** 32)
                )
            target_fn = _range_scan_target
        elif mode == "brute_force":
            def _brute_force_target():
                return self.brute_force(kwargs.get('start', 1))
            target_fn = _brute_force_target
        else:
            raise ValueError(f"未知模式: {mode}")

        self._thread = threading.Thread(target=target_fn, daemon=True, name="engine-worker")
        self._thread.start()
        # 注意: daemon 线程在主进程退出时会强制终止，
        # 可能丢失最多 30 秒（checkpoint 间隔）的未保存数据。
        # 生产环境应使用 SIGTERM handler 触发 save_checkpoint() 后再退出。

    def stop(self):
        """停止对撞"""
        self._stop_event.set()
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        # 保存最终断点
        if self.checkpoint_mgr:
            matches_list = [
                {"address": m["address"], "timestamp": m["timestamp"]}
                for m in self.stats.matches
            ] if hasattr(self.stats, 'matches') else []
            self.checkpoint_mgr.save(
                mode=self._current_mode,
                targets=self.targets,
                current_position=self._current_position,
                total_checked=self.stats.total_checked,
                matches=matches_list,
                range_start=self._range_start,
                range_end=self._range_end
            )
        # 停止监控系统
        if self.monitoring_enabled and self.monitoring_system:
            self.monitoring_system.stop()

    def is_running(self) -> bool:
        return self._running and self._thread and self._thread.is_alive()

    def get_stats(self) -> CollisionStats:
        return self.stats


# =============================================================================
# GPUCollisionEngine 类 - GPU 加速对撞引擎
# =============================================================================
# 使用新模块的 GPUCollisionEngine（如果可用），否则保留兼容的包装类
if GPU_ENGINE_AVAILABLE:
    # 直接使用新模块的GPU引擎
    GPUCollisionEngine = _GPUCollisionEngine
else:
    # 提供一个兼容的占位类，在GPU不可用时给出明确错误
    class GPUCollisionEngine:
        """GPU 加速的比特币私钥对撞引擎（占位类 - GPU不可用）

        当pyopencl未安装或GPU初始化失败时，此类提供友好的错误提示。
        """

        def __init__(self, targets: Set[str], **kwargs):
            raise RuntimeError(
                "GPU 加速不可用。请确保已安装 pyopencl 并有可用的 OpenCL 设备。\n"
                "安装命令: pip install pyopencl"
            )

        @staticmethod
        def is_gpu_available() -> bool:
            """检查 GPU 是否可用"""
            return False

        @staticmethod
        def get_device_info() -> dict:
            """返回 GPU 设备信息"""
            return {}

# 多GPU引擎导出
if MULTI_GPU_ENGINE_AVAILABLE:
    MultiGPUCollisionEngine = _MultiGPUCollisionEngine
else:
    # GPU 不可用时的占位类
    class MultiGPUCollisionEngine:
        """多 GPU 碰撞引擎（占位类 - GPU不可用）"""

        def __init__(self, *args, **kwargs):
            raise RuntimeError(
                "多GPU 加速不可用。请确保已安装 pyopencl 并有可用的 OpenCL 设备。\n"
                "安装命令: pip install pyopencl"
            )


# =============================================================================
# 入口
# =============================================================================
# v5.0.0: 已移除 CollisionCLI 和 __main__ 入口
# 请使用 key_collision_cli.py 或 start_menu.py 启动

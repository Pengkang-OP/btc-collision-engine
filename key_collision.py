#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
比特币私钥对撞引擎和 CLI 界面

这是一个基于纯Python标准库实现的比特币私钥对撞工具。
支持多种对撞模式：随机碰撞、范围扫描、暴力穷举。

可选依赖coincurve库以提升性能。

作者: BTC Project
版本: v4.2.3
"""

import os
import sys
import time
import secrets
import threading
import logging
import json
import hashlib
import atexit
from datetime import datetime
from typing import Set, List, Dict, Optional, Callable, Tuple

# 尝试导入coincurve以提升性能
try:
    import coincurve
    COINCURVE_AVAILABLE = True
    logging.info("coincurve库已加载，将使用高性能加密后端")
except ImportError:
    COINCURVE_AVAILABLE = False
    logging.info("coincurve库未安装，将使用纯Python实现")

# 尝试导入 p2pkh_simulator（旧版第一方模拟器，可选）
try:
    from p2pkh_simulator import (
        Secp256k1, ECPoint, EllipticCurve, HashUtils, Base58, WIF,
        P2PKHAddressGenerator, ColorPrinter
    )
    P2PKH_SIMULATOR_AVAILABLE = True
except ImportError:
    P2PKH_SIMULATOR_AVAILABLE = False
    # 定义占位符，避免后续代码指向这些类型时出错
    Secp256k1 = ECPoint = EllipticCurve = HashUtils = Base58 = WIF = None
    P2PKHAddressGenerator = ColorPrinter = None
    logging.warning(
        "p2pkh_simulator 模块未找到，key_collision.py 的旧版 GUI 功能不可用。"
        "请使用 key_collision_cli.py 运行命令行模式。"
    )

# 导入监控系统
try:
    from src.monitoring import MonitoringSystem
    MONITORING_AVAILABLE = True
except ImportError:
    MONITORING_AVAILABLE = False
    MonitoringSystem = None

# 条件导入新GPU引擎（优先使用src.collision.gpu_collision_engine）
try:
    from src.collision.gpu_collision_engine import GPUCollisionEngine as _GPUCollisionEngine
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
# v4.2.3: 优先使用 src/ 统一实现，回退到本地兼容实现
# 解决两套代码独立演进导致的功能不一致问题
_TARGET_RESOLVER_SRC = None

try:
    from src.collision import TargetResolver as _SrcTargetResolver
    _TARGET_RESOLVER_SRC = _SrcTargetResolver
except ImportError:
    # src/ 模块不可用时回退到本地实现
    pass


class TargetResolver:
    """解析多种格式的目标，统一转换为 P2PKH 地址集合

    v4.2.3: 内部委托给 src.collision.TargetResolver 统一实现。
    当 src/ 模块不可用时，使用本地兼容实现。
    """

    def __init__(self):
        if _TARGET_RESOLVER_SRC is not None:
            self._impl = _TARGET_RESOLVER_SRC()
        else:
            self._impl = None
            self.generator = P2PKHAddressGenerator()

    @staticmethod
    def detect_format(input_str: str) -> str:
        """自动检测输入格式，返回: 'address', 'wif', 'pubkey_compressed', 'pubkey_uncompressed', 'unknown'"""
        # 优先使用统一实现
        if _TARGET_RESOLVER_SRC is not None:
            return _TARGET_RESOLVER_SRC.detect_format(input_str)
        return _LegacyTargetResolver._detect_format(input_str)

    @staticmethod
    def analyze_target_formats(targets: set[str]) -> dict[str, int]:
        """v4.2.3: 分析目标地址格式分布"""
        if _TARGET_RESOLVER_SRC is not None:
            return _TARGET_RESOLVER_SRC.analyze_target_formats(targets)
        return _LegacyTargetResolver._analyze_formats(targets)

    def resolve(self, input_str: str) -> Optional[str]:
        """将任意格式输入解析为 P2PKH 地址，解析失败返回 None"""
        if self._impl is not None:
            return self._impl.resolve(input_str)
        return _LegacyTargetResolver._resolve(input_str, self.generator)

    def resolve_multiple(self, inputs: List[str]) -> Set[str]:
        """解析多个输入，返回地址集合"""
        if self._impl is not None:
            return self._impl.resolve_multiple(inputs)
        return _LegacyTargetResolver._resolve_multiple(inputs, self.generator)

    def load_from_file(self, filepath: str) -> Set[str]:
        """从文件逐行加载并解析，跳过空行和#注释"""
        if self._impl is not None:
            return self._impl.load_from_file(filepath)
        return _LegacyTargetResolver._load_from_file(filepath, self.generator)


class _LegacyTargetResolver:
    """v4.2.3: 旧版 TargetResolver 逻辑保留作为 src/ 模块不可用时的回退"""

    @staticmethod
    def _detect_format(input_str: str) -> str:
        input_str = input_str.strip()
        if not input_str:
            return 'unknown'
        # P2PKH地址: 以'1'开头, 25-34字符, Base58字符集
        if input_str.startswith('1') and 25 <= len(input_str) <= 34:
            valid_chars = set(Base58.ALPHABET)
            if all(c in valid_chars for c in input_str):
                return 'address'
        # WIF
        if input_str.startswith('5') and len(input_str) == 51:
            valid_chars = set(Base58.ALPHABET)
            if all(c in valid_chars for c in input_str):
                return 'wif'
        if input_str.startswith(('K', 'L')) and len(input_str) == 52:
            valid_chars = set(Base58.ALPHABET)
            if all(c in valid_chars for c in input_str):
                return 'wif'
        # 压缩公钥
        if len(input_str) == 66 and input_str.startswith(('02', '03')):
            try:
                bytes.fromhex(input_str)
                return 'pubkey_compressed'
            except ValueError:
                pass
        # 非压缩公钥
        if len(input_str) == 130 and input_str.startswith('04'):
            try:
                bytes.fromhex(input_str)
                return 'pubkey_uncompressed'
            except ValueError:
                pass
        return 'unknown'

    @staticmethod
    def _resolve(input_str: str, generator) -> Optional[str]:
        input_str = input_str.strip()
        fmt = _LegacyTargetResolver._detect_format(input_str)
        try:
            if fmt == 'address':
                version, payload = Base58.check_decode(input_str)
                if version == 0x00:
                    return input_str
                return None
            elif fmt == 'wif':
                private_key, compressed = WIF.decode(input_str)
                public_key = generator.private_key_to_public_key(private_key, compressed=compressed)
                address = generator.public_key_to_address(public_key)
                return address
            elif fmt in ('pubkey_compressed', 'pubkey_uncompressed'):
                public_key = bytes.fromhex(input_str)
                address = generator.public_key_to_address(public_key)
                return address
            else:
                return None
        except Exception:
            return None

    @staticmethod
    def _resolve_multiple(inputs: List[str], generator) -> Set[str]:
        addresses = set()
        for inp in inputs:
            addr = _LegacyTargetResolver._resolve(inp, generator)
            if addr:
                addresses.add(addr)
        return addresses

    @staticmethod
    def _analyze_formats(targets: set[str]) -> dict[str, int]:
        """简单格式统计"""
        counts: dict[str, int] = {}
        for addr in targets:
            if addr.startswith('1'):
                counts['p2pkh'] = counts.get('p2pkh', 0) + 1
            elif addr.startswith('3'):
                counts['p2sh'] = counts.get('p2sh', 0) + 1
            elif addr.startswith('bc1'):
                counts['bech32'] = counts.get('bech32', 0) + 1
            else:
                counts['unknown'] = counts.get('unknown', 0) + 1
        return counts

    @staticmethod
    def _load_from_file(filepath: str, generator) -> Set[str]:
        addresses = set()
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    addr = _LegacyTargetResolver._resolve(line, generator)
                    if addr:
                        addresses.add(addr)
        except FileNotFoundError:
            logging.error(f"文件未找到: {filepath}")
        except Exception as e:
            logging.error(f"读取文件时出错: {e}")
        return addresses


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
        self.filepath = filepath or os.path.join(os.path.dirname(os.path.abspath(__file__)), self.DEFAULT_FILE)
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
        self.generator = P2PKHAddressGenerator()
        self.stats = CollisionStats()
        self._stop_event = threading.Event()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self.progress_interval = 1000  # 每N次检测触发一次进度回调
        self.logger = logging.getLogger("KeyCollisionEngine")
        # 断点管理器
        self.checkpoint_mgr = CheckpointManager(auto_save_interval=checkpoint_interval) if checkpoint_enabled else None
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
            self.start(mode='range',
                      start=data.get('current_position', 1),
                      end=data.get('range_end', 2**32))
        elif mode == 'brute_force':
            self.start(mode='brute_force',
                      start=data.get('current_position', 1))
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
            target_fn = lambda: self.range_scan(kwargs.get('start', 1), kwargs.get('end', 2**32))
        elif mode == "brute_force":
            target_fn = lambda: self.brute_force(kwargs.get('start', 1))
        else:
            raise ValueError(f"未知模式: {mode}")

        self._thread = threading.Thread(target=target_fn, daemon=True)
        self._thread.start()

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
# CollisionCLI 类 - CLI 交互界面
# =============================================================================
class CollisionCLI:
    """对撞工具命令行界面

    .. deprecated:: v4.2.3
        此 CLI 已被 src/cli/main.py (key_collision_cli.py) + start_menu.py 完全替代。
        请使用 `python key_collision_cli.py --help` 或 `python start_menu.py` 启动。
        直接运行 `python key_collision.py` 仍可使用,但不会获得新功能和修复。
    """

    def __init__(self):
        import warnings

        warnings.warn(
            "CollisionCLI 已弃用，请使用 key_collision_cli.py 或 start_menu.py",
            DeprecationWarning,
            stacklevel=2,
        )
        self.printer = ColorPrinter()
        self.resolver = TargetResolver()
        self.engine: Optional[KeyCollisionEngine] = None
        self.targets: Set[str] = set()

    def print_banner(self):
        """打印欢迎横幅"""
        p = self.printer
        print(f"""
{p.BRIGHT_YELLOW}{'='*70}{p.RESET}
{p.BOLD}{p.BRIGHT_RED}
   ██╗  ██╗███████╗██╗   ██╗     ██████╗ ██████╗██╗     ██╗██╗███████╗██╗ ██████╗ ███╗   ██╗
   ██║ ██╔╝██╔════╝██║   ██║    ██╔════╝██╔════╝██║     ██║██║██╔════╝██║██╔═══██╗████╗  ██║
   █████╔╝ █████╗  ██║   ██║    ██║     ██║     ██║     ██║██║███████╗██║██║   ██║██╔██╗ ██║
   ██╔═██╗ ██╔══╝  ██║   ██║    ██║     ██║     ██║     ██║██║╚════██║██║██║   ██║██║╚██╗██║
   ██║  ██╗███████╗╚██████╔╝    ╚██████╗╚██████╗███████╗██║██║███████║██║╚██████╔╝██║ ╚████║
   ╚═╝  ╚═╝╚══════╝ ╚═════╝      ╚═════╝ ╚═════╝╚══════╝╚═╝╚═╝╚══════╝╚═╝ ╚═════╝ ╚═╝  ╚═══╝
{p.RESET}
{p.BRIGHT_GREEN}   btc-collision-engine{p.RESET}
{p.DIM}   纯Python实现 | 标准库 only | 教育演示用途{p.RESET}
{p.BRIGHT_YELLOW}{'='*70}{p.RESET}
        """)

    def print_menu(self):
        """打印主菜单"""
        p = self.printer
        print(f"""
{p.BOLD}{p.BRIGHT_CYAN}╔══════════════════════════════════════════════════════════════════════╗{p.RESET}
{p.BOLD}{p.BRIGHT_CYAN}║                        主菜单                                        ║{p.RESET}
{p.BOLD}{p.BRIGHT_CYAN}╠══════════════════════════════════════════════════════════════════════╣{p.RESET}
{p.BRIGHT_WHITE}  [{p.BRIGHT_GREEN}1{p.BRIGHT_WHITE}] 设置目标地址{p.RESET}
{p.BRIGHT_WHITE}  [{p.BRIGHT_GREEN}2{p.BRIGHT_WHITE}] 随机碰撞模式{p.RESET}
{p.BRIGHT_WHITE}  [{p.BRIGHT_GREEN}3{p.BRIGHT_WHITE}] 范围扫描模式{p.RESET}
{p.BRIGHT_WHITE}  [{p.BRIGHT_GREEN}4{p.BRIGHT_WHITE}] 暴力穷举模式{p.RESET}
{p.BRIGHT_WHITE}  [{p.BRIGHT_GREEN}5{p.BRIGHT_WHITE}] 查看当前目标{p.RESET}
{p.BRIGHT_WHITE}  [{p.BRIGHT_GREEN}6{p.BRIGHT_WHITE}] 演示模式（已知小范围私钥）{p.RESET}
{p.BRIGHT_WHITE}  [{p.BRIGHT_RED}0{p.BRIGHT_WHITE}] 退出{p.RESET}
{p.BOLD}{p.BRIGHT_CYAN}╚══════════════════════════════════════════════════════════════════════╝{p.RESET}
        """)

    def setup_targets(self):
        """设置目标地址（手动输入或文件导入）"""
        p = self.printer
        p.clear_screen()
        p.print_title("设置目标地址")

        print(f"{p.BRIGHT_WHITE}选择输入方式:{p.RESET}")
        print(f"  [{p.BRIGHT_GREEN}1{p.BRIGHT_WHITE}] 手动输入（支持地址/WIF/公钥）{p.RESET}")
        print(f"  [{p.BRIGHT_GREEN}2{p.BRIGHT_WHITE}] 从文件导入{p.RESET}")
        print(f"  [{p.BRIGHT_GREEN}3{p.BRIGHT_WHITE}] 返回主菜单{p.RESET}")

        choice = input(f"\n{p.BRIGHT_WHITE}请选择: {p.RESET}").strip()

        if choice == '1':
            print(f"\n{p.DIM}支持格式: P2PKH地址(1开头), WIF(5/K/L开头), 公钥(hex){p.RESET}")
            print(f"{p.DIM}输入 'done' 结束输入{p.RESET}\n")

            new_targets = set()
            while True:
                user_input = input(f"{p.BRIGHT_WHITE}输入目标 (或 'done' 结束): {p.RESET}").strip()
                if user_input.lower() == 'done':
                    break

                addr = self.resolver.resolve(user_input)
                if addr:
                    new_targets.add(addr)
                    p.print_success(f"已添加: {addr}")
                else:
                    p.print_error("无法解析输入")

            self.targets.update(new_targets)
            p.print_success(f"总共设置了 {len(self.targets)} 个目标地址")
            p.wait_for_enter()

        elif choice == '2':
            filepath = input(f"{p.BRIGHT_WHITE}请输入文件路径: {p.RESET}").strip()
            new_targets = self.resolver.load_from_file(filepath)
            self.targets.update(new_targets)
            p.print_success(f"从文件加载了 {len(new_targets)} 个目标地址")
            p.print_info("当前总目标数", str(len(self.targets)), p.BRIGHT_CYAN)
            p.wait_for_enter()

    def on_progress(self, stats: CollisionStats):
        """进度回调 - 打印实时统计"""
        p = self.printer
        # 格式: [已检测: 1,234,567 | 速度: 1,200/s | 运行: 00:17:13 | 匹配: 0]
        checked_str = f"{stats.total_checked:,}"
        speed_str = stats.format_speed()
        elapsed_str = stats.format_elapsed()
        match_str = f"{len(stats.matches)}"

        progress_line = f"\r{p.BRIGHT_CYAN}[{p.RESET}已检测: {p.BRIGHT_WHITE}{checked_str}{p.RESET} | 速度: {p.BRIGHT_GREEN}{speed_str}{p.RESET} | 运行: {p.BRIGHT_YELLOW}{elapsed_str}{p.RESET} | 匹配: {p.BRIGHT_RED}{match_str}{p.RESET}{p.BRIGHT_CYAN}]{p.RESET}"
        print(progress_line, end='', flush=True)

    def on_match(self, private_key: bytes, address: str, wif: str):
        """匹配回调 - 高亮显示匹配结果

        安全说明:
        - 仅交互式终端 (TTY) 显示完整私钥
        - 非交互环境通过 logging 输出脱敏版本
        - 始终记录脱敏审计日志
        """
        p = self.printer
        logger = logging.getLogger(__name__)
        key_hash = hashlib.sha256(private_key).hexdigest()[:16]

        # 始终记录脱敏审计日志
        logger.info(
            "匹配发现: address=%s private_key_hash=%s",
            address, f"KEY_HASH:{key_hash}"
        )

        # 交互式终端：显示完整私钥（带安全警告）
        if sys.stdout.isatty():
            print(f"\n\n{p.BG_GREEN}{p.BLACK}{'='*70}{p.RESET}")
            p.print_success("🎉 找到匹配！")
            print(f"{p.BG_GREEN}{p.BLACK}{'='*70}{p.RESET}\n")

            p.print_label("匹配地址")
            p.print_address(f"  {address}")

            p.print_label("私钥 (Hex)")
            p.print_private_key(f"  {private_key.hex()}")

            p.print_label("私钥 (WIF)")
            p.print_private_key(f"  {wif}")

            print(f"\n{p.BRIGHT_RED}⚠ 安全警告: 请勿分享、截图或在网络上传输以上私钥信息！{p.RESET}")
            print(f"{p.BG_GREEN}{p.BLACK}{'='*70}{p.RESET}\n")
        else:
            # 非交互环境：仅输出脱敏信息
            print(f"\n[MATCH] address={address} private_key_hash=KEY_HASH:{key_hash}\n")

    def run_random_mode(self):
        """运行随机碰撞模式"""
        p = self.printer

        if not self.targets:
            p.print_error("请先设置目标地址")
            p.wait_for_enter()
            return

        p.clear_screen()
        p.print_title("随机碰撞模式")
        p.print_info("目标数量", str(len(self.targets)), p.BRIGHT_CYAN)
        print(f"\n{p.BRIGHT_YELLOW}按 Enter 开始，按 Ctrl+C 停止{p.RESET}\n")
        input()

        self.engine = KeyCollisionEngine(
            targets=self.targets,
            on_progress=self.on_progress,
            on_match=self.on_match,
            monitoring_enabled=True
        )

        self.engine.start(mode="random")

        try:
            while self.engine.is_running():
                time.sleep(0.1)
        except KeyboardInterrupt:
            print(f"\n{p.BRIGHT_YELLOW}正在停止...{p.RESET}")
        finally:
            self.engine.stop()
            stats = self.engine.get_stats()
            print(f"\n\n{p.BRIGHT_CYAN}最终统计:{p.RESET}")
            print(f"  已检测: {stats.total_checked:,}")
            print(f"  速度: {stats.format_speed()}")
            print(f"  运行时间: {stats.format_elapsed()}")
            print(f"  匹配数: {len(stats.matches)}")
            p.wait_for_enter()

    def run_range_mode(self):
        """运行范围扫描模式"""
        p = self.printer

        if not self.targets:
            p.print_error("请先设置目标地址")
            p.wait_for_enter()
            return

        p.clear_screen()
        p.print_title("范围扫描模式")
        p.print_info("目标数量", str(len(self.targets)), p.BRIGHT_CYAN)

        try:
            start_str = input(f"\n{p.BRIGHT_WHITE}输入起始私钥 (十进制整数): {p.RESET}").strip()
            start = int(start_str)

            end_str = input(f"{p.BRIGHT_WHITE}输入结束私钥 (十进制整数): {p.RESET}").strip()
            end = int(end_str)

            if start < 1 or end >= Secp256k1.N or start > end:
                p.print_error("无效的范围")
                p.wait_for_enter()
                return

            print(f"\n{p.BRIGHT_YELLOW}按 Enter 开始，按 Ctrl+C 停止{p.RESET}\n")
            input()

            self.engine = KeyCollisionEngine(
                targets=self.targets,
                on_progress=self.on_progress,
                on_match=self.on_match
            )

            self.engine.start(mode="range", start=start, end=end)

            try:
                while self.engine.is_running():
                    time.sleep(0.1)
            except KeyboardInterrupt:
                print(f"\n{p.BRIGHT_YELLOW}正在停止...{p.RESET}")
            finally:
                self.engine.stop()
                stats = self.engine.get_stats()
                print(f"\n\n{p.BRIGHT_CYAN}最终统计:{p.RESET}")
                print(f"  已检测: {stats.total_checked:,}")
                print(f"  速度: {stats.format_speed()}")
                print(f"  运行时间: {stats.format_elapsed()}")
                print(f"  匹配数: {len(stats.matches)}")
                p.wait_for_enter()

        except ValueError:
            p.print_error("请输入有效的整数")
            p.wait_for_enter()

    def run_brute_force_mode(self):
        """运行暴力穷举模式"""
        p = self.printer

        if not self.targets:
            p.print_error("请先设置目标地址")
            p.wait_for_enter()
            return

        p.clear_screen()
        p.print_title("暴力穷举模式")
        p.print_info("目标数量", str(len(self.targets)), p.BRIGHT_CYAN)

        try:
            start_str = input(f"\n{p.BRIGHT_WHITE}输入起始私钥 (十进制整数, 默认1): {p.RESET}").strip()
            start = int(start_str) if start_str else 1

            print(f"\n{p.BRIGHT_YELLOW}按 Enter 开始，按 Ctrl+C 停止{p.RESET}\n")
            input()

            self.engine = KeyCollisionEngine(
                targets=self.targets,
                on_progress=self.on_progress,
                on_match=self.on_match
            )

            self.engine.start(mode="brute_force", start=start)

            try:
                while self.engine.is_running():
                    time.sleep(0.1)
            except KeyboardInterrupt:
                print(f"\n{p.BRIGHT_YELLOW}正在停止...{p.RESET}")
            finally:
                self.engine.stop()
                stats = self.engine.get_stats()
                print(f"\n\n{p.BRIGHT_CYAN}最终统计:{p.RESET}")
                print(f"  已检测: {stats.total_checked:,}")
                print(f"  速度: {stats.format_speed()}")
                print(f"  运行时间: {stats.format_elapsed()}")
                print(f"  匹配数: {len(stats.matches)}")
                p.wait_for_enter()

        except ValueError:
            p.print_error("请输入有效的整数")
            p.wait_for_enter()

    def run_demo_mode(self):
        """演示模式 - 使用已知小范围私钥进行演示"""
        p = self.printer

        p.clear_screen()
        p.print_title("演示模式")

        # 使用已知私钥 1-100 范围
        # 私钥=1 的地址: 1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH
        demo_private_key = b'\x00' * 31 + b'\x01'

        # 生成地址
        if COINCURVE_AVAILABLE:
            # 使用coincurve库生成地址，提升性能
            try:
                public_key = coincurve.PrivateKey(demo_private_key).public_key.format(compressed=True)
                # 计算hash160
                hash160 = hashlib.new('ripemd160', hashlib.sha256(public_key).digest()).digest()
                # 生成P2PKH地址
                demo_address = Base58.check_encode(0x00, hash160)
            except Exception:
                # 如果coincurve失败，回退到纯Python实现
                demo_address, _, _ = self.generator.generate_address(demo_private_key)
        else:
            # 使用纯Python实现
            demo_address, _, _ = self.generator.generate_address(demo_private_key)

        p.print_info("演示说明", "使用私钥=1的已知地址作为目标", p.BRIGHT_CYAN)
        p.print_info("目标地址", demo_address, p.BRIGHT_YELLOW)
        p.print_info("搜索范围", "私钥 1-100", p.BRIGHT_GREEN)

        # 设置目标
        self.targets = {demo_address}

        print(f"\n{p.BRIGHT_YELLOW}按 Enter 开始演示...{p.RESET}\n")
        input()

        self.engine = KeyCollisionEngine(
            targets=self.targets,
            on_progress=self.on_progress,
            on_match=self.on_match,
            monitoring_enabled=True
        )

        # 使用 brute_force 模式从 1 开始
        self.engine.start(mode="brute_force", start=1)

        try:
            while self.engine.is_running():
                time.sleep(0.1)
        except KeyboardInterrupt:
            print(f"\n{p.BRIGHT_YELLOW}正在停止...{p.RESET}")
        finally:
            self.engine.stop()
            stats = self.engine.get_stats()
            print(f"\n\n{p.BRIGHT_CYAN}演示结束统计:{p.RESET}")
            print(f"  已检测: {stats.total_checked:,}")
            print(f"  速度: {stats.format_speed()}")
            print(f"  运行时间: {stats.format_elapsed()}")
            print(f"  匹配数: {len(stats.matches)}")

            if stats.matches:
                p.print_success("演示成功！找到了匹配的私钥！")
            else:
                p.print_warning("演示结束，未找到匹配")

            p.wait_for_enter()

    def run(self):
        """主循环"""
        self.print_banner()

        while True:
            self.print_menu()
            choice = input(f"{self.printer.BRIGHT_WHITE}请选择: {self.printer.RESET}").strip()

            if choice == '0':
                print(f"\n{self.printer.BRIGHT_GREEN}感谢使用，再见！{self.printer.RESET}\n")
                break

            elif choice == '1':
                self.setup_targets()

            elif choice == '2':
                self.run_random_mode()

            elif choice == '3':
                self.run_range_mode()

            elif choice == '4':
                self.run_brute_force_mode()

            elif choice == '5':
                p = self.printer
                p.clear_screen()
                p.print_title("当前目标地址")
                if self.targets:
                    for i, addr in enumerate(sorted(self.targets), 1):
                        p.print_info(f"{i}", addr, p.BRIGHT_YELLOW)
                    p.print_info("总计", str(len(self.targets)), p.BRIGHT_CYAN)
                else:
                    p.print_warning("尚未设置目标地址")
                p.wait_for_enter()

            elif choice == '6':
                self.run_demo_mode()

            else:
                p = self.printer
                p.print_error("无效的选择，请重新输入")
                p.wait_for_enter()


# =============================================================================
# 入口
# =============================================================================
# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)

# 安装日志安全过滤器（防止私钥泄露到日志文件）
try:
    from src.utils.logging_config import _setup_security_filter
    _setup_security_filter()
except Exception:
    pass  # 安全过滤器初始化失败不阻止运行

if __name__ == "__main__":
    import warnings

    warnings.warn(
        "直接运行 key_collision.py 已弃用，请使用 key_collision_cli.py 或 start_menu.py",
        DeprecationWarning,
    )
    cli = CollisionCLI()
    cli.run()

"""GPU设备管理器.

负责GPU设备的初始化、配置和管理。
"""

import json
import logging
import time
import traceback
from pathlib import Path
from typing import Any, cast

from ..core.base58 import Base58
from ..utils import get_configured_logger
from ..utils.bech32_codec import decode_segwit_address
from ..utils.exception_handler import ExceptionHandler
from ..utils.performance_monitor import EnhancedPerformanceMonitor
from .amd_optimizer import AmdGPUOptimizer
from .async_executor import AsyncGPUExecutor
from .context import GPUContext
from .device import GPUDevice, GPUDeviceDetector
from .intel_optimizer import IntelGPUOptimizer
from .kernel import OPENCL_KERNEL_SOURCE
from .kernel_impl import GPUKernel
from .memory_pool import get_gpu_memory_pool
from .nvidia_optimizer import NvidiaGPUOptimizer
from .profiles.loader import GPUProfileLoader

__all__ = ["GPUDeviceManager", "NoValidTargetsError"]


_logger = get_configured_logger("GPUDeviceManager")


class NoValidTargetsError(ValueError):
    """没有有效的目标地址 (仅 P2PKH 格式可用, 其他格式已被跳过)."""


class GPUDeviceManager:
    """GPU设备管理器.

    负责GPU设备的初始化、配置和管理。
    """

    __slots__ = (
        "_amd_optimizer",
        "_async_executor",
        "_gpu_context",
        "_gpu_device",
        "_gpu_kernel",
        "_gpu_memory_pool",
        "_intel_optimizer",
        "_nvidia_optimizer",
        "_profile_loader",
        "config",
        "device_index",
        "logger",
        "target_hash160s",
        "target_list",
    )

    def __init__(
        self,
        device_index: int = -1,
        config: dict[str, Any] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        """初始化 GPU 设备管理器。.

        Args:
            device_index: GPU设备索引（-1表示自动选择）
            config: 配置字典
            logger: 日志记录器
        """
        self.device_index = device_index
        self.config = config or {}
        self.logger = logger or _logger

        self._gpu_device: GPUDevice | None = None
        self._gpu_context: GPUContext | None = None
        self._gpu_kernel: GPUKernel | None = None
        self._async_executor: AsyncGPUExecutor | None = None
        self._gpu_memory_pool: Any | None = None

        self._profile_loader = GPUProfileLoader()
        self._intel_optimizer: Any | None = None
        self._nvidia_optimizer: Any | None = None
        self._amd_optimizer: Any | None = None

        self.target_hash160s: bytes = b""
        self.target_list: list[str] = []

    def _require_device(self) -> GPUDevice:
        """返回已初始化的 GPU 设备，未初始化则抛出 RuntimeError。.

        替代 assert，确保 python -O 模式下仍有效。
        """
        if self._gpu_device is None:
            raise RuntimeError("GPU device not initialized")
        return self._gpu_device

    def _require_context(self) -> GPUContext:
        """返回已初始化的 GPU 上下文。."""
        if self._gpu_context is None:
            raise RuntimeError("GPU context not initialized")
        return self._gpu_context

    def _require_async_executor(self) -> AsyncGPUExecutor:
        """返回已初始化的异步执行器。."""
        if self._async_executor is None:
            raise RuntimeError("Async executor not initialized")
        return self._async_executor

    def initialize(
        self,
        targets: set[str],
        batch_size: int | None = None,
        check_uncompressed: int = 0,
    ) -> "GPUDeviceManager":
        """初始化GPU设备及所有依赖组件.

        执行完整的GPU初始化流程，按依赖顺序依次初始化各组件:

        初始化顺序:
        1. 检测 GPU 可用性
        2. 初始化 GPU 设备 (init_device)
        3. 准备目标地址 (prepare_targets)
        4. 计算最优 batch_size
        5. 创建 GPU 上下文并编译内核
        6. 初始化 GPU 内存池（含预分配）
        7. 初始化异步执行器（双缓冲）
        8. 设置目标地址和 nonce 映射
        9. 应用厂商特定优化 (NVIDIA/AMD/Intel)

        Args:
            targets: 目标地址集合
            batch_size: 批次大小（None表示自动计算）
            check_uncompressed: 是否同时检查非压缩格式 (0=仅压缩, 1=双格式)

        Returns:
            self，支持链式调用

        Raises:
            RuntimeError: GPU 不可用或初始化失败时抛出
            NoValidTargetsError: 无有效 P2PKH 目标地址时抛出

        """
        with EnhancedPerformanceMonitor(self.logger, "GPU设备初始化", level="INFO") as pm:
            try:
                if not GPUDeviceDetector.is_gpu_available():
                    raise RuntimeError("pyopencl 不可用")

                # 1. 初始化GPU设备
                self._init_device()
                if self._gpu_device is None:
                    raise RuntimeError("GPUDeviceManager._init_device() did not set _gpu_device")

                # 2. 准备目标地址
                target_hash160s, target_list = self._prepare_targets(targets)
                self.target_hash160s = target_hash160s
                self.target_list = target_list

                # 3. 计算最优batch_size
                if batch_size is None:
                    batch_size = self._calculate_optimal_batch_size()

                # 4. 创建GPU上下文
                self._init_context()
                if self._gpu_context is None:
                    raise RuntimeError("GPUDeviceManager._init_context() did not set _gpu_context")

                # 5. 编译和创建内核
                self._init_kernel(batch_size)
                if self._gpu_kernel is None:
                    raise RuntimeError("GPUDeviceManager._init_kernel() did not set _gpu_kernel")

                # 6. 初始化内存池（含预分配）
                self._init_memory_pool(batch_size)

                # 7. 初始化异步执行器
                self._init_async_executor(batch_size)

                # 8. 设置目标地址
                if target_hash160s:
                    self._gpu_kernel.set_targets(
                        target_hash160s,
                        len(target_list),
                        check_uncompressed=check_uncompressed,
                    )

                # 8.1 传递 check_uncompressed 给异步执行器
                if self._async_executor:
                    self._async_executor.check_uncompressed = check_uncompressed

                # 9. 应用厂商优化
                self._apply_vendor_optimizations()

                # 10. 记录初始化完成
                device_info = self._gpu_device.get_device_info()
                _name = device_info.get("name", "Unknown")
                _vendor = device_info.get("vendor", "Unknown")
                _wgs = getattr(self._gpu_kernel, "_work_group_size", "N/A")
                self.logger.info(
                    "GPU 设备初始化成功: %s (厂商: %s, batch_size: %d, work_group_size: %s)",
                    _name,
                    _vendor,
                    batch_size,
                    _wgs,
                )

                pm.add_metadata("device_name", device_info.get("name", "Unknown"))
                pm.add_metadata("vendor", device_info.get("vendor", "Unknown"))
                pm.add_metadata("batch_size", batch_size)

            except NoValidTargetsError as e:
                # 使用ExceptionHandler记录详细错误
                ExceptionHandler.handle_engine_error("GPU", e, context="设备初始化")
                # 目标地址格式不兼容 (仅支持 P2PKH)
                self.logger.error(
                    "GPU初始化失败: %s\n原因: 目标地址格式不兼容\n"
                    "  GPU 引擎当前仅支持 P2PKH 地址 (1... 开头, Base58 编码)。\n"
                    "  如果你的目标包含 P2SH (3...) 或 Bech32/Taproot (bc1...) 地址,\n"
                    "  请使用 CPU 模式或仅使用 P2PKH 地址。",
                    e,
                )
                raise RuntimeError(
                    f"GPU初始化失败: {e} (GPU 引擎仅支持 P2PKH 地址格式, 其他格式请使用 CPU 模式)",
                ) from e
            except ValueError as e:
                # 使用ExceptionHandler记录详细错误
                ExceptionHandler.handle_engine_error("GPU", e, context="设备初始化")
                self.logger.error(
                    "GPU初始化失败: %s\n建议操作:\n"
                    "  1. 检查GPU驱动是否正常\n"
                    "  2. 验证OpenCL环境配置\n"
                    "  3. 使用CPU引擎作为备选方案\n"
                    "  4. 查看日志获取详细错误信息",
                    e,
                )
                raise RuntimeError(
                    f"GPU初始化失败: {e}。请检查GPU驱动和OpenCL环境, 或使用CPU引擎作为备选方案。",
                ) from e
            except RuntimeError as e:
                # 使用ExceptionHandler记录详细错误
                ExceptionHandler.handle_engine_error("GPU", e, context="设备初始化")
                self.logger.error(
                    "GPU初始化失败: %s\n建议操作:\n"
                    "  1. 检查GPU驱动是否正常\n"
                    "  2. 验证OpenCL环境配置\n"
                    "  3. 使用CPU引擎作为备选方案\n"
                    "  4. 查看日志获取详细错误信息",
                    e,
                )
                raise RuntimeError(
                    f"GPU初始化失败: {e}。请检查GPU驱动和OpenCL环境, 或使用CPU引擎作为备选方案。",
                ) from e

        return self

    def _init_device(self) -> None:
        """初始化GPU设备."""
        with EnhancedPerformanceMonitor(self.logger, "GPU设备初始化", level="DEBUG"):
            self._gpu_device = GPUDevice()

            # 读取异步执行配置
            enable_async = self._read_async_config()

            # 初始化设备
            self._gpu_device.initialize(self.device_index, enable_async=enable_async)

            device_info = self._gpu_device.get_device_info()
            _name = device_info.get("name", "Unknown")
            _vendor = device_info.get("vendor", "Unknown")
            self.logger.info("检测到GPU设备: %s (%s)", _name, _vendor)
            mem_size = device_info.get("global_mem_size", 0) / (1024**3)
            self.logger.info(
                "  - 显存: %.1f GB\n  - 计算单元: %s\n  - 平台: %s",
                mem_size,
                device_info.get("max_compute_units", "N/A"),
                device_info.get("platform", "Unknown"),
            )

    def _read_async_config(self) -> bool:
        """读取异步执行配置."""
        enable_async = True
        config_source = "默认"

        # 优先级1: 构造函数传入的配置
        if self.config:
            gpu_config = self.config.get("gpu", {})
            if "async_execution" in gpu_config:
                enable_async = gpu_config["async_execution"]
                config_source = "构造参数"
                self.logger.info("[OK] 从构造参数读取异步设置: %s (优先级1)", enable_async)

        # 优先级2: 自动读取配置文件
        if config_source == "默认":
            project_root = Path(__file__).parent.parent.parent
            config_files = [
                project_root / "config.intel_arc.json",
                project_root / "config.json",
            ]

            for cfg_file in config_files:
                if cfg_file.exists():
                    try:
                        with Path(cfg_file).open(encoding="utf-8") as f:
                            cfg = json.load(f)
                            gpu_cfg = cfg.get("gpu", {})
                            if "async_execution" in gpu_cfg:
                                enable_async = bool(gpu_cfg["async_execution"])
                                config_source = f"配置文件 {cfg_file.name}"
                                self.logger.info(
                                    "[OK] 从%s读取异步设置: %s (优先级2)",
                                    config_source,
                                    enable_async,
                                )
                                break
                    except json.JSONDecodeError as e:
                        self.logger.warning("配置文件 %s JSON格式错误: %s", cfg_file, e)
                    except PermissionError:
                        self.logger.warning("无法读取 %s: 权限不足", cfg_file)
                    except RuntimeError as e:
                        self.logger.debug("读取配置文件 %s 失败(非关键): %s", cfg_file, e)

        # 应用配置
        if enable_async:
            self._require_device().enable_async_execution = True
            self.logger.info(
                "[OK] GPU异步执行已启用 (来源: %s) - 双缓冲优化",
                config_source,
            )
        else:
            self.logger.info(
                "GPU异步执行未启用 (来源: %s) - 使用同步模式",
                config_source,
            )
            self.logger.info("提示: 在配置文件中设置 'gpu.async_execution': true 以启用异步优化")

        return enable_async

    @staticmethod
    def _classify_address_format(address: str) -> str:
        """根据前缀识别比特币地址格式，用于用户友好的警告提示。.

        Returns:
            格式名称字符串: "P2PKH", "P2SH", "Bech32", "Bech32m/Taproot", "未知"

        """
        if address.startswith("1"):
            return "P2PKH"
        if address.startswith("3"):
            return "P2SH"
        if address.startswith("bc1q"):
            return "Bech32 (P2WPKH/P2WSH)"
        if address.startswith("bc1p"):
            return "Bech32m (Taproot)"
        return "未知格式"

    def _prepare_targets(self, targets: set[str]):  # noqa: C901
        """准备目标地址 (支持 P2PKH 和 Bech32 P2WPKH 格式).

        GPU 引擎支持以下目标格式:
        1. P2PKH (version=0x00, 以 '1' 开头): 直接提取 hash160
        2. Bech32 P2WPKH (以 'bc1q' 开头, 20字节 witness): 提取 witness_program 作为 hash160
        3. 其他格式 (P2SH/P2WSH/Taproot): 被跳过，生成 WARNING 日志

        v4.3.0: 增强支持 Bech32 P2WPKH 地址
        """
        target_list = []
        hash160_list = []
        skipped_addresses: list[tuple[str, str, str]] = []  # (masked, format, reason)
        bech32_p2wpkh_count = 0  # 统计Bech32 P2WPKH地址数量

        for address in sorted(targets):
            address_lower = address.lower()

            # 1. 首先尝试 Bech32 地址检测
            if address_lower.startswith("bc1") or address_lower.startswith("tb1"):
                # Taproot 地址 (bc1p/tb1p): 跳过
                if address_lower.startswith(("bc1p", "tb1p")):
                    masked = address[:8] + "..." + address[-6:] if len(address) >= 14 else address
                    skipped_addresses.append(
                        (
                            masked,
                            "Bech32m (Taproot)",
                            "Taproot的witness_program=x-only公钥，密码学上无法通过hash160(pubkey)匹配",
                        ),
                    )
                    continue

                # 尝试解码 Bech32 地址
                try:
                    hrp, witness_version, witness_program = decode_segwit_address(address)
                    if witness_program is None:
                        raise ValueError("Bech32解码失败")

                    # 检查 witness version
                    if witness_version != 0:
                        masked = address[:8] + "..." + address[-6:] if len(address) >= 14 else address
                        skipped_addresses.append(
                            (
                                masked,
                                f"Bech32 (witness v{witness_version})",
                                "仅支持 witness v0",
                            ),
                        )
                        continue

                    # P2WPKH: 20字节 witness_program = hash160(pubkey) → 可匹配
                    if len(witness_program) == 20:
                        target_list.append(address)
                        hash160_list.append(witness_program)
                        bech32_p2wpkh_count += 1
                        short_hash = witness_program.hex()[:8]
                        self.logger.debug(
                            f"Bech32 P2WPKH 目标: {address[:8]}... -> hash160={short_hash}...",
                        )
                        continue

                    # P2WSH: 32字节 witness_program = sha256(redeemScript) → 不可匹配
                    if len(witness_program) == 32:
                        masked = address[:8] + "..." + address[-6:] if len(address) >= 14 else address
                        skipped_addresses.append(
                            (
                                masked,
                                "Bech32 (P2WSH)",
                                "P2WSH的witness_program=sha256(redeemScript)，密码学上无法通过hash160(pubkey)匹配",
                            ),
                        )
                        continue

                    masked = address[:8] + "..." + address[-6:] if len(address) >= 14 else address
                    skipped_addresses.append(
                        (
                            masked,
                            "Bech32",
                            f"不支持的 witness_program 长度: {len(witness_program)}",
                        ),
                    )
                    continue

                except Exception as e:
                    masked = address[:8] + "..." + address[-6:] if len(address) >= 14 else address
                    skipped_addresses.append((masked, "Bech32", f"解码失败: {type(e).__name__}"))
                    continue

            # 2. 尝试 Base58 地址检测 (P2PKH / P2SH)
            try:
                version, payload = Base58.check_decode(address)

                # P2PKH: version=0x00, 20字节 payload = hash160(pubkey) → 可匹配
                if version == 0x00 and len(payload) == 20:
                    target_list.append(address)
                    hash160_list.append(payload)

                elif version == 0x05 and len(payload) == 20:
                    # P2SH: payload = hash160(redeemScript) ≠ hash160(pubkey) → 不可匹配
                    addr_len = len(address)
                    masked = address[:8] + "..." + address[-6:] if addr_len >= 14 else address
                    skipped_addresses.append(
                        (
                            masked,
                            "P2SH",
                            "P2SH的payload=hash160(redeemScript)，密码学上无法通过hash160(pubkey)匹配",
                        ),
                    )
                else:
                    fmt = self._classify_address_format(address)
                    addr_len = len(address)
                    masked = address[:8] + "..." + address[-6:] if addr_len >= 14 else address
                    reason = f"version=0x{version:02x} (仅接受 P2PKH/Bech32 P2WPKH)"
                    skipped_addresses.append((masked, fmt, reason))

            except (ValueError, TypeError) as e:
                fmt = self._classify_address_format(address)
                addr_len = len(address)
                masked = address[:8] + "..." + address[-6:] if addr_len >= 14 else address
                reason = f"{type(e).__name__}"
                skipped_addresses.append((masked, fmt, reason))
                continue

            except RuntimeError as e:
                fmt = self._classify_address_format(address)
                addr_len = len(address)
                masked = address[:8] + "..." + address[-6:] if addr_len >= 14 else address
                self.logger.warning("目标地址解析失败 [%s]: %s", masked, type(e).__name__)
                continue

        # 统计信息
        p2pkh_count = len([a for a in target_list if a.startswith("1")])
        total_targets = len(hash160_list)

        # 输出警告日志
        if skipped_addresses:
            skipped_count = len(skipped_addresses)
            self.logger.warning(
                "GPU 引擎跳过 %d 个不兼容目标 (支持: P2PKH/Bech32 P2WPKH):",
                skipped_count,
            )
            # 显示每个被跳过地址的格式和原因 (最多显示 5 条避免日志洪水)
            for masked, fmt, reason in skipped_addresses[:5]:
                self.logger.warning("  [SKIP] %s | 格式: %s | 原因: %s", masked, fmt, reason)
            if skipped_count > 5:
                self.logger.warning("  ... 以及 %d 条未显示 (详情见上文)", skipped_count - 5)
            self.logger.warning(
                "建议: P2SH/P2WSH/Taproot 目标因密码学路径不同无法通过私钥碰撞匹配。"
                " 请使用 P2PKH (1开头) 或 Bech32 P2WPKH (bc1q开头，20字节witness) 地址。"
                " 详细信息请参考 README.md 的 '目标地址格式支持' 章节。",
            )

        if not hash160_list:
            raise NoValidTargetsError(
                f"没有有效的 P2PKH/Bech32 P2WPKH 目标地址 (已跳过 {len(skipped_addresses)} 个)。"
                " 请添加 '1' 开头的 P2PKH 地址或 'bc1q' 开头的 Bech32 P2WPKH 地址。"
                " 其他格式(P2SH/P2WSH/Taproot)因密码学路径不同无法通过私钥碰撞匹配。",
            )

        # 输出统计信息
        self.logger.info(
            f"GPU 目标准备完成: P2PKH={p2pkh_count}, Bech32 P2WPKH={bech32_p2wpkh_count}, "
            f"总目标={total_targets}, 跳过={len(skipped_addresses)}",
        )

        target_hash160s = b"".join(hash160_list)
        return target_hash160s, target_list

    def _calculate_optimal_batch_size(self) -> int:
        """计算最优batch_size."""
        self._require_device()
        if self._gpu_device is None:
            raise RuntimeError("GPUDeviceManager._require_device() did not set _gpu_device")
        device_info: dict[str, Any] = self._gpu_device.get_device_info()
        device_name = device_info.get("name", "")
        vendor = device_info.get("vendor_identifier", "unknown")

        # 尝试从GPU配置文件中获取推荐的batch_size
        profile = self._profile_loader.get_profile(vendor, device_name)
        if profile and "recommended_batch_size" in profile:
            recommended_batch_size = profile["recommended_batch_size"]
            self.logger.info("从GPU配置文件获取推荐 batch_size: %s", recommended_batch_size)
            return int(recommended_batch_size)

        # 基于显存大小计算
        global_mem_size = device_info.get("global_mem_size", 1024**3)  # 默认1GB

        # 保守估计：每100万私钥需要约100MB显存
        estimated_batch_size = int((global_mem_size / (100 * 1024 * 1024)) * 1_000_000)

        # 限制范围 100K到16M
        estimated_batch_size = max(100_000, min(estimated_batch_size, 16_777_216))

        self.logger.info("自动计算 batch_size: %d (基于GPU显存)", estimated_batch_size)
        return estimated_batch_size

    def _init_context(self) -> None:
        """初始化GPU上下文."""
        with EnhancedPerformanceMonitor(self.logger, "GPU上下文初始化", level="DEBUG"):
            self._gpu_context = GPUContext(self._require_device())

            # 应用优化
            self._gpu_context.apply_optimizations()

    def _init_kernel(self, batch_size: int) -> None:
        """初始化GPU内核."""
        with EnhancedPerformanceMonitor(self.logger, "OpenCL内核编译", level="INFO"):
            ctx = self._require_context()
            dev = self._require_device()
            # 编译内核
            ctx.compile_kernel(OPENCL_KERNEL_SOURCE)

            # 创建GPUKernel
            self._gpu_kernel = GPUKernel(
                dev,
                max_batch_size=batch_size,
                program=cast("Any", self._gpu_context.program),  # type: ignore[union-attr]
            )

    def _init_memory_pool(self, batch_size: int = 0) -> None:
        """初始化GPU内存池（含常用缓冲区预分配）.

        在池创建后立即预分配常用大小的缓冲区，
        消除运行时首次分配的延迟开销（通常节省 5-15ms）。

        Args:
            batch_size: 当前引擎批大小，用于预分配匹配结果缓冲区

        """
        # 从配置读取内存池设置
        gpu_config = self.config.get("gpu", {})
        use_gpu_memory_pool = gpu_config.get("use_memory_pool", True)
        gpu_pool_max_buffers = gpu_config.get("pool_max_buffers", 100)

        if use_gpu_memory_pool:
            self._gpu_memory_pool = get_gpu_memory_pool(
                self._require_device().context,
                max_buffers=gpu_pool_max_buffers,
            )
            # 预分配常用缓冲区，减少运行时首次分配延迟
            preallocate_sizes = self._compute_prealloc_sizes(batch_size)
            if preallocate_sizes:
                try:
                    self._gpu_memory_pool.preallocate_buffers(preallocate_sizes, count_per_size=2)
                    self.logger.debug(
                        "GPU内存池预分配: %d 种大小 × 2",
                        len(preallocate_sizes),
                    )
                except (RuntimeError, MemoryError, ValueError):
                    self.logger.debug("GPU内存池预分配跳过（非致命）", exc_info=True)
            self.logger.info(
                "GPU内存池初始化完成: %s",
                self._gpu_memory_pool.get_stats(),
            )
        else:
            self.logger.info("GPU内存池未启用,使用直接分配模式")

    @staticmethod
    def _compute_prealloc_sizes(batch_size: int) -> list:
        """计算引擎常用缓冲区的预分配大小列表.

        基于引擎批大小推导关键缓冲区尺寸:
        - 匹配结果缓冲区: batch_size × 4 字节
        - 256/1K/64K 通用对齐尺寸（覆盖小/中/大分配）

        Args:
            batch_size: 引擎批大小

        Returns:
            去重后的缓冲区大小列表（字节）

        """
        sizes = {256, 1024, 65536}  # 通用对齐尺寸
        if batch_size > 0:
            sizes.add(batch_size * 4)  # 匹配结果缓冲区
        return sorted(sizes)

    def _init_async_executor(self, batch_size: int) -> None:
        """初始化异步执行器."""
        dev = self._require_device()
        if dev.enable_async_execution:
            self.logger.info("初始化GPU异步执行器...")

            # 从配置读取queue_depth (0=auto, 由GPU型号自动检测)
            gpu_config = self.config.get("gpu", {})
            config_queue_depth = gpu_config.get("queue_depth", 0)

            # 尝试从GPU配置文件中获取推荐的队列深度
            device_info = dev.get_device_info()
            device_name = device_info.get("name", "")
            vendor = device_info.get("vendor_identifier", "unknown")

            profile = self._profile_loader.get_profile(vendor, device_name)
            profile_queue_depth = profile.get("queue_depth", 0) if profile else 0

            # v5.1 优化：取 config 和 GPU 推荐值中的较大者，GPU 硬件优化优先
            queue_depth = max(config_queue_depth, profile_queue_depth, 4)
            if profile_queue_depth > 0:
                self.logger.info(
                    "GPU推荐队列深度: %s (config: %s, 最终: %s)",
                    profile_queue_depth,
                    config_queue_depth,
                    queue_depth,
                )

            self._async_executor = AsyncGPUExecutor(
                dev,
                max_batch_size=batch_size,
                queue_depth=queue_depth,
            )

            # v5.1: 使用GPU特定初始批次大小（而非引擎配置），避免缓冲区频繁 resize
            executor = self._require_async_executor()
            init_batch = getattr(executor, "initial_batch_size", batch_size)
            executor.initialize_buffers(dev.context, num_keys=init_batch)

            # v5.1: 启动后台结果收集器（消除主循环阻塞，实现流水线并行）
            executor.start_result_collector()

            self.logger.debug(
                "[OK] GPU异步执行器已初始化(队列=%d, 批次=%d)",
                queue_depth,
                init_batch,
            )
        else:
            self._async_executor = None
            self.logger.debug("GPU异步执行器未初始化(使用同步模式)")

    def _apply_vendor_optimizations(self) -> None:
        """应用厂商特定优化.

        v4.2.1 修复: Intel 优化路径现在传递 self 引用作为 engine，
        使 benchmark_suite / auto_tuner / performance_reporter 三个
        P2 组件能够正常初始化（之前因缺少 engine 引用而始终为 None）。
        """
        dev = self._require_device()
        device_info = dev.get_device_info()
        device_info.get("name", "")
        vendor = device_info.get("vendor", "")
        vendor_lower = vendor.lower()

        if vendor_lower.startswith("intel") or "intel" in vendor_lower:
            self.logger.info("[*] 检测到 Intel GPU，应用特殊优化")
            self._intel_optimizer = IntelGPUOptimizer(
                device=self._gpu_device,
                config=self.config,
                engine_logger=self.logger,
            )
            self._intel_optimizer.apply_optimizations(
                {
                    "kernel_source": OPENCL_KERNEL_SOURCE,
                    "engine": self,
                },
            )
        elif "nvidia" in vendor_lower:
            self.logger.info("[*] 检测到 NVIDIA GPU，应用特殊优化")
            try:
                self._nvidia_optimizer = NvidiaGPUOptimizer(
                    device_info=device_info,
                    config=self.config,
                    engine_logger=self.logger,
                )
                optimization_result = self._nvidia_optimizer.apply_optimizations()
                arch_name = optimization_result.get("arch_name", "Unknown")
                mem_ratio = optimization_result.get("recommended_memory_ratio", 0.60)
                self.logger.info(
                    "[OK] NVIDIA 优化器已初始化: 架构=%s, memory_ratio=%.2f",
                    arch_name,
                    mem_ratio,
                )
            except RuntimeError as e:
                self.logger.warning("[WARN] NVIDIA 优化器初始化失败（非致命）: %s", e)
                self._nvidia_optimizer = None
        elif "amd" in vendor_lower or "advanced micro" in vendor_lower:
            self.logger.info("[*] 检测到 AMD GPU，应用特殊优化")
            try:
                self._amd_optimizer = AmdGPUOptimizer(
                    device_info=device_info,
                    config=self.config,
                    engine_logger=self.logger,
                )
                optimization_result = self._amd_optimizer.apply_optimizations()
                arch_name = optimization_result.get("arch_name", "Unknown")
                mem_ratio = optimization_result.get("recommended_memory_ratio", 0.60)
                self.logger.info(
                    "[OK] AMD 优化器已初始化: 架构=%s, memory_ratio=%.2f",
                    arch_name,
                    mem_ratio,
                )
            except RuntimeError as e:
                self.logger.warning("[WARN] AMD 优化器初始化失败（非致命）: %s", e)
                self._amd_optimizer = None

    def cleanup(self) -> None:
        """清理GPU资源（按依赖逆序释放）.

        清理顺序（与初始化顺序相反）:
        1. 清理异步执行器（资源取消 + 等待完成）
        2. 清理 GPU 内核
        3. 清理内存池（释放所有缓冲）
        4. 清理 GPU 上下文
        5. 清理 GPU 设备

        所有清理步骤均包含异常保护，单个步骤失败不影响后续清理。
        """
        try:
            # 清理异步执行器
            if self._async_executor:
                start_time = time.time()
                self._async_executor.cleanup()
                elapsed = time.time() - start_time
                self.logger.info(
                    "设备管理器：异步执行器已清理 (耗时: %.2f秒)",
                    elapsed,
                )

            # 清理内核
            if self._gpu_kernel:
                start_time = time.time()
                self._gpu_kernel.cleanup()
                elapsed = time.time() - start_time
                self.logger.info(
                    "设备管理器：内核已清理 (耗时: %.2f秒)",
                    elapsed,
                )

            # 清理内存池
            if self._gpu_memory_pool:
                start_time = time.time()
                self._gpu_memory_pool.clear()
                self._gpu_memory_pool = None
                elapsed = time.time() - start_time
                self.logger.info(
                    "设备管理器：内存池已清理 (耗时: %.2f秒)",
                    elapsed,
                )

            # 清理上下文
            if self._gpu_context:
                start_time = time.time()
                self._gpu_context.cleanup()
                elapsed = time.time() - start_time
                self.logger.info(
                    "设备管理器：上下文已清理 (耗时: %.2f秒)",
                    elapsed,
                )

            # 清理设备
            if self._gpu_device:
                start_time = time.time()
                self._gpu_device.cleanup()
                elapsed = time.time() - start_time
                self.logger.info(
                    "设备管理器：设备已清理 (耗时: %.2f秒)",
                    elapsed,
                )

            self.logger.info("设备管理器：GPU资源清理完成")
        except RuntimeError as e:
            self.logger.warning("设备管理器：GPU资源清理失败: %s", e)
            traceback.print_exc()

    @property
    def device(self) -> GPUDevice:
        """获取GPU设备实例."""
        if self._gpu_device is None:
            raise RuntimeError("GPUDevice 尚未初始化，请先调用 initialize()")
        return self._gpu_device

    @property
    def context(self) -> GPUContext:
        """获取GPU上下文实例."""
        if self._gpu_context is None:
            raise RuntimeError("GPUContext 尚未初始化，请先调用 initialize()")
        return self._gpu_context

    @property
    def kernel(self) -> GPUKernel:
        """获取GPU内核实例."""
        if self._gpu_kernel is None:
            raise RuntimeError("GPUKernel 尚未初始化，请先调用 initialize()")
        return self._gpu_kernel

    @property
    def async_executor(self) -> AsyncGPUExecutor:
        """获取异步执行器实例."""
        if self._async_executor is None:
            raise RuntimeError("AsyncGPUExecutor 尚未初始化，请先调用 initialize()")
        return self._async_executor

    @property
    def memory_pool(self) -> Any:
        """获取内存池实例."""
        return self._gpu_memory_pool

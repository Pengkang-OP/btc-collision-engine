"""Intel GPU特定优化

针对Intel GPU(特别是Arc系列)的优化策略,包括:
- uint32 workaround避免global char* hang bug
- 超时保护机制
- 保守的batch_size策略
- 日志频率限制（防止重复日志泵洪）
"""

from typing import Any, Dict, Optional
import logging

# P3-5: 统一日志获取
from ...utils import init_logging, get_configured_logger
import time
from .base import GPUVendorBase
from ..constants import PER_KEY_MEMORY_BYTES, MIN_BATCH_SIZE, align_batch_size

logger = get_configured_logger("IntelVendor")


class _RateLimitedLogger:
    """日志频率限制器 - 防止相同日志在短时间内重复输出导致泵洪"""

    def __init__(self, base_logger: Any, min_interval: float = 60.0) -> None:
        """
        Args:
            base_logger: 基础 logger
            min_interval: 相同消息的最小输出间隔（秒），默认 60s
        """
        self._logger = base_logger
        self._min_interval = min_interval
        self._last_logged: Dict[str, float] = {}

    def _should_log(self, key: str) -> bool:
        now = time.time()
        last = self._last_logged.get(key, 0.0)
        if now - last >= self._min_interval:
            self._last_logged[key] = now
            return True
        return False

    def warning(self, msg: str, key: str = None) -> None:
        k = key or msg[:80]
        if self._should_log(k):
            self._logger.warning(msg)

    def info(self, msg: str, key: str = None) -> None:
        k = key or msg[:80]
        if self._should_log(k):
            self._logger.info(msg)

    def error(self, msg: str, key: str = None) -> None:
        """error 级别不限流，始终输出"""
        self._logger.error(msg)

    def debug(self, msg: str) -> None:
        self._logger.debug(msg)


# 初始化限流 logger（1分钟内相同消息不重复输出）
_rate_logger = _RateLimitedLogger(logger, min_interval=60.0)


class IntelGPUVendor(GPUVendorBase):
    """Intel GPU优化处理器"""
    
    def get_vendor_name(self) -> str:
        return "Intel"
    
    def apply_optimizations(self, device: Any, profile: Dict[str, Any]) -> None:
        """
        应用Intel特定优化
        
        优化策略:
        1. uint32 workaround(避免global char* hang bug)
        2. 超时保护机制
        3. 保守的内存使用策略
        4. Arc驱动特定优化
        5. 根据驱动版本应用特定优化
        """
        device_name = device.device_info.get('name', 'Unknown')
        logger.info(f"应用Intel优化策略: {device_name}")
        
        optimizations = profile.get('optimizations', [])
        known_issues = profile.get('known_issues', [])
        
        # 1. uint32 workaround - 关键优化
        if 'uint32_workaround' in optimizations:
            _rate_logger.info("✅ 启用uint32 workaround(避免Intel Arc global char* hang bug)",
                             key="intel_uint32_workaround")
            # 标记设备需要特殊处理
            device.requires_uint32_workaround = True
            # 在GPUKernel中使用uint32*替代uchar*
            # 这是Intel Arc驱动的关键bug workaround
        
        # 2. 超时保护
        if 'timeout_protection' in optimizations:
            timeout_seconds = profile.get('timeout_seconds', 30)
            _rate_logger.info(f"✅ 启用超时保护机制: {timeout_seconds}秒",
                             key="intel_timeout_protection")
            # 在GPUKernel.run_batch中添加超时
            # 防止内核hang住导致线程永久阻塞
            device.timeout_seconds = timeout_seconds
        
        # 3. 异步传输 - 仅对低端/不稳定型号禁用，Arc A770 等高端卡保持异步启用
        if 'async_transfer' in optimizations:
            # 清除 (R)/(TM) 等商标标记后再匹配
            import re
            device_name_clean = re.sub(r'\((?:r|tm|R|TM)\)', '', device_name.lower()).strip()
            device_name_clean = re.sub(r'\s+', ' ', device_name_clean)  # 合并多余空格
            # Arc A770/A750/A580 及 Pro 系列支持异步执行，不禁用
            is_high_end = any(x in device_name_clean for x in [
                'arc a770', 'arc a750', 'arc a580',
                'arc pro', 'arc a3'
            ])
            if not is_high_end:
                _rate_logger.warning("⚠️ Intel GPU: 禁用异步传输以确保稳定性",
                                    key="intel_async_disabled")
                device.enable_async_execution = False
            else:
                _rate_logger.info(
                    f"✅ Intel Arc 高端型号 ({device_name}): 保持异步执行启用",
                    key="intel_async_kept"
                )
        
        # 4. 专业驱动优化
        if 'pro_driver_optimization' in optimizations:
            logger.debug("启用Intel Pro驱动优化")
            # Arc Pro系列使用专业驱动,更稳定
        
        # 5. 驱动版本检查
        self._check_driver_version(device)
        
        # 6. 驱动特定优化
        if device.driver_optimization_flags.get('conservative_mode', False):
            _rate_logger.warning(
                "Intel驱动保守模式: "
                "使用更小的batch_size和更严格的超时",
                key="intel_conservative_mode"
            )
        
        # 7. 记录已知问题
        if 'global_char_hang_bug' in known_issues:
            _rate_logger.warning(
                "⚠️ Intel Arc存在global char* hang bug, "
                "已启用uint32 workaround",
                key="intel_known_hang_bug"
            )
        
        # 8. 显存效率设置 (v2.2.1优化: 45% -> 70%)
        memory_efficiency = profile.get('memory_efficiency', 0.70)
        device.memory_efficiency = memory_efficiency
        _rate_logger.info(
            f"✅ Intel GPU内存效率: {memory_efficiency*100:.0f}% (v2.2.1优化)",
            key="intel_memory_efficiency"
        )
    
    def calculate_batch_size(self, device: Any, profile: Dict[str, Any]) -> int:
        """
        计算Intel GPU的最优batch_size
        
        策略:
        1. Intel Arc需要使用更保守的batch_size
        2. 避免显存占用过高导致不稳定
        3. 优先考虑稳定性而非性能
        """
        recommended = profile.get('recommended_batch_size', 262144)
        maximum = profile.get('max_batch_size', 524288)
        memory_efficiency = profile.get('memory_efficiency', 0.70)  # v2.2.1优化: 45% -> 70%
        
        # 根据显存计算理论最大值(使用更保守的memory_efficiency)
        global_mem = device.device_info.get('global_mem_size', 0)
        per_key_memory = PER_KEY_MEMORY_BYTES
        mem_based_max = int((global_mem * memory_efficiency) / per_key_memory)
        
        # 取三者最小值
        optimal = min(recommended, maximum, mem_based_max)
        
        # 向下对齐到1024的倍数，并确保不低于最小值
        optimal = align_batch_size(optimal)
        
        logger.info(
            f"Intel batch_size计算: recommended={recommended}, "
            f"mem_based={mem_based_max}, optimal={optimal} "
            f"(保守策略)"
        )
        
        return optimal
    
    def _check_driver_version(self, device):
        """检查驱动版本并给出建议"""
        driver_version = device.driver_version
        if not driver_version:
            _rate_logger.warning("⚠️ 无法检测Intel驱动版本，使用保守模式",
                               key="intel_no_driver_version")
            return
        
        try:
            # 解析版本号 (格式: 31.0.101.4500)
            parts = driver_version.split('.')
            if len(parts) >= 4:
                major = int(parts[0])
                minor = int(parts[1])
                build = int(parts[2])
                revision = int(parts[3])
                
                # 检查是否为推荐版本
                if (major, minor, build, revision) < (31, 0, 101, 4500):
                    _rate_logger.warning(
                        f"⚠️ Intel驱动版本 {driver_version} 较旧，"
                        f"建议更新到 31.0.101.4500+ 以获得更好的稳定性",
                        key=f"intel_driver_old_{driver_version}"
                    )
                else:
                    _rate_logger.info(f"✅ Intel驱动版本 {driver_version} 符合要求",
                                    key=f"intel_driver_ok_{driver_version}")
            else:
                logger.debug(f"Intel驱动版本格式: {driver_version}")
        except (ValueError, IndexError) as e:
            logger.debug(f"无法解析Intel驱动版本: {driver_version}, 错误: {e}")
    
    def handle_errors(self, error: Exception, stats: Optional[Any] = None) -> bool:
        """
        处理Intel GPU特定错误
        
        Intel Arc容易出现超时和hang错误
        """
        error_msg = str(error).lower()
        
        # 超时错误
        if 'timeout' in error_msg or 'timed out' in error_msg:
            logger.error(f"Intel GPU执行超时: {error}")
            if stats:
                stats.record_gpu_error(is_resource_error=False)
            return True  # 继续执行,但记录错误
        
        # 内核hang错误
        if 'hang' in error_msg or 'stall' in error_msg:
            logger.error(f"Intel GPU内核hang: {error}")
            if stats:
                stats.record_gpu_error(is_resource_error=True)
            return True  # 继续执行
        
        # 资源不足
        if any(keyword in error_msg for keyword in [
            'out of memory', 'out of resources', 'allocation failed'
        ]):
            logger.error(f"Intel GPU资源不足: {error}")
            if stats:
                stats.record_gpu_error(is_resource_error=True)
            return True
        
        return super().handle_errors(error, stats)

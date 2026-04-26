# -*- coding: utf-8 -*-
"""GPU参数自动调优器

根据不同厂商和型号的GPU自动配置最优参数。
支持NVIDIA、AMD、Intel Arc的特定优化。
"""

import logging
import threading
from typing import Dict

logger = logging.getLogger(__name__)

# 字节到GB的转换常量
_BYTES_TO_GB = 1024 ** 3  # 1,073,741,824


def _align_work_group_size(recommended: int, max_wgs: int, alignment: int) -> int:
    """将work_group_size对齐到厂商最优值，且不超过设备限制"""
    if max_wgs <= 0:
        return 1

    wgs = min(recommended, max_wgs)

    if max_wgs < alignment:
        return max_wgs

    wgs = (wgs // alignment) * alignment
    if wgs == 0:
        wgs = alignment

    return min(wgs, max_wgs)


def _get_memory_gb(device: Dict) -> float:
    """获取GPU显存大小(GB)
    
    v2.2.1修复: 兼容global_mem_size(字节)和global_mem_gb两种格式
    
    Args:
        device: 设备信息字典
        
    Returns:
        显存大小(GB)，如果无法获取则返回0
    """
    if not isinstance(device, dict):
        logger.error(f"device参数类型错误: 期望dict, 实际{type(device)}")
        return 0
    
    memory_gb = device.get('global_mem_gb', 0)
    
    # 验证memory_gb是否为有效数值
    if not isinstance(memory_gb, (int, float)) or memory_gb < 0:
        memory_gb = 0
    
    if memory_gb == 0:
        # 如果没有global_mem_gb，从global_mem_size(字节)转换
        memory_bytes = device.get('global_mem_size', 0)
        
        # 验证memory_bytes是否为有效数值
        if not isinstance(memory_bytes, (int, float)) or memory_bytes < 0:
            memory_bytes = 0
            
        if memory_bytes > 0:
            memory_gb = memory_bytes / _BYTES_TO_GB
            logger.debug(f"从global_mem_size转换显存: {memory_bytes} 字节 = {memory_gb:.2f} GB")
        else:
            logger.warning("无法获取GPU显存信息(global_mem_gb和global_mem_size均为0)")
    
    return memory_gb


class GPUAutoConfigurator:
    """GPU参数自动调优器
    
    根据GPU厂商、型号、显存等参数自动生成最优配置。
    
    使用示例:
        configurator = GPUAutoConfigurator()
        
        # 为设备生成配置
        config = configurator.configure_for_device(device_info)
        
        # 获取特定厂商配置
        nvidia_config = configurator.get_nvidia_config(device_info)
    """
    
    # NVIDIA GPU配置模板
    NVIDIA_CONFIG = {
        'batch_size': 131072,      # 128K - NVIDIA适合大批次
        'work_group_size': 512,    # 大工作组
        'memory_usage_ratio': 0.7, # 较高显存使用率
        'enable_async': True,      # 异步执行
        'use_fast_math': True,     # 快速数学运算
        'use_uint32_workaround': False,
        'compiler_flags': '-cl-fast-relaxed-math'
    }
    
    # AMD GPU配置模板
    AMD_CONFIG = {
        'batch_size': 65536,       # 64K - 中等批次
        'work_group_size': 256,    # 中等工作组
        'memory_usage_ratio': 0.6, # 中等显存使用率
        'enable_async': True,
        'use_fast_math': True,
        'use_uint32_workaround': False,
        'compiler_flags': '-cl-opt-disable'  # AMD某些情况下需要
    }
    
    # Intel Arc GPU配置模板
    # CFG-2修复: 统一为保守策略，避免显存使用过高导致不稳定
    INTEL_ARC_CONFIG = {
        'batch_size': 262144,      # v2.2.1优化: 262K - 经测试最优批次大小
        'work_group_size': 512,    # v2.3.0优化: 512 - 匹配A770的512个EU(原256)
        'memory_usage_ratio': 0.45, # CFG-2修复: 保守策略(原0.7)，提高稳定性
        'enable_async': True,      # 异步执行(必须)
        'use_fast_math': False,    # 禁用快速数学(加密运算需要精度)
        'use_uint32_workaround': True,  # uint32溢出workaround(必须)
        'compiler_flags': ''       # 不使用优化标志(加密运算不适用)
    }
    
    # 未知GPU保守配置
    UNKNOWN_CONFIG = {
        'batch_size': 32768,
        'work_group_size': 256,
        'memory_usage_ratio': 0.5,
        'enable_async': False,
        'use_fast_math': False,
        'use_uint32_workaround': False,
        'compiler_flags': ''
    }
    
    def __init__(self):
        """初始化自动调优器"""
        self._config_cache = {}
        
        logger.info("GPUAutoConfigurator已初始化")
    
    def configure_for_device(self, device: Dict) -> Dict:
        """为指定设备生成优化配置
        
        Args:
            device: 设备信息字典(包含vendor, name, global_mem_gb等)
            
        Returns:
            优化配置字典
        """
        vendor = device.get('vendor', 'unknown')
        device_key = f"{vendor}_{device.get('name', 'unknown')}"
        
        # 检查缓存
        if device_key in self._config_cache:
            logger.debug(f"使用缓存配置: {device_key}")
            return self._config_cache[device_key].copy()
        
        # 根据厂商生成配置（兼容完整厂商名称如 'Intel(R) Corporation'）
        vendor_lower = vendor.lower()
        if 'nvidia' in vendor_lower:
            config = self.get_nvidia_config(device)
        elif 'amd' in vendor_lower or 'advanced micro' in vendor_lower:
            config = self.get_amd_config(device)
        elif 'intel' in vendor_lower:
            config = self.get_intel_config(device)
        else:
            config = self.get_unknown_config(device)
        
        # 根据显存调整批次大小
        config = self._adjust_for_memory(device, config)
        
        # 缓存配置
        self._config_cache[device_key] = config.copy()
        
        logger.info(
            f"设备配置已生成: {device.get('name')} "
            f"(厂商={vendor}, 批次={config['batch_size']:,})"
        )
        
        return config
    
    def get_nvidia_config(self, device: Dict) -> Dict:
        """生成NVIDIA GPU配置
        
        NVIDIA特点:
        - 适合大批次处理
        - 支持大工作组(512-1024)
        - 可以使用快速数学运算
        - 异步执行性能好
        """
        config = self.NVIDIA_CONFIG.copy()
        
        # v2.2.1修复: 使用统一的显存获取方法
        memory_gb = _get_memory_gb(device)
        if memory_gb >= 24:
            # RTX 3090/4090等高端卡
            config['batch_size'] = 262144  # 256K
            config['memory_usage_ratio'] = 0.8
        elif memory_gb >= 12:
            # RTX 3080/4070等
            config['batch_size'] = 131072  # 128K
            config['memory_usage_ratio'] = 0.75
        elif memory_gb >= 8:
            # RTX 3070/2080等
            config['batch_size'] = 65536   # 64K
            config['memory_usage_ratio'] = 0.7
        else:
            # GTX 1660 Ti等
            config['batch_size'] = 32768   # 32K
            config['memory_usage_ratio'] = 0.6
        
        # 自适应 work_group_size: NVIDIA Warp大小对齕32
        max_wgs = device.get('max_work_group_size', 1024)
        recommended_wgs = 256
        adjusted_wgs = _align_work_group_size(recommended_wgs, max_wgs, 32)
        if adjusted_wgs != recommended_wgs:
            logger.info(
                f"[NVIDIA] work_group_size从{recommended_wgs}调整为{adjusted_wgs} "
                f"(设备限制: {max_wgs}, 对齐: 32)"
            )
        config['work_group_size'] = adjusted_wgs
        
        return config
    
    def get_amd_config(self, device: Dict) -> Dict:
        """生成AMD GPU配置
        
        AMD特点:
        - 中等批次大小
        - 工作组大小适中
        - 某些型号需要禁用编译器优化
        """
        config = self.AMD_CONFIG.copy()
        
        # v2.2.1修复: 使用统一的显存获取方法
        memory_gb = _get_memory_gb(device)
        if memory_gb >= 16:
            # RX 6800 XT/7900 XTX等
            config['batch_size'] = 131072  # 128K
        elif memory_gb >= 8:
            # RX 6700 XT/7600等
            config['batch_size'] = 65536   # 64K
        else:
            config['batch_size'] = 32768   # 32K
        
        # 自适应 work_group_size: AMD Wavefront大小对齕64 (GCN架构, RDNA为32)
        max_wgs = device.get('max_work_group_size', 1024)
        recommended_wgs = 256
        adjusted_wgs = _align_work_group_size(recommended_wgs, max_wgs, 64)
        if adjusted_wgs != recommended_wgs:
            logger.info(
                f"[AMD] work_group_size从{recommended_wgs}调整为{adjusted_wgs} "
                f"(设备限制: {max_wgs}, 对齐: 64)"
            )
        config['work_group_size'] = adjusted_wgs
        
        return config
    
    def get_intel_config(self, device: Dict) -> Dict:
        """生成Intel Arc GPU配置
        
        Intel Arc特点:
        - 需要uint32 workarounds(溢出问题)
        - 必须启用异步执行
        - 禁用快速数学运算(精度问题)
        - 较小批次大小(避免超时)
        """
        config = self.INTEL_ARC_CONFIG.copy()
        
        # v2.2.1修复: 使用统一的显存获取方法
        memory_gb = _get_memory_gb(device)
        if memory_gb >= 15:  # v2.2.1修改: 15.56GB的A770也能匹配
            # Arc A770 16GB - v3.1.0优化: 提升到 1M（原262K），充分利用16GB显存
            config['batch_size'] = 1048576  # 1M，42MB显存占用（A770有充足余量）
            config['memory_usage_ratio'] = 0.70
            recommended_wgs = 512  # v2.3.0优化: 匹配512个EU
        elif memory_gb >= 8:
            # Arc A750/A580 - v2.2.1优化: 提升到131K
            config['batch_size'] = 131072   # 131K
            config['memory_usage_ratio'] = 0.6
            recommended_wgs = 512
        else:
            # Arc A380等低端卡
            config['batch_size'] = 65536   # 65K
            config['memory_usage_ratio'] = 0.5
            recommended_wgs = 512
        
        # 自适应 work_group_size: Intel Arc EU对齕32
        max_wgs = device.get('max_work_group_size', 1024)
        adjusted_wgs = _align_work_group_size(recommended_wgs, max_wgs, 32)
        if adjusted_wgs != recommended_wgs:
            logger.info(
                f"[Intel Arc] work_group_size从{recommended_wgs}调整为{adjusted_wgs} "
                f"(设备限制: {max_wgs}, 对齐: 32)"
            )
        config['work_group_size'] = adjusted_wgs
        
        return config
    
    def get_unknown_config(self, device: Dict) -> Dict:
        """生成未知GPU的保守配置
        
        对于未知厂商,使用最保守的配置以确保稳定性。
        """
        config = self.UNKNOWN_CONFIG.copy()
        
        # v2.2.1修复: 使用统一的显存获取方法
        memory_gb = _get_memory_gb(device)
        if memory_gb >= 8:
            config['batch_size'] = 65536
        elif memory_gb >= 4:
            config['batch_size'] = 32768
        else:
            config['batch_size'] = 16384
        
        # 自适应 work_group_size: 保守配置对齕32
        max_wgs = device.get('max_work_group_size', 1024)
        recommended_wgs = 256
        adjusted_wgs = _align_work_group_size(recommended_wgs, max_wgs, 32)
        if adjusted_wgs != recommended_wgs:
            logger.info(
                f"[Unknown GPU] work_group_size从{recommended_wgs}调整为{adjusted_wgs} "
                f"(设备限制: {max_wgs}, 对齐: 32)"
            )
        config['work_group_size'] = adjusted_wgs
        
        return config
    
    def _adjust_for_memory(self, device: Dict, config: Dict) -> Dict:
        """根据实际显存调整配置
        
        Args:
            device: 设备信息
            config: 基础配置
            
        Returns:
            调整后的配置
        """
        # v2.2.1修复: 使用统一的显存获取方法
        memory_gb = _get_memory_gb(device)
        
        batch_size = config['batch_size']
        
        # v2.2.1修复: 修正显存估算公式
        # 实际测试: 262K批次使用约9MB显存，而非536MB
        # 
        # 显存组成 (每密钥):
        #   - 私钥缓冲区 (_keys_buf):    32 字节
        #   - 匹配缓冲区 (_match_buf):    4 字节
        #   - 安全边际:                   15% (6 字节)
        #   总计:                        42 字节
        estimated_memory_gb = (batch_size * 42) / (1024 ** 3)
        
        # 如果估算显存超过可用显存的安全比例,减小批次
        max_safe_memory = memory_gb * config['memory_usage_ratio']
        
        if estimated_memory_gb > max_safe_memory:
            # 按比例减小批次大小
            ratio = max_safe_memory / estimated_memory_gb
            new_batch_size = int(batch_size * ratio)
            
            # 确保最小batch_size为1024
            if new_batch_size < 1024:
                new_batch_size = 1024
                logger.warning(
                    f"显存不足,批次大小从 {batch_size:,} 调整为最小值 {new_batch_size:,}"
                )
            else:
                # 对齐到2的幂
                new_batch_size = 1 << (new_batch_size.bit_length() - 1)
                logger.warning(
                    f"显存不足,批次大小从 {batch_size:,} 调整为 {new_batch_size:,}"
                )
            
            config['batch_size'] = new_batch_size
        
        return config
    
    def validate_config(self, config: Dict, device: Dict) -> tuple:
        """验证配置是否合理
        
        Args:
            config: 配置字典
            device: 设备信息
            
        Returns:
            (is_valid, warnings) 元组
        """
        warnings = []
        
        # 检查批次大小
        batch_size = config.get('batch_size', 0)
        if batch_size < 1024:
            warnings.append(f"批次大小过小({batch_size}),性能可能较差")
        elif batch_size > 1048576:
            warnings.append(f"批次大小过大({batch_size}),可能导致显存不足")
        
        # 检查工作組大小
        work_group = config.get('work_group_size', 0)
        max_work_group = device.get('max_work_group_size', 1024)
        if work_group > max_work_group:
            warnings.append(
                f"工作组大小({work_group})超过设备最大值({max_work_group})"
            )
        
        # 检查显存使用率
        memory_ratio = config.get('memory_usage_ratio', 0.5)
        if memory_ratio > 0.9:
            warnings.append(f"显存使用率过高({memory_ratio}),可能导致不稳定")
        elif memory_ratio < 0.3:
            warnings.append(f"显存使用率过低({memory_ratio}),性能可能不佳")
        
        is_valid = len(warnings) == 0
        
        return is_valid, warnings
    
    def get_config_summary(self, config: Dict) -> str:
        """获取配置摘要
        
        Args:
            config: 配置字典
            
        Returns:
            格式化字符串
        """
        lines = [
            "GPU配置详情:",
            f"  批次大小: {config.get('batch_size', 0):,}",
            f"  工作组大小: {config.get('work_group_size', 0)}",
            f"  显存使用率: {config.get('memory_usage_ratio', 0):.0%}",
            f"  异步执行: {config.get('enable_async', False)}",
            f"  快速数学: {config.get('use_fast_math', False)}",
            f"  uint32 workaround: {config.get('use_uint32_workaround', False)}",
            f"  编译标志: {config.get('compiler_flags', '无')}"
        ]
        
        return '\n'.join(lines)
    
    def clear_cache(self):
        """清除配置缓存"""
        self._config_cache.clear()
        logger.debug("配置缓存已清除")


# 线程安全的单例
_configurator_instance = None
_configurator_lock = threading.Lock()

def get_gpu_configurator() -> GPUAutoConfigurator:
    """获取GPU自动调优器单例（线程安全）
    
    Returns:
        GPUAutoConfigurator实例
    """
    global _configurator_instance
    
    # 双重检查锁定模式
    if _configurator_instance is None:
        with _configurator_lock:
            if _configurator_instance is None:
                _configurator_instance = GPUAutoConfigurator()
    
    return _configurator_instance


def reset_gpu_configurator():
    """重置GPU自动调优器单例(用于测试)"""
    global _configurator_instance
    with _configurator_lock:
        _configurator_instance = None

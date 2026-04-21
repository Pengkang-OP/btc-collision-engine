# -*- coding: utf-8 -*-
"""GPU负载均衡器

为多GPU环境提供智能的任务分配和负载均衡。
支持按性能分配和平均分配两种策略。
"""

import logging
from typing import List, Dict, Tuple, Optional
import time

logger = logging.getLogger(__name__)


class GPULoadBalancer:
    """GPU负载均衡器
    
    根据GPU设备性能智能分配私钥搜索任务。
    
    负载分配策略:
    1. performance(按性能): 根据显存和计算单元分配权重
    2. equal(平均分配): 所有GPU平均分配任务
    
    使用示例:
        balancer = GPULoadBalancer(devices, strategy='performance')
        
        # 计算负载权重
        weights = balancer.calculate_weights()
        
        # 为GPU分配私钥范围
        start, end = balancer.assign_key_range(1000000, device_idx=0)
    """
    
    # 厂商性能系数(基于实际测试经验值)
    VENDOR_PERFORMANCE_FACTORS = {
        'nvidia': 1.0,    # NVIDIA基准性能
        'amd': 0.95,      # AMD略低
        'intel': 0.9,     # Intel Arc需要workarounds
        'unknown': 0.8    # 未知厂商保守估计
    }
    
    def __init__(
        self,
        devices: List[Dict],
        strategy: str = 'performance',
        rebalance_interval: int = 60
    ):
        """初始化负载均衡器
        
        Args:
            devices: GPU设备列表
            strategy: 负载策略 ('performance' 或 'equal')
            rebalance_interval: 动态重平衡间隔(秒)
        """
        if not devices:
            raise ValueError("设备列表不能为空")
        
        self.devices = devices
        self.strategy = strategy
        self.rebalance_interval = rebalance_interval
        
        self._weights = {}
        self._key_ranges = {}
        self._last_rebalance_time = time.time()
        self._performance_stats = {}
        
        # 计算初始权重
        self._calculate_initial_weights()
        
        logger.info(
            f"GPU负载均衡器已初始化: "
            f"设备数={len(devices)}, 策略={strategy}"
        )
    
    def _calculate_initial_weights(self):
        """计算初始负载权重"""
        if self.strategy == 'equal':
            # 平均分配
            weight = 1.0 / len(self.devices)
            self._weights = {
                device['global_index']: weight
                for device in self.devices
            }
        else:
            # 按性能分配
            self._weights = self._calculate_performance_weights()
        
        logger.info(f"初始负载权重: {self._weights}")
    
    def _calculate_performance_weights(self) -> Dict[int, float]:
        """基于设备性能计算权重
        
        算法:
        weight = (memory_gb * 0.6 + compute_units * 0.01) * vendor_factor
        
        Returns:
            设备索引 -> 权重映射
        """
        raw_weights = {}
        
        for device in self.devices:
            idx = device['global_index']
            memory_gb = device.get('global_mem_gb', 0)
            compute_units = device.get('max_compute_units', 0)
            vendor = device.get('vendor', 'unknown')
            
            # 厂商系数
            vendor_factor = self.VENDOR_PERFORMANCE_FACTORS.get(vendor, 0.8)
            
            # 计算原始权重
            weight = (memory_gb * 0.6 + compute_units * 0.01) * vendor_factor
            raw_weights[idx] = weight
        
        # 归一化(使总和为1)
        total_weight = sum(raw_weights.values())
        if total_weight > 0:
            normalized_weights = {
                idx: w / total_weight
                for idx, w in raw_weights.items()
            }
        else:
            # 降级为平均分配
            normalized_weights = {
                idx: 1.0 / len(self.devices)
                for idx in raw_weights.keys()
            }
        
        return normalized_weights
    
    def calculate_weights(self) -> Dict[int, float]:
        """获取当前负载权重
        
        Returns:
            设备索引 -> 权重映射
        """
        return self._weights.copy()
    
    def assign_key_range(
        self,
        total_keys: int,
        device_idx: int,
        key_offset: int = 0
    ) -> Tuple[int, int]:
        """为指定GPU分配私钥搜索范围
        
        Args:
            total_keys: 总私钥数量
            device_idx: GPU设备索引
            key_offset: 私钥起始偏移量
            
        Returns:
            (start_key, end_key) 私钥范围
        """
        if device_idx not in self._weights:
            raise ValueError(f"设备索引 {device_idx} 不存在于负载均衡器中")
        
        weight = self._weights[device_idx]
        
        # 计算该GPU分配的私钥数量
        device_keys = int(total_keys * weight)
        
        # 计算范围
        start_key = key_offset + int(total_keys * self._get_cumulative_weight(device_idx))
        end_key = start_key + device_keys
        
        # 缓存范围
        self._key_ranges[device_idx] = (start_key, end_key)
        
        logger.debug(
            f"设备 {device_idx} 分配范围: "
            f"[{start_key}, {end_key}), 数量={device_keys:,}, "
            f"权重={weight:.3f}"
        )
        
        return start_key, end_key
    
    def _get_cumulative_weight(self, device_idx: int) -> float:
        """获取设备的累积权重(用于计算偏移)
        
        Args:
            device_idx: 设备索引
            
        Returns:
            累积权重(0.0-1.0)
        """
        # 按设备索引排序
        sorted_indices = sorted(self._weights.keys())
        
        cumulative = 0.0
        for idx in sorted_indices:
            if idx == device_idx:
                break
            cumulative += self._weights[idx]
        
        return cumulative
    
    def assign_all_key_ranges(
        self,
        total_keys: int,
        key_offset: int = 0
    ) -> Dict[int, Tuple[int, int]]:
        """为所有GPU分配私钥范围
        
        Args:
            total_keys: 总私钥数量
            key_offset: 私钥起始偏移量
            
        Returns:
            设备索引 -> (start, end) 映射
        """
        ranges = {}
        current_offset = key_offset
        
        # 按权重排序,确保大权重GPU先分配
        sorted_devices = sorted(
            self.devices,
            key=lambda d: self._weights.get(d['global_index'], 0),
            reverse=True
        )
        
        for device in sorted_devices:
            idx = device['global_index']
            weight = self._weights[idx]
            device_keys = int(total_keys * weight)
            
            start_key = current_offset
            end_key = start_key + device_keys
            
            ranges[idx] = (start_key, end_key)
            self._key_ranges[idx] = (start_key, end_key)
            
            current_offset = end_key
            
            logger.debug(
                f"设备 {idx} 分配: [{start_key}, {end_key}), "
                f"数量={device_keys:,}"
            )
        
        return ranges
    
    def record_performance(
        self,
        device_idx: int,
        throughput: float,
        error_rate: float = 0.0
    ):
        """记录GPU实际性能
        
        Args:
            device_idx: 设备索引
            throughput: 吞吐量(keys/s)
            error_rate: 错误率(0.0-1.0)
        """
        self._performance_stats[device_idx] = {
            'throughput': throughput,
            'error_rate': error_rate,
            'timestamp': time.time()
        }
    
    def should_rebalance(self) -> bool:
        """检查是否需要重新平衡负载
        
        Returns:
            True表示需要重新平衡
        """
        now = time.time()
        elapsed = now - self._last_rebalance_time
        
        return elapsed >= self.rebalance_interval
    
    def redistribute_load(self) -> Dict[int, float]:
        """根据实际性能重新分配负载
        
        Returns:
            新的权重映射
        """
        if not self._performance_stats:
            logger.debug("无性能数据,保持当前权重")
            return self._weights
        
        # 检查是否需要重新平衡
        if not self.should_rebalance():
            return self._weights
        
        logger.info("开始动态负载重平衡...")
        
        # 基于实际吞吐量计算新权重
        new_weights = {}
        total_throughput = 0
        
        for idx, stats in self._performance_stats.items():
            throughput = stats['throughput']
            error_rate = stats['error_rate']
            
            # 有效吞吐量(考虑错误率)
            effective_throughput = throughput * (1 - error_rate)
            new_weights[idx] = effective_throughput
            total_throughput += effective_throughput
        
        # 归一化
        if total_throughput > 0:
            self._weights = {
                idx: tp / total_throughput
                for idx, tp in new_weights.items()
            }
        else:
            # 降级为平均分配
            self._weights = {
                idx: 1.0 / len(self.devices)
                for idx in self._weights.keys()
            }
        
        self._last_rebalance_time = time.time()
        
        logger.info(f"负载重平衡完成: {self._weights}")
        return self._weights
    
    def get_device_load(self, device_idx: int) -> Optional[Dict]:
        """获取指定GPU的负载信息
        
        Args:
            device_idx: 设备索引
            
        Returns:
            负载信息字典
        """
        if device_idx not in self._weights:
            return None
        
        weight = self._weights[device_idx]
        key_range = self._key_ranges.get(device_idx, (0, 0))
        perf_stats = self._performance_stats.get(device_idx, {})
        
        return {
            'device_idx': device_idx,
            'weight': weight,
            'key_range': key_range,
            'throughput': perf_stats.get('throughput', 0),
            'error_rate': perf_stats.get('error_rate', 0),
            'last_update': perf_stats.get('timestamp', 0)
        }
    
    def get_all_loads(self) -> Dict[int, Dict]:
        """获取所有GPU的负载信息
        
        Returns:
            设备索引 -> 负载信息映射
        """
        loads = {}
        for device in self.devices:
            idx = device['global_index']
            load = self.get_device_load(idx)
            if load:
                loads[idx] = load
        
        return loads
    
    def get_strategy(self) -> str:
        """获取当前负载策略
        
        Returns:
            策略名称
        """
        return self.strategy
    
    def set_strategy(self, strategy: str):
        """设置负载策略
        
        Args:
            strategy: 'performance' 或 'equal'
        """
        if strategy not in ('performance', 'equal'):
            raise ValueError(f"无效的策略: {strategy}, 必须是 'performance' 或 'equal'")
        
        self.strategy = strategy
        self._calculate_initial_weights()
        
        logger.info(f"负载策略已更改为: {strategy}")
    
    def reset(self):
        """重置负载均衡器"""
        self._weights = {}
        self._key_ranges = {}
        self._performance_stats = {}
        self._last_rebalance_time = time.time()
        
        self._calculate_initial_weights()
        
        logger.info("负载均衡器已重置")

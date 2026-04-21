# -*- coding: utf-8 -*-
"""锁性能监控器

监控多GPU引擎中锁的等待时间、竞争频率等指标。
用于诊断性能瓶颈和锁竞争问题。
"""

import threading
import time
from typing import Dict, List
from collections import defaultdict


class LockMonitor:
    """锁性能监控器
    
    功能:
    - 记录锁等待时间
    - 统计锁竞争频率
    - 检测锁持有时间过长
    - 生成性能报告
    """
    
    def __init__(self, slow_threshold_ms: float = 10.0):
        """初始化监控器
        
        Args:
            slow_threshold_ms: 慢锁阈值(毫秒),超过此时间视为慢锁
        """
        self.slow_threshold_ms = slow_threshold_ms
        self._lock = threading.Lock()
        
        # 统计数据
        self._lock_stats = defaultdict(lambda: {
            'acquisitions': 0,  # 获取次数
            'total_wait_ms': 0.0,  # 总等待时间
            'max_wait_ms': 0.0,  # 最大等待时间
            'total_hold_ms': 0.0,  # 总持有时间
            'max_hold_ms': 0.0,  # 最大持有时间
            'slow_acquisitions': 0,  # 慢锁次数
        })
        
        # 是否启用监控
        self._enabled = True
    
    def enable(self):
        """启用监控"""
        self._enabled = True
    
    def disable(self):
        """禁用监控"""
        self._enabled = False
    
    def record_lock_acquire(self, lock_name: str, wait_time_ms: float):
        """记录锁获取
        
        Args:
            lock_name: 锁名称
            wait_time_ms: 等待时间(毫秒)
        """
        if not self._enabled:
            return
        
        with self._lock:
            stats = self._lock_stats[lock_name]
            stats['acquisitions'] += 1
            stats['total_wait_ms'] += wait_time_ms
            stats['max_wait_ms'] = max(stats['max_wait_ms'], wait_time_ms)
            
            if wait_time_ms > self.slow_threshold_ms:
                stats['slow_acquisitions'] += 1
    
    def record_lock_release(self, lock_name: str, hold_time_ms: float):
        """记录锁释放
        
        Args:
            lock_name: 锁名称
            hold_time_ms: 持有时间(毫秒)
        """
        if not self._enabled:
            return
        
        with self._lock:
            stats = self._lock_stats[lock_name]
            stats['total_hold_ms'] += hold_time_ms
            stats['max_hold_ms'] = max(stats['max_hold_ms'], hold_time_ms)
    
    def get_stats(self, lock_name: str) -> Dict:
        """获取锁统计信息
        
        Args:
            lock_name: 锁名称
            
        Returns:
            统计信息字典
        """
        with self._lock:
            if lock_name not in self._lock_stats:
                return {}
            
            stats = self._lock_stats[lock_name].copy()
            
            # 计算平均值
            if stats['acquisitions'] > 0:
                stats['avg_wait_ms'] = stats['total_wait_ms'] / stats['acquisitions']
                stats['avg_hold_ms'] = stats['total_hold_ms'] / stats['acquisitions']
            else:
                stats['avg_wait_ms'] = 0
                stats['avg_hold_ms'] = 0
            
            return stats
    
    def get_all_stats(self) -> Dict[str, Dict]:
        """获取所有锁统计信息
        
        Returns:
            所有锁的统计信息
        """
        with self._lock:
            result = {}
            for lock_name in self._lock_stats:
                result[lock_name] = self.get_stats(lock_name)
            return result
    
    def generate_report(self) -> str:
        """生成性能报告
        
        Returns:
            格式化的报告字符串
        """
        stats = self.get_all_stats()
        
        if not stats:
            return "锁监控报告: 无数据\n"
        
        report = []
        report.append("=" * 70)
        report.append("锁性能监控报告")
        report.append("=" * 70)
        report.append(f"慢锁阈值: {self.slow_threshold_ms}ms")
        report.append("")
        
        for lock_name, lock_stats in sorted(stats.items()):
            report.append(f"锁: {lock_name}")
            report.append(f"  获取次数: {lock_stats['acquisitions']}")
            report.append(f"  平均等待: {lock_stats['avg_wait_ms']:.2f}ms")
            report.append(f"  最大等待: {lock_stats['max_wait_ms']:.2f}ms")
            report.append(f"  平均持有: {lock_stats['avg_hold_ms']:.2f}ms")
            report.append(f"  最大持有: {lock_stats['max_hold_ms']:.2f}ms")
            report.append(f"  慢锁次数: {lock_stats['slow_acquisitions']}")
            report.append("")
        
        return "\n".join(report)
    
    def reset(self):
        """重置统计数据"""
        with self._lock:
            self._lock_stats.clear()


class MonitoredLock:
    """带监控的锁
    
    包装threading.Lock,自动记录性能指标。
    """
    
    def __init__(self, monitor: LockMonitor, name: str):
        """初始化
        
        Args:
            monitor: 锁监控器
            name: 锁名称
        """
        self._lock = threading.Lock()
        self._monitor = monitor
        self._name = name
        self._acquire_time = None
    
    def acquire(self, blocking=True, timeout=-1):
        """获取锁"""
        start_time = time.time()
        result = self._lock.acquire(blocking, timeout)
        wait_time_ms = (time.time() - start_time) * 1000
        
        self._monitor.record_lock_acquire(self._name, wait_time_ms)
        
        if result:
            self._acquire_time = time.time()
        
        return result
    
    def release(self):
        """释放锁"""
        if self._acquire_time:
            hold_time_ms = (time.time() - self._acquire_time) * 1000
            self._monitor.record_lock_release(self._name, hold_time_ms)
            self._acquire_time = None
        
        self._lock.release()
    
    def __enter__(self):
        self.acquire()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
        return False


# 全局锁监控器实例
_lock_monitor = LockMonitor()


def get_lock_monitor() -> LockMonitor:
    """获取全局锁监控器
    
    Returns:
        LockMonitor实例
    """
    return _lock_monitor


def create_monitored_lock(name: str) -> MonitoredLock:
    """创建带监控的锁
    
    Args:
        name: 锁名称
        
    Returns:
        MonitoredLock实例
    """
    return MonitoredLock(_lock_monitor, name)

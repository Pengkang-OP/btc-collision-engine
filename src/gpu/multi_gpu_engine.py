# -*- coding: utf-8 -*-
"""多GPU碰撞引擎

协调多个GPU工作器进行并行私钥碰撞搜索。
采用任务分割策略,每个GPU独立搜索不同的私钥范围。
"""

import logging
import time
import threading
from typing import Set, Dict, List, Optional, Callable

from .selector import get_gpu_selector
from .load_balancer import GPULoadBalancer
from .worker import SingleGPUWorker
from .data_monitor import DataMonitor

logger = logging.getLogger(__name__)


class MultiGPUCollisionEngine:
    """多GPU碰撞引擎
    
    协调多个GPU并行工作,自动分配任务和汇总结果。
    
    使用示例:
        engine = MultiGPUCollisionEngine()
        
        # 初始化(自动选择2个最佳GPU)
        engine.initialize(device_count=2)
        
        # 启动碰撞
        engine.start(targets=target_addresses, mode='random')
        
        # 获取统计
        stats = engine.get_combined_stats()
        
        # 停止
        engine.stop()
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """初始化多GPU引擎
        
        Args:
            config: 配置字典
        """
        self.config = config or {}
        
        # 核心组件
        self.selector = get_gpu_selector()
        self.load_balancer = None
        self.workers = {}
        
        # 状态管理 (使用锁保护)
        self._state_lock = threading.Lock()
        self._running = False
        self._initialized = False
        self._devices = []
        self._targets = set()
        
        # 工作器字典锁
        self._workers_lock = threading.Lock()
        
        # 匹配结果锁
        self._matches_lock = threading.Lock()
        
        # 结果收集
        self._all_matches = []
        self._match_callback = None
        
        # 统计信息
        self._start_time = None
        self._total_keys_checked = 0
        
        # 数据监控器
        monitor_config = self.config.get('data_monitor', {})
        self.data_monitor = DataMonitor(config=monitor_config)
        self._monitor_enabled = self.config.get('enable_data_monitor', True)
        
        logger.info("MultiGPUCollisionEngine已创建")
    
    def initialize(
        self,
        device_indices: Optional[List[int]] = None,
        device_count: int = -1,
        strategy: str = 'performance'
    ) -> bool:
        """初始化GPU设备
        
        Args:
            device_indices: 指定GPU索引列表(为None时自动选择)
            device_count: 自动选择的GPU数量(-1表示使用所有可用GPU)
            strategy: 负载策略('performance'或'equal')
            
        Returns:
            初始化是否成功
        """
        try:
            # 检测设备
            all_devices = self.selector.detect_all_devices()
            if not all_devices:
                logger.error("未检测到GPU设备")
                return False
            
            # 选择设备
            if device_indices:
                # 手动指定
                self._devices = self.selector.select_devices_by_indices(device_indices)
            elif device_count > 0:
                # 自动选择前N个最佳
                sorted_devices = sorted(
                    all_devices,
                    key=lambda d: d.get('score', 0),
                    reverse=True
                )
                self._devices = sorted_devices[:device_count]
            else:
                # 使用所有GPU
                self._devices = all_devices
            
            if not self._devices:
                logger.error("无可用GPU设备")
                return False
            
            logger.info(
                f"初始化 {len(self._devices)} 个GPU设备: "
                f"{[d['name'] for d in self._devices]}"
            )
            
            # 创建负载均衡器
            self.load_balancer = GPULoadBalancer(
                devices=self._devices,
                strategy=strategy
            )
            
            with self._state_lock:
                self._initialized = True
            
            logger.info("多GPU引擎初始化成功")
            return True
            
        except Exception as e:
            logger.error(f"多GPU引擎初始化失败: {e}")
            return False
    
    def start(
        self,
        targets: Set[str],
        mode: str = 'random',
        total_keys: int = 10000000,
        match_callback: Optional[Callable] = None
    ) -> bool:
        """启动多GPU碰撞搜索
        
        Args:
            targets: 目标地址集合
            mode: 碰撞模式(目前仅支持'random')
            total_keys: 总私钥搜索数量
            match_callback: 找到匹配时的回调函数(device_idx, match)
            
        Returns:
            启动是否成功
        """
        if not self._initialized:
            logger.error("引擎未初始化,请先调用initialize()")
            return False
        
        try:
            # 在锁内完成所有检查和状态修改,避免TOCTOU竞态条件
            with self._state_lock:
                if self._running:
                    logger.warning("引擎已在运行中")
                    return False
                
                # 设置状态变量
                self._targets = targets
                self._match_callback = match_callback
                self._start_time = time.time()
            
            # _all_matches使用单独的锁
            with self._matches_lock:
                self._all_matches = []
            
            # 分配任务
            key_ranges = self.load_balancer.assign_all_key_ranges(total_keys)
            
            # 创建工作器
            for device in self._devices:
                idx = device['global_index']
                key_range = key_ranges[idx]
                
                # 获取设备特定配置
                device_config = self._get_device_config(device)
                
                # 创建工作器
                worker = SingleGPUWorker(
                    device_idx=idx,
                    key_range=key_range,
                    targets=targets,
                    config=device_config,
                    result_callback=self._on_match_found,
                    data_monitor=self.data_monitor if self._monitor_enabled else None
                )
                
                with self._workers_lock:
                    self.workers[idx] = worker
            
            # 启动所有工作器
            with self._workers_lock:
                workers_snapshot = dict(self.workers)
            
            for idx, worker in workers_snapshot.items():
                worker.start()
                logger.info(f"GPU {idx} 工作器已启动")
            
            # 启动数据监控器
            if self._monitor_enabled:
                self.data_monitor.start(
                    anomaly_callback=self._on_anomaly_detected
                )
                logger.info("数据监控器已启动")
            
            with self._state_lock:
                self._running = True
            
            logger.info(
                f"多GPU碰撞已启动: {len(self.workers)}个GPU, "
                f"总私钥数={total_keys:,}"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"启动多GPU碰撞失败: {e}")
            return False
    
    def stop(self):
        """停止所有GPU工作器"""
        # 在锁内检查并设置停止标志
        with self._state_lock:
            if not self._running:
                return
            # 防止重复进入stop()
            if getattr(self, '_stopping', False):
                return
            self._stopping = True
        
        try:
            logger.info("停止多GPU碰撞...")
            
            # 停止所有工作器
            with self._workers_lock:
                workers_snapshot = dict(self.workers)
            
            for idx, worker in workers_snapshot.items():
                try:
                    worker.stop_search()
                    logger.info(f"GPU {idx} 工作器停止信号已发送")
                except Exception as e:
                    logger.error(f"停止GPU {idx} 工作器失败: {e}")
            
            # 等待所有工作器结束
            for idx, worker in workers_snapshot.items():
                try:
                    worker.join(timeout=30)
                    if worker.is_alive():
                        logger.warning(f"GPU {idx} 工作器未在30秒内停止")
                    else:
                        logger.info(f"GPU {idx} 工作器已停止")
                except Exception as e:
                    logger.error(f"等待GPU {idx} 工作器失败: {e}")
            
            # 更新统计
            self._update_combined_stats()
            
            # 停止数据监控器
            if self._monitor_enabled:
                self.data_monitor.stop()
                logger.info("数据监控器已停止")
            
            logger.info("多GPU碰撞已停止")
        finally:
            # 确保状态被正确更新
            with self._state_lock:
                self._running = False
                self._stopping = False
    
    def pause(self):
        """暂停所有GPU工作器"""
        with self._workers_lock:
            workers_snapshot = dict(self.workers)
        
        for idx, worker in workers_snapshot.items():
            try:
                worker.pause_search()
            except Exception as e:
                logger.error(f"暂停GPU {idx} 失败: {e}")
        
        logger.info("所有GPU工作器已暂停")
    
    def resume(self):
        """恢复所有GPU工作器"""
        with self._workers_lock:
            workers_snapshot = dict(self.workers)
        
        for idx, worker in workers_snapshot.items():
            try:
                worker.resume_search()
            except Exception as e:
                logger.error(f"恢复GPU {idx} 失败: {e}")
        
        logger.info("所有GPU工作器已恢复")
    
    def get_combined_stats(self) -> Dict:
        """获取汇总统计信息
        
        Returns:
            汇总统计字典
        """
        stats = {
            'status': 'running' if self._running else 'stopped',
            'device_count': len(self.workers),
            'total_keys_checked': 0,
            'total_matches': 0,
            'combined_throughput': 0,
            'elapsed_time': 0,
            'per_device': {}
        }
        
        # 使用锁保护workers和_all_matches访问
        with self._workers_lock:
            workers_snapshot = dict(self.workers)
        
        with self._matches_lock:
            stats['total_matches'] = len(self._all_matches)
        
        total_keys = 0
        total_throughput = 0
        
        for idx, worker in workers_snapshot.items():
            worker_stats = worker.get_stats()
            stats['per_device'][idx] = worker_stats
            
            total_keys += worker_stats.get('keys_checked', 0)
            total_throughput += worker_stats.get('throughput', 0)
        
        stats['total_keys_checked'] = total_keys
        stats['combined_throughput'] = total_throughput
        
        if self._start_time:
            stats['elapsed_time'] = time.time() - self._start_time
        
        return stats
    
    def get_per_device_stats(self) -> Dict[int, Dict]:
        """获取每个GPU的独立统计
        
        Returns:
            设备索引 -> 统计信息映射
        """
        # 使用锁保护workers访问
        with self._workers_lock:
            workers_snapshot = dict(self.workers)
        
        stats = {}
        for idx, worker in workers_snapshot.items():
            stats[idx] = worker.get_stats()
        
        return stats
    
    def get_matches(self) -> List[Dict]:
        """获取所有匹配结果
        
        Returns:
            匹配结果列表
        """
        # 使用锁保护_all_matches读取
        with self._matches_lock:
            return self._all_matches.copy()
    
    def is_running(self) -> bool:
        """检查引擎是否在运行
        
        Returns:
            True表示正在运行
        """
        # 使用锁保护_running读取
        with self._state_lock:
            return self._running
    
    def is_initialized(self) -> bool:
        """检查引擎是否已初始化
        
        Returns:
            True表示已初始化
        """
        # 使用锁保护_initialized读取
        with self._state_lock:
            return self._initialized
    
    def get_devices(self) -> List[Dict]:
        """获取当前使用的GPU设备列表
        
        Returns:
            设备信息列表
        """
        # 使用锁保护_devices读取
        with self._state_lock:
            return self._devices.copy()
    
    def get_load_balancer(self) -> Optional[GPULoadBalancer]:
        """获取负载均衡器
        
        Returns:
            GPULoadBalancer实例
        """
        return self.load_balancer
    
    def _on_match_found(self, device_idx: int, match: Dict):
        """处理匹配结果(回调)
        
        Args:
            device_idx: 发现匹配的设备索引
            match: 匹配信息
        """
        match['device_idx'] = device_idx
        match['timestamp'] = time.time()
        
        # 使用锁保护_all_matches
        with self._matches_lock:
            self._all_matches.append(match)
        
        # 报告给数据监控器
        if self._monitor_enabled:
            self.data_monitor.report_match(device_idx, match)
        
        logger.info(
            f"GPU {device_idx} 发现匹配: {match.get('address', 'Unknown')}"
        )
        
        # 调用外部回调
        if self._match_callback:
            try:
                self._match_callback(device_idx, match)
            except Exception as e:
                logger.error(f"匹配回调异常: {e}")
    
    def _on_anomaly_detected(self, device_idx: int, issue: Dict):
        """处理数据异常检测回调
        
        Args:
            device_idx: GPU设备索引
            issue: 数据质量问题
        """
        severity = issue.get('severity', 'low')
        issue_type = issue.get('issue_type', 'unknown')
        message = issue.get('message', '')
        
        # 根据严重程度采取不同措施
        if severity == 'critical':
            logger.critical(
                f"GPU {device_idx} 严重数据异常: {message}"
            )
            # 可选择暂停该GPU工作器
            if self.config.get('auto_pause_on_critical', False):
                logger.warning(f"自动暂停GPU {device_idx}")
                self._pause_device(device_idx)
        
        elif severity == 'high':
            logger.error(
                f"GPU {device_idx} 高级别数据异常: {message}"
            )
        
        elif severity == 'medium':
            logger.warning(
                f"GPU {device_idx} 中级别数据异常: {message}"
            )
        
        else:  # low
            logger.debug(
                f"GPU {device_idx} 低级别数据异常: {message}"
            )
    
    def _pause_device(self, device_idx: int):
        """暂停指定GPU工作器
        
        Args:
            device_idx: GPU设备索引
        """
        with self._workers_lock:
            if device_idx in self.workers:
                try:
                    self.workers[device_idx].pause_search()
                    logger.info(f"GPU {device_idx} 已暂停")
                except Exception as e:
                    logger.error(f"暂停GPU {device_idx} 失败: {e}")
    
    def get_monitor_stats(self) -> Dict:
        """获取数据监控统计
        
        Returns:
            监控统计字典
        """
        if self._monitor_enabled:
            return self.data_monitor.get_stats()
        else:
            return {'enabled': False}
    
    def get_monitor_issues(self, severity: str = None, 
                          device_idx: int = None, limit: int = 100) -> List[Dict]:
        """获取数据质量问题
        
        Args:
            severity: 过滤严重程度
            device_idx: 过滤设备索引
            limit: 返回数量限制
            
        Returns:
            问题列表
        """
        if self._monitor_enabled:
            return self.data_monitor.get_issues(
                severity=severity, 
                device_idx=device_idx,
                limit=limit
            )
        else:
            return []
    
    def _get_device_config(self, device: Dict) -> Dict:
        """获取设备特定配置
        
        Args:
            device: 设备信息
            
        Returns:
            配置字典
        """
        # 基础配置
        config = {
            'batch_size': device.get('recommended_batch_size', 65536),
            'work_group_size': device.get('recommended_work_group', 256)
        }
        
        # 合并用户配置
        per_device_config = self.config.get('per_device_config', {})
        device_idx_str = str(device['global_index'])
        
        if device_idx_str in per_device_config:
            config.update(per_device_config[device_idx_str])
        
        return config
    
    def _update_combined_stats(self):
        """更新汇总统计"""
        # 使用锁保护workers访问
        with self._workers_lock:
            workers_snapshot = dict(self.workers)
        
        total_keys = 0
        for worker in workers_snapshot.values():
            stats = worker.get_stats()
            total_keys += stats.get('keys_checked', 0)
        
        # 使用state_lock保护_total_keys_checked赋值
        with self._state_lock:
            self._total_keys_checked = total_keys
    
    def cleanup(self):
        """清理所有资源"""
        # 直接调用stop(),stop()内部会检查_running状态
        # 如果未运行则直接return,不会产生额外开销
        self.stop()
        
        with self._workers_lock:
            self.workers.clear()
        
        self._devices.clear()
        
        with self._matches_lock:
            self._all_matches.clear()
        
        with self._state_lock:
            self._initialized = False
            self._running = False
        
        logger.info("多GPU引擎资源已清理")
    
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.cleanup()
        return False
    
    def __del__(self):
        """析构函数"""
        try:
            self.cleanup()
        except Exception:
            pass

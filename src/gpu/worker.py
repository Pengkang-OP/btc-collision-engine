# -*- coding: utf-8 -*-
"""单GPU工作器

封装单个GPU的碰撞引擎,在线程中独立运行私钥搜索任务。
提供线程安全的状态管理和结果收集。
"""

import threading
import time
import logging
from typing import Set, Dict, Optional, Tuple, Callable
from queue import Queue, Empty

logger = logging.getLogger(__name__)


class SingleGPUWorker(threading.Thread):
    """单GPU工作器线程
    
    在独立线程中运行单个GPU的私钥碰撞搜索。
    
    使用示例:
        worker = SingleGPUWorker(
            device_idx=0,
            key_range=(0, 1000000),
            targets=target_addresses,
            config=gpu_config
        )
        
        worker.start()  # 启动搜索
        
        # 获取统计
        stats = worker.get_stats()
        
        worker.stop_search()  # 停止搜索
        worker.join()  # 等待线程结束
    """
    
    def __init__(
        self,
        device_idx: int,
        key_range: Tuple[int, int],
        targets: Set[str],
        config: Dict,
        result_callback: Optional[Callable] = None
    ):
        """初始化GPU工作器
        
        Args:
            device_idx: GPU设备索引
            key_range: 私钥搜索范围(start, end)
            targets: 目标地址集合
            config: GPU配置参数
            result_callback: 找到匹配时的回调函数
        """
        super().__init__(daemon=True)
        
        self.device_idx = device_idx
        self.key_range = key_range
        self.targets = targets
        self.config = config
        self.result_callback = result_callback
        
        # 线程控制
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()  # 初始状态为运行
        
        # 状态锁
        self._lock = threading.Lock()
        
        # 结果队列
        self._result_queue = Queue()
        
        # 统计信息
        self._stats = {
            'device_idx': device_idx,
            'status': 'initialized',  # initialized, running, paused, stopped, error
            'keys_checked': 0,
            'matches_found': 0,
            'start_time': None,
            'elapsed_time': 0,
            'throughput': 0,
            'error_count': 0,
            'last_error': None
        }
        
        # GPU引擎实例
        self._gpu_engine = None
        
        logger.info(
            f"GPU工作器已创建: 设备={device_idx}, "
            f"范围={key_range[0]:,}-{key_range[1]:,}"
        )
    
    def run(self):
        """线程主循环"""
        try:
            self._initialize_gpu_engine()
            self._stats['status'] = 'running'
            self._stats['start_time'] = time.time()
            
            logger.info(f"GPU {self.device_idx} 开始搜索...")
            
            # 执行搜索
            self._execute_search()
            
        except Exception as e:
            logger.error(f"GPU {self.device_idx} 工作器异常: {e}")
            with self._lock:
                self._stats['status'] = 'error'
                self._stats['last_error'] = str(e)
                self._stats['error_count'] += 1
        
        finally:
            self._cleanup()
            self._stats['status'] = 'stopped'
            logger.info(f"GPU {self.device_idx} 工作器已停止")
    
    def _initialize_gpu_engine(self):
        """初始化GPU碰撞引擎"""
        try:
            # 导入GPU碰撞引擎
            from ..collision.gpu_collision_engine import GPUCollisionEngine
            
            # 创建引擎实例
            self._gpu_engine = GPUCollisionEngine()
            
            # 配置引擎
            batch_size = self.config.get('batch_size', 65536)
            
            # 初始化GPU
            self._gpu_engine.initialize(
                device_index=self.device_idx,
                batch_size=batch_size
            )
            
            # 设置目标地址
            self._gpu_engine.set_target_addresses(list(self.targets))
            
            logger.info(
                f"GPU {self.device_idx} 引擎初始化完成: "
                f"批次={batch_size:,}"
            )
            
        except Exception as e:
            logger.error(f"GPU {self.device_idx} 引擎初始化失败: {e}")
            raise
    
    def _execute_search(self):
        """执行私钥搜索"""
        if not self._gpu_engine:
            return
        
        start_key, end_key = self.key_range
        total_keys = end_key - start_key
        
        try:
            # 启动GPU引擎(它会在内部循环)
            self._gpu_engine.start(mode='random')
            
            # 监控循环
            while not self._stop_event.is_set():
                # 检查暂停状态
                if not self._pause_event.is_set():
                    time.sleep(0.1)
                    continue
                
                # 更新统计
                self._update_stats()
                
                # 检查是否完成
                if self._stats['keys_checked'] >= total_keys:
                    logger.info(f"GPU {self.device_idx} 完成搜索范围")
                    break
                
                # 短暂休眠让出CPU
                time.sleep(0.5)
            
            # 停止引擎
            if self._gpu_engine:
                self._gpu_engine.stop()
                
        except Exception as e:
            logger.error(f"GPU {self.device_idx} 搜索异常: {e}")
            with self._lock:
                self._stats['error_count'] += 1
                self._stats['last_error'] = str(e)
    
    def _update_stats(self):
        """更新统计信息"""
        if not self._gpu_engine:
            return
        
        try:
            # 获取引擎统计
            engine_stats = self._gpu_engine.get_stats()
            
            with self._lock:
                self._stats['keys_checked'] = engine_stats.get('total_checked', 0)
                self._stats['matches_found'] = len(engine_stats.get('matches', []))
                
                # 计算运行时间
                if self._stats['start_time']:
                    self._stats['elapsed_time'] = time.time() - self._stats['start_time']
                
                # 计算吞吐量
                if self._stats['elapsed_time'] > 0:
                    self._stats['throughput'] = (
                        self._stats['keys_checked'] / self._stats['elapsed_time']
                    )
                
                # 检查新匹配
                matches = engine_stats.get('matches', [])
                for match in matches:
                    self._result_queue.put(match)
                    
                    # 调用回调
                    if self.result_callback:
                        try:
                            self.result_callback(self.device_idx, match)
                        except Exception as e:
                            logger.error(f"结果回调异常: {e}")
                            
        except Exception as e:
            logger.debug(f"更新统计信息失败: {e}")
    
    def _cleanup(self):
        """清理资源"""
        try:
            if self._gpu_engine:
                self._gpu_engine.stop()
                self._gpu_engine.cleanup()
                self._gpu_engine = None
        except Exception as e:
            logger.error(f"GPU {self.device_idx} 清理失败: {e}")
    
    def stop_search(self):
        """停止搜索"""
        logger.info(f"GPU {self.device_idx} 收到停止信号")
        self._stop_event.set()
    
    def pause_search(self):
        """暂停搜索"""
        logger.info(f"GPU {self.device_idx} 暂停")
        self._pause_event.clear()
        with self._lock:
            self._stats['status'] = 'paused'
    
    def resume_search(self):
        """恢复搜索"""
        logger.info(f"GPU {self.device_idx} 恢复")
        self._pause_event.set()
        with self._lock:
            self._stats['status'] = 'running'
    
    def get_stats(self) -> Dict:
        """获取统计信息(线程安全)
        
        Returns:
            统计信息字典
        """
        with self._lock:
            return self._stats.copy()
    
    def get_results(self, max_results: int = 100) -> list:
        """获取搜索结果
        
        Args:
            max_results: 最大返回数量
            
        Returns:
            匹配结果列表
        """
        results = []
        try:
            for _ in range(min(max_results, self._result_queue.qsize())):
                result = self._result_queue.get_nowait()
                results.append(result)
        except Empty:
            pass
        
        return results
    
    def is_running(self) -> bool:
        """检查是否正在运行
        
        Returns:
            True表示正在运行
        """
        with self._lock:
            return self._stats['status'] == 'running'
    
    def is_alive(self) -> bool:
        """检查线程是否存活
        
        Returns:
            True表示线程存活
        """
        return self.is_alive()
    
    def get_device_idx(self) -> int:
        """获取设备索引
        
        Returns:
            GPU设备索引
        """
        return self.device_idx
    
    def get_key_range(self) -> Tuple[int, int]:
        """获取私钥搜索范围
        
        Returns:
            (start, end) 范围
        """
        return self.key_range
    
    def __repr__(self):
        return (
            f"<SingleGPUWorker device={self.device_idx} "
            f"status={self._stats['status']} "
            f"throughput={self._stats['throughput']:.0f} keys/s>"
        )

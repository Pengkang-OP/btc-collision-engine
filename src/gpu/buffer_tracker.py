"""GPU缓冲区追踪器模块

提供 GPUBufferTracker 类，用于检测和管理 GPU 内存缓冲区泄漏。
"""

import time
import threading
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


# ========== GPU缓冲区追踪器 ==========
class GPUBufferTracker:
    """P2-2修复: GPU缓冲区跟踪器,用于检测内存泄漏
    
    追踪所有分配的GPU缓冲区,检测超时未释放的缓冲区。
    线程安全,支持多线程并发访问。
    
    增强功能:
    - 自动清理超时缓冲区
    - 引擎关闭时强制检查
    - 内存使用趋势监控
    """
    
    # 类级别配置
    DEFAULT_TIMEOUT = 300  # 默认超时5分钟
    MAX_TRACKED_BUFFERS = 1000  # 最大追踪缓冲区数量
    
    def __init__(self, timeout: int = None):
        self._allocated_buffers: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._timeout = timeout or self.DEFAULT_TIMEOUT
        self._cleanup_count = 0
        self._leak_detection_count = 0
    
    def track_buffer(self, name: str, buffer: Any, size: int):
        """注册缓冲区
        
        Args:
            name: 缓冲区名称
            buffer: OpenCL Buffer对象
            size: 缓冲区大小(字节)
        """
        with self._lock:
            self._allocated_buffers[name] = {
                'buffer': buffer,
                'size': size,
                'timestamp': time.time(),
                'allocated': True
            }
        logger.debug(f"GPU Buffer追踪: 分配 {name} ({size/1024:.1f} KB)")
    
    def release_buffer(self, name: str):
        """注销缓冲区
        
        Args:
            name: 缓冲区名称
        """
        with self._lock:
            if name in self._allocated_buffers:
                del self._allocated_buffers[name]
                logger.debug(f"GPU Buffer追踪: 释放 {name}")
    
    def get_leaked_buffers(self, timeout: int = 300) -> List[str]:
        """检测超过timeout未释放的缓冲区
        
        Args:
            timeout: 超时阈值(秒),默认5分钟
            
        Returns:
            泄漏的缓冲区名称列表
        """
        current_time = time.time()
        leaked = []
        
        with self._lock:
            for name, info in self._allocated_buffers.items():
                if current_time - info['timestamp'] > timeout:
                    leaked.append(name)
        
        if leaked:
            logger.warning(
                f"检测到{len(leaked)}个可能的GPU Buffer泄漏: {', '.join(leaked)}"
            )
        
        return leaked
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓冲区统计信息
        
        Returns:
            统计信息字典
        """
        with self._lock:
            total_size = sum(info['size'] for info in self._allocated_buffers.values())
            return {
                'count': len(self._allocated_buffers),
                'total_size_bytes': total_size,
                'total_size_mb': total_size / 1024 / 1024,
                'buffers': list(self._allocated_buffers.keys()),
                'cleanup_count': self._cleanup_count,
                'leak_detection_count': self._leak_detection_count,
                'timeout_seconds': self._timeout
            }
    
    def cleanup_timed_out_buffers(self) -> List[str]:
        """自动清理超时的缓冲区
        
        审查修复#2: 实际释放GPU资源，而不仅删除追踪记录。
        
        Returns:
            被清理的缓冲区名称列表
        """
        current_time = time.time()
        cleaned = []
        failed_to_release = []  # 记录释放失败的资源
        
        with self._lock:
            to_remove = []
            for name, info in self._allocated_buffers.items():
                if current_time - info['timestamp'] > self._timeout:
                    to_remove.append(name)
            
            for name in to_remove:
                info = self._allocated_buffers[name]
                # 审查修复#2: 尝试释放GPU资源
                try:
                    buffer = info.get('buffer')
                    if buffer is not None and hasattr(buffer, 'release'):
                        buffer.release()
                        logger.debug(f"自动清理超时缓冲区: {name}")
                    else:
                        failed_to_release.append(name)
                        logger.warning(f"超时缓冲区无release方法: {name}")
                except Exception as e:
                    failed_to_release.append(name)
                    logger.error(f"清理超时缓冲区失败 {name}: {e}")
                finally:
                    del self._allocated_buffers[name]
                    cleaned.append(name)
                    self._cleanup_count += 1
        
        if cleaned:
            msg = f"自动清理{len(cleaned)}个超时GPU缓冲区"
            if failed_to_release:
                msg += f"，{len(failed_to_release)}个释放失败"
            logger.warning(msg)
        
        return cleaned
    
    def start_periodic_check(self, interval: int = 300):
        """启动定期泄漏检查（默认每5分钟）"""
        self._check_interval = interval
        self._periodic_check_stop = threading.Event()
        self._periodic_check_thread = threading.Thread(
            target=self._periodic_check_loop,
            daemon=True,
            name="buffer-tracker-periodic"
        )
        self._periodic_check_thread.start()
        logger.info(f"GPU缓冲区追踪器：定期检查已启动，间隔 {interval} 秒")

    def stop_periodic_check(self):
        """停止定期泄漏检查"""
        if hasattr(self, '_periodic_check_stop') and self._periodic_check_stop:
            self._periodic_check_stop.set()
            if hasattr(self, '_periodic_check_thread') and self._periodic_check_thread:
                self._periodic_check_thread.join(timeout=10)
            logger.info("GPU缓冲区追踪器：定期检查已停止")

    def _periodic_check_loop(self):
        """定期检查循环"""
        while not self._periodic_check_stop.is_set():
            self._periodic_check_stop.wait(timeout=self._check_interval)
            if self._periodic_check_stop.is_set():
                break
            try:
                leaked = self.get_leaked_buffers(timeout=self._timeout)
                if leaked:
                    stats = self.get_stats()
                    logger.warning(
                        f"GPU缓冲区泄漏检测: 漏漏缓冲区数={len(leaked)}, "
                        f"总已追踪={stats['count']}, 已泄漏={leaked}"
                    )
            except Exception as e:
                logger.error(f"定期泄漏检查失败: {e}")

    def force_check_on_shutdown(self) -> Dict[str, Any]:
        """引擎关闭时强制检查内存泄漏
        
        Returns:
            检查结果字典
        """
        self._leak_detection_count += 1
        
        with self._lock:
            remaining = len(self._allocated_buffers)
            total_size = sum(info['size'] for info in self._allocated_buffers.values())
            buffer_names = list(self._allocated_buffers.keys())
            
            # 尝试释放所有剩余缓冲区
            released = []
            failed = []
            
            for name, info in self._allocated_buffers.items():
                try:
                    buffer = info.get('buffer')
                    if buffer is not None and hasattr(buffer, 'release'):
                        buffer.release()
                        released.append(name)
                        logger.debug(f"关闭时释放缓冲区: {name}")
                except Exception as e:
                    failed.append({'name': name, 'error': str(e)})
                    logger.error(f"关闭时释放缓冲区失败 {name}: {e}")
            
            # 清空追踪记录
            self._allocated_buffers.clear()
        
        # 审查修复#3: 修正语义准确性
        result = {
            'remaining_buffers': remaining,
            'total_size_bytes': total_size,
            'released': released,
            'release_failed': failed,
            'has_unreleased': remaining > 0,  # 有未释放的缓冲区
            'has_leak': len(failed) > 0,      # 释放失败才算泄漏
            'all_released_successfully': len(failed) == 0
        }
        
        # v2.2.1修复: 只在释放失败时输出CRITICAL警告
        if len(failed) > 0:
            logger.critical(
                f"GPU引擎关闭时{len(failed)}个缓冲区释放失败 "
                f"(可能内存泄漏): {', '.join([f['name'] for f in failed])}"
            )
        elif remaining > 0:
            logger.info(
                f"GPU引擎关闭时释放了{remaining}个缓冲区 "
                f"(总大小: {total_size/1024:.1f}KB): {', '.join(buffer_names)}"
            )
        else:
            logger.info("GPU引擎关闭时所有缓冲区已正确释放")
        
        return result

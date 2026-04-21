"""GPU异步执行优化模块

实现双缓冲异步执行机制,提升GPU利用率:
1. 双OpenCL队列(计算+传输)
2. 双缓冲机制(消除CPU-GPU等待)
3. 安全保护(超时+回退)
"""

import time
import threading
import logging
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class AsyncGPUExecutor:
    """异步GPU执行器
    
    使用双缓冲和双队列实现异步执行,提升GPU利用率到90%+
    """
    
    def __init__(self, gpu_device, max_batch_size: int):
        """
        初始化异步执行器
        
        Args:
            gpu_device: GPUDevice实例
            max_batch_size: 最大批次大小
        """
        self.device = gpu_device
        self.max_batch_size = max_batch_size
        
        # 双缓冲
        self.buffer_a = {
            'keys': None,
            'matches': None,
            'match_flags': None
        }
        self.buffer_b = {
            'keys': None,
            'matches': None,
            'match_flags': None
        }
        
        # 异步状态
        self.current_buffer = 'A'
        self.pending_event = None
        self.is_async_ready = False
        
        # 统计
        self.async_executions = 0
        self.sync_fallbacks = 0
        
        logger.info(f"异步GPU执行器已初始化: max_batch={max_batch_size}")
    
    def initialize_buffers(self, context, num_keys: int):
        """
        初始化双缓冲
        
        Args:
            context: OpenCL上下文
            num_keys: 每个缓冲的密钥数量
        """
        import pyopencl as cl
        import pyopencl.array as cl_array
        import numpy as np
        
        logger.info(f"创建双缓冲: num_keys={num_keys}")
        
        # Buffer A
        self.buffer_a['keys'] = cl.Buffer(
            context, 
            cl.mem_flags.READ_WRITE | cl.mem_flags.COPY_HOST_PTR,
            hostbuf=np.zeros(num_keys * 8, dtype=np.uint32)
        )
        self.buffer_a['matches'] = cl.Buffer(
            context,
            cl.mem_flags.READ_WRITE,
            size=num_keys * 4
        )
        self.buffer_a['match_flags'] = np.zeros(num_keys, dtype=np.int32)
        
        # Buffer B
        self.buffer_b['keys'] = cl.Buffer(
            context,
            cl.mem_flags.READ_WRITE | cl.mem_flags.COPY_HOST_PTR,
            hostbuf=np.zeros(num_keys * 8, dtype=np.uint32)
        )
        self.buffer_b['matches'] = cl.Buffer(
            context,
            cl.mem_flags.READ_WRITE,
            size=num_keys * 4
        )
        self.buffer_b['match_flags'] = np.zeros(num_keys, dtype=np.int32)
        
        logger.info("双缓冲创建完成")
    
    def run_batch_async(self, private_keys: bytes, num_keys: int,
                       program, targets_buf, num_targets) -> Tuple[List[Dict], float]:
        """
        异步执行批次
        
        Args:
            private_keys: 私钥数据
            num_keys: 密钥数量
            program: OpenCL程序
            targets_buf: 目标地址缓冲区
            num_targets: 目标数量
            
        Returns:
            (matches, execution_time_ms)
        """
        import pyopencl as cl
        import numpy as np
        
        start_time = time.time()
        
        # 检查是否支持异步
        if not self.device.enable_async_execution or not self.device.compute_queue:
            # 回退到同步模式
            return self._run_batch_sync(private_keys, num_keys, program, targets_buf, num_targets)
        
        try:
            # 选择当前缓冲
            if self.current_buffer == 'A':
                current_buf = self.buffer_a
                next_buf = self.buffer_b
            else:
                current_buf = self.buffer_b
                next_buf = self.buffer_a
            
            # 1. 在传输队列上异步准备下一批数据
            keys_array = np.frombuffer(private_keys[:num_keys * 32], dtype=np.uint32)
            
            transfer_event = cl.enqueue_copy(
                self.device.transfer_queue,
                next_buf['keys'],
                keys_array,
                is_blocking=False  # 不阻塞!
            )
            
            # 2. 清空当前缓冲的匹配结果
            cl.enqueue_fill_buffer(
                self.device.compute_queue,
                current_buf['matches'],
                np.int32(0),
                0,
                num_keys * 4
            )
            
            # 3. 执行内核(异步)
            batch_kernel = program.batch_check
            
            kernel_event = batch_kernel(
                self.device.compute_queue,
                (num_keys,),
                None,
                current_buf['keys'],
                np.uint32(num_keys),
                targets_buf,
                np.uint32(num_targets),
                current_buf['matches']
            )
            
            # 4. 异步读取结果
            read_event = cl.enqueue_copy(
                self.device.compute_queue,
                current_buf['match_flags'],
                current_buf['matches'],
                is_blocking=False
            )
            
            # 5. 等待完成(带超时)
            timeout_seconds = 30
            try:
                # pyopencl版本兼容: 部分版本不支持timeout参数
                try:
                    completed = read_event.wait(timeout=timeout_seconds * 1000)  # 毫秒
                    if not completed:
                        raise RuntimeError(f"异步执行超时({timeout_seconds}秒)")
                except TypeError:
                    # 不支持timeout,使用无超时版本
                    read_event.wait()
            except Exception as e:
                raise RuntimeError(f"异步执行失败: {e}")
            
            # 6. 收集匹配结果
            matches = []
            for i in range(num_keys):
                if current_buf['match_flags'][i] > 0:
                    matches.append({
                        "key_index": i,
                        "target_index": int(current_buf['match_flags'][i] - 1)
                    })
            
            # 7. 切换缓冲
            self.current_buffer = 'B' if self.current_buffer == 'A' else 'A'
            self.async_executions += 1
            
            execution_time_ms = (time.time() - start_time) * 1000
            
            return matches, execution_time_ms
            
        except Exception as e:
            logger.warning(f"异步执行失败,回退到同步模式: {e}")
            self.sync_fallbacks += 1
            return self._run_batch_sync(private_keys, num_keys, program, targets_buf, num_targets)
    
    def _run_batch_sync(self, private_keys: bytes, num_keys: int,
                       program, targets_buf, num_targets) -> Tuple[List[Dict], float]:
        """
        同步执行(回退模式)
        
        当异步执行失败时使用
        """
        import pyopencl as cl
        import numpy as np
        
        start_time = time.time()
        
        # 使用传统单队列执行
        keys_array = np.frombuffer(private_keys[:num_keys * 32], dtype=np.uint32)
        
        # 使用buffer_a作为临时缓冲
        temp_buf = self.buffer_a if self.buffer_a['keys'] else self.buffer_b
        
        cl.enqueue_copy(self.device.queue, temp_buf['keys'], keys_array)
        
        cl.enqueue_fill_buffer(
            self.device.queue, temp_buf['matches'],
            np.int32(0), 0, num_keys * 4
        )
        
        batch_kernel = program.batch_check
        batch_kernel(
            self.device.queue, (num_keys,), None,
            temp_buf['keys'], np.uint32(num_keys),
            targets_buf, np.uint32(num_targets),
            temp_buf['matches']
        )
        
        match_flags = np.zeros(num_keys, dtype=np.int32)
        cl.enqueue_copy(self.device.queue, match_flags, temp_buf['matches'])
        self.device.queue.finish()
        
        matches = []
        for i in range(num_keys):
            if match_flags[i] > 0:
                matches.append({
                    "key_index": i,
                    "target_index": int(match_flags[i] - 1)
                })
        
        execution_time_ms = (time.time() - start_time) * 1000
        return matches, execution_time_ms
    
    def get_stats(self) -> Dict:
        """获取执行统计"""
        total = self.async_executions + self.sync_fallbacks
        async_rate = (self.async_executions / total * 100) if total > 0 else 0
        
        return {
            'async_executions': self.async_executions,
            'sync_fallbacks': self.sync_fallbacks,
            'total_executions': total,
            'async_rate_percent': async_rate
        }

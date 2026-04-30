"""GPU 性能基准测试套件

提供标准化的性能测试框架，用于：
1. 评估不同 GPU 设备的性能
2. 验证优化效果
3. 建立性能基线
4. 跨厂商性能对比

测试维度：
- 内核编译性能
- 批次执行性能
- 显存带宽利用率
- 不同 batch_size 的性能影响
"""

import os
import sys
import time
import logging
from ..utils import init_logging, get_configured_logger
import statistics
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = get_configured_logger("GPUBenchmarkSuite")


class BenchmarkType(Enum):
    """基准测试类型"""
    COMPILE = "kernel_compile"           # 内核编译
    BATCH_EXECUTION = "batch_execution"  # 批次执行
    MEMORY_BANDWIDTH = "memory_bandwidth"  # 显存带宽
    SCALABILITY = "scalability"          # 扩展性测试


@dataclass
class BenchmarkResult:
    """基准测试结果"""
    test_name: str
    test_type: BenchmarkType
    device_name: str
    vendor: str
    
    # 性能指标
    duration_ms: float
    throughput: float = 0.0  # 吞吐量（如 keys/sec）
    
    # 测试参数
    parameters: Dict = field(default_factory=dict)
    
    # 统计信息
    min_ms: float = 0.0
    max_ms: float = 0.0
    mean_ms: float = 0.0
    median_ms: float = 0.0
    std_dev_ms: float = 0.0
    
    # 元数据
    timestamp: float = field(default_factory=time.time)
    iterations: int = 1
    status: str = "success"
    error_message: str = ""


class GPUBenchmarkSuite:
    """GPU 性能基准测试套件
    
    使用示例:
        >>> suite = GPUBenchmarkSuite(gpu_engine)
        >>> # 运行所有测试
        >>> results = suite.run_all_benchmarks()
        >>> # 生成报告
        >>> report = suite.generate_report(results)
        >>> print(report)
    """
    
    def __init__(self, gpu_engine) -> None:
        """初始化基准测试套件
        
        Args:
            gpu_engine: GPU 碰撞引擎实例
        """
        self.gpu_engine = gpu_engine
        self.results: List[BenchmarkResult] = []
        self._test_devices = []
        
        logger.info("GPU 性能基准测试套件已初始化")
    
    def run_all_benchmarks(self, iterations: int = 5) -> List[BenchmarkResult]:
        """运行所有基准测试
        
        Args:
            iterations: 每个测试的迭代次数
            
        Returns:
            测试结果列表
        """
        logger.info("="*60)
        logger.info("🚀 开始 GPU 性能基准测试")
        logger.info("="*60)
        
        all_results = []
        
        # 1. 内核编译测试
        logger.info("\n📝 测试 1/4: 内核编译性能")
        results = self.benchmark_kernel_compile(iterations)
        all_results.extend(results)
        
        # 2. 批次执行测试
        logger.info("\n⚡ 测试 2/4: 批次执行性能")
        results = self.benchmark_batch_execution(iterations)
        all_results.extend(results)
        
        # 3. 显存带宽测试
        logger.info("\n💾 测试 3/4: 显存带宽利用率")
        results = self.benchmark_memory_bandwidth(iterations)
        all_results.extend(results)
        
        # 4. 扩展性测试
        logger.info("\n📊 测试 4/4: batch_size 扩展性")
        results = self.benchmark_scalability(iterations)
        all_results.extend(results)
        
        self.results = all_results
        
        logger.info("\n" + "="*60)
        logger.info(f"✅ 基准测试完成: {len(all_results)} 个测试")
        logger.info("="*60)
        
        return all_results
    
    def benchmark_kernel_compile(self, iterations: int = 5) -> List[BenchmarkResult]:
        """基准测试：内核编译性能
        
        Args:
            iterations: 迭代次数
            
        Returns:
            测试结果
        """
        results = []
        compile_times = []
        
        for i in range(iterations):
            start_time = time.time()
            
            # 触发内核编译
            try:
                if hasattr(self.gpu_engine, '_gpu_kernel'):
                    # 重新编译内核
                    self.gpu_engine._gpu_kernel._compile()
                
                duration_ms = (time.time() - start_time) * 1000
                compile_times.append(duration_ms)
                
                logger.info(f"  编译 #{i+1}: {duration_ms:.0f}ms")
                
            except Exception as e:
                logger.error(f"  编译 #{i+1} 失败: {e}")
                compile_times.append(0)
        
        # 创建结果
        if compile_times:
            valid_times = [t for t in compile_times if t > 0]
            if valid_times:
                result = BenchmarkResult(
                    test_name="kernel_compile",
                    test_type=BenchmarkType.COMPILE,
                    device_name=self._get_device_name(),
                    vendor=self._get_vendor(),
                    duration_ms=statistics.mean(valid_times),
                    min_ms=min(valid_times),
                    max_ms=max(valid_times),
                    mean_ms=statistics.mean(valid_times),
                    median_ms=statistics.median(valid_times),
                    std_dev_ms=statistics.stdev(valid_times) if len(valid_times) > 1 else 0,
                    iterations=len(valid_times),
                    parameters={"iterations": iterations}
                )
                results.append(result)
        
        return results
    
    def benchmark_batch_execution(self, iterations: int = 5) -> List[BenchmarkResult]:
        """基准测试：批次执行性能
        
        Args:
            iterations: 迭代次数
            
        Returns:
            测试结果
        """
        import os
        
        results = []
        batch_sizes = [10000, 50000, 100000]
        
        for batch_size in batch_sizes:
            exec_times = []
            
            for i in range(iterations):
                # 准备测试数据（PRNG模式：仅需 32 字节随机种子）
                seed = os.urandom(32)
                
                start_time = time.time()
                
                try:
                    # 执行批次
                    if hasattr(self.gpu_engine, '_gpu_kernel'):
                        matches = self.gpu_engine._gpu_kernel.run_batch(
                            seed=seed,
                            num_keys=batch_size,
                        )
                    
                    duration_ms = (time.time() - start_time) * 1000
                    exec_times.append(duration_ms)
                    
                    # 计算吞吐量
                    keys_per_sec = (batch_size / duration_ms * 1000) if duration_ms > 0 else 0
                    
                    logger.info(
                        f"  batch_size={batch_size:>6}, "
                        f"#{i+1}: {duration_ms:.0f}ms "
                        f"({keys_per_sec:.0f} keys/sec)"
                    )
                    
                except Exception as e:
                    logger.error(f"  batch_size={batch_size}, #{i+1} 失败: {e}")
                    exec_times.append(0)
            
            # 创建结果
            if exec_times:
                valid_times = [t for t in exec_times if t > 0]
                if valid_times:
                    avg_time = statistics.mean(valid_times)
                    throughput = (batch_size / avg_time * 1000) if avg_time > 0 else 0
                    
                    result = BenchmarkResult(
                        test_name=f"batch_execution_{batch_size}",
                        test_type=BenchmarkType.BATCH_EXECUTION,
                        device_name=self._get_device_name(),
                        vendor=self._get_vendor(),
                        duration_ms=avg_time,
                        throughput=throughput,
                        min_ms=min(valid_times),
                        max_ms=max(valid_times),
                        mean_ms=avg_time,
                        median_ms=statistics.median(valid_times),
                        std_dev_ms=statistics.stdev(valid_times) if len(valid_times) > 1 else 0,
                        iterations=len(valid_times),
                        parameters={
                            "batch_size": batch_size,
                            "iterations": iterations
                        }
                    )
                    results.append(result)
        
        return results
    
    def benchmark_memory_bandwidth(self, iterations: int = 5) -> List[BenchmarkResult]:
        """基准测试：显存带宽利用率
        
        Args:
            iterations: 迭代次数
            
        Returns:
            测试结果
        """
        # 简化版本：基于批次执行推算
        # 完整版本需要直接测试显存读写
        
        results = []
        logger.info("  显存带宽测试（基于执行时间推算）")
        
        # 复用批次执行数据
        batch_results = self.benchmark_batch_execution(iterations=3)
        
        for result in batch_results:
            batch_size = result.parameters.get("batch_size", 0)
            if batch_size > 0:
                # 每个私钥 32 字节
                data_transferred = batch_size * 32  # 字节
                bandwidth_mbps = (data_transferred / 1024**2) / (result.duration_ms / 1000)
                
                bw_result = BenchmarkResult(
                    test_name=f"memory_bandwidth_{batch_size}",
                    test_type=BenchmarkType.MEMORY_BANDWIDTH,
                    device_name=self._get_device_name(),
                    vendor=self._get_vendor(),
                    duration_ms=result.duration_ms,
                    throughput=bandwidth_mbps,  # MB/s
                    parameters={
                        "batch_size": batch_size,
                        "data_transferred_mb": data_transferred / 1024**2
                    }
                )
                results.append(bw_result)
        
        return results
    
    def benchmark_scalability(self, iterations: int = 3) -> List[BenchmarkResult]:
        """基准测试：batch_size 扩展性
        
        Args:
            iterations: 迭代次数
            
        Returns:
            测试结果
        """
        import os
        
        results = []
        batch_sizes = [10000, 25000, 50000, 100000, 250000, 500000]
        
        logger.info("  测试不同 batch_size 的扩展性:")
        
        for batch_size in batch_sizes:
            exec_times = []
            
            for i in range(iterations):
                seed = os.urandom(32)
                
                start_time = time.time()
                
                try:
                    if hasattr(self.gpu_engine, '_gpu_kernel'):
                        self.gpu_engine._gpu_kernel.run_batch(
                            seed=seed,
                            num_keys=batch_size,
                        )
                    
                    duration_ms = (time.time() - start_time) * 1000
                    exec_times.append(duration_ms)
                    
                    keys_per_sec = (batch_size / duration_ms * 1000) if duration_ms > 0 else 0
                    
                    logger.info(
                        f"    batch_size={batch_size:>7}, "
                        f"#{i+1}: {duration_ms:.0f}ms "
                        f"({keys_per_sec:,.0f} keys/sec)"
                    )
                    
                except Exception as e:
                    logger.error(f"    batch_size={batch_size}, #{i+1} 失败: {e}")
                    exec_times.append(0)
            
            # 创建结果
            if exec_times:
                valid_times = [t for t in exec_times if t > 0]
                if valid_times:
                    avg_time = statistics.mean(valid_times)
                    throughput = (batch_size / avg_time * 1000) if avg_time > 0 else 0
                    
                    result = BenchmarkResult(
                        test_name=f"scalability_{batch_size}",
                        test_type=BenchmarkType.SCALABILITY,
                        device_name=self._get_device_name(),
                        vendor=self._get_vendor(),
                        duration_ms=avg_time,
                        throughput=throughput,
                        parameters={
                            "batch_size": batch_size,
                            "iterations": iterations
                        }
                    )
                    results.append(result)
        
        return results
    
    def generate_report(self, results: Optional[List[BenchmarkResult]] = None) -> str:
        """生成基准测试报告
        
        Args:
            results: 测试结果（可选，默认使用 self.results）
            
        Returns:
            格式化的报告字符串
        """
        if results is None:
            results = self.results
        
        if not results:
            return "无测试结果"
        
        report_lines = [
            "=" * 80,
            "📊 GPU 性能基准测试报告",
            "=" * 80,
            f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"GPU 设备: {self._get_device_name()}",
            f"厂    商: {self._get_vendor()}",
            f"测试总数: {len(results)}",
            ""
        ]
        
        # 按测试类型分组
        by_type = {}
        for result in results:
            test_type = result.test_type.value
            if test_type not in by_type:
                by_type[test_type] = []
            by_type[test_type].append(result)
        
        # 内核编译测试
        if BenchmarkType.COMPILE.value in by_type:
            report_lines.append("=" * 80)
            report_lines.append("🔨 内核编译性能")
            report_lines.append("-" * 80)
            
            for result in by_type[BenchmarkType.COMPILE.value]:
                report_lines.append(f"  平均编译时间: {result.mean_ms:.0f}ms")
                report_lines.append(f"  范围: {result.min_ms:.0f}ms - {result.max_ms:.0f}ms")
                report_lines.append(f"  标准差: {result.std_dev_ms:.0f}ms")
                report_lines.append("")
        
        # 批次执行测试
        if BenchmarkType.BATCH_EXECUTION.value in by_type:
            report_lines.append("=" * 80)
            report_lines.append("⚡ 批次执行性能")
            report_lines.append("-" * 80)
            report_lines.append(f"  {'Batch Size':>12} | {'平均时间':>10} | {'吞吐量':>12} | {'最小':>10} | {'最大':>10}")
            report_lines.append(f"  {'-'*12}-+-{'-'*10}-+-{'-'*12}-+-{'-'*10}-+-{'-'*10}")
            
            for result in by_type[BenchmarkType.BATCH_EXECUTION.value]:
                batch_size = result.parameters.get('batch_size', 0)
                report_lines.append(
                    f"  {batch_size:>12,} | {result.mean_ms:>8.0f}ms | "
                    f"{result.throughput:>10,.0f}/s | {result.min_ms:>8.0f}ms | {result.max_ms:>8.0f}ms"
                )
            report_lines.append("")
        
        # 显存带宽测试
        if BenchmarkType.MEMORY_BANDWIDTH.value in by_type:
            report_lines.append("=" * 80)
            report_lines.append("💾 显存带宽")
            report_lines.append("-" * 80)
            
            for result in by_type[BenchmarkType.MEMORY_BANDWIDTH.value]:
                batch_size = result.parameters.get('batch_size', 0)
                report_lines.append(
                    f"  Batch Size {batch_size:>7,}: {result.throughput:.2f} MB/s"
                )
            report_lines.append("")
        
        # 扩展性测试
        if BenchmarkType.SCALABILITY.value in by_type:
            report_lines.append("=" * 80)
            report_lines.append("📈 扩展性测试")
            report_lines.append("-" * 80)
            report_lines.append(f"  {'Batch Size':>12} | {'平均时间':>10} | {'吞吐量':>14} | {'效率':>8}")
            report_lines.append(f"  {'-'*12}-+-{'-'*10}-+-{'-'*14}-+-{'-'*8}")
            
            # 计算最佳吞吐量作为基准
            max_throughput = max(r.throughput for r in by_type[BenchmarkType.SCALABILITY.value])
            
            for result in by_type[BenchmarkType.SCALABILITY.value]:
                batch_size = result.parameters.get('batch_size', 0)
                efficiency = (result.throughput / max_throughput * 100) if max_throughput > 0 else 0
                report_lines.append(
                    f"  {batch_size:>12,} | {result.mean_ms:>8.0f}ms | "
                    f"{result.throughput:>12,.0f}/s | {efficiency:>6.1f}%"
                )
            report_lines.append("")
        
        # 总结
        report_lines.append("=" * 80)
        report_lines.append("📋 性能总结")
        report_lines.append("=" * 80)
        
        # 最佳批次执行性能
        exec_results = by_type.get(BenchmarkType.BATCH_EXECUTION.value, [])
        if exec_results:
            best = max(exec_results, key=lambda r: r.throughput)
            report_lines.append(f"  最佳吞吐量: {best.throughput:,.0f} keys/sec")
            report_lines.append(f"  最佳 batch_size: {best.parameters.get('batch_size', 0):,}")
        
        report_lines.append("=" * 80)
        
        return "\n".join(report_lines)
    
    def save_results(self, filepath: str, results: Optional[List[BenchmarkResult]] = None) -> None:
        """保存测试结果到 JSON 文件
        
        Args:
            filepath: 文件路径
            results: 测试结果（可选）
        """
        import json
        
        if results is None:
            results = self.results
        
        # 转换为可序列化格式
        serializable = []
        for result in results:
            serializable.append({
                'test_name': result.test_name,
                'test_type': result.test_type.value,
                'device_name': result.device_name,
                'vendor': result.vendor,
                'duration_ms': result.duration_ms,
                'throughput': result.throughput,
                'parameters': result.parameters,
                'min_ms': result.min_ms,
                'max_ms': result.max_ms,
                'mean_ms': result.mean_ms,
                'median_ms': result.median_ms,
                'std_dev_ms': result.std_dev_ms,
                'timestamp': result.timestamp,
                'iterations': result.iterations,
                'status': result.status,
                'error_message': result.error_message
            })
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(serializable, f, indent=2, ensure_ascii=False)
        
        logger.info(f"测试结果已保存到: {filepath}")
    
    def _get_device_name(self) -> str:
        """获取设备名称"""
        if hasattr(self.gpu_engine, '_gpu_device') and self.gpu_engine._gpu_device:
            return self.gpu_engine._gpu_device.device_info.get('name', 'Unknown')
        return 'Unknown'
    
    def _get_vendor(self) -> str:
        """获取厂商名称"""
        if hasattr(self.gpu_engine, '_gpu_device') and self.gpu_engine._gpu_device:
            return self.gpu_engine._gpu_device.device_info.get('vendor', 'Unknown')
        return 'Unknown'

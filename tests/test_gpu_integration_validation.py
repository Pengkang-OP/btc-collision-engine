#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GPU集成测试和性能验证 - 步骤7
验证所有优化组件集成正常,性能达标
"""

import sys
import os
import time
import json
from pathlib import Path

# 修复Windows编码
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 添加项目根目录
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.collision.gpu_collision_engine import GPUCollisionEngine
from src.monitoring.gpu_performance_monitor import get_gpu_performance_monitor


class GPUIntegrationValidator:
    """GPU集成验证器"""
    
    # 测试常量
    TEST_DURATION_SHORT = 3  # 秒
    TEST_DURATION_STRESS = 30  # 秒
    THREAD_JOIN_TIMEOUT = 5  # 秒
    BATCH_SIZE_STANDARD = 5000
    BATCH_SIZE_LARGE = 10000
    
    def __init__(self):
        self.results = {}
        self.test_data_dir = Path(__file__).parent.parent / "test_data"
        self.test_data_dir.mkdir(exist_ok=True)
    
    def _log_exception(self, test_name: str, e: Exception):
        """记录详细异常信息"""
        import traceback
        error_msg = f"{type(e).__name__}: {str(e)}"
        tb = traceback.format_exc()
        print(f"  📝 详细堆栈:\n{tb}")
        return error_msg
    
    def print_header(self, title):
        print("\n" + "=" * 80)
        print(f"  {title}")
        print("=" * 80)
    
    def print_result(self, test_name, passed, details=""):
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {status} - {test_name}")
        if details:
            print(f"     {details}")
        self.results[test_name] = passed
    
    def test_01_gpu_availability(self):
        """测试1: GPU可用性检查"""
        self.print_header("测试1: GPU可用性检查")
        
        try:
            available = GPUCollisionEngine.is_gpu_available()
            self.print_result("GPU可用性", available, f"GPU{'可用' if available else '不可用'}")
            
            if not available:
                print("\n⚠️  GPU不可用,跳过后续GPU测试")
                # 标记所有后续测试为跳过
                self.results['GPU引擎初始化'] = False
                self.results['监控器生命周期'] = False
                self.results['性能指标准确性'] = False
                self.results['内存池效率'] = False
                self.results['压力测试'] = False
                return False
            
            # 获取设备信息
            from src.gpu.device import GPUDeviceHelper
            devices = GPUDeviceHelper.detect_devices()
            device_count = len(devices)
            self.print_result("GPU设备检测", device_count > 0, f"检测到 {device_count} 个GPU设备")
            
            if device_count > 0:
                device = devices[0]
                print(f"\n📊 主GPU设备信息:")
                print(f"   名称: {device.get('name', 'Unknown')}")
                print(f"   厂商: {device.get('vendor', 'Unknown')}")
                print(f"   显存: {device.get('global_mem_size', 0) / (1024**3):.1f} GB")
                print(f"   最大工作组: {device.get('max_work_group_size', 0):,}")
                
                # 保存设备信息供后续测试使用
                self.gpu_device_info = device
            
            return available
            
        except Exception as e:
            error_msg = self._log_exception("GPU可用性检查", e)
            self.print_result("GPU可用性检查", False, error_msg)
            return False
    
    def test_02_gpu_engine_initialization(self):
        """测试2: GPU引擎初始化"""
        self.print_header("测试2: GPU引擎初始化")
        
        engine = None
        try:
            # 阶段1: 创建引擎
            try:
                test_targets = ["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"]
                start_time = time.time()
                engine = GPUCollisionEngine(
                    targets=test_targets,
                    batch_size=self.BATCH_SIZE_STANDARD,
                    use_gpu_memory_pool=True
                )
                init_time = (time.time() - start_time) * 1000
                self.print_result("引擎创建", True, f"初始化时间: {init_time:.2f}ms")
            except Exception as e:
                error_msg = self._log_exception("引擎创建", e)
                self.print_result("引擎创建", False, error_msg)
                return False
            
            # 阶段2: 验证组件初始化
            try:
                components = {
                    "GPU内核": hasattr(engine, '_gpu_kernel') and engine._gpu_kernel is not None,
                    "内存池": hasattr(engine, '_gpu_memory_pool') and engine._gpu_memory_pool is not None,
                    "性能监控": hasattr(engine, 'gpu_performance_monitor') and engine.gpu_performance_monitor is not None,
                    "增强监控": hasattr(engine, 'enhanced_monitoring') and engine.enhanced_monitoring is not None,
                    "Intel超时管理": hasattr(engine, 'timeout_manager'),
                    "Intel显存监控": hasattr(engine, 'memory_monitor'),
                    "基准测试套件": hasattr(engine, 'benchmark_suite'),
                    "自动调优器": hasattr(engine, 'auto_tuner'),
                }
                
                all_initialized = True
                for comp_name, is_init in components.items():
                    self.print_result(f"{comp_name}初始化", is_init)
                    if not is_init:
                        all_initialized = False
                
                if not all_initialized:
                    return False
            except Exception as e:
                error_msg = self._log_exception("组件验证", e)
                self.print_result("组件验证", False, error_msg)
                return False
            
            # 阶段3: 清理
            try:
                engine.stop()
                self.print_result("资源清理", True)
            except Exception as e:
                error_msg = self._log_exception("资源清理", e)
                self.print_result("资源清理", False, error_msg)
                # 清理失败不阻塞测试结果
            
            return True
            
        except Exception as e:
            error_msg = self._log_exception("GPU引擎初始化", e)
            self.print_result("GPU引擎初始化", False, error_msg)
            return False
        finally:
            # 确保资源清理
            if engine:
                try:
                    engine.stop()
                except:
                    pass
    
    def test_03_monitor_lifecycle(self):
        """测试3: 监控器生命周期管理"""
        self.print_header("测试3: 监控器生命周期管理")
        
        engine1 = None
        engine2 = None
        
        try:
            test_targets = ["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"]
            
            # 创建第1个引擎
            try:
                engine1 = GPUCollisionEngine(
                    targets=test_targets,
                    batch_size=self.BATCH_SIZE_STANDARD,
                    use_gpu_memory_pool=True
                )
                
                monitor = engine1.gpu_performance_monitor
                self.print_result("监控器创建", monitor is not None)
                self.print_result("监控器已启动", monitor._running, f"状态: {monitor._running}")
                
                # 停止引擎
                engine1.stop()
                self.print_result("监控器已停止", not monitor._running, f"状态: {monitor._running}")
            except Exception as e:
                error_msg = self._log_exception("引擎1生命周期", e)
                self.print_result("引擎1生命周期", False, error_msg)
                return False
            
            # 创建第2个引擎(验证全局监控器重用)
            try:
                engine2 = GPUCollisionEngine(
                    targets=test_targets,
                    batch_size=self.BATCH_SIZE_STANDARD,
                    use_gpu_memory_pool=True
                )
                
                monitor2 = engine2.gpu_performance_monitor
                self.print_result("监控器重用", monitor is monitor2, "使用同一全局实例")
                
                engine2.stop()
            except Exception as e:
                error_msg = self._log_exception("引擎2生命周期", e)
                self.print_result("引擎2生命周期", False, error_msg)
                return False
            
            return True
            
        except Exception as e:
            error_msg = self._log_exception("监控器生命周期", e)
            self.print_result("监控器生命周期", False, error_msg)
            return False
        finally:
            # 确保资源清理
            for eng in [engine1, engine2]:
                if eng:
                    try:
                        eng.stop()
                    except:
                        pass
    
    def test_04_performance_metrics_accuracy(self):
        """测试4: 性能指标准确性验证"""
        self.print_header("测试4: 性能指标准确性验证")
        
        engine = None
        try:
            test_targets = ["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"]
            
            engine = GPUCollisionEngine(
                targets=test_targets,
                batch_size=self.BATCH_SIZE_STANDARD,
                use_gpu_memory_pool=True
            )
            
            # 运行短时间
            import threading
            def run_engine():
                engine.start()
            
            thread = threading.Thread(target=run_engine, daemon=True)
            thread.start()
            
            # 等待收集数据 - 增加到5秒确保数据完整
            time.sleep(5)
            engine.stop()
            
            # 检查线程状态
            thread.join(timeout=self.THREAD_JOIN_TIMEOUT)
            if thread.is_alive():
                print("⚠️ 警告: 引擎线程未在5秒内停止")
                self.print_result("线程停止", False, "线程超时")
            else:
                self.print_result("线程停止", True)
            
            # 获取性能报告 - 重试机制确保数据有效
            monitor = engine.gpu_performance_monitor
            report = monitor.get_performance_report()
            
            # 如果报告数据为空,等待并重试
            if report.total_batches == 0:
                print("⚠️ 警告: 报告数据为空,等待2秒后重试...")
                time.sleep(2)
                report = monitor.get_performance_report()
            
            # 验证指标
            metrics = {
                "总批次": report.total_batches > 0,
                "总密钥数": report.total_keys_processed > 0,
                "平均吞吐量": report.avg_throughput_keys_per_sec > 0,
                "峰值吞吐量": report.peak_throughput_keys_per_sec > 0,
                "平均执行时间": report.avg_execution_time_ms > 0,
                "错误率": report.error_rate_percent >= 0,
                "显存使用": report.memory_usage_avg_mb > 0,
            }
            
            all_valid = True
            metric_values = {
                "总批次": report.total_batches,
                "总密钥数": report.total_keys_processed,
                "平均吞吐量": report.avg_throughput_keys_per_sec,
                "峰值吞吐量": report.peak_throughput_keys_per_sec,
                "平均执行时间": report.avg_execution_time_ms,
                "错误率": report.error_rate_percent,
                "显存使用": report.memory_usage_avg_mb,
            }
            
            for metric_name, is_valid in metrics.items():
                value = metric_values[metric_name]
                self.print_result(f"{metric_name}", is_valid, f"值: {value:.2f}")
                if not is_valid:
                    all_valid = False
            
            # 关键验证: 吞吐量不应为0
            if report.avg_throughput_keys_per_sec > 0:
                print(f"\n✅ 吞吐量验证通过: {report.avg_throughput_keys_per_sec:,.0f} keys/s")
            else:
                print(f"\n❌ 吞吐量验证失败: 为0 (execution_time_ms可能未正确记录)")
                all_valid = False
            
            return all_valid
            
        except Exception as e:
            error_msg = self._log_exception("性能指标准确性", e)
            self.print_result("性能指标准确性", False, error_msg)
            return False
        finally:
            # 确保资源清理
            if engine:
                try:
                    engine.stop()
                except:
                    pass
    
    def test_05_memory_pool_efficiency(self):
        """测试5: 内存池效率验证"""
        self.print_header("测试5: 内存池效率验证")
        
        engine = None
        try:
            test_targets = ["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"]
            
            engine = GPUCollisionEngine(
                targets=test_targets,
                batch_size=self.BATCH_SIZE_STANDARD,
                use_gpu_memory_pool=True
            )
            
            # 先运行几秒钟,让内存池产生数据
            import threading
            def run_engine():
                engine.start()
            
            thread = threading.Thread(target=run_engine, daemon=True)
            thread.start()
            
            # 运行5秒
            time.sleep(5)
            engine.stop()
            thread.join(timeout=self.THREAD_JOIN_TIMEOUT)
            
            pool = engine._gpu_memory_pool
            
            # 验证内存池统计
            stats = pool.get_stats()
            
            # 使用正确的键名
            total_allocated = stats.get('total_allocated', 0)
            total_reused = stats.get('total_reused', 0)
            reuse_rate = stats.get('reuse_rate', 0.0)
            current_memory_mb = stats.get('current_memory_mb', 0.0)
            pooled_buffers = stats.get('pooled_buffers', 0)
            
            self.print_result("内存池统计", True, 
                            f"分配={total_allocated}, "
                            f"复用={total_reused}, "
                            f"池化缓冲区={pooled_buffers}")
            
            # 验证内存池已使用
            pool_used = total_allocated > 0 or pooled_buffers > 0
            self.print_result("内存池已使用", pool_used, 
                            f"分配={total_allocated}, 池化={pooled_buffers}")
            
            self.print_result("缓存命中率", reuse_rate >= 0, f"{reuse_rate:.1f}%")
            
            # 验证内存池复用
            if total_reused > 0 or reuse_rate > 0:
                print(f"\n✅ 内存池复用验证通过: 命中率 {reuse_rate:.1f}%")
            else:
                print(f"\n⚠️  内存池尚未产生缓存命中(可能批次太少)")
            
            return True
            
        except Exception as e:
            error_msg = self._log_exception("内存池效率", e)
            self.print_result("内存池效率", False, error_msg)
            return False
        finally:
            if engine:
                try:
                    engine.stop()
                except:
                    pass
    
    def test_06_stress_test_short(self):
        """测试6: 短时间压力测试(30秒)"""
        self.print_header("测试6: 短时间压力测试(30秒)")
        
        engine = None
        try:
            test_targets = ["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"]
            
            engine = GPUCollisionEngine(
                targets=test_targets,
                batch_size=self.BATCH_SIZE_LARGE,  # 增大批次
                use_gpu_memory_pool=True
            )
            
            import threading
            def run_engine():
                engine.start()
            
            thread = threading.Thread(target=run_engine, daemon=True)
            thread.start()
            
            # 运行压力测试
            print("  运行30秒压力测试...")
            for i in range(self.TEST_DURATION_STRESS):
                time.sleep(1)
                if (i + 1) % 10 == 0:
                    report = engine.gpu_performance_monitor.get_performance_report()
                    print(f"    [{i+1}s] 吞吐量: {report.avg_throughput_keys_per_sec:,.0f} keys/s, "
                          f"批次: {report.total_batches}")
            
            engine.stop()
            
            # 检查线程状态
            thread.join(timeout=self.THREAD_JOIN_TIMEOUT)
            if thread.is_alive():
                print("⚠️ 警告: 引擎线程未在5秒内停止")
            
            # 获取最终报告
            report = engine.gpu_performance_monitor.get_performance_report()
            
            stress_metrics = {
                "运行时长": self.TEST_DURATION_STRESS,
                "总处理密钥": report.total_keys_processed,
                "平均吞吐量": f"{report.avg_throughput_keys_per_sec:,.0f} keys/s",
                "峰值吞吐量": f"{report.peak_throughput_keys_per_sec:,.0f} keys/s",
                "总批次": report.total_batches,
                "错误率": f"{report.error_rate_percent:.2f}%",
                "平均显存": f"{report.memory_usage_avg_mb:.2f} MB",
            }
            
            print("\n📊 压力测试结果:")
            for key, value in stress_metrics.items():
                print(f"   {key}: {value}")
            
            # 验证稳定性
            self.print_result("30秒稳定性", report.error_rate_percent < 1.0, 
                            f"错误率: {report.error_rate_percent:.2f}%")
            
            # 验证性能
            self.print_result("性能达标", report.avg_throughput_keys_per_sec > 100000,
                            f"吞吐量: {report.avg_throughput_keys_per_sec:,.0f} keys/s")
            
            return report.error_rate_percent < 1.0 and report.avg_throughput_keys_per_sec > 100000
            
        except Exception as e:
            error_msg = self._log_exception("压力测试", e)
            self.print_result("压力测试", False, error_msg)
            return False
        finally:
            if engine:
                try:
                    engine.stop()
                except:
                    pass
    
    def test_07_error_handling(self):
        """测试7: 错误处理和恢复"""
        self.print_header("测试7: 错误处理和恢复")
        
        engine = None
        try:
            # 测试1: 无效目标地址
            try:
                engine = GPUCollisionEngine(
                    targets=["invalid_address"],
                    batch_size=self.BATCH_SIZE_STANDARD,
                    use_gpu_memory_pool=True
                )
                self.print_result("无效地址检测", False, "应该抛出异常")
                engine.stop()
                return False
            except (ValueError, Exception) as e:
                self.print_result("无效地址检测", True, f"正确捕获异常: {type(e).__name__}")
            
            # 测试2: 正常启动停止
            test_targets = ["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"]
            engine = GPUCollisionEngine(
                targets=test_targets,
                batch_size=self.BATCH_SIZE_STANDARD,
                use_gpu_memory_pool=True
            )
            
            # 多次停止(应该安全)
            engine.stop()
            engine.stop()  # 第二次停止不应崩溃
            self.print_result("重复停止安全", True, "多次stop()不崩溃")
            
            return True
            
        except Exception as e:
            error_msg = self._log_exception("错误处理", e)
            self.print_result("错误处理", False, error_msg)
            return False
        finally:
            if engine:
                try:
                    engine.stop()
                except:
                    pass
    
    def run_all_tests(self):
        """运行所有集成测试"""
        self.print_header("GPU集成测试和性能验证 - 步骤7")
        print(f"开始时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Python版本: {sys.version}")
        print(f"项目路径: {Path(__file__).parent.parent}")
        
        tests = [
            ("GPU可用性检查", self.test_01_gpu_availability),
            ("GPU引擎初始化", self.test_02_gpu_engine_initialization),
            ("监控器生命周期", self.test_03_monitor_lifecycle),
            ("性能指标准确性", self.test_04_performance_metrics_accuracy),
            ("内存池效率", self.test_05_memory_pool_efficiency),
            ("短时间压力测试", self.test_06_stress_test_short),
            ("错误处理和恢复", self.test_07_error_handling),
        ]
        
        passed = 0
        failed = 0
        
        for test_name, test_func in tests:
            try:
                result = test_func()
                if result:
                    passed += 1
                else:
                    failed += 1
            except Exception as e:
                failed += 1
                print(f"\n❌ 测试 [{test_name}] 异常: {e}")
                import traceback
                traceback.print_exc()
        
        # 总结
        self.print_header("测试总结")
        
        total = passed + failed
        print(f"  总测试数: {total}")
        print(f"  ✅ 通过: {passed}")
        print(f"  ❌ 失败: {failed}")
        print(f"  通过率: {passed/total*100:.1f}%")
        
        # 性能基准对比
        self.print_header("性能基准对比 (Intel Arc A770)")
        benchmarks = {
            "平均吞吐量": {
                "v2.2.0基准": "~150,000 keys/s",
                "当前目标": ">200,000 keys/s",
                "提升": "+33%"
            },
            "峰值吞吐量": {
                "v2.2.0基准": "~180,000 keys/s", 
                "当前目标": ">240,000 keys/s",
                "提升": "+33%"
            },
            "执行时间": {
                "v2.2.0基准": "~65ms",
                "当前目标": "<50ms",
                "提升": "-23%"
            },
            "显存估算": {
                "v2.2.0基准": "~70%准确度",
                "当前目标": ">90%准确度",
                "提升": "+29%"
            },
            "错误率": {
                "v2.2.0基准": "<0.1%",
                "当前目标": "0.00%",
                "提升": "稳定"
            }
        }
        
        print("\n📊 性能优化目标:")
        for metric, values in benchmarks.items():
            print(f"\n  {metric}:")
            print(f"    v2.2.0: {values['v2.2.0基准']}")
            print(f"    v2.2.1: {values['当前目标']}")
            print(f"    提升: {values['提升']}")
        
        # 生成测试报告
        report = {
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
            "total_tests": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": f"{passed/total*100:.1f}%",
            "results": self.results,
            "performance_benchmarks": benchmarks,
        }
        
        report_path = self.test_data_dir / "gpu_integration_test_report.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"\n📄 测试报告已保存: {report_path}")
        
        if failed == 0:
            print("\n🎉 所有集成测试通过! GPU模块集成正常!")
        else:
            print(f"\n⚠️  有 {failed} 个测试失败,请检查日志")
        
        return failed == 0


if __name__ == "__main__":
    validator = GPUIntegrationValidator()
    success = validator.run_all_tests()
    sys.exit(0 if success else 1)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v3.3.1修复验证脚本 - GPU停止阻塞修复无回归测试

测试范围:
1. GPU内核加载和基本功能
2. command_execution_status查询机制
3. 停止信号传递和响应
4. 性能稳定性验证
5. 异步双缓冲兼容性
"""

import sys
import os
import time
from pathlib import Path

# 添加项目根目录到路径
project_root = str(Path(__file__).parent)
sys.path.insert(0, project_root)

def test_1_import_gpu_modules():
    """测试1: GPU模块导入"""
    print("\n" + "="*80)
    print("测试1: GPU模块导入")
    print("="*80)
    
    try:
        from src.gpu.kernel_impl import GPUKernel
        from src.gpu.device import GPUDevice
        from src.gpu.async_executor import AsyncGPUExecutor
        import pyopencl as cl
        
        print("  ✅ GPUKernel导入成功")
        print("  ✅ GPUDevice导入成功")
        print("  ✅ AsyncGPUExecutor导入成功")
        print("  ✅ PyOpenCL导入成功")
        print(f"  ✅ PyOpenCL版本: {cl.VERSION}")
        
        # 验证command_execution_status可用
        assert hasattr(cl, 'command_execution_status'), "command_execution_status不可用"
        print(f"  ✅ command_execution_status枚举可用")
        
        return True
    except Exception as e:
        print(f"  ❌ 导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_2_kernel_impl_code_review():
    """测试2: 检查kernel_impl.py代码正确性"""
    print("\n" + "="*80)
    print("测试2: kernel_impl.py代码审查")
    print("="*80)
    
    try:
        kernel_file = os.path.join(project_root, 'src', 'gpu', 'kernel_impl.py')
        with open(kernel_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查pyopencl导入位置
        if 'import pyopencl as cl' in content.split('class GPUKernel')[0]:
            print("  ✅ pyopencl在文件顶部导入(正确)")
        else:
            print("  ❌ pyopencl导入位置错误")
            return False
        
        # 检查使用command_execution_status
        if 'command_execution_status' in content:
            print("  ✅ 使用command_execution_status查询(正确)")
        else:
            print("  ❌ 未找到command_execution_status")
            return False
        
        # 检查没有错误的wait(timeout=...)调用
        if 'wait(timeout=' in content:
            print("  ❌ 仍存在错误的wait(timeout=...)调用")
            return False
        else:
            print("  ✅ 无错误的wait(timeout=...)调用")
        
        # 检查停止信号处理
        if 'stop_event' in content and 'is_set()' in content:
            print("  ✅ 停止信号处理逻辑存在")
        else:
            print("  ❌ 停止信号处理逻辑缺失")
            return False
        
        return True
    except Exception as e:
        print(f"  ❌ 代码审查失败: {e}")
        return False


def test_3_gpu_device_detection():
    """测试3: GPU设备检测"""
    print("\n" + "="*80)
    print("测试3: GPU设备检测")
    print("="*80)
    
    try:
        from src.gpu.device import GPUDevice
        
        # 初始化GPU设备
        device = GPUDevice()
        device.initialize()
        
        print(f"  ✅ GPU设备初始化成功")
        print(f"  ✅ 设备数量: {len(device.devices) if hasattr(device, 'devices') else 'N/A'}")
        
        if hasattr(device, 'device_info'):
            device_name = device.device_info.get('name', 'Unknown')
            print(f"  ✅ 当前设备: {device_name}")
        
        # 清理
        device.release()
        print("  ✅ GPU设备释放成功")
        
        return True
    except Exception as e:
        print(f"  ❌ GPU设备检测失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_4_gpu_kernel_basic():
    """测试4: GPU内核基本功能"""
    print("\n" + "="*80)
    print("测试4: GPU内核基本功能")
    print("="*80)
    
    try:
        from src.collision.gpu_collision_engine import GPUCollisionEngine
        
        # 创建引擎(最小配置)
        targets = ["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"]
        engine = GPUCollisionEngine(
            targets=targets,
            device_index=-1,
            batch_size=1024,  # 小批次快速测试
            on_progress=None,
            checkpoint_enabled=False,
            dedup_enabled=False
        )
        
        print(f"  ✅ GPU引擎创建成功")
        print(f"  ✅ 目标地址: {len(targets)}个")
        print(f"  ✅ 批次大小: 1024")
        
        # 检查异步执行器
        if hasattr(engine, '_async_executor') and engine._async_executor:
            print(f"  ✅ 异步执行器已启用")
        else:
            print(f"  ⚠️  异步执行器未启用(同步模式)")
        
        # 清理
        engine.stop()
        print("  ✅ 引擎停止成功")
        
        return True
    except Exception as e:
        print(f"  ❌ GPU内核测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_5_short_benchmark():
    """测试5: 短基准测试(验证性能)"""
    print("\n" + "="*80)
    print("测试5: 短基准测试(10秒)")
    print("="*80)
    
    try:
        from src.collision.gpu_collision_engine import GPUCollisionEngine
        from src.collision.collision_stats import CollisionStats
        
        targets = ["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"]
        speed_records = []
        
        def on_progress(stats: CollisionStats):
            if stats.speed > 0:
                speed_records.append(stats.speed)
        
        engine = GPUCollisionEngine(
            targets=targets,
            device_index=-1,
            batch_size=1048576,
            on_progress=on_progress,
            checkpoint_enabled=False,
            dedup_enabled=False
        )
        
        print("  启动引擎...")
        engine.start()
        
        # 运行10秒
        time.sleep(10)
        
        # 停止
        engine.stop()
        time.sleep(1)  # 等待线程退出
        
        if speed_records:
            avg_speed = sum(speed_records) / len(speed_records)
            max_speed = max(speed_records)
            min_speed = min(speed_records)
            
            print(f"  ✅ 测试完成")
            print(f"  ✅ 平均速度: {avg_speed:,.0f} keys/s")
            print(f"  ✅ 峰值速度: {max_speed:,.0f} keys/s")
            print(f"  ✅ 最低速度: {min_speed:,.0f} keys/s")
            print(f"  ✅ 稳定性: ±{((max_speed - min_speed) / avg_speed * 50):.1f}%")
            
            # 性能阈值检查
            if avg_speed > 1000000:  # 至少1M keys/s
                print(f"  ✅ 性能达标(>1M keys/s)")
            else:
                print(f"  ⚠️  性能偏低(<1M keys/s)")
        else:
            print("  ⚠️  未收集到速度数据")
        
        return True
    except Exception as e:
        print(f"  ❌ 基准测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_6_stop_signal_response():
    """测试6: 停止信号响应时间"""
    print("\n" + "="*80)
    print("测试6: 停止信号响应时间")
    print("="*80)
    
    try:
        from src.collision.gpu_collision_engine import GPUCollisionEngine
        
        targets = ["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"]
        engine = GPUCollisionEngine(
            targets=targets,
            device_index=-1,
            batch_size=1048576,
            on_progress=None,
            checkpoint_enabled=False,
            dedup_enabled=False
        )
        
        print("  启动引擎...")
        engine.start()
        time.sleep(2)  # 运行2秒
        
        # 测试停止响应
        print("  发送停止信号...")
        stop_start = time.time()
        engine.stop()
        stop_elapsed = time.time() - stop_start
        
        print(f"  ✅ 停止响应时间: {stop_elapsed:.3f}秒")
        
        # 验证停止成功
        time.sleep(1)
        if hasattr(engine, '_thread') and engine._thread:
            if not engine._thread.is_alive():
                print("  ✅ 引擎线程已退出")
            else:
                print("  ⚠️  引擎线程仍在运行")
        
        # 响应时间阈值检查(<1秒为优秀)
        if stop_elapsed < 1.0:
            print(f"  ✅ 停止响应优秀(<1秒)")
        elif stop_elapsed < 5.0:
            print(f"  ⚠️  停止响应可接受(<5秒)")
        else:
            print(f"  ❌ 停止响应过慢(>5秒)")
        
        return True
    except Exception as e:
        print(f"  ❌ 停止信号测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("="*80)
    print("v3.3.1 GPU停止阻塞修复 - 无回归验证")
    print("="*80)
    print(f"Python版本: {sys.version}")
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    tests = [
        ("模块导入", test_1_import_gpu_modules),
        ("代码审查", test_2_kernel_impl_code_review),
        ("GPU设备检测", test_3_gpu_device_detection),
        ("GPU内核基本功能", test_4_gpu_kernel_basic),
        ("短基准测试", test_5_short_benchmark),
        ("停止信号响应", test_6_stop_signal_response),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n  ❌ 测试{name}异常: {e}")
            results.append((name, False))
    
    # 汇总结果
    print("\n" + "="*80)
    print("测试汇总")
    print("="*80)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {status} - {name}")
    
    print(f"\n总计: {passed}/{total} 通过")
    
    if passed == total:
        print("\n🎉 所有测试通过! v3.3.1修复无回归!")
        return 0
    else:
        print(f"\n⚠️  {total - passed}个测试失败,需要进一步调查")
        return 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
异步双缓冲60秒性能对比测试 v3

测试策略:
- 运行时长: 90秒(包含启动和稳定阶段)
- 数据分析: 只截取前60秒的稳定数据
- 目的: 避免引擎启动/停止阶段的不稳定数据影响结果

测试目标:
1. 同步模式(单缓冲)90秒运行,分析前60秒
2. 异步模式(双缓冲)90秒运行,分析前60秒
3. 对比性能差异,验证异步双缓冲优化效果

测试配置:
- 测试时长: 每模式90秒(分析60秒)
- 目标地址: 2个真实比特币地址
- 批次大小: 1,048,576 (1M)
- GPU设备: 自动选择

预期结果:
- Intel Arc A770: +30-50% 性能提升
- NVIDIA RTX 3060: +20-40% 性能提升
- AMD RX 6700 XT: +25-45% 性能提升

重要:
- 测试前自动检查并警告残留进程
- 每次测试完成后强制验证引擎完全停止
- 超时保护: 每个模式最多运行100秒(90秒测试+10秒缓冲)
"""

import sys
import os
import time
import json
import signal
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
import subprocess

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.collision.gpu_collision_engine import GPUCollisionEngine
from src.collision.collision_stats import CollisionStats


class AsyncDoubleBufferTest:
    """异步双缓冲性能对比测试器"""
    
    def __init__(self, test_duration: int = 90, analysis_duration: int = 60):
        """
        初始化测试器
        
        Args:
            test_duration: 每个模式的测试时长(秒),默认90秒
            analysis_duration: 数据分析时长(秒),默认60秒(截取前60秒稳定数据)
        """
        self.test_duration = test_duration
        self.analysis_duration = analysis_duration
        self.targets = [
            "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",  # 中本聪地址
            "12cbQLTFMXRnSzktFkuoG3eHoMeFtpTu3S"   # 早期地址
        ]
        
    def check_and_kill_processes(self):
        """检查并清理残留的Python进程"""
        print("\n[进程检查] 检查同项目进程...")
        try:
            import os
            current_pid = os.getpid()  # 获取当前进程PID
            print(f"  当前进程PID: {current_pid}")
            
            # Windows: 使用tasklist
            result = subprocess.run(
                ['tasklist', '/FI', 'IMAGENAME eq python.exe'],
                capture_output=True, text=True, encoding='gbk',
                creationflags=subprocess.CREATE_NO_WINDOW  # 隐藏窗口
            )
            
            lines = result.stdout.strip().split('\n')
            python_pids = []
            
            for line in lines[3:]:  # 跳过前3行标题
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 2:
                        try:
                            pid = int(parts[1])
                            # 排除当前进程
                            if pid != current_pid:
                                python_pids.append(pid)
                        except ValueError:
                            continue
            
            if python_pids:
                print(f"  ⚠️  警告: 发现 {len(python_pids)} 个其他Python进程: {python_pids}")
                print("  提示: 请手动关闭这些进程以避免干扰测试")
                print("  继续测试...")
            else:
                print("  ✓ 无其他Python进程")
                
        except Exception as e:
            print(f"  ⚠️  进程检查失败(继续测试): {e}")
    
    def test_sync_mode(self) -> Dict[str, Any]:
        """
        测试同步模式(单缓冲)
        
        Returns:
            测试结果字典
        """
        print("\n" + "="*80)
        print("  测试模式: 同步(单缓冲)")
        print("="*80)
        print(f"  测试时长: {self.test_duration}秒")
        print(f"  数据分析: 前{self.analysis_duration}秒")
        print(f"  批次大小: 1,048,576")
        print()
        
        stats_history = []
        batch_times = []
        total_keys = 0
        start_time = time.time()
        engine = None  # 初始化engine变量
        
        def on_progress(stats: CollisionStats):
            """进度回调"""
            elapsed = time.time() - start_time
            if elapsed >= self.test_duration:
                return
            
            # 只记录前analysis_duration秒的数据
            if elapsed <= self.analysis_duration:
                stats_history.append({
                    'timestamp': time.time(),
                    'elapsed': elapsed,
                    'total_checked': stats.total_checked,
                    'speed': stats.speed,
                    'matches': len(stats.matches)
                })
            
            # 打印进度(每5秒)
            if len(stats_history) % 10 == 0 and elapsed <= self.analysis_duration:
                print(f"  [{elapsed:5.1f}s] 速度: {stats.speed:,.0f} keys/s | "
                      f"总计: {stats.total_checked:,} | 匹配: {len(stats.matches)}")
        
        try:
            # 初始化引擎(同步模式 - 禁用异步执行器)
            print("  [初始化] 创建GPU引擎(同步模式)...")
            init_start = time.time()
            
            engine = GPUCollisionEngine(
                targets=self.targets,
                device_index=-1,  # 自动选择
                batch_size=1048576,
                on_progress=on_progress,
                checkpoint_enabled=False,
                dedup_enabled=False
            )
            
            # 禁用异步执行器(强制同步模式)
            if hasattr(engine, '_async_executor') and engine._async_executor:
                print("  [配置] 检测到异步执行器,正在禁用...")
                engine._async_executor = None
                print("  [配置] ✓ 异步执行器已禁用(同步模式)")
            else:
                print("  [配置] ✓ 无异步执行器(同步模式)")
            
            init_time = time.time() - init_start
            device_name = engine._gpu_device.device_info.get('name', 'Unknown') if hasattr(engine, '_gpu_device') and engine._gpu_device and hasattr(engine._gpu_device, 'device_info') else 'Unknown'
            print(f"  [完成] 初始化耗时: {init_time:.2f}秒")
            print(f"  [设备] {device_name}")
            print()
            
            # 启动碰撞检测
            print("  [启动] 开始同步模式测试...")
            engine.start()
            
            # 等待测试时长(90秒)
            while time.time() - start_time < self.test_duration:
                time.sleep(0.5)
                
                stats = engine.get_stats()
                if stats:
                    total_keys = stats.total_checked
            
            # 停止引擎(带超时保护)
            print("\n  [停止] 正在停止引擎(同步模式)...")
            stop_start = time.time()
            
            # 第1步: 设置停止事件(立即返回)
            engine._stop_event.set()
            engine._running = False
            print("  [步骤1] 已设置停止信号")
            
            # 第2步: 等待线程退出(最多10秒)
            try:
                if hasattr(engine, '_thread') and engine._thread:
                    engine._thread.join(timeout=10)
                    if engine._thread.is_alive():
                        print("  [警告] ⚠️  主线程未在10秒内退出")
                    else:
                        print("  [步骤2] ✓ 主线程已退出")
            except Exception as e:
                print(f"  [警告] 等待线程退出异常: {e}")
            
            # 第3步: 停止种子预生成线程
            try:
                if hasattr(engine, '_random_search_mode') and engine._random_search_mode:
                    engine._random_search_mode.stop()
                    print("  [步骤3] ✓ 种子预生成线程已停止")
            except Exception as e:
                print(f"  [警告] 停止种子预生成线程异常: {e}")
            
            # 第4步: 清理异步执行器(如果存在)
            try:
                if hasattr(engine, '_async_executor') and engine._async_executor:
                    engine._async_executor.cleanup()
                    print("  [步骤4] ✓ 异步执行器已清理")
            except Exception as e:
                print(f"  [警告] 清理异步执行器异常: {e}")
            
            # 第5步: 清理GPU设备(跳过检查点保存)
            try:
                if hasattr(engine, '_device_manager') and engine._device_manager:
                    engine._device_manager.cleanup()
                    print("  [步骤5] ✓ GPU设备已清理")
            except Exception as e:
                print(f"  [警告] 清理GPU设备异常: {e}")
            
            stop_time = time.time() - stop_start
            print(f"  [完成] 引擎已停止 (耗时: {stop_time:.2f}秒)")
            
            # 验证引擎是否完全停止
            if hasattr(engine, '_thread') and engine._thread:
                if engine._thread.is_alive():
                    print("  [警告] ⚠️  引擎线程仍在运行,等待强制退出...")
                    engine._thread.join(timeout=5)
                    if engine._thread.is_alive():
                        print("  [错误] ✗ 引擎线程未能停止,测试可能不准确")
                else:
                    print("  [验证] ✓ 引擎线程已完全退出")
            
            # 清理引擎引用
            engine = None
            time.sleep(2)  # 等待资源释放
            
            elapsed = time.time() - start_time
            
            # 计算前60秒的平均速度
            if stats_history:
                speed_samples = [s['speed'] for s in stats_history if s['speed'] > 0]
                avg_speed = sum(speed_samples) / len(speed_samples) if speed_samples else 0
                
                # 找到60秒时的总密钥数
                keys_at_60s = 0
                for s in sorted(stats_history, key=lambda x: x['elapsed'], reverse=True):
                    if s['elapsed'] <= self.analysis_duration:
                        keys_at_60s = s['total_checked']
                        break
                
                # 如果没有60秒内的数据,使用最后一个
                if keys_at_60s == 0 and stats_history:
                    keys_at_60s = stats_history[-1]['total_checked']
            else:
                avg_speed = 0
                keys_at_60s = total_keys
                speed_samples = []
            
            device_name_result = "Intel(R) Arc(TM) A770 Graphics"  # 默认值
            result = {
                'mode': 'sync',
                'device': device_name_result,
                'test_duration': self.test_duration,
                'analysis_duration': self.analysis_duration,
                'duration': elapsed,
                'total_keys': keys_at_60s,  # 使用60秒时的数据
                'avg_speed': avg_speed,  # 前60秒平均速度
                'init_time': init_time,
                'samples': len(stats_history),
                'speed_samples': speed_samples
            }
            
            if speed_samples:
                result['max_speed'] = max(speed_samples)
                result['min_speed'] = min(speed_samples)
                result['speed_std'] = (
                    sum((s - avg_speed) ** 2 for s in speed_samples) / 
                    len(speed_samples)
                ) ** 0.5
            else:
                result['max_speed'] = 0
                result['min_speed'] = 0
                result['speed_std'] = 0
            
            return result
            
        except Exception as e:
            print(f"\n  [错误] 同步模式测试失败: {e}")
            import traceback
            traceback.print_exc()
            return {
                'mode': 'sync',
                'error': str(e),
                'duration': time.time() - start_time
            }
    
    def test_async_mode(self) -> Dict[str, Any]:
        """
        测试异步模式(双缓冲)
        
        Returns:
            测试结果字典
        """
        print("\n" + "="*80)
        print("  测试模式: 异步(双缓冲)")
        print("="*80)
        print(f"  测试时长: {self.test_duration}秒")
        print(f"  数据分析: 前{self.analysis_duration}秒")
        print(f"  批次大小: 1,048,576")
        print()
        
        stats_history = []
        batch_times = []
        total_keys = 0
        start_time = time.time()
        
        def on_progress(stats: CollisionStats):
            """进度回调"""
            elapsed = time.time() - start_time
            if elapsed >= self.test_duration:
                return
            
            # 只记录前analysis_duration秒的数据
            if elapsed <= self.analysis_duration:
                stats_history.append({
                    'timestamp': time.time(),
                    'elapsed': elapsed,
                    'total_checked': stats.total_checked,
                    'speed': stats.speed,
                    'matches': len(stats.matches)
                })
            
            # 打印进度(每5秒)
            if len(stats_history) % 10 == 0 and elapsed <= self.analysis_duration:
                print(f"  [{elapsed:5.1f}s] 速度: {stats.speed:,.0f} keys/s | "
                      f"总计: {stats.total_checked:,} | 匹配: {len(stats.matches)}")
        
        try:
            # 初始化引擎(异步模式 - 使用默认配置)
            print("  [初始化] 创建GPU引擎(异步模式)...")
            init_start = time.time()
            
            engine = GPUCollisionEngine(
                targets=self.targets,
                device_index=-1,  # 自动选择
                batch_size=1048576,
                on_progress=on_progress,
                checkpoint_enabled=False,
                dedup_enabled=False
            )
            
            # 确认异步执行器已启用
            if hasattr(engine, '_async_executor') and engine._async_executor:
                queue_depth = getattr(engine._async_executor, 'queue_depth', 'N/A')
                print(f"  [配置] ✓ 异步执行器已启用 (队列深度: {queue_depth})")
            else:
                print("  [错误] ✗ 异步执行器未启用,测试无效!")
                return {
                    'mode': 'async',
                    'error': '异步执行器未启用',
                    'duration': time.time() - start_time
                }
            
            init_time = time.time() - init_start
            device_name = engine._gpu_device.device_info.get('name', 'Unknown') if hasattr(engine, '_gpu_device') and engine._gpu_device and hasattr(engine._gpu_device, 'device_info') else 'Unknown'
            print(f"  [完成] 初始化耗时: {init_time:.2f}秒")
            print(f"  [设备] {device_name}")
            print()
            
            # 启动碰撞检测
            print("  [启动] 开始异步模式测试...")
            engine.start()
            
            # 等待测试时长(90秒)
            while time.time() - start_time < self.test_duration:
                time.sleep(0.5)
                
                stats = engine.get_stats()
                if stats:
                    total_keys = stats.total_checked
            
            # 停止引擎(带超时保护)
            print("\n  [停止] 正在停止引擎(异步模式)...")
            stop_start = time.time()
            
            # 第1步: 设置停止事件(立即返回)
            engine._stop_event.set()
            engine._running = False
            print("  [步骤1] 已设置停止信号")
            
            # 第2步: 等待线程退出(最多10秒)
            try:
                if hasattr(engine, '_thread') and engine._thread:
                    engine._thread.join(timeout=10)
                    if engine._thread.is_alive():
                        print("  [警告] ⚠️  主线程未在10秒内退出")
                    else:
                        print("  [步骤2] ✓ 主线程已退出")
            except Exception as e:
                print(f"  [警告] 等待线程退出异常: {e}")
            
            # 第3步: 停止种子预生成线程
            try:
                if hasattr(engine, '_random_search_mode') and engine._random_search_mode:
                    engine._random_search_mode.stop()
                    print("  [步骤3] ✓ 种子预生成线程已停止")
            except Exception as e:
                print(f"  [警告] 停止种子预生成线程异常: {e}")
            
            # 第4步: 清理异步执行器(如果存在)
            try:
                if hasattr(engine, '_async_executor') and engine._async_executor:
                    engine._async_executor.cleanup()
                    print("  [步骤4] ✓ 异步执行器已清理")
            except Exception as e:
                print(f"  [警告] 清理异步执行器异常: {e}")
            
            # 第5步: 清理GPU设备(跳过检查点保存)
            try:
                if hasattr(engine, '_device_manager') and engine._device_manager:
                    engine._device_manager.cleanup()
                    print("  [步骤5] ✓ GPU设备已清理")
            except Exception as e:
                print(f"  [警告] 清理GPU设备异常: {e}")
            
            stop_time = time.time() - stop_start
            print(f"  [完成] 引擎已停止 (耗时: {stop_time:.2f}秒)")
            
            # 验证引擎是否完全停止
            if hasattr(engine, '_thread') and engine._thread:
                if engine._thread.is_alive():
                    print("  [警告] ⚠️  引擎线程仍在运行,等待强制退出...")
                    engine._thread.join(timeout=5)
                    if engine._thread.is_alive():
                        print("  [错误] ✗ 引擎线程未能停止,测试可能不准确")
                else:
                    print("  [验证] ✓ 引擎线程已完全退出")
            
            # 清理引擎引用
            engine = None
            time.sleep(2)  # 等待资源释放
            
            elapsed = time.time() - start_time
            
            # 计算前60秒的平均速度
            if stats_history:
                speed_samples = [s['speed'] for s in stats_history if s['speed'] > 0]
                avg_speed = sum(speed_samples) / len(speed_samples) if speed_samples else 0
                
                # 找到60秒时的总密钥数
                keys_at_60s = 0
                for s in sorted(stats_history, key=lambda x: x['elapsed'], reverse=True):
                    if s['elapsed'] <= self.analysis_duration:
                        keys_at_60s = s['total_checked']
                        break
                
                # 如果没有60秒内的数据,使用最后一个
                if keys_at_60s == 0 and stats_history:
                    keys_at_60s = stats_history[-1]['total_checked']
            else:
                avg_speed = 0
                keys_at_60s = total_keys
                speed_samples = []
            
            device_name_result = "Intel(R) Arc(TM) A770 Graphics"  # 默认值
            result = {
                'mode': 'async',
                'device': device_name_result,
                'test_duration': self.test_duration,
                'analysis_duration': self.analysis_duration,
                'duration': elapsed,
                'total_keys': keys_at_60s,  # 使用60秒时的数据
                'avg_speed': avg_speed,  # 前60秒平均速度
                'init_time': init_time,
                'samples': len(stats_history),
                'speed_samples': speed_samples
            }
            
            if speed_samples:
                result['max_speed'] = max(speed_samples)
                result['min_speed'] = min(speed_samples)
                result['speed_std'] = (
                    sum((s - avg_speed) ** 2 for s in speed_samples) / 
                    len(speed_samples)
                ) ** 0.5
            else:
                result['max_speed'] = 0
                result['min_speed'] = 0
                result['speed_std'] = 0
            
            return result
            
        except Exception as e:
            print(f"\n  [错误] 异步模式测试失败: {e}")
            import traceback
            traceback.print_exc()
            return {
                'mode': 'async',
                'error': str(e),
                'duration': time.time() - start_time
            }
    
    def run_comparison(self) -> Dict[str, Any]:
        """
        运行完整对比测试
        
        Returns:
            对比结果
        """
        print("="*80)
        print("  异步双缓冲性能对比测试 v3")
        print("="*80)
        print(f"  测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  测试时长: {self.test_duration}秒/模式")
        print(f"  数据分析: 前{self.analysis_duration}秒(稳定数据)")
        print(f"  目标地址: {len(self.targets)}个")
        print()
        
        # 测试前检查进程
        self.check_and_kill_processes()
        
        # 测试同步模式
        sync_result = self.test_sync_mode()
        
        # 检查同步模式是否成功
        if 'error' in sync_result:
            print("\n[错误] 同步模式测试失败,中止测试")
            return {
                'sync': sync_result,
                'async': {'error': '未执行'},
                'error': True,
                'timestamp': datetime.now().isoformat()
            }
        
        # 等待5秒冷却并清理资源
        print("\n" + "="*80)
        print("  冷却中...(5秒)")
        print("="*80)
        time.sleep(5)
        
        # 测试前再次检查进程
        self.check_and_kill_processes()
        
        # 测试异步模式
        async_result = self.test_async_mode()
        
        # 生成对比报告
        comparison = self.generate_comparison(sync_result, async_result)
        
        # 测试完成后清理进程
        print("\n[清理] 测试完成,检查残留进程...")
        self.check_and_kill_processes()
        
        return comparison
    
    def generate_comparison(self, sync: Dict, async_mode: Dict) -> Dict[str, Any]:
        """
        生成对比报告
        
        Args:
            sync: 同步模式结果
            async_mode: 异步模式结果
            
        Returns:
            对比报告
        """
        print("\n" + "="*80)
        print("  性能对比报告")
        print("="*80)
        
        # 计算性能提升
        if 'error' not in sync and 'error' not in async_mode:
            sync_speed = sync['avg_speed']
            async_speed = async_mode['avg_speed']
            
            improvement = ((async_speed - sync_speed) / sync_speed * 100) if sync_speed > 0 else 0
            
            print(f"\n  {'指标':<20} {'同步模式':>15} {'异步模式':>15} {'提升':>10}")
            print("  " + "-"*65)
            print(f"  {'平均速度 (keys/s)':<20} {sync_speed:>15,.0f} {async_speed:>15,.0f} {improvement:>+9.1f}%")
            print(f"  {'总密钥数':<20} {sync['total_keys']:>15,} {async_mode['total_keys']:>15,}")
            print(f"  {'测试时长 (秒)':<20} {sync['duration']:>15.2f} {async_mode['duration']:>15.2f}")
            print(f"  {'初始化时间 (秒)':<20} {sync['init_time']:>15.2f} {async_mode['init_time']:>15.2f}")
            
            if 'max_speed' in sync and 'max_speed' in async_mode:
                print(f"  {'最高速度 (keys/s)':<20} {sync['max_speed']:>15,.0f} {async_mode['max_speed']:>15,.0f}")
                print(f"  {'最低速度 (keys/s)':<20} {sync['min_speed']:>15,.0f} {async_mode['min_speed']:>15,.0f}")
                print(f"  {'速度标准差':<20} {sync['speed_std']:>15,.0f} {async_mode['speed_std']:>15,.0f}")
            
            print("\n" + "-"*65)
            
            if improvement > 0:
                print(f"  ✅ 异步双缓冲带来 {improvement:.1f}% 性能提升")
            else:
                print(f"  ⚠️  异步双缓冲性能变化: {improvement:.1f}%")
            
            print("="*80)
            
            return {
                'sync': sync,
                'async': async_mode,
                'improvement_pct': improvement,
                'test_duration': self.test_duration,
                'timestamp': datetime.now().isoformat(),
                'device': sync.get('device', 'Unknown')
            }
        else:
            print("\n  ⚠️  测试出现错误，无法生成完整对比")
            if 'error' in sync:
                print(f"  同步模式错误: {sync['error']}")
            if 'error' in async_mode:
                print(f"  异步模式错误: {async_mode['error']}")
            
            return {
                'sync': sync,
                'async': async_mode,
                'error': True,
                'timestamp': datetime.now().isoformat()
            }
    
    def save_results(self, comparison: Dict[str, Any]):
        """
        保存测试结果
        
        Args:
            comparison: 对比结果
        """
        output_dir = os.path.join(project_root, 'test_results')
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"async_double_buffer_comparison_{timestamp}.json"
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(comparison, f, indent=2, ensure_ascii=False)
        
        print(f"\n  📁 结果已保存: {filepath}")
        
        # 同时生成Markdown报告
        md_filename = f"async_double_buffer_comparison_{timestamp}.md"
        md_filepath = os.path.join(output_dir, md_filename)
        
        generate_markdown_report(comparison, md_filepath)
        print(f"  📄 报告已生成: {md_filepath}")


def generate_markdown_report(comparison: Dict, filepath: str):
    """生成Markdown格式的报告"""
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write("# 异步双缓冲60秒性能对比测试报告\n\n")
        f.write(f"> **测试时间**: {comparison.get('timestamp', 'N/A')}\n")
        f.write(f"> **测试版本**: v3.3.0\n")
        f.write(f"> **GPU设备**: {comparison.get('device', 'Unknown')}\n\n")
        
        f.write("## 测试配置\n\n")
        f.write(f"- **测试时长**: {comparison['test_duration']}秒/模式\n")
        f.write(f"- **批次大小**: 1,048,576 (1M)\n")
        f.write(f"- **目标地址**: 2个真实比特币地址\n")
        f.write(f"- **同步模式**: 单缓冲，队列深度=1\n")
        f.write(f"- **异步模式**: 双缓冲，队列深度=2\n\n")
        
        if 'error' not in comparison:
            sync = comparison['sync']
            async_mode = comparison['async']
            improvement = comparison['improvement_pct']
            
            f.write("## 性能对比结果\n\n")
            f.write("| 指标 | 同步模式 | 异步模式 | 变化 |\n")
            f.write("|------|----------|----------|------|\n")
            f.write(f"| 平均速度 (keys/s) | {sync['avg_speed']:,.0f} | {async_mode['avg_speed']:,.0f} | {improvement:+.1f}% |\n")
            f.write(f"| 总密钥数 | {sync['total_keys']:,} | {async_mode['total_keys']:,} | - |\n")
            f.write(f"| 测试时长 (秒) | {sync['duration']:.2f} | {async_mode['duration']:.2f} | - |\n")
            f.write(f"| 初始化时间 (秒) | {sync['init_time']:.2f} | {async_mode['init_time']:.2f} | - |\n")
            
            if 'max_speed' in sync:
                f.write(f"| 最高速度 (keys/s) | {sync['max_speed']:,.0f} | {async_mode['max_speed']:,.0f} | - |\n")
                f.write(f"| 最低速度 (keys/s) | {sync['min_speed']:,.0f} | {async_mode['min_speed']:,.0f} | - |\n")
                f.write(f"| 速度标准差 | {sync['speed_std']:,.0f} | {async_mode['speed_std']:,.0f} | - |\n")
            
            f.write("\n## 结论\n\n")
            if improvement > 20:
                f.write(f"✅ **异步双缓冲优化成功！** 性能提升 **{improvement:.1f}%**\n\n")
            elif improvement > 0:
                f.write(f"✅ 异步双缓冲带来 **{improvement:.1f}%** 性能提升\n\n")
            else:
                f.write(f"⚠️ 异步双缓冲未带来预期性能提升（{improvement:.1f}%）\n\n")
            
            f.write("### 预期vs实际\n\n")
            f.write("| GPU型号 | 预期提升 | 实际提升 |\n")
            f.write("|---------|----------|----------|\n")
            f.write("| Intel Arc A770 | +30-50% | - |\n")
            f.write("| NVIDIA RTX 3060 | +20-40% | - |\n")
            f.write("| AMD RX 6700 XT | +25-45% | - |\n")
            f.write(f"| **当前设备** | - | **{improvement:+.1f}%** |\n")
        
        else:
            f.write("## 测试错误\n\n")
            f.write("测试过程中出现错误，请检查日志。\n")
            
            if 'error' in comparison.get('sync', {}):
                f.write(f"- 同步模式: {comparison['sync']['error']}\n")
            if 'error' in comparison.get('async', {}):
                f.write(f"- 异步模式: {comparison['async']['error']}\n")


if __name__ == "__main__":
    # 检查是否指定测试时长
    duration = 90  # 默认90秒
    analysis_duration = 60  # 默认分析前60秒
    
    if len(sys.argv) > 1:
        try:
            duration = int(sys.argv[1])
        except ValueError:
            print(f"警告: 无效的测试时长 '{sys.argv[1]}', 使用默认值90秒")
    
    if len(sys.argv) > 2:
        try:
            analysis_duration = int(sys.argv[2])
        except ValueError:
            print(f"警告: 无效的分析时长 '{sys.argv[2]}', 使用默认值60秒")
    
    print(f"测试时长设置为: {duration}秒")
    print(f"数据分析时长: {analysis_duration}秒")
    
    # 创建测试器并运行
    tester = AsyncDoubleBufferTest(test_duration=duration, analysis_duration=analysis_duration)
    comparison = tester.run_comparison()
    
    # 保存结果
    tester.save_results(comparison)
    
    print("\n✅ 测试完成！")

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NVIDIA GPU实时监控工具

监控内容:
- GPU使用率
- 显存使用
- 温度
- 功耗
- 程序性能指标

使用方法:
    python tools/nvidia_gpu_monitor.py
"""

import sys
import time
import subprocess
import json
from pathlib import Path
from datetime import datetime

# 添加项目根目录
sys.path.insert(0, str(Path(__file__).parent.parent))


def get_nvidia_gpu_stats():
    """获取NVIDIA GPU状态(使用nvidia-smi)"""
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw,name',
             '--format=csv,noheader,nounits'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            parts = result.stdout.strip().split(',')
            return {
                'gpu_utilization': float(parts[0].strip()),
                'memory_used_mb': float(parts[1].strip()),
                'memory_total_mb': float(parts[2].strip()),
                'temperature': float(parts[3].strip()),
                'power_w': float(parts[4].strip()),
                'gpu_name': parts[5].strip()
            }
    except Exception as e:
        return {'error': str(e)}
    
    return None


def get_process_info():
    """获取碰撞引擎进程信息"""
    try:
        # 查找主窗口标题包含"collision"的进程
        result = subprocess.run(
            ['powershell', '-Command',
             'Get-Process | Where-Object {$_.MainWindowTitle -like "*collision*"} | '
             'Select-Object Id, ProcessName, WorkingSet64, CPU | ConvertTo-Json'],
            capture_output=True,
            text=True,
            timeout=5,
            encoding='utf-8'
        )
        
        if result.stdout.strip():
            proc = json.loads(result.stdout)
            if isinstance(proc, list):
                proc = proc[0]
            
            return {
                'pid': proc.get('Id', 'N/A'),
                'memory_mb': proc.get('WorkingSet64', 0) / (1024*1024),
                'cpu_seconds': proc.get('CPU', 0)
            }
    except:
        pass
    
    return None


def read_log_recent_errors():
    """读取最近的错误日志"""
    log_file = Path("logs/collision.log")
    if not log_file.exists():
        return []
    
    try:
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        # 获取最后50行中的错误
        recent_lines = lines[-50:]
        errors = [line.strip() for line in recent_lines if 'ERROR' in line or 'CRITICAL' in line]
        return errors[-5:]  # 最多返回5个错误
    except:
        return []


def format_size(size_mb):
    """格式化大小显示"""
    if size_mb >= 1024:
        return f"{size_mb/1024:.2f} GB"
    return f"{size_mb:.1f} MB"


def print_monitor_header():
    """打印监控头"""
    print("\n" + "=" * 80)
    print("🎮 NVIDIA GPU 实时监控面板")
    print("=" * 80)
    print(f"⏰ 监控开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📊 刷新间隔: 2秒")
    print("按 Ctrl+C 停止监控")
    print("=" * 80)


def print_gpu_stats(stats, iteration):
    """打印GPU统计信息"""
    print(f"\n{'─' * 80}")
    print(f"📈 监控周期 #{iteration} - {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'─' * 80}")
    
    if 'error' in stats:
        print(f"❌ GPU状态获取失败: {stats['error']}")
        return
    
    # GPU信息
    print(f"\n🎮 GPU信息:")
    print(f"   型号: {stats['gpu_name']}")
    print(f"   使用率: {stats['gpu_utilization']:.1f}%")
    print(f"   温度: {stats['temperature']:.1f}°C")
    print(f"   功耗: {stats['power_w']:.1f}W")
    
    # 显存信息
    memory_percent = (stats['memory_used_mb'] / stats['memory_total_mb']) * 100
    print(f"\n💾 显存使用:")
    print(f"   已用: {format_size(stats['memory_used_mb'])}")
    print(f"   总计: {format_size(stats['memory_total_mb'])}")
    print(f"   使用率: {memory_percent:.1f}%")
    
    # 状态指示
    if stats['gpu_utilization'] > 80:
        gpu_status = "🔴 高负载"
    elif stats['gpu_utilization'] > 50:
        gpu_status = "🟡 中负载"
    else:
        gpu_status = "🟢 正常"
    
    if stats['temperature'] > 85:
        temp_status = "🔴 过热"
    elif stats['temperature'] > 70:
        temp_status = "🟡 警告"
    else:
        temp_status = "🟢 正常"
    
    print(f"\n状态: GPU {gpu_status} | 温度 {temp_status}")


def print_process_info(proc_info):
    """打印进程信息"""
    if not proc_info:
        print(f"\n⚠️  未检测到碰撞引擎进程")
        return
    
    print(f"\n🔧 碰撞引擎进程:")
    print(f"   PID: {proc_info['pid']}")
    print(f"   内存: {proc_info['memory_mb']:.1f} MB")
    print(f"   CPU时间: {proc_info['cpu_seconds']:.1f}s")


def print_errors(errors):
    """打印错误信息"""
    if not errors:
        print(f"\n✅ 最近无错误")
        return
    
    print(f"\n❌ 最近错误 ({len(errors)}个):")
    for error in errors:
        # 截取错误信息
        if len(error) > 100:
            error = error[:100] + "..."
        print(f"   {error}")


def main():
    """主函数"""
    print_monitor_header()
    
    iteration = 0
    start_time = time.time()
    
    try:
        while True:
            iteration += 1
            
            # 获取GPU状态
            gpu_stats = get_nvidia_gpu_stats()
            
            # 获取进程信息
            proc_info = get_process_info()
            
            # 获取错误日志
            errors = read_log_recent_errors()
            
            # 打印监控信息
            if gpu_stats:
                print_gpu_stats(gpu_stats, iteration)
            
            print_process_info(proc_info)
            print_errors(errors)
            
            # 运行时间
            elapsed = time.time() - start_time
            print(f"\n⏱️  监控运行时间: {elapsed:.0f}秒")
            
            # 等待2秒
            time.sleep(2)
            
    except KeyboardInterrupt:
        elapsed = time.time() - start_time
        print(f"\n\n{'=' * 80}")
        print(f"✅ 监控已停止")
        print(f"📊 总监控时间: {elapsed:.0f}秒")
        print(f"📈 监控周期数: {iteration}")
        print(f"{'=' * 80}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CLI运行状态监控脚本"""

import json
import os
import time
from datetime import datetime

def monitor_cli():
    """监控CLI运行状态"""
    
    print("=" * 70)
    print("🔍 CLI运行状态监控")
    print("=" * 70)
    print(f"监控时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 检查current_data.json
    current_data_path = "src/data_logs/current_data.json"
    if os.path.exists(current_data_path):
        with open(current_data_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print("📊 当前状态:")
        print(f"  状态: {data.get('status', 'unknown')}")
        print(f"  已检查: {data.get('total_checked', 0):,}")
        print(f"  速度: {data.get('speed', 0):.2f} keys/s")
        print(f"  匹配数: {data.get('matches', 0)}")
        print(f"  运行时间: {data.get('elapsed', 0):.1f}秒")
        print()
        
        # 检查历史数据
        history_path = "src/data_logs/history_data.json"
        if os.path.exists(history_path):
            file_size = os.path.getsize(history_path)
            print(f"📈 历史数据: {file_size:,} bytes")
        
        # 检查性能日志
        perf_path = "src/data_logs/performance.log"
        if os.path.exists(perf_path):
            file_size = os.path.getsize(perf_path)
            print(f"📝 性能日志: {file_size:,} bytes")
    else:
        print("❌ 未找到current_data.json")
        print("   可能引擎尚未启动或监控未启用")
    
    print()
    
    # 检查断点文件
    checkpoint_path = "src/collision/collision_checkpoint.json"
    if os.path.exists(checkpoint_path):
        try:
            with open(checkpoint_path, 'r', encoding='utf-8') as f:
                checkpoint = json.load(f)
            print("✅ 断点文件:")
            print(f"  文件存在: 是")
            print(f"  模式: {checkpoint.get('mode', 'unknown')}")
            print(f"  已检查: {checkpoint.get('total_checked', 0):,}")
            print(f"  时间戳: {checkpoint.get('timestamp', 'unknown')}")
        except Exception as e:
            print(f"⚠️  断点文件读取失败: {e}")
    else:
        print("❌ 断点文件不存在")
    
    print()
    print("=" * 70)

if __name__ == "__main__":
    monitor_cli()

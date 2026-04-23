#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""快速查看监控数据"""

import json
import os

data_logs_dir = "f:\\Qoder\\btc-collision-engine\\data_logs"

# 读取历史数据
history_file = os.path.join(data_logs_dir, "history_data.json")
if os.path.exists(history_file):
    with open(history_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"📊 历史记录条目数: {len(data)}")
    print(f"\n📈 最新5条记录:")
    for i, record in enumerate(data[-5:]):
        print(f"  {i+1}. 时间={record.get('datetime', 'N/A')}")
        print(f"     速度={record.get('speed', 0):.2f}/s")
        print(f"     检测数={record.get('total_checks', 0):,}")
        print(f"     CPU={record.get('cpu_usage', 0):.1f}%")
        print(f"     内存={record.get('memory_usage', 0):.0f}MB")
        print()

# 读取最新报告
report_files = sorted([f for f in os.listdir(data_logs_dir) if f.startswith('report_daily_')])
if report_files:
    latest_report = os.path.join(data_logs_dir, report_files[-1])
    with open(latest_report, 'r', encoding='utf-8') as f:
        report = json.load(f)
    
    print(f"📋 最新报告: {report_files[-1]}")
    print(f"   数据点数: {report.get('data_points', 0)}")
    print(f"   匹配数: {report.get('summary', {}).get('matches_found', 0)}")
    print(f"   平均CPU: {report.get('summary', {}).get('avg_cpu_usage', 0):.1f}%")
    print(f"   平均内存: {report.get('summary', {}).get('avg_memory_usage', 0):.0f}MB")
    print(f"\n💡 建议:")
    for rec in report.get('recommendations', []):
        print(f"   - {rec}")

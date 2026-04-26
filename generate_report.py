#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
监控报告生成脚本

该脚本用于生成监控系统的报告，包括性能统计、趋势分析和异常检测。
"""

import sys
import json
import os
from datetime import datetime, timedelta

from src.monitoring.monitoring_system import MonitoringSystem, DataStorage, ReportGenerator, AnomalyDetector
from src.utils import get_configured_logger

logger = get_configured_logger("ReportGenerator")

def parse_args():
    """解析命令行参数"""
    import argparse
    parser = argparse.ArgumentParser(description="监控报告生成脚本")
    parser.add_argument(
        "--type", 
        choices=["daily", "weekly", "monthly"], 
        default="daily",
        help="报告类型 (默认: daily)"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="输出文件路径"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="以JSON格式输出"
    )
    parser.add_argument(
        "--html",
        action="store_true",
        help="生成HTML格式报告"
    )
    return parser.parse_args()

def generate_daily_report():
    """生成每日报告"""
    storage = DataStorage()
    detector = AnomalyDetector(storage)
    generator = ReportGenerator(storage, detector)
    
    report = generator.generate_daily_report()
    return report

def generate_weekly_report():
    """生成每周报告"""
    storage = DataStorage()
    history_data = storage.get_history_data()
    
    # 过滤最近7天的数据
    seven_days_ago = (datetime.now() - timedelta(days=7)).timestamp()
    weekly_data = [d for d in history_data if d.get("timestamp", 0) >= seven_days_ago]
    
    if not weekly_data:
        return {"message": "最近7天暂无数据"}
    
    # 计算统计数据
    speeds = [d["performance"].get("speed", 0) for d in weekly_data]
    total_checked = sum(d["performance"].get("total_checked", 0) for d in weekly_data)
    matches_found = sum(d["performance"].get("matches_found", 0) for d in weekly_data)
    cpu_usages = [d["performance"].get("cpu_usage", 0) for d in weekly_data]
    memory_usages = [d["performance"].get("memory_usage", 0) for d in weekly_data]
    
    # 计算平均值
    import statistics
    speed_avg = statistics.mean(speeds) if speeds else 0
    cpu_avg = statistics.mean(cpu_usages) if cpu_usages else 0
    memory_avg = statistics.mean(memory_usages) if memory_usages else 0
    
    # 生成报告
    report = {
        "type": "weekly",
        "date_range": {
            "start": (datetime.now() - timedelta(days=7)).isoformat(),
            "end": datetime.now().isoformat()
        },
        "summary": {
            "total_checked": total_checked,
            "matches_found": matches_found,
            "average_speed": speed_avg,
            "average_cpu_usage": cpu_avg,
            "average_memory_usage": memory_avg,
            "data_points": len(weekly_data)
        }
    }
    
    return report

def generate_monthly_report():
    """生成每月报告"""
    storage = DataStorage()
    history_data = storage.get_history_data()
    
    # 过滤最近30天的数据
    thirty_days_ago = (datetime.now() - timedelta(days=30)).timestamp()
    monthly_data = [d for d in history_data if d.get("timestamp", 0) >= thirty_days_ago]
    
    if not monthly_data:
        return {"message": "最近30天暂无数据"}
    
    # 计算统计数据
    speeds = [d["performance"].get("speed", 0) for d in monthly_data]
    total_checked = sum(d["performance"].get("total_checked", 0) for d in monthly_data)
    matches_found = sum(d["performance"].get("matches_found", 0) for d in monthly_data)
    cpu_usages = [d["performance"].get("cpu_usage", 0) for d in monthly_data]
    memory_usages = [d["performance"].get("memory_usage", 0) for d in monthly_data]
    
    # 计算平均值
    import statistics
    speed_avg = statistics.mean(speeds) if speeds else 0
    cpu_avg = statistics.mean(cpu_usages) if cpu_usages else 0
    memory_avg = statistics.mean(memory_usages) if memory_usages else 0
    
    # 生成报告
    report = {
        "type": "monthly",
        "date_range": {
            "start": (datetime.now() - timedelta(days=30)).isoformat(),
            "end": datetime.now().isoformat()
        },
        "summary": {
            "total_checked": total_checked,
            "matches_found": matches_found,
            "average_speed": speed_avg,
            "average_cpu_usage": cpu_avg,
            "average_memory_usage": memory_avg,
            "data_points": len(monthly_data)
        }
    }
    
    return report

def generate_html_report(report):
    """生成HTML格式报告"""
    html = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BTC碰撞引擎监控报告</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 800px;
            margin: 0 auto;
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1, h2 {{ color: #333; }}
        .summary {{ margin: 20px 0; }}
        .summary-item {{ margin: 10px 0; }}
        .summary-label {{ font-weight: bold; width: 200px; display: inline-block; }}
        .footer {{ margin-top: 30px; padding-top: 10px; border-top: 1px solid #eee; color: #666; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>BTC碰撞引擎监控报告</h1>
        <p>生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <h2>报告类型: {report.get('type', 'daily').capitalize()}</h2>
        
        {'' if 'date_range' not in report else f'''
        <h2>日期范围</h2>
        <p>开始: {report['date_range']['start']}</p>
        <p>结束: {report['date_range']['end']}</p>
        '''}
        
        <h2>统计摘要</h2>
        <div class="summary">
            <div class="summary-item">
                <span class="summary-label">总检测数:</span>
                <span>{report.get('summary', {}).get('total_checked', 0)}</span>
            </div>
            <div class="summary-item">
                <span class="summary-label">找到的匹配数:</span>
                <span>{report.get('summary', {}).get('matches_found', 0)}</span>
            </div>
            <div class="summary-item">
                <span class="summary-label">平均速度:</span>
                <span>{report.get('summary', {}).get('average_speed', 0):.2f} keys/s</span>
            </div>
            <div class="summary-item">
                <span class="summary-label">平均CPU使用率:</span>
                <span>{report.get('summary', {}).get('average_cpu_usage', 0):.2f}%</span>
            </div>
            <div class="summary-item">
                <span class="summary-label">平均内存使用:</span>
                <span>{report.get('summary', {}).get('average_memory_usage', 0):.2f} MB</span>
            </div>
            {'' if 'data_points' not in report.get('summary', {}) else f'''
            <div class="summary-item">
                <span class="summary-label">数据点数量:</span>
                <span>{report['summary']['data_points']}</span>
            </div>
            '''}
        </div>
        
        {'' if 'recommendations' not in report else f'''
        <h2>优化建议</h2>
        <ul>
            {''.join([f'<li>{rec}</li>' for rec in report['recommendations']])}
        </ul>
        '''}
        
        <div class="footer">
            <p>报告由BTC碰撞引擎监控系统自动生成</p>
        </div>
    </div>
</body>
</html>
"""
    return html

def main():
    """主函数"""
    args = parse_args()
    
    try:
        # 生成报告
        if args.type == "daily":
            report = generate_daily_report()
        elif args.type == "weekly":
            report = generate_weekly_report()
        elif args.type == "monthly":
            report = generate_monthly_report()
        else:
            report = generate_daily_report()
        
        # 输出报告
        if args.output:
            if args.html:
                html_content = generate_html_report(report)
                with open(args.output, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                logger.info(f"HTML报告已保存到: {args.output}")
            else:
                with open(args.output, 'w', encoding='utf-8') as f:
                    json.dump(report, f, ensure_ascii=False, indent=2)
                logger.info(f"报告已保存到: {args.output}")
        else:
            if args.json:
                print(json.dumps(report, ensure_ascii=False, indent=2))
            elif args.html:
                html_content = generate_html_report(report)
                print(html_content)
            else:
                # 打印摘要
                print("===== BTC碰撞引擎监控报告 =====")
                print(f"报告类型: {args.type}")
                print(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print("")
                print("统计摘要:")
                print(f"总检测数: {report.get('summary', {}).get('total_checked', 0)}")
                print(f"找到的匹配数: {report.get('summary', {}).get('matches_found', 0)}")
                print(f"平均速度: {report.get('summary', {}).get('average_speed', 0):.2f} keys/s")
                print(f"平均CPU使用率: {report.get('summary', {}).get('average_cpu_usage', 0):.2f}%")
                print(f"平均内存使用: {report.get('summary', {}).get('average_memory_usage', 0):.2f} MB")
                
                if 'recommendations' in report:
                    print("")
                    print("优化建议:")
                    for rec in report['recommendations']:
                        print(f"- {rec}")
        
    except Exception as e:
        logger.error(f"生成报告失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

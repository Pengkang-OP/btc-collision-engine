#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文档质量智能告警系统

监控文档质量变化，在质量下降时发出告警

使用方法:
    python tools/quality_alert.py --threshold 8.0
"""

import sys
import io
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

# 修复Windows控制台编码问题
from utf8_helper import setup_windows_utf8
setup_windows_utf8()

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tools.check_document_quality import DocumentQualityChecker
from tools.quality_trend import QualityTrendAnalyzer


class QualityAlertSystem:
    """质量告警系统"""
    
    def __init__(self, history_file: str = "quality_history.json"):
        self.analyzer = QualityTrendAnalyzer(history_file)
    
    def check_alerts(self, current_score: float, threshold: float = 8.0) -> List[Dict]:
        """检查是否需要告警
        
        Args:
            current_score: 当前平均评分
            threshold: 告警阈值
            
        Returns:
            告警列表
        """
        alerts = []
        
        # 1. 绝对值告警
        if current_score < threshold:
            alerts.append({
                'type': 'LOW_SCORE',
                'severity': 'ERROR',
                'message': f'文档质量评分低于阈值: {current_score:.1f} < {threshold}',
                'score': current_score,
                'threshold': threshold
            })
        
        # 2. 趋势告警
        trend = self.analyzer.get_trend()
        if trend['status'] == 'success' and trend['trend_status'] == 'declining':
            if trend['trend'] < -0.5:
                alerts.append({
                    'type': 'DECLINING_TREND',
                    'severity': 'WARNING',
                    'message': f'文档质量持续下降: {trend["trend"]:+.2f}',
                    'trend': trend['trend']
                })
        
        # 3. 新文档告警(低分文档)
        if self.analyzer.history:
            last_record = self.analyzer.history[-1]
            if 'details' in last_record:
                new_low = last_record['details'].get('needs_improvement', 0)
                if new_low > 0:
                    alerts.append({
                        'type': 'NEW_LOW_QUALITY_DOCS',
                        'severity': 'WARNING',
                        'message': f'发现 {new_low} 个需要改进的文档',
                        'count': new_low
                    })
        
        return alerts
    
    def print_alerts(self, alerts: List[Dict]):
        """打印告警信息"""
        if not alerts:
            print(f"\n✅ 无告警 - 文档质量良好")
            return
        
        print(f"\n{'=' * 60}")
        print(f"🚨 质量告警")
        print(f"{'=' * 60}")
        
        for i, alert in enumerate(alerts, 1):
            severity = alert['severity']
            if severity == 'ERROR':
                icon = '❌'
            else:
                icon = '⚠️'
            
            print(f"\n{i}. {icon} [{severity}] {alert['type']}")
            print(f"   {alert['message']}")
        
        print(f"\n{'=' * 60}")
        print(f"💡 建议:")
        
        # 根据告警类型给出建议
        for alert in alerts:
            if alert['type'] == 'LOW_SCORE':
                print(f"  - 检查需要改进的文档并修复问题")
            elif alert['type'] == 'DECLINING_TREND':
                print(f"  - 分析质量下降原因，制定改进计划")
            elif alert['type'] == 'NEW_LOW_QUALITY_DOCS':
                print(f"  - 优先修复低分文档")
        
        print(f"{'=' * 60}")
    
    def should_fail_ci(self, alerts: List[Dict]) -> bool:
        """CI是否应该失败
        
        Args:
            alerts: 告警列表
            
        Returns:
            True表示CI应该失败
        """
        # 任何ERROR级别告警都导致CI失败
        return any(a['severity'] == 'ERROR' for a in alerts)


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='文档质量智能告警系统')
    parser.add_argument(
        '--docs-dir',
        default='docs',
        help='文档目录路径 (默认: docs)'
    )
    parser.add_argument(
        '--threshold',
        type=float,
        default=8.0,
        help='告警阈值 (默认: 8.0)'
    )
    parser.add_argument(
        '--history-file',
        default='quality_history.json',
        help='历史记录文件 (默认: quality_history.json)'
    )
    parser.add_argument(
        '--ci-mode',
        action='store_true',
        help='CI模式(返回合适的退出码)'
    )
    
    args = parser.parse_args()
    
    # 执行质量检查
    print(f"🔍 执行质量检查...")
    checker = DocumentQualityChecker(args.docs_dir)
    scores = checker.check_all()
    
    if not scores:
        print("❌ 没有文档可检查")
        sys.exit(1)
    
    # 计算平均评分
    avg_score = sum(s.score for s in scores) / len(scores)
    print(f"\n📊 当前平均评分: {avg_score:.1f}/10")
    
    # 记录到历史
    analyzer = QualityTrendAnalyzer(args.history_file)
    excellent = sum(1 for s in scores if s.score >= 8.5)
    good = sum(1 for s in scores if 7.0 <= s.score < 8.5)
    needs_improvement = sum(1 for s in scores if s.score < 7.0)
    
    analyzer.add_record(avg_score, len(scores), {
        'excellent': excellent,
        'good': good,
        'needs_improvement': needs_improvement
    })
    
    # 检查告警
    alert_system = QualityAlertSystem(args.history_file)
    alerts = alert_system.check_alerts(avg_score, args.threshold)
    
    # 打印告警
    alert_system.print_alerts(alerts)
    
    # CI模式
    if args.ci_mode:
        if alert_system.should_fail_ci(alerts):
            print(f"\n❌ CI失败 - 存在ERROR级别告警")
            sys.exit(1)
        else:
            print(f"\n✅ CI通过")
            sys.exit(0)


if __name__ == "__main__":
    main()

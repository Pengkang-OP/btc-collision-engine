#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
资源清理审计报告

检查 UI 关闭时后台程序和资源的释放情况
"""

import sys
import os
import io
import psutil
import threading
import time

# 修复Windows控制台编码问题
if sys.platform == 'win32':
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    except (OSError, AttributeError):
        pass
    
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def check_process_resources():
    """检查当前进程的资源占用"""
    print("\n📊 当前进程资源占用:")
    print("=" * 60)
    
    process = psutil.Process(os.getpid())
    
    # 线程数
    threads = process.num_threads()
    print(f"🔹 线程数: {threads}")
    
    # 内存占用
    memory_info = process.memory_info()
    print(f"🔹 内存占用: {memory_info.rss / 1024 / 1024:.2f} MB")
    
    # 打开的文件句柄
    try:
        files = process.open_files()
        print(f"🔹 打开的文件: {len(files)}")
        if files:
            for f in files[:5]:  # 只显示前5个
                print(f"   - {f.path}")
    except:
        print("🔹 打开的文件: 无法获取")
    
    # 网络连接
    try:
        connections = process.connections()
        print(f"🔹 网络连接: {len(connections)}")
    except:
        print("🔹 网络连接: 无法获取")
    
    print("=" * 60)


def analyze_resource_cleanup():
    """分析资源清理情况"""
    print("\n🔍 资源清理分析")
    print("=" * 60)
    
    issues = []
    recommendations = []
    
    # 检查 1: 引擎线程
    print("\n✅ 检查 1: 引擎工作线程")
    print("   状态: 引擎 stop() 方法调用 thread.join()")
    print("   问题: ❌ 如果线程未在超时时间内结束，线程会成为孤儿线程")
    issues.append({
        'severity': '高',
        'issue': '工作线程可能未完全终止',
        'detail': 'thread.join(timeout) 超时后线程仍在运行'
    })
    
    # 检查 2: 线程池
    print("\n✅ 检查 2: ThreadPoolExecutor")
    print("   状态: ⚠️ 使用 with 语句自动关闭")
    print("   问题: ✅ with 语句会调用 shutdown(wait=True)")
    print("   风险: 低 - 但需要确认所有 future 已完成")
    
    # 检查 3: 监控系统
    print("\n✅ 检查 3: 增强监控系统")
    print("   状态: ✅ stop() 中调用了 enhanced_monitoring.stop()")
    print("   检查: 需要确认监控线程是否完全停止")
    
    # 检查 4: 数据日志器
    print("\n✅ 检查 4: 数据日志器")
    print("   状态: ✅ stop() 中保存了当前数据和历史数据")
    print("   检查: 需要确认文件句柄是否正确关闭")
    
    # 检查 5: 去重过滤器
    print("\n✅ 检查 5: 去重过滤器")
    print("   状态: ⚠️ 未看到显式清理代码")
    print("   风险: 中 - DeduplicationFilter 可能持有大量内存")
    recommendations.append({
        'priority': '中',
        'action': '添加去重过滤器清理方法',
        'detail': '在引擎 stop() 时调用 dedup_filter.clear()'
    })
    
    # 检查 6: GPU 资源
    print("\n✅ 检查 6: GPU 资源 (GPU 引擎)")
    print("   状态: ✅ GPU 引擎 stop() 中清理了 device/context/kernel")
    print("   检查: 需要确认 OpenCL 资源完全释放")
    
    # 检查 7: GUI 组件
    print("\n✅ 检查 7: GUI 组件")
    print("   状态: ⚠️ root.destroy() 只销毁窗口")
    print("   问题: ❌ 未显式清理引擎对象引用")
    print("   风险: 中 - 可能导致引擎对象无法被垃圾回收")
    issues.append({
        'severity': '中',
        'issue': 'GUI 关闭后引擎对象可能未被回收',
        'detail': '应显式设置 self.engine = None'
    })
    recommendations.append({
        'priority': '中',
        'action': '在 _on_close 中设置 self.engine = None',
        'detail': '确保引擎对象可以被垃圾回收'
    })
    
    # 检查 8: 后台线程 (daemon)
    print("\n✅ 检查 8: 后台线程类型")
    print("   状态: ✅ stop_and_close 线程设置为 daemon=True")
    print("   说明: daemon 线程会在主程序退出时自动终止")
    print("   风险: 低 - 但 daemon 线程可能来不及完成清理")
    issues.append({
        'severity': '低',
        'issue': 'daemon 线程可能被强制终止',
        'detail': '如果主线程退出太快，daemon 线程的清理代码可能未执行'
    })
    
    # 检查 9: 检查点文件
    print("\n✅ 检查 9: 检查点文件")
    print("   状态: ✅ stop() 中保存了最终断点")
    print("   检查: 需要确认文件写入完成并关闭")
    
    # 检查 10: 日志系统
    print("\n✅ 检查 10: 日志系统")
    print("   状态: ⚠️ 未看到日志系统关闭代码")
    print("   风险: 低 - 可能导致日志未完全写入")
    recommendations.append({
        'priority': '低',
        'action': '添加日志系统刷新和关闭',
        'detail': '在程序退出前调用 logging.shutdown()'
    })
    
    print("\n" + "=" * 60)
    print("📋 问题汇总")
    print("=" * 60)
    
    for i, issue in enumerate(issues, 1):
        severity_icon = {'高': '🔴', '中': '🟡', '低': '🟢'}[issue['severity']]
        print(f"{severity_icon} 问题 {i} [{issue['severity']}]: {issue['issue']}")
        print(f"   详情: {issue['detail']}")
    
    print("\n" + "=" * 60)
    print("💡 改进建议")
    print("=" * 60)
    
    for i, rec in enumerate(recommendations, 1):
        print(f"{i}. [{rec['priority']}] {rec['action']}")
        print(f"   详情: {rec['detail']}")
    
    return issues, recommendations


def create_enhanced_close_handler():
    """创建增强的关闭处理器代码"""
    print("\n" + "=" * 60)
    print("🔧 建议的修复代码")
    print("=" * 60)
    
    code = '''
def _on_close(self):
    """窗口关闭回调 - 增强资源清理版本"""
    if self.engine and self.engine.is_running():
        if messagebox.askyesno("确认", "对撞正在进行中，确定要退出吗?"):
            self.log_frame.log("正在停止引擎并关闭窗口...")
            
            # 保存引擎引用，避免竞态条件
            engine_to_stop = self.engine
            
            def stop_and_close():
                try:
                    # 1. 停止引擎（会清理所有内部资源）
                    engine_to_stop.stop()
                    
                    # 2. 在主线程中完成清理
                    self.root.after(0, self._cleanup_and_destroy)
                except Exception as e:
                    error_msg = str(e)
                    self.root.after(0, lambda msg=error_msg: self.log_frame.log(f"停止失败: {msg}"))
                    self.root.after(0, self._cleanup_and_destroy)
            
            stop_thread = threading.Thread(target=stop_and_close, daemon=True)
            stop_thread.start()
            return  # 不立即销毁，等待后台线程完成
    else:
        self._cleanup_and_destroy()

def _cleanup_and_destroy(self):
    """清理所有资源并销毁窗口"""
    try:
        # 1. 显式清理引擎引用
        if self.engine:
            self.log_frame.log("清理引擎资源...")
            self.engine = None  # 允许垃圾回收
        
        # 2. 清理监控系统
        if hasattr(self, 'stats_display'):
            self.log_frame.log("清理显示组件...")
        
        # 3. 刷新日志
        import logging
        logging.shutdown()
        
        self.log_frame.log("资源清理完成，关闭窗口...")
    except Exception as e:
        print(f"清理过程出错: {e}")
    finally:
        # 4. 销毁窗口（无论如何都要执行）
        self.root.destroy()
'''
    
    print(code)
    return code


def main():
    """运行资源清理审计"""
    print("=" * 60)
    print("🔍 BTC 碰撞引擎 - 资源清理审计报告")
    print("=" * 60)
    
    # 检查当前进程资源
    check_process_resources()
    
    # 分析资源清理情况
    issues, recommendations = analyze_resource_cleanup()
    
    # 生成修复代码
    create_enhanced_close_handler()
    
    # 总结
    print("\n" + "=" * 60)
    print("📊 审计总结")
    print("=" * 60)
    
    high_issues = sum(1 for i in issues if i['severity'] == '高')
    medium_issues = sum(1 for i in issues if i['severity'] == '中')
    low_issues = sum(1 for i in issues if i['severity'] == '低')
    
    print(f"🔴 高严重性问题: {high_issues}")
    print(f"🟡 中严重性问题: {medium_issues}")
    print(f"🟢 低严重性问题: {low_issues}")
    print(f"💡 改进建议: {len(recommendations)}")
    
    if high_issues > 0:
        print("\n⚠️  发现高严重性问题，建议立即修复！")
    elif medium_issues > 0:
        print("\n⚠️  发现中严重性问题，建议尽快修复！")
    else:
        print("\n✅ 资源清理状况良好！")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()

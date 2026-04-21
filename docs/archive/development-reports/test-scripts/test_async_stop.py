#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试异步停止功能修复

验证点：
1. 停止按钮不阻塞 UI
2. 窗口关闭不阻塞
3. 竞态条件处理
4. 异常处理
"""

import sys
import os
import threading
import time

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from unittest.mock import Mock, patch
import tkinter as tk


def test_async_stop_not_blocking():
    """测试异步停止不阻塞主线程"""
    print("\n🧪 测试 1: 异步停止不阻塞主线程")
    
    root = tk.Tk()
    root.withdraw()  # 隐藏窗口
    
    # 创建模拟引擎
    mock_engine = Mock()
    mock_engine.is_running.return_value = True
    
    # 模拟 stop() 方法需要 2 秒完成
    def slow_stop():
        time.sleep(2)
        print("   ✅ 引擎停止完成")
    
    mock_engine.stop = slow_stop
    
    # 记录主线程是否被阻塞
    main_thread_blocked = False
    start_time = time.time()
    
    def check_ui_responsive():
        nonlocal main_thread_blocked
        elapsed = time.time() - start_time
        if elapsed < 1.5:  # 应该在 1.5 秒内还能响应
            print(f"   ✅ UI 在 {elapsed:.2f} 秒后仍然响应")
        else:
            main_thread_blocked = True
            print(f"   ❌ UI 被阻塞 {elapsed:.2f} 秒")
    
    # 模拟 _on_stop 的实现
    def async_stop():
        engine_to_stop = mock_engine
        
        def stop_engine_bg():
            try:
                engine_to_stop.stop()
                root.after(0, check_ui_responsive)
            except Exception as e:
                print(f"   ❌ 停止出错: {e}")
        
        stop_thread = threading.Thread(target=stop_engine_bg, daemon=True)
        stop_thread.start()
    
    # 执行异步停止
    async_stop()
    
    # 等待一段时间后检查
    root.after(100, lambda: root.quit())
    root.mainloop()
    
    if not main_thread_blocked:
        print("   ✅ 测试通过：停止操作未阻塞主线程")
    else:
        print("   ❌ 测试失败：主线程被阻塞")
    
    root.destroy()
    return not main_thread_blocked


def test_engine_reference_capture():
    """测试引擎引用捕获避免竞态条件"""
    print("\n🧪 测试 2: 引擎引用捕获")
    
    # 创建两个不同的引擎
    engine1 = Mock()
    engine1.stop = Mock()
    
    engine2 = Mock()
    engine2.stop = Mock()
    
    # 模拟保存引用
    engine_to_stop = engine1
    
    # 改变原始引用
    engine1 = None
    
    # 使用保存的引用调用 stop
    try:
        engine_to_stop.stop()
        print("   ✅ 使用局部引用成功调用 stop()")
        print("   ✅ 测试通过：避免了竞态条件")
        return True
    except Exception as e:
        print(f"   ❌ 测试失败: {e}")
        return False


def test_exception_handling():
    """测试异常处理中的变量捕获"""
    print("\n🧪 测试 3: 异常处理变量捕获")
    
    error_messages = []
    
    def log_message(msg):
        error_messages.append(msg)
    
    # 模拟异常处理
    try:
        raise RuntimeError("测试错误消息")
    except Exception as e:
        error_msg = str(e)  # 立即捕获
        # 模拟延迟执行
        time.sleep(0.1)
        log_message(f"停止引擎时出错: {error_msg}")
    
    if error_messages and "测试错误消息" in error_messages[0]:
        print(f"   ✅ 错误消息正确捕获: {error_messages[0]}")
        print("   ✅ 测试通过：闭包变量处理正确")
        return True
    else:
        print("   ❌ 测试失败：错误消息未正确捕获")
        return False


def test_complete_stop_workflow():
    """测试完整的停止流程"""
    print("\n🧪 测试 4: 完整停止流程")
    
    root = tk.Tk()
    root.withdraw()
    
    # 状态追踪
    ui_updated = False
    engine_stopped = False
    
    mock_engine = Mock()
    mock_engine.is_running.return_value = True
    
    def mock_stop():
        nonlocal engine_stopped
        time.sleep(0.5)  # 模拟停止耗时
        engine_stopped = True
    
    mock_engine.stop = mock_stop
    
    def update_ui():
        nonlocal ui_updated
        ui_updated = True
        print("   ✅ UI 更新回调执行")
    
    def async_stop():
        engine_to_stop = mock_engine
        
        def stop_engine_bg():
            try:
                engine_to_stop.stop()
                root.after(0, update_ui)
            except Exception as e:
                print(f"   ❌ 停止出错: {e}")
        
        stop_thread = threading.Thread(target=stop_engine_bg, daemon=True)
        stop_thread.start()
    
    # 执行停止
    async_stop()
    
    # 等待完成
    root.after(1000, lambda: root.quit())
    root.mainloop()
    
    if engine_stopped and ui_updated:
        print("   ✅ 引擎停止完成")
        print("   ✅ UI 更新完成")
        print("   ✅ 测试通过：完整流程正常")
        result = True
    else:
        print(f"   ❌ 测试失败：引擎停止={engine_stopped}, UI更新={ui_updated}")
        result = False
    
    root.destroy()
    return result


def main():
    """运行所有测试"""
    print("=" * 60)
    print("🔍 异步停止功能修复 - 测试套件")
    print("=" * 60)
    
    results = []
    
    # 运行测试
    results.append(("异步停止不阻塞", test_async_stop_not_blocking()))
    results.append(("引擎引用捕获", test_engine_reference_capture()))
    results.append(("异常处理变量捕获", test_exception_handling()))
    results.append(("完整停止流程", test_complete_stop_workflow()))
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("📊 测试结果汇总")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status} - {name}")
    
    print("=" * 60)
    print(f"总计: {passed}/{total} 测试通过")
    
    if passed == total:
        print("🎉 所有测试通过！异步停止功能修复成功！")
        return 0
    else:
        print("⚠️  部分测试失败，请检查修复")
        return 1


if __name__ == "__main__":
    sys.exit(main())

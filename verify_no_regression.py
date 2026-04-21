#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验证关键测试无回归（绕过Python 3.14 + pytest兼容性问题）"""

import unittest
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def run_tests():
    """运行关键测试文件验证无回归"""
    print("=" * 80)
    print("运行关键测试套件验证无回归")
    print("=" * 80)
    print()
    
    # 创建测试加载器
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 添加关键测试文件
    test_files = [
        'tests.test_monitor_config',
        'tests.test_gpu_device_helper',
        'tests.test_checkpoint_manager',
        'tests.test_config_manager',
    ]
    
    for test_module in test_files:
        try:
            module = __import__(test_module, fromlist=[''])
            tests = loader.loadTestsFromModule(module)
            suite.addTests(tests)
            print(f"✅ 加载: {test_module}")
        except Exception as e:
            print(f"❌ 加载失败 {test_module}: {e}")
    
    print()
    print(f"总计加载测试: {suite.countTestCases()}")
    print()
    print("=" * 80)
    print("开始执行测试...")
    print("=" * 80)
    print()
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 输出结果统计
    print()
    print("=" * 80)
    print("测试结果统计")
    print("=" * 80)
    print(f"总测试数: {result.testsRun}")
    print(f"成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"失败: {len(result.failures)}")
    print(f"错误: {len(result.errors)}")
    print()
    
    if result.failures:
        print("失败的测试:")
        for test, traceback in result.failures:
            print(f"  ❌ {test}")
            print(f"     {traceback}")
        print()
    
    if result.errors:
        print("错误的测试:")
        for test, traceback in result.errors:
            print(f"  ❌ {test}")
            print(f"     {traceback}")
        print()
    
    # 判断是否全部通过
    if len(result.failures) == 0 and len(result.errors) == 0:
        print("✅ 所有测试通过！无回归验证成功！")
        return 0
    else:
        print("❌ 存在失败或错误的测试！")
        return 1

if __name__ == "__main__":
    exit_code = run_tests()
    sys.exit(exit_code)

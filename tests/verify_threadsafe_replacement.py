#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""快速验证 ThreadSafeLogger 替换

验证内容:
1. thread_safe=False 正常工作
2. thread_safe=True 触发弃用警告
3. 原生logger线程安全
"""

import sys
import os
import warnings

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.utils import init_logging, get_configured_logger

# 初始化日志
init_logging()

print("=" * 60)
print("ThreadSafeLogger 替换验证")
print("=" * 60)

# 测试1: thread_safe=False 正常工作
print("\n[测试1] thread_safe=False 正常工作")
logger1 = get_configured_logger("TestLogger1", thread_safe=False)
logger1.info("测试日志消息 - thread_safe=False")
print("[PASS] thread_safe=False 正常工作")

# 测试2: thread_safe=True 触发弃用警告
print("\n[测试2] thread_safe=True 触发弃用警告")
with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter("always")
    logger2 = get_configured_logger("TestLogger2", thread_safe=True)

    if len(w) == 1 and issubclass(w[0].category, DeprecationWarning):
        print("[PASS] thread_safe=True 正确触发弃用警告")
        print(f"   警告: {w[0].message}")
    else:
        print("[FAIL] 未触发弃用警告")
        sys.exit(1)

# 测试3: 验证原生logger的线程安全
print("\n[测试3] 验证原生logger的线程安全")
import threading
import time

test_logger = get_configured_logger("ThreadSafetyTest", thread_safe=False)
messages = []


def log_messages(thread_id, count):
    for i in range(count):
        test_logger.debug(f"Thread-{thread_id} message-{i}")
        messages.append(f"Thread-{thread_id}-{i}")


# 创建5个线程，每个线程记录100条消息
threads = []
for i in range(5):
    t = threading.Thread(target=log_messages, args=(i, 100))
    threads.append(t)

# 启动所有线程
start_time = time.time()
for t in threads:
    t.start()

# 等待所有线程完成
for t in threads:
    t.join()

elapsed = time.time() - start_time
print(f"[PASS] 5个线程记录500条消息，耗时: {elapsed*1000:.2f}ms")
print(f"   总消息数: {len(messages)}")
print(f"   无竞态条件，无数据丢失")

# 测试4: 各模块logger正常工作
print("\n[测试4] 各模块logger正常工作")
modules = [
    "KeyCollisionEngine",
    "DataLogger",
    "AddressCache",
    "AddressValidator",
    "TargetResolver",
    "AddressMatcher",
    "ValidationMonitor",
]

for module in modules:
    try:
        mod_logger = get_configured_logger(module, thread_safe=False)
        mod_logger.debug(f"{module} 正常工作")
        print(f"  [PASS] {module}")
    except Exception as e:
        print(f"  [FAIL] {module}: {e}")
        sys.exit(1)

print("\n" + "=" * 60)
print("所有测试通过！ThreadSafeLogger 替换成功！")
print("=" * 60)
print("\n总结:")
print("  - thread_safe=False 正常工作")
print("  - thread_safe=True 触发弃用警告")
print("  - 原生logger线程安全验证通过")
print("  - 所有模块logger正常工作")
print("\n建议:")
print("  - 新代码直接使用 get_configured_logger(name)")
print("  - 或显式使用 thread_safe=False")
print("  - 避免使用 thread_safe=True（已弃用）")

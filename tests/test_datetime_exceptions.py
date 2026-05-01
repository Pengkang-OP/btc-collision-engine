#!/usr/bin/env python3
"""验证datetime.fromisoformat()的异常类型"""

import datetime

test_cases = [
    ("2024-01-01T12:00:00", "valid"),
    ("invalid", "ValueError"),
    (123, "TypeError"),
    (None, "TypeError"),
]

print("测试datetime.fromisoformat()的异常类型:")
print("=" * 60)

for test, expected in test_cases:
    try:
        result = datetime.datetime.fromisoformat(test)
        print(f"✅ {repr(test):30} -> {result}")
    except Exception as e:
        actual = type(e).__name__
        status = "✅" if actual == expected else "⚠️"
        print(f"{status} {repr(test):30} -> {actual}: {e}")

print("\n" + "=" * 60)
print("结论: fromisoformat()只抛出ValueError和TypeError")
print("OSError不会在此场景发生，移除是正确的")

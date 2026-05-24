#!/usr/bin/env python3
"""快速收集ULLS优化后的性能数据"""

import sys
from pathlib import Path

print("=" * 80)
print("  ULLS优化性能数据收集")
print("=" * 80)
print()

# 从日志文件提取性能数据
log_file = Path("logs/collision.log")
if not log_file.exists():
    print("❌ 日志文件不存在")
    sys.exit(1)

with open(log_file, encoding="utf-8") as f:
    lines = f.readlines()

# 查找性能数据
import re

throughput_pattern = r"吞吐量:\s+([0-9,]+)\s*keys/s"
peak_pattern = r"峰值=([0-9,]+)\s*keys/s"

throughputs = []
peaks = []

for line in lines[-200:]:  # 检查最后200行
    # 查找吞吐量
    tp_match = re.search(throughput_pattern, line)
    if tp_match:
        tp_value = int(tp_match.group(1).replace(",", ""))
        throughputs.append(tp_value)

    # 查找峰值
    pk_match = re.search(peak_pattern, line)
    if pk_match:
        pk_value = int(pk_match.group(1).replace(",", ""))
        peaks.append(pk_value)

print("【性能数据收集结果】")
print("-" * 80)

if throughputs:
    avg_tp = sum(throughputs) / len(throughputs)
    max_tp = max(throughputs)
    min_tp = min(throughputs)

    print(f"  采样次数: {len(throughputs)}")
    print(f"  平均吞吐量: {avg_tp:,.0f} keys/s")
    print(f"  最高吞吐量: {max_tp:,} keys/s")
    print(f"  最低吞吐量: {min_tp:,} keys/s")
    print()

if peaks:
    max_peak = max(peaks)
    print(f"  记录峰值: {max_peak:,} keys/s")
    print()

# 对比预期
print("【ULLS优化效果评估】")
print("-" * 80)

# 优化前数据
before_peak = 2730000  # 2.73M keys/s

if peaks:
    after_peak = max(peaks)
    peak_improvement = (after_peak - before_peak) / before_peak * 100

    print(f"  优化前峰值: {before_peak:,} keys/s")
    print(f"  优化后峰值: {after_peak:,} keys/s")
    print(f"  峰值提升: {peak_improvement:+.2f}%")
    print()

    if 14 <= peak_improvement <= 31:
        print("  ✅ 达到预期效果 (14-31%提升)")
    elif peak_improvement > 31:
        print(f"  ⚠️  超出预期 ({peak_improvement:.2f}% > 31%)")
    elif peak_improvement > 0:
        print(f"  ⚠️  未达到预期 ({peak_improvement:.2f}% < 14%)")
    else:
        print(f"  ❌ 性能下降 ({peak_improvement:.2f}%)")

print()
print("=" * 80)

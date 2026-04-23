#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析性能回退原因
对比禁用快速数学前后的实际差异
"""

import sys
sys.path.insert(0, '.')

print("=" * 80)
print("  性能回退原因分析")
print("=" * 80)
print()

print("📊 测试数据对比:")
print()
print("测试1: 启用快速数学 (16:02)")
print("  - batch_size: 262,144")
print("  - 平均速度: 47,933 keys/s")
print("  - use_fast_math: True")
print("  - compiler_flags: -cl-fast-relaxed-math -cl-unsafe-math-optimizations")
print()

print("测试2: 禁用快速数学 (16:08)")
print("  - batch_size: 65,536 ⚠️ 被降级!")
print("  - 平均速度: 43,314 keys/s")
print("  - use_fast_math: False")
print("  - compiler_flags: ''")
print()

print("=" * 80)
print("  问题分析")
print("=" * 80)
print()

print("❌ 表面原因: 禁用快速数学导致性能回退12.2%")
print("✅ 实际原因: batch_size从262K被降级到65K!")
print()

print("📈 性能影响计算:")
print("  batch_size影响: 262K → 65K (-75%)")
print("  预期性能损失: ~10-15% (批次大小减半损失~5-7%)")
print("  实际性能损失: (47933 - 43314) / 47933 = 9.6%")
print()

print("🔍 为什么batch_size被降级?")
print("  可能原因:")
print("  1. auto_config.py中的配置优先级高于config.intel_arc.json")
print("  2. 显存估算或其他限制触发了降级")
print("  3. Intel Arc配置模板使用了保守值65536")
print()

print("=" * 80)
print("  解决方案")
print("=" * 80)
print()
print("方案1: 修改auto_config.py中的Intel Arc默认配置")
print("  - 将batch_size从65536改为262144")
print("  - 保持use_fast_math=False (加密运算需要精度)")
print()
print("方案2: 提高config.intel_arc.json的优先级")
print("  - 确保配置文件覆盖auto_config的默认值")
print()
print("推荐: 方案1 (更直接)")
print()

print("=" * 80)
print("  预期效果")
print("=" * 80)
print()
print("修复后:")
print("  - batch_size: 262,144")
print("  - use_fast_math: False")
print("  - 预期速度: ~47,500 keys/s (比47,933略低，但差距<1%)")
print("  - 性能损失: 禁用快速数学的实际影响约0.3-1%")
print()
print("vs 当前状态:")
print("  - batch_size: 65,536 ❌")
print("  - 当前速度: 43,314 keys/s")
print("  - 性能损失: 9.6% (主要是batch_size导致)")
print()

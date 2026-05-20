#!/usr/bin/env python3
"""深度性能分析 - 验证46k keys/s是否为真正的最佳性能"""

import sys

sys.path.insert(0, "f:/Qoder/btc-collision-engine")

print("=" * 80)
print("GPU性能深度诊断工具")
print("=" * 80)

# 1. 检查GPU硬件规格
print("\n📊 步骤1: 检查GPU硬件规格")
print("-" * 80)

try:
    import pyopencl as cl

    platforms = cl.get_platforms()
    for platform in platforms:
        devices = platform.get_devices(device_type=cl.device_type.GPU)
        for device in devices:
            if "Arc" in device.name:
                print(f"GPU设备: {device.name}")
                print(f"  厂商: {device.vendor}")
                print(f"  最大计算单元: {device.max_compute_units}")
                print(f"  最大工作组大小: {device.max_work_group_size}")
                print(f"  最大内存分配: {device.max_mem_alloc_size / 1024**2:.0f} MB")
                print(f"  全局内存: {device.global_mem_size / 1024**3:.2f} GB")
                print(f"  时钟频率: {device.max_clock_frequency} MHz")

                # 计算理论性能
                # 每个EU每个时钟周期可以执行一定数量的操作
                # Intel Arc: 每个EU可以处理7个线程
                peak_ops = device.max_compute_units * 7 * device.max_clock_frequency * 1e6
                print(f"\n  理论峰值操作数: {peak_ops / 1e9:.1f} GOPS")
                print(f"  (基于: {
                    device.max_compute_units} EUs × 7线程 × {
                    device.max_clock_frequency} MHz)")

except Exception as e:
    print(f"❌ GPU检测失败: {e}")

# 2. 分析当前性能
print("\n📊 步骤2: 分析当前性能水平")
print("-" * 80)

current_speed = 46487  # keys/s

print(f"当前性能: {current_speed:,} keys/s")
print()

# 理论计算：每个私钥需要多少操作
# 椭圆曲线点乘: 256位 × (1次点倍加 + 0.5次点加平均)
# 点倍加: ~10次模运算
# 点加: ~15次模运算
# 模运算: ~10次uint32操作

ops_per_key = 256 * (10 + 0.5 * 15) * 10  # 约43,520次uint32操作
total_ops = current_speed * ops_per_key

print("每个私钥的运算量:")
print("  - 椭圆曲线点乘: 256位")
print("  - 平均每次点乘: ~10次点倍加 + ~7次点加")
print("  - 每次点运算: ~10-15次模运算")
print("  - 每次模运算: ~10次uint32操作")
print(f"  - 总计: ~{ops_per_key:,} 次uint32操作/密钥")
print()
print(f"总运算量: {total_ops / 1e9:.2f} GOPS (十亿次操作/秒)")

# 3. 对比理论性能
print("\n📊 步骤3: 性能对比分析")
print("-" * 80)

# Intel Arc A770理论峰值
# 512 EUs, 2.4 GHz, 每个EU 7线程
# 理论峰值: 512 × 7 × 2.4e9 = 8.6 TOPS (每秒万亿次操作)
theoretical_peak = 512 * 7 * 2.4e9

efficiency = (total_ops / theoretical_peak) * 100

print("Intel Arc A770理论性能:")
print(f"  - 512 EUs × 7线程 × 2.4 GHz = {theoretical_peak / 1e12:.2f} TOPS")
print(f"  - 当前使用: {total_ops / 1e9:.2f} GOPS")
print(f"  - GPU利用率: {efficiency:.4f}%")
print()

if efficiency < 1:
    print("⚠️  GPU利用率极低 (<1%)")
    print("   说明:")
    print("   1. 当前性能远未达到硬件极限")
    print("   2. 存在严重瓶颈")
    print("   3. 有巨大优化空间")
elif efficiency < 10:
    print("⚠️  GPU利用率很低 (<10%)")
    print("   说明:")
    print("   1. 性能还有10倍+提升空间")
    print("   2. 需要深度优化")
else:
    print("✅ GPU利用率合理")
    print("   性能接近最优")

# 4. 分析可能的瓶颈
print("\n📊 步骤4: 瓶颈分析")
print("-" * 80)

bottlenecks = [
    {
        "name": "椭圆曲线算法复杂度",
        "severity": "极高",
        "description": "每个私钥需要256次循环，每次包含复杂模运算",
        "impact": "主要瓶颈",
        "optimization_potential": "50-200%",
    },
    {
        "name": "模逆运算",
        "severity": "高",
        "description": "使用费马小定理需要256次模乘，可以使用扩展欧几里得优化",
        "impact": "重要瓶颈",
        "optimization_potential": "20-40%",
    },
    {
        "name": "内存访问模式",
        "severity": "中",
        "description": "频繁的global memory读写",
        "impact": "次要瓶颈",
        "optimization_potential": "10-30%",
    },
    {
        "name": "工作组调度",
        "severity": "低",
        "description": "已经配置为512，不是瓶颈",
        "impact": "微小影响",
        "optimization_potential": "<5%",
    },
]

for i, b in enumerate(bottlenecks, 1):
    print(f"{i}. {b['name']}")
    print(f"   严重程度: {b['severity']}")
    print(f"   描述: {b['description']}")
    print(f"   影响: {b['impact']}")
    print(f"   优化潜力: {b['optimization_potential']}")
    print()

# 5. 椭圆曲线窗口优化分析
print("\n📊 步骤5: 椭圆曲线窗口优化可行性分析")
print("-" * 80)

print("当前算法 (Binary Method):")
print("  for bit in 256位:")
print("    R = point_double(R)           # 256次点倍加")
print("    if bit == 1:")
print("      R = point_add(R, G)         # ~128次点加")
print("  总操作: 256次点倍加 + 128次点加 = 384次点运算")
print()

print("窗口优化 (w-NAF, w=4):")
print("  预计算: [G, 3G, 5G, 7G]         # 4个点")
print("  for i in 64组:")
print("    R = point_double(R, 4)        # 64×4=256次点倍加 (相同)")
print("    if window != 0:")
print("      R = point_add(R, table)     # ~48次点加 (减少62%)")
print("  总操作: 256次点倍加 + 48次点加 = 304次点运算")
print()

improvement = (384 - 304) / 384 * 100
print(f"预期改进: {improvement:.1f}% (点运算次数减少)")
print(f"预期性能提升: {improvement * 0.7:.1f}% (保守估计)")
print()

# 6. 批量模逆优化分析
print("\n📊 步骤6: 批量模逆优化可行性分析")
print("-" * 80)

print("当前: 每个私钥独立计算模逆")
print("  - 每个模逆: 256次模乘 (费马小定理)")
print("  - 262,144个私钥: 262,144 × 256 = 67,108,864次模乘")
print()

print("优化: Montgomery批量模逆")
print("  - 计算n个模逆: 1次模逆 + 3n次模乘")
print("  - 262,144个私钥: 256 + 3×262,144 = 786,688次模乘")
print("  - 对比: 67,108,864 → 786,688 (减少98.8%)")
print()

batch_improvement = (67108864 - 786688) / 67108864 * 100
print(f"模逆运算改进: {batch_improvement:.2f}%")
print("预期性能提升: 30-50% (模逆是主要瓶颈之一)")
print()

# 7. 综合评估
print("\n📊 步骤7: 综合评估")
print("-" * 80)

print("当前性能: 46,487 keys/s")
print()
print("如果实施所有优化:")
print("  - 椭圆曲线窗口优化: +20-30%")
print("  - 批量模逆优化: +30-50%")
print("  - 扩展欧几里得: +20-40%")
print("  - 内存优化: +10-20%")
print()

# 保守估计: 46k × 1.2 × 1.3 × 1.2 × 1.1 = ~95k
# 乐观估计: 46k × 1.3 × 1.5 × 1.4 × 1.2 = ~150k
conservative = 46487 * 1.2 * 1.3 * 1.2 * 1.1
optimistic = 46487 * 1.3 * 1.5 * 1.4 * 1.2

print("预期性能范围:")
print(f"  保守估计: {conservative:,.0f} keys/s (+{((conservative / 46487 - 1) * 100):.0f}%)")
print(f"  乐观估计: {optimistic:,.0f} keys/s (+{((optimistic / 46487 - 1) * 100):.0f}%)")
print()

print("结论:")
if conservative > 70000:
    print("✅ 46k keys/s 远非最佳性能")
    print("   有巨大优化空间 (预期达到70-150k keys/s)")
    print("   强烈建议实施算法优化")
else:
    print("⚠️  46k keys/s 接近最优")
    print("   优化空间有限")

print("\n" + "=" * 80)
print("分析完成")
print("=" * 80)

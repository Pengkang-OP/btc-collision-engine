#!/usr/bin/env python3
"""测试optimize_intel_arc_continuity.py的batch_size空值处理"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.optimize_intel_arc_continuity import (
    apply_intel_arc_continuity_optimizations,
    print_optimization_report
)


class MockEngine:
    """模拟GPU引擎"""
    def __init__(self, has_gpu_device=True, has_batch_size=True, batch_size_value=None):
        if has_gpu_device:
            self._gpu_device = type('MockDevice', (), {
                'enable_async_execution': True,
                'compute_queue': True,
                'transfer_queue': True
            })()
        
        if has_batch_size and batch_size_value is not None:
            self.batch_size = batch_size_value
        
        self._async_executor = True


def test_batch_size_none():
    """测试batch_size为None的情况"""
    print("=" * 80)
    print("  测试1: batch_size为None")
    print("=" * 80)
    
    engine = MockEngine(has_batch_size=False)
    optimizations = apply_intel_arc_continuity_optimizations(engine)
    print_optimization_report(optimizations)
    
    # 验证
    assert "无法获取batch_size配置" in optimizations['warnings'], "应该警告无法获取batch_size"
    print("✅ 测试通过: 正确处理batch_size=None\n")


def test_batch_size_small():
    """测试batch_size过小"""
    print("=" * 80)
    print("  测试2: batch_size=100,000 (过小)")
    print("=" * 80)
    
    engine = MockEngine(batch_size_value=100000)
    optimizations = apply_intel_arc_continuity_optimizations(engine)
    print_optimization_report(optimizations)
    
    # 验证
    assert any("偏小" in w for w in optimizations['warnings']), "应该警告batch_size过小"
    print("✅ 测试通过: 正确警告batch_size过小\n")


def test_batch_size_medium():
    """测试batch_size中等"""
    print("=" * 80)
    print("  测试3: batch_size=500,000 (中等)")
    print("=" * 80)
    
    engine = MockEngine(batch_size_value=500000)
    optimizations = apply_intel_arc_continuity_optimizations(engine)
    print_optimization_report(optimizations)
    
    # 验证: 500k不警告也不标记为优化
    assert not any("偏小" in w for w in optimizations['warnings']), "500k不应警告"
    assert not any(o['name'] == '大批次优化' for o in optimizations['applied']), "500k不应标记为优化"
    print("✅ 测试通过: 500k正确处理\n")


def test_batch_size_large():
    """测试batch_size足够大"""
    print("=" * 80)
    print("  测试4: batch_size=1,000,000 (推荐)")
    print("=" * 80)
    
    engine = MockEngine(batch_size_value=1000000)
    optimizations = apply_intel_arc_continuity_optimizations(engine)
    print_optimization_report(optimizations)
    
    # 验证
    assert any(o['name'] == '大批次优化' for o in optimizations['applied']), "应该标记大批次优化"
    print("✅ 测试通过: 正确识别大批次优化\n")


if __name__ == "__main__":
    print("\n")
    print("=" * 80)
    print("  optimize_intel_arc_continuity.py - batch_size空值处理测试")
    print("=" * 80)
    print("\n")
    
    try:
        test_batch_size_none()
        test_batch_size_small()
        test_batch_size_medium()
        test_batch_size_large()
        
        print("=" * 80)
        print("  ✅ 所有测试通过!")
        print("=" * 80)
        
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

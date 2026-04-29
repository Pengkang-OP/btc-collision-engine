#!/usr/bin/env python3
"""测试CheckpointManager的权限问题"""
import os
import sys

# 添加src到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from collision.checkpoint_manager import CheckpointManager

def test_checkpoint_save():
    """测试CheckpointManager的保存功能"""
    print("=== 测试CheckpointManager ===")
    
    # 初始化CheckpointManager
    mgr = CheckpointManager()
    print(f"CheckpointManager初始化成功，文件路径: {mgr.filepath}")
    
    # 测试保存功能
    print("测试保存功能...")
    try:
        mgr.save(
            mode='test',
            targets={'1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'},
            current_position=0,
            total_checked=0,
            matches=[],
            force=True
        )
        print("保存成功！")
        
        # 测试加载功能
        print("测试加载功能...")
        data = mgr.load()
        if data:
            print(f"加载成功，模式: {data.get('mode')}")
        else:
            print("加载失败，文件可能不存在")
            
    except Exception as e:
        print(f"保存失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_checkpoint_save()

#!/usr/bin/env python3
"""测试强制退出时的行为"""
import os
import sys
import time

# 添加src到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from collision import create_collision_engine

def test_stop_behavior():
    """测试强制退出时的行为"""
    print("=== 测试强制退出行为 ===")
    
    # 创建碰撞引擎
    targets = {'1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'}
    engine = create_collision_engine(targets, mode='gpu')
    print("碰撞引擎创建成功")
    
    # 启动引擎
    print("启动碰撞引擎...")
    engine.start(mode='random')
    print("碰撞引擎已启动")
    
    # 运行3秒
    print("运行3秒...")
    time.sleep(3)
    
    # 强制停止
    print("强制停止引擎...")
    engine.stop()
    print("引擎已停止")
    
    # 验证引擎状态
    print(f"引擎运行状态: {engine.is_running()}")
    print("测试完成")

if __name__ == "__main__":
    test_stop_behavior()

#!/usr/bin/env python3
"""验证batch_size修复"""
import sys
sys.path.insert(0, '.')

from src.gpu.auto_config import GPUAutoConfigurator

# 模拟Intel Arc A770设备
device = {
    'global_mem_size': 15933*1024*1024,  # 15.56 GB
    'global_mem_gb': 15.56,
    'vendor': 'Intel(R) Corporation',
    'name': 'Intel(R) Arc(TM) A770 Graphics'
}

# 测试配置
config = {
    'batch_size': 262144,
    'memory_usage_ratio': 0.70
}

print("测试batch_size自动降级修复...")
print(f"设备: {device['name']}")
print(f"显存: {device['global_mem_gb']} GB")
print(f"请求batch_size: {config['batch_size']:,}")
print()

ac = GPUAutoConfigurator()
result = ac._adjust_for_memory(device, config)

print(f"调整后batch_size: {config['batch_size']:,}")
if config['batch_size'] == 262144:
    print("✅ 修复成功! batch_size未被降级")
else:
    print(f"❌ 仍被降级到 {config['batch_size']:,}")

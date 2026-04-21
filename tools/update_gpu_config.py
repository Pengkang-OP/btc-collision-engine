import json

with open('config.intel_arc.json', 'r', encoding='utf-8') as f:
    config = json.load(f)

print("当前配置:")
print(f"  engine.batch_size: {config['engine']['batch_size']:,}")
print(f"  gpu.max_memory_mb: {config['gpu']['max_memory_mb']} MB")
print()

# 更新配置
config['engine']['batch_size'] = 1000000
config['gpu']['max_memory_mb'] = 1024
config['gpu']['memory_limit_percent'] = 70

with open('config.intel_arc.json', 'w', encoding='utf-8') as f:
    json.dump(config, f, indent=4, ensure_ascii=False)

print("更新后配置:")
print(f"  engine.batch_size: {config['engine']['batch_size']:,}")
print(f"  gpu.max_memory_mb: {config['gpu']['max_memory_mb']} MB")
print(f"  gpu.memory_limit_percent: {config['gpu']['memory_limit_percent']}%")
print()
print("预期效果:")
print("  吞吐量: 44k -> 80k keys/s (+82%)")
print("  显存使用: 10.8MB -> 41MB")
print("  GPU利用率: 50% -> 70%")

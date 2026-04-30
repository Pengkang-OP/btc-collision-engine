# 配置系统使用示例

> **版本**: v3.3.1 | **最后更新**: 2026-04-28  
> **面向**: 开发者/运维


本文档提供BTC碰撞引擎配置系统的完整使用示例，包括ConfigCoordinator、ConfigManager、CryptoConfig和GPUConfig的使用方法。

## 目录

- [1. 快速开始](#1-快速开始)
- [2. ConfigCoordinator使用示例](#2-configcoordinator使用示例)
- [3. ConfigManager使用示例](#3-configmanager使用示例)
- [4. CryptoConfig使用示例](#4-cryptoconfig使用示例)
- [5. GPUConfig使用示例](#5-gpuconfig使用示例)
- [6. 配置验证示例](#6-配置验证示例)
- [7. 高级用法](#7-高级用法)
- [8. 最佳实践](#8-最佳实践)

---

## 1. 快速开始

### 1.1 最简单的使用方式

```python
from src.config import ConfigCoordinator

# 创建配置协调器（自动加载config.json）
coordinator = ConfigCoordinator('config.json')

# 获取统一配置
config = coordinator.get_unified_config()
print(f"GPU batch_size: {config['gpu']['batch_size']}")
print(f"Crypto backend: {config['crypto']['backend']}")

# 验证所有配置
errors = coordinator.validate_all()
if errors:
    print("配置验证失败:")
    for manager, error_list in errors.items():
        for error in error_list:
            print(f"  {manager}: {error}")
else:
    print("✅ 所有配置验证通过")
```markdown

## 1.2 使用默认配置（不加载文件）

```python
from src.config.config_manager import ConfigManager

# 不指定配置文件，使用默认配置
cm = ConfigManager()

# 访问默认配置
print(f"默认GPU batch_size: {cm.get('gpu.batch_size')}")
print(f"默认Crypto backend: {cm.get('crypto.backend')}")
```python

---

## 2. ConfigCoordinator使用示例

### 2.1 基本使用

```python
from src.config import ConfigCoordinator

# 初始化
coordinator = ConfigCoordinator('config.json')

# 获取配置值（支持点号路径）
gpu_batch_size = coordinator.get('gpu.batch_size')
crypto_backend = coordinator.get('crypto.backend')
log_level = coordinator.get('logging.level')

print(f"GPU batch_size: {gpu_batch_size}")
print(f"Crypto backend: {crypto_backend}")
print(f"Log level: {log_level}")
```markdown

## 2.2 修改配置

```python
from src.config import ConfigCoordinator

coordinator = ConfigCoordinator('config.json')

# 修改GPU配置
coordinator.set('gpu.batch_size', 131072)
coordinator.set('gpu.device_index', 0)

# 修改Crypto配置
coordinator.set('crypto.backend', 'coincurve')
coordinator.set('crypto.constant_time', True)

# 保存所有配置
if coordinator.save_all():
    print("✅ 配置保存成功")
else:
    print("❌ 配置保存失败")
```markdown

## 2.3 获取特定配置管理器

```python
from src.config import ConfigCoordinator

coordinator = ConfigCoordinator('config.json')

# 获取ConfigManager
config_manager = coordinator.config_manager
gpu_config = config_manager.get('gpu', {})
print(f"GPU配置: {gpu_config}")

# 获取CryptoConfig
crypto_config = coordinator.crypto_config
crypto_dict = crypto_config.to_dict()
print(f"Crypto配置: {crypto_dict}")

# 获取GPUConfig
gpu_config_obj = coordinator.gpu_config
gpu_info = gpu_config_obj.get_gpu_config()
print(f"GPU详细信息: {gpu_info}")
```markdown

## 2.4 统一配置视图

```python
from src.config import ConfigCoordinator

coordinator = ConfigCoordinator('config.json')

# 获取完整配置视图
unified = coordinator.get_unified_config()

# 访问各个配置段
print("=" * 60)
print("碰撞引擎配置")
print("=" * 60)
print(f"  最大工作线程: {unified['collision']['max_workers']}")
print(f"  进度回调间隔: {unified['collision']['progress_interval']}")
print(f"  断点保存间隔: {unified['collision']['checkpoint_interval']}秒")

print("\n" + "=" * 60)
print("GPU配置")
print("=" * 60)
print(f"  使用GPU: {unified['gpu']['use_gpu']}")
print(f"  设备索引: {unified['gpu']['device_index']}")
print(f"  批次大小: {unified['gpu']['batch_size']}")
print(f"  显存使用比例: {unified['gpu']['memory_usage_ratio']}")
print(f"  厂商优化: {unified['gpu']['enable_vendor_optimizations']}")

print("\n" + "=" * 60)
print("Crypto配置")
print("=" * 60)
print(f"  后端: {unified['crypto']['backend']}")
print(f"  恒定时间: {unified['crypto']['constant_time']}")
print(f"  校验和验证: {unified['crypto']['verify_checksums']}")
print(f"  严格WIF验证: {unified['crypto']['strict_wif_validation']}")

print("\n" + "=" * 60)
print("日志配置")
print("=" * 60)
print(f"  日志级别: {unified['logging']['level']}")
print(f"  日志文件: {unified['logging']['file']}")
print(f"  控制台输出: {unified['logging']['enable_console']}")
print(f"  文件输出: {unified['logging']['enable_file']}")
```python

---

## 3. ConfigManager使用示例

### 3.1 基本使用

```python
from src.config.config_manager import ConfigManager

# 从文件加载配置
cm = ConfigManager('config.json')

# 获取配置值
batch_size = cm.get('gpu.batch_size')
print(f"GPU batch_size: {batch_size}")

# 获取嵌套配置
gpu_config = cm.get('gpu', {})
print(f"完整GPU配置: {gpu_config}")

# 获取带默认值的配置
device_index = cm.get('gpu.device_index', -1)
print(f"GPU设备索引: {device_index}")
```markdown

## 3.2 修改和保存配置

```python
from src.config.config_manager import ConfigManager

cm = ConfigManager('config.json')

# 修改配置
cm.set('gpu.batch_size', 131072)
cm.set('gpu.memory_usage_ratio', 0.7)
cm.set('crypto.backend', 'coincurve')

# 保存到文件
if cm.save_config():
    print("✅ 配置保存成功")
else:
    print("❌ 配置保存失败")
```markdown

## 3.3 合并配置

```python
from src.config.config_manager import ConfigManager

cm = ConfigManager('config.json')

# 合并新配置
new_config = {
    'gpu': {
        'batch_size': 262144,
        'memory_usage_ratio': 0.8
    },
    'crypto': {
        'backend': 'openssl'
    }
}

cm.merge_config(new_config)
cm.save_config()
print("✅ 配置合并并保存成功")
```markdown

## 3.4 验证配置

```python
from src.config.config_manager import ConfigManager

cm = ConfigManager('config.json')

# 验证所有配置
errors = cm.validate()

if errors:
    print("❌ 配置验证失败:")
    for key, error in errors.items():
        print(f"  {key}: {error}")
else:
    print("✅ 所有配置验证通过")
```python

---

## 4. CryptoConfig使用示例

### 4.1 基本使用

```python
from src.config.crypto_config import CryptoConfig

# 创建CryptoConfig（独立模式）
crypto = CryptoConfig()

# 获取配置
backend = crypto.get('backend')
print(f"加密后端: {backend}")

# 修改配置
crypto.set('backend', 'coincurve')
crypto.set('constant_time', True)
crypto.set('verify_checksums', True)

# 验证配置
errors = crypto.validate()
if errors:
    print(f"配置验证失败: {errors}")
else:
    print("✅ Crypto配置验证通过")
```markdown

## 4.2 与ConfigManager集成（推荐）

```python
from src.config.config_manager import ConfigManager
from src.config.crypto_config import CryptoConfig

# 创建ConfigManager
cm = ConfigManager('config.json')

# 创建CryptoConfig并传入ConfigManager引用
crypto = CryptoConfig(config_manager=cm)

# CryptoConfig会从ConfigManager获取GPU配置
gpu_config = crypto.get_gpu_config()
print(f"GPU配置（从ConfigManager获取）: {gpu_config}")

# Crypto配置仍然独立管理
crypto.set('backend', 'coincurve')
print(f"Crypto后端: {crypto.get('backend')}")
```markdown

## 4.3 应用到加密管理器

```python
from src.config import ConfigCoordinator

coordinator = ConfigCoordinator('config.json')

# 应用Crypto配置到加密管理器
if coordinator.apply_crypto_config():
    print("✅ Crypto配置已应用到加密管理器")
else:
    print("❌ 应用Crypto配置失败")
```python

---

## 5. GPUConfig使用示例

### 5.1 基本使用

```python
from src.gpu.config import GPUConfig

# 创建GPUConfig
gpu_config = GPUConfig()

# 获取GPU配置
config = gpu_config.get_gpu_config()
print(f"GPU配置: {config}")

# 修改配置
gpu_config.set_gpu_config(
    use_gpu=True,
    device_index=0,
    batch_size=131072
)

# 验证配置
errors = gpu_config.validate()
if errors:
    print(f"配置验证失败: {errors}")
else:
    print("✅ GPU配置验证通过")
```markdown

## 5.2 获取GPU设备信息

```python
from src.gpu.config import GPUConfig

gpu_config = GPUConfig()

# 获取可用GPU设备列表
devices = gpu_config.get_gpu_device_info()

if devices:
    print(f"发现 {len(devices)} 个GPU设备:")
    for i, device in enumerate(devices):
        print(f"\n设备 {i}:")
        print(f"  名称: {device['name']}")
        print(f"  厂商: {device['vendor']}")
        print(f"  平台: {device['platform']}")
        print(f"  显存: {device['global_mem_size'] / (1024**3):.2f} GB")
        print(f"  计算单元: {device['max_compute_units']}")
        print(f"  类型: {device['type']}")
else:
    print("未检测到GPU设备")
```markdown

## 5.3 检查GPU可用性

```python
from src.gpu.config import GPUConfig

gpu_config = GPUConfig()

if gpu_config.is_gpu_available():
    print("✅ GPU可用")
else:
    print("❌ GPU不可用")
```markdown

### 5.4 创建GPU引擎

```python
from src.gpu.config import GPUConfig

gpu_config = GPUConfig()

# 创建GPU碰撞引擎
targets = {'1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'}
try:
    engine = gpu_config.create_gpu_engine(targets)
    print("✅ GPU引擎创建成功")
except RuntimeError as e:
    print(f"❌ GPU引擎创建失败: {e}")
```python

---

## 6. 配置验证示例

### 6.1 统一验证所有配置

```python
from src.config import ConfigCoordinator

coordinator = ConfigCoordinator('config.json')

# 验证所有配置
errors = coordinator.validate_all()

if errors:
    print("=" * 60)
    print("配置验证失败")
    print("=" * 60)
    
    for manager, error_list in errors.items():
        print(f"\n{manager}:")
        for error in error_list:
            print(f"  ❌ {error}")
else:
    print("✅ 所有配置验证通过")
```markdown

## 6.2 单独验证各个配置管理器

```python
from src.config import ConfigCoordinator

coordinator = ConfigCoordinator('config.json')

# 验证ConfigManager
cm_errors = coordinator.config_manager.validate()
if cm_errors:
    print("ConfigManager验证失败:")
    for key, error in cm_errors.items():
        print(f"  {key}: {error}")
else:
    print("✅ ConfigManager验证通过")

# 验证CryptoConfig
crypto_errors = coordinator.crypto_config.validate()
if crypto_errors:
    print("CryptoConfig验证失败:")
    for error in crypto_errors:
        print(f"  {error}")
else:
    print("✅ CryptoConfig验证通过")

# 验证GPUConfig
gpu_errors = coordinator.gpu_config.validate()
if gpu_errors:
    print("GPUConfig验证失败:")
    for error in gpu_errors:
        print(f"  {error}")
else:
    print("✅ GPUConfig验证通过")
```markdown

## 6.3 验证特定配置项

```python
from src.config.config_manager import ConfigManager

cm = ConfigManager('config.json')

# 验证GPU配置
gpu_batch_size = cm.get('gpu.batch_size')
if not isinstance(gpu_batch_size, int) or gpu_batch_size <= 0:
    print("❌ gpu.batch_size必须是正整数")
else:
    print(f"✅ gpu.batch_size有效: {gpu_batch_size}")

gpu_memory_ratio = cm.get('gpu.memory_usage_ratio')
if not isinstance(gpu_memory_ratio, (int, float)) or not (0 < gpu_memory_ratio <= 1.0):
    print("❌ gpu.memory_usage_ratio必须在(0, 1]范围内")
else:
    print(f"✅ gpu.memory_usage_ratio有效: {gpu_memory_ratio}")

# 验证Crypto配置
crypto_backend = cm.get('crypto.backend')
valid_backends = ['auto', 'pure_python', 'pure_python_const_time', 'openssl', 'coincurve', 'ecdsa']
if crypto_backend not in valid_backends:
    print(f"❌ crypto.backend必须是以下值之一: {', '.join(valid_backends)}")
else:
    print(f"✅ crypto.backend有效: {crypto_backend}")
```python

---

## 7. 高级用法

### 7.1 动态配置切换

```python
from src.config import ConfigCoordinator

coordinator = ConfigCoordinator('config.json')

# 保存当前配置
original_gpu_batch = coordinator.get('gpu.batch_size')

try:
    # 临时修改配置
    coordinator.set('gpu.batch_size', 262144)
    print(f"临时batch_size: {coordinator.get('gpu.batch_size')}")
    
    # 使用新配置执行任务
    # ... 执行任务 ...
    
finally:
    # 恢复原始配置
    coordinator.set('gpu.batch_size', original_gpu_batch)
    print(f"已恢复batch_size: {coordinator.get('gpu.batch_size')}")
```markdown

## 7.2 配置导入导出

```python
import json
from src.config import ConfigCoordinator

coordinator = ConfigCoordinator('config.json')

# 导出配置到JSON
config = coordinator.get_unified_config()
with open('exported_config.json', 'w', encoding='utf-8') as f:
    json.dump(config, f, indent=2, ensure_ascii=False)
print("✅ 配置导出成功")

# 从JSON导入配置
with open('exported_config.json', 'r', encoding='utf-8') as f:
    imported_config = json.load(f)

coordinator.config_manager.merge_config(imported_config)
coordinator.config_manager.save_config()
print("✅ 配置导入成功")
```markdown

## 7.3 配置变更监听

```python
from src.config import ConfigCoordinator

class ConfigWatcher:
    def __init__(self, coordinator):
        self.coordinator = coordinator
        self._last_config = coordinator.get_unified_config()
    
    def check_changes(self):
        """检查配置是否发生变化"""
        current_config = self.coordinator.get_unified_config()
        
        if current_config != self._last_config:
            print("⚠️ 配置已更改")
            
            # 找出变更的配置项
            self._find_changes(self._last_config, current_config)
            
            self._last_config = current_config
            return True
        
        return False
    
    def _find_changes(self, old, new, path=""):
        """递归查找变更"""
        for key in new:
            current_path = f"{path}.{key}" if path else key
            
            if key not in old:
                print(f"  + 新增: {current_path} = {new[key]}")
            elif isinstance(new[key], dict) and isinstance(old.get(key), dict):
                self._find_changes(old[key], new[key], current_path)
            elif old[key] != new[key]:
                print(f"  ~ 修改: {current_path}: {old[key]} -> {new[key]}")
        
        for key in old:
            if key not in new:
                current_path = f"{path}.{key}" if path else key
                print(f"  - 删除: {current_path}")

# 使用示例
coordinator = ConfigCoordinator('config.json')
watcher = ConfigWatcher(coordinator)

# 监控配置变化
import time
while True:
    if watcher.check_changes():
        print("检测到配置变更，执行相应操作...")
    time.sleep(5)
```markdown

## 7.4 多环境配置

```python
from src.config import ConfigCoordinator

class MultiEnvConfig:
    """多环境配置管理器"""
    
    def __init__(self, base_config_file):
        self.base_coordinator = ConfigCoordinator(base_config_file)
        self.env_coordinators = {}
    
    def load_env(self, env_name, env_config_file):
        """加载环境配置"""
        self.env_coordinators[env_name] = ConfigCoordinator(env_config_file)
        print(f"✅ 加载{env_name}环境配置: {env_config_file}")
    
    def get_coordinator(self, env_name='default'):
        """获取指定环境的配置协调器"""
        if env_name == 'default':
            return self.base_coordinator
        return self.env_coordinators.get(env_name, self.base_coordinator)
    
    def switch_env(self, env_name):
        """切换到指定环境"""
        coordinator = self.get_coordinator(env_name)
        print(f"🔄 切换到{env_name}环境")
        return coordinator

# 使用示例
multi_config = MultiEnvConfig('config.json')
multi_config.load_env('dev', 'config.dev.json')
multi_config.load_env('prod', 'config.prod.json')

# 使用开发环境配置
dev_coordinator = multi_config.get_coordinator('dev')
print(f"开发环境batch_size: {dev_coordinator.get('gpu.batch_size')}")

# 使用生产环境配置
prod_coordinator = multi_config.get_coordinator('prod')
print(f"生产环境batch_size: {prod_coordinator.get('gpu.batch_size')}")
```python

---

## 8. 最佳实践

### 8.1 推荐做法

✅ **使用ConfigCoordinator作为统一入口**
```python
# 推荐
from src.config import ConfigCoordinator
coordinator = ConfigCoordinator('config.json')
config = coordinator.get_unified_config()
```python

✅ **启动时验证配置**
```python
coordinator = ConfigCoordinator('config.json')
errors = coordinator.validate_all()
if errors:
    raise ValueError(f"配置验证失败: {errors}")
```python

✅ **使用点号路径访问配置**
```python
# 推荐
batch_size = coordinator.get('gpu.batch_size')

# 不推荐
gpu_config = coordinator.config_manager.config['gpu']
batch_size = gpu_config['batch_size']
```python

✅ **修改配置后及时保存**
```python
coordinator.set('gpu.batch_size', 131072)
coordinator.save_all()  # 立即保存
```markdown

## 8.2 避免的做法

❌ **直接修改内部配置字典**
```python
# 错误做法
coordinator.config_manager.config['gpu']['batch_size'] = 131072

# 正确做法
coordinator.set('gpu.batch_size', 131072)
```python

❌ **忽略配置验证错误**
```python
# 错误做法
coordinator = ConfigCoordinator('config.json')
# 不验证直接使用

# 正确做法
coordinator = ConfigCoordinator('config.json')
errors = coordinator.validate_all()
if errors:
    # 处理验证错误
    pass
```python

❌ **频繁保存配置**
```python
# 错误做法
for i in range(100):
    coordinator.set('gpu.batch_size', i)
    coordinator.save_all()  # 频繁I/O

# 正确做法
for i in range(100):
    coordinator.set('gpu.batch_size', i)
coordinator.save_all()  # 批量保存
```markdown

## 8.3 性能优化

```python
from src.config import ConfigCoordinator

# 1. 缓存常用配置
coordinator = ConfigCoordinator('config.json')
_cached_config = coordinator.get_unified_config()

def get_batch_size():
    """从缓存获取batch_size"""
    return _cached_config['gpu']['batch_size']

# 2. 延迟加载配置
class LazyConfig:
    def __init__(self, config_file):
        self._config_file = config_file
        self._coordinator = None
    
    @property
    def coordinator(self):
        if self._coordinator is None:
            self._coordinator = ConfigCoordinator(self._config_file)
        return self._coordinator
    
    def get(self, key, default=None):
        return self.coordinator.get(key, default)

# 3. 批量修改配置
def update_gpu_config(batch_size=None, device_index=None, memory_ratio=None):
    """批量更新GPU配置"""
    coordinator = ConfigCoordinator('config.json')
    
    if batch_size is not None:
        coordinator.set('gpu.batch_size', batch_size)
    if device_index is not None:
        coordinator.set('gpu.device_index', device_index)
    if memory_ratio is not None:
        coordinator.set('gpu.memory_usage_ratio', memory_ratio)
    
    coordinator.save_all()
```python

---

## 附录A: 配置项完整列表

### A.1 collision配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `collision.max_workers` | int/None | None | 线程池最大工作线程数 |
| `collision.progress_interval` | int | 1000 | 进度回调间隔 |
| `collision.checkpoint_interval` | int | 30 | 断点自动保存间隔（秒） |
| `collision.dedup_max_size` | int | 1000000 | 去重过滤器最大容量 |

### A.2 gpu配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `gpu.use_gpu` | bool | True | 是否使用GPU |
| `gpu.device_index` | int | -1 | GPU设备索引（-1=自动选择） |
| `gpu.batch_size` | int | 65536 | 批次大小 |
| `gpu.auto_detect` | bool | True | 自动检测GPU设备 |
| `gpu.memory_usage_ratio` | float | 0.5 | 显存使用比例（0.0-1.0） |
| `gpu.enable_vendor_optimizations` | bool | True | 启用厂商优化 |

### A.3 crypto配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `crypto.backend` | str | "auto" | 加密后端（auto/pure_python/openssl/coincurve/ecdsa） |
| `crypto.constant_time` | bool | False | 恒定时间算法 |
| `crypto.verify_checksums` | bool | True | 校验和验证 |
| `crypto.strict_wif_validation` | bool | True | 严格WIF验证 |

### A.4 logging配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `logging.level` | str | "INFO" | 日志级别 |
| `logging.format` | str | ... | 日志格式 |
| `logging.file` | str | "logs/collision.log" | 日志文件路径 |
| `logging.max_bytes` | int | 10485760 | 日志文件最大大小（字节） |
| `logging.backup_count` | int | 5 | 日志备份数量 |
| `logging.enable_console` | bool | True | 启用控制台输出 |
| `logging.enable_file` | bool | True | 启用文件输出 |

### A.5 gui配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `gui.theme` | str | "dark" | 主题 |
| `gui.font` | str | "Microsoft YaHei" | 字体 |
| `gui.font_size` | int | 10 | 字体大小 |
| `gui.window_width` | int | 800 | 窗口宽度 |
| `gui.window_height` | int | 600 | 窗口高度 |

---

## 附录B: 常见错误和解决方案

### B.1 配置验证失败

**错误**: `gpu.batch_size必须是正整数`

**原因**: batch_size设置为负数或0

**解决方案**:
```python
coordinator.set('gpu.batch_size', 65536)  # 设置为正整数
```markdown

### B.2 配置保存失败

**错误**: `保存配置文件失败: Permission denied`

**原因**: 没有写入权限

**解决方案**:
```bash
# Windows
icacls config.json /grant Users:F

# Linux
chmod 644 config.json
```markdown

## B.3 配置加载失败

**错误**: `加载配置文件失败: JSON decode error`

**原因**: 配置文件格式错误

**解决方案**:
```python
# 使用默认配置重新创建
cm = ConfigManager()
cm.config_file = 'config.json'
cm.save_config()
```

---

**文档版本**: v1.0  
**最后更新**: 2026-04-20  
**维护者**: BTC碰撞引擎开发团队


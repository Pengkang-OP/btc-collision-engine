# 配置变更管理流程

**版本**: v4.2.2
**日期**: 2026-04-24
**状态**: ✅ 已实施

---

## 1. 目的

规范配置项的添加、修改和删除流程，确保：

- 配置验证Schema同步更新
- 文档及时更新
- 向后兼容性得到保证
- 变更可追溯

---

## 2. 配置变更类型

### 2.1 添加配置项

**定义**: 新增配置参数

**要求**:

- [ ] 在JSON Schema中添加定义
- [ ] 提供默认值
- [ ] 更新配置文档
- [ ] 添加单元测试
- [ ] 确保向后兼容

**示例流程**:

```
1. 在config_manager.py的CONFIG_SCHEMA中添加:
   "new_option": {"type": "boolean", "default": false}

2. 在DEFAULT_CONFIG中添加默认值:
   "new_option": False

3. 更新docs/config.md文档

4. 添加测试用例:
   def test_new_option_default():
       config = load_config()
       assert config['new_option'] is False

5. 运行测试验证
```

---

### 2.2 修改配置项

**定义**: 修改现有配置参数的类型、范围或默认值

**要求**:

- [ ] 评估向后兼容性
- [ ] 更新JSON Schema
- [ ] 更新默认值（如需要）
- [ ] 添加迁移逻辑
- [ ] 更新文档
- [ ] 添加弃用警告（如需要）

**兼容性级别**:

**完全兼容**: 只放宽限制

```python
# ✅ 兼容: 扩大范围
"batch_size": {"minimum": 1, "maximum": 33554432}  # 从16777216扩大

# ✅ 兼容: 添加新枚举值
"log_level": {"enum": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "TRACE"]}
```

**部分兼容**: 需要迁移

```python
# ⚠️ 部分兼容: 改变类型但提供转换
# 旧: "timeout": 30 (int)
# 新: "timeout": "30s" (string)

# 添加迁移逻辑
def migrate_config(config):
    if isinstance(config.get('timeout'), int):
        config['timeout'] = f"{config['timeout']}s"
        logger.warning("配置timeout已自动迁移为字符串格式")
    return config
```

**不兼容**: 需要版本升级

```python
# ❌ 不兼容: 删除配置项
# 旧: "deprecated_option": ...
# 新: (删除)

# 处理方案:
# 1. 先标记为弃用
# 2. 在下个大版本删除
# 3. 提供迁移指南
```

---

### 2.3 删除配置项

**定义**: 移除不再使用的配置参数

**要求**:

- [ ] 提前一个版本标记为弃用
- [ ] 添加弃用警告
- [ ] 提供替代方案
- [ ] 更新文档
- [ ] 在下个大版本删除

**弃用流程**:

```python
        "  请使用 'new_option' 替代\n"
        "  自动迁移: old_option=True -> new_option='enabled'"
    )
    # 自动迁移
    config['new_option'] = 'enabled' if config['old_option'] else 'disabled'

# 移除所有相关代码
```

---

## 3. 变更清单模板

### 3.1 配置变更申请表

```markdown
# 配置变更申请

## 基本信息
- **变更编号**: CFG-2026-001
- **申请日期**: 2026-04-24
- **申请人**: 开发者姓名
- **关联问题**: #123

## 变更类型
- [ ] 添加配置项
- [ ] 修改配置项
- [ ] 删除配置项

## 变更详情

### 添加配置项
- **配置项名称**: new_option
- **类型**: boolean
- **默认值**: false
- **取值范围**: true/false
- **描述**: 启用新功能
- **影响范围**: GPU引擎初始化

### 修改配置项
- **配置项名称**: batch_size
- **当前定义**: {"minimum": 1, "maximum": 16777216}
- **新定义**: {"minimum": 1, "maximum": 33554432}
- **修改原因**: 支持更大批次
- **兼容性**: 完全兼容（放宽限制）

### 删除配置项
- **配置项名称**: old_option
- **弃用版本**: v4.2.1
- **计划删除版本**: v4.2.1
- **替代方案**: 使用new_option
- **迁移指南**: [链接到文档]

## 影响分析

### 向后兼容性
- [ ] 完全兼容
- [ ] 部分兼容（需要迁移）
- [ ] 不兼容（需要版本升级）

### 影响模块
- [ ] GPU引擎
- [ ] CPU引擎
- [ ] 配置管理器
- [ ] CLI
- [ ] GUI
- [ ] 其他: _____

### 需要更新的文档
- [ ] README.md
- [ ] docs/config.md
- [ ] docs/api.md
- [ ] CHANGELOG.md
- [ ] 其他: _____

## 测试计划

### 单元测试
- [ ] 添加新配置项的测试
- [ ] 测试默认值
- [ ] 测试边界值
- [ ] 测试无效值

### 集成测试
- [ ] 配置加载测试
- [ ] 配置验证测试
- [ ] 迁移逻辑测试

### 兼容性测试
- [ ] 旧配置文件加载测试
- [ ] 迁移后功能测试
- [ ] 回退测试

## 审批

- **开发负责人**: ___________ 日期: _______
- **测试负责人**: ___________ 日期: _______
- **产品负责人**: ___________ 日期: _______
```

---

## 4. 实施检查清单

### 4.1 开发阶段

- [ ] 在CONFIG_SCHEMA中添加/修改配置项
- [ ] 在DEFAULT_CONFIG中添加默认值
- [ ] 实现配置读取逻辑
- [ ] 实现配置验证逻辑
- [ ] 实现迁移逻辑（如需要）
- [ ] 添加弃用警告（如需要）
- [ ] 更新类型注解

### 4.2 测试阶段

- [ ] 单元测试通过
- [ ] 集成测试通过
- [ ] 兼容性测试通过
- [ ] 性能测试通过（如影响性能）
- [ ] 文档测试通过

### 4.3 文档阶段

- [ ] 更新config.md
- [ ] 更新CHANGELOG.md
- [ ] 更新示例配置
- [ ] 添加迁移指南（如需要）
- [ ] 更新API文档

### 4.4 发布阶段

- [ ] 代码审查通过
- [ ] 测试报告通过
- [ ] 文档审查通过
- [ ] 发布说明更新
- [ ] 通知用户（重大变更）

---

## 5. 自动化检查

### 5.1 CI/CD检查

```yaml
# .github/workflows/config-validation.yml
name: 配置验证

on:
  push:
    paths:
      - 'src/config/**'
      - 'config*.json'

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2

      - name: 验证JSON Schema
        run: |
          python -c "
          from src.config.config_manager import ConfigManager
          cm = ConfigManager()
          errors = cm.validate()
          if errors:
              print('配置验证失败:')
              for k, v in errors.items():
                  print(f'  {k}: {v}')
              exit(1)
          "

      - name: 检查Schema同步
        run: |
          python scripts/check_schema_sync.py
```

### 5.2 Schema同步检查脚本

```python
#!/usr/bin/env python3
"""检查配置项是否在Schema中都有定义"""

import json
from pathlib import Path
from src.config.config_manager import ConfigManager

def check_schema_sync():
    """检查配置文件和Schema是否同步"""
    # 加载示例配置
    config_file = Path('config.json')
    with open(config_file) as f:
        config = json.load(f)

    # 验证
    cm = ConfigManager()
    errors = cm._validate_with_schema(config)

    if errors:
        print("❌ 配置验证失败:")
        for key, error in errors.items():
            print(f"  {key}: {error}")
        return False

    print("✅ 配置和Schema同步")
    return True

if __name__ == '__main__':
    import sys
    sys.exit(0 if check_schema_sync() else 1)
```

---

## 6. 配置版本管理

### 6.1 版本号规则

```
主版本.次版本.修订版本
  |      |      |
  |      |      +- 配置验证修复
  |      +-------- 添加配置项（兼容）
  +--------------- 删除配置项（不兼容）
```

**示例**:

- v4.2.1: 添加async_execution（兼容）
- v4.2.1: 修复work_group_size验证
- v4.2.1: 删除deprecated_option（不兼容）

### 6.2 配置迁移历史

```markdown
# 配置迁移历史

## v4.2.1 (2026-04-24)
- ✅ 新增: async_execution (boolean, default: true)
- ✅ 新增: work_group_size (integer, 64-2048)
- ✅ 新增: use_fast_math (boolean)
- ✅ 新增: use_uint32_workaround (boolean)
- ✅ 新增: compiler_flags (string)

## v4.2.1 (2026-03-15)
- ⚠️ 修改: memory_usage_ratio范围从0.1-0.9改为0.1-1.0
- ✅ 新增: enable_vendor_optimizations

## v4.2.1 (2026-01-01)
- ❌ 删除: legacy_mode (使用gpu.vendor_optimizations替代)
- ✅ 新增: gpu.use_gpu
```

---

## 7. 最佳实践

### 7.1 设计原则

1. **最小化**: 只添加必要的配置项
2. **明确性**: 配置项名称清晰表达用途
3. **安全性**: 敏感配置项使用加密存储
4. **文档化**: 每个配置项都有完整文档
5. **验证性**: 所有配置项都有验证规则

### 7.2 命名规范

```python
# ✅ 好的命名
"batch_size"          # 清晰
"memory_usage_ratio"  # 明确
"enable_async"        # 布尔值用enable/enable

# ❌ 不好的命名
"bs"                  # 缩写不清
"mem"                 # 含义不明
"async"               # 缺少动词
```

### 7.3 默认值原则

```python
# ✅ 安全的默认值
"batch_size": 1024           # 保守值
"memory_usage_ratio": 0.5    # 50%显存
"enable_async": True         # 性能最优

# ❌ 危险的默认值
"batch_size": 16777216       # 可能导致OOM
"memory_usage_ratio": 0.95   # 几乎用尽显存
```

---

## 8. 故障排除

### 8.1 常见问题

**Q1: 配置验证失败怎么办？**

```
A: 检查清单:
   1. 配置项名称是否正确？
   2. 值类型是否正确？
   3. 值是否在有效范围内？
   4. JSON格式是否正确？
```

**Q2: 如何查看当前生效的配置？**

```python
from src.config.config_manager import ConfigManager

cm = ConfigManager()
cm.load('config.json')
print(json.dumps(cm.config, indent=2))
```

**Q3: 配置文件格式错误如何恢复？**

```
A: 使用默认配置:
   python main.py --use-default-config

   或从备份恢复:
   cp config.json.backup config.json
```

---

## 9. 参考资料

- [JSON Schema规范](https://json-schema.org/)
- [配置管理最佳实践](https://12factor.net/config)
- [语义化版本](https://semver.org/)

---

**维护者**: AI审计系统
**下次审查**: 2026-07-24

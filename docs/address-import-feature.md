# 地址导入和自动保存功能

> **版本**: v5.0.0 | **最后更新**: 2026-05-15
> **面向**: 用户

<!-- markdownlint-disable MD051 -->

## 目录

- [功能概述](#功能概述)
- [主要特性](#主要特性)
- [使用方法](#使用方法)
  - [基本导入](#基本导入)
- [带进度回调的导入](#带进度回调的导入)
  - [不同存储格式](#不同存储格式)
- [不验证直接导入（快速模式）](#不验证直接导入快速模式)
- [源文件格式](#源文件格式)
  - [TXT格式](#txt格式)
- [JSON格式](#json格式)
  - [CSV格式](#csv格式)
- [返回结果](#返回结果)
- [元数据](#元数据)
- [测试](#测试)
- [示例](#示例)
- [注意事项](#注意事项)

<!-- markdownlint-enable MD051 -->

## 功能概述

`AddressStorage` 类新增了 `import_addresses` 方法，支持从外部源导入比特币地址数据，并在导入过程中进行数据验证，验证通过后自动将有效地址保存到持久化存储中。

## 主要特性

1. **多格式支持**: 支持从 TXT、JSON、CSV 格式文件导入地址
2. **地址验证**: 使用 `AddressBatchValidator` 验证地址格式和校验和
3. **自动持久化**: 验证通过后自动保存到指定存储格式
4. **多存储格式**: 支持 JSON、SQLite、CSV 三种存储格式
5. **元数据记录**: 保存导入时间、源文件、地址数量等元数据
6. **进度回调**: 支持进度回调函数，实时反馈导入进度
7. **错误处理**: 对无效地址进行过滤和记录，提供详细错误信息
8. **数据完整性**: 确保导入过程中的数据完整性和一致性

## 使用方法

### 基本导入

```python
from src.collision.targets.storage import AddressStorage

# 创建存储实例
storage = AddressStorage()

# 从文本文件导入地址（默认验证并保存为JSON格式）
result = storage.import_addresses(
    source_path='addresses.txt',
    storage_dir='./targets_data',
    validate=True,
    storage_type='json'
)

print(f"导入成功: {result['success']}")
print(f"有效地址数: {result['imported_count']}")
print(f"无效地址数: {result['invalid_count']}")
print(f"存储路径: {result['storage_path']}")
```

### 带进度回调的导入

```python
def progress_callback(imported, total, address):
    print(f"进度: {imported}/{total} - 处理地址: {address[:20]}...")

result = storage.import_addresses(
    source_path='addresses.txt',
    storage_dir='./targets_data',
    validate=True,
    storage_type='json',
    progress_callback=progress_callback
)
```markdown

### 不同存储格式

```python
# JSON格式（默认）
result = storage.import_addresses(
    source_path='addresses.txt',
    storage_dir='./targets_data',
    storage_type='json'
)

# SQLite格式
result = storage.import_addresses(
    source_path='addresses.txt',
    storage_dir='./targets_data',
    storage_type='sqlite'
)

# CSV格式
result = storage.import_addresses(
    source_path='addresses.txt',
    storage_dir='./targets_data',
    storage_type='csv'
)
```

### 不验证直接导入（快速模式）

```python
# 关闭验证，直接导入所有地址（包括可能无效的地址）
result = storage.import_addresses(
    source_path='addresses.txt',
    storage_dir='./targets_data',
    validate=False,  # 关闭验证
    storage_type='json'
)
```

## 源文件格式

### TXT格式
每行一个地址，支持注释（以#开头）：
```text
# 目标地址文件

1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa
1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2

# 这是注释

12c6DSiU4Rq3P4ZxziKxzrL5LmMBrzjrJX
```

### JSON格式
支持多种结构：
```json
{
  "addresses": [
    "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
    "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2"
  ]
}
```

或：
```json
{
  "targets": [
    "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
    "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2"
  ]
}
```

或简单数组：
```json
[
  "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
  "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2"
]
```

### CSV格式
第一行为头部（可选），之后每行第一个字段为地址：
```csv
address,name
1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa,test1
1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2,test2
```

## 返回结果

`import_addresses` 方法返回一个字典，包含以下字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `success` | bool | 是否导入成功 |
| `imported_count` | int | 成功导入的有效地址数 |
| `invalid_count` | int | 无效地址数 |
| `total_count` | int | 总处理地址数 |
| `invalid_addresses` | list | 无效地址列表，每项包含 `address` 和 `error` |
| `storage_path` | str | 存储文件路径 |
| `error` | str | 错误信息（如果有） |

## 元数据

导入成功后，存储文件会包含以下元数据：

```json
{
  "version": "1.0",
  "created_at": "2024-01-01T12:00:00",
  "target_count": 100,
  "targets": ["1A1z...", "1BvB..."],
  "metadata": {
    "import_time": "2024-01-01T12:00:00",
    "source_file": "/path/to/source.txt",
    "imported_count": 100,
    "invalid_count": 5,
    "total_processed": 105,
    "validation_enabled": true,
    "storage_type": "json"
  }
}
```

## 测试

运行测试验证功能：

```bash
python -m pytest tests/test_address_import.py -v
```

## 示例

查看完整使用示例：

```bash
python examples/address_import_example.py
```

## 注意事项

1. **存储目录**: 如果不指定 `storage_dir`，默认使用当前工作目录下的 `targets_data` 文件夹
2. **文件命名**: 导入文件使用时间戳命名，格式为 `imported_addresses_YYYYMMDD_HHMMSS.ext`
3. **验证性能**: 验证过程使用多线程并行处理，大批量地址导入时性能较好
4. **错误处理**: 无效地址会被过滤并记录，不会中断导入过程
5. **数据一致性**: 导入过程使用事务性操作，确保数据完整性

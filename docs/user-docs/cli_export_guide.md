# 📤 导出功能使用指南

> **版本**: v4.2.2 | **最后更新**: 2026-05-15
> **相关文档**: [CLI快速参考](CLI_QUICK_REFERENCE.md) | [GPU引擎指南](gpu-engine-guide.md)

---

## 📋 目录

1. [导出功能概述](#导出功能概述)
2. [使用方法](#使用方法)
3. [JSON输出格式](#json输出格式)
4. [数据分析示例](#数据分析示例)
5. [注意事项](#注意事项)

---

## 🔍 导出功能概述

BTC碰撞引擎提供两个专用的数据导出参数，可在运行结束后将进度统计与匹配结果保存为结构化JSON文件，便于后续分析、可视化和自动化处理。

### 参数说明

| 参数 | 类型 | 说明 |
|------|------|------|
| `--export-progress FILE` | 字符串（文件路径） | 运行结束后将进度统计导出到指定JSON文件 |
| `--export-matches FILE` | 字符串（文件路径） | 运行结束后将所有匹配结果导出到指定JSON文件 |

### 支持的碰撞模式

两个导出参数均兼容所有碰撞模式和引擎类型：

| 碰撞模式 | `--export-progress` | `--export-matches` | 备注 |
|---------|--------------------|--------------------|------|
| `random`（随机） | ✅ | ✅ | 无总范围，不含进度百分比 |
| `range`（范围扫描） | ✅ | ✅ | 含 `total_range` 和 `progress_percent` |
| `brute_force`（暴力穷举） | ✅ | ✅ | 含 `total_range` 和 `progress_percent` |
| CPU引擎 | ✅ | ✅ | `engine_type: "cpu"` |
| 单GPU引擎 | ✅ | ✅ | `engine_type: "gpu"` |
| 多GPU引擎 | ✅ | ✅ | `engine_type: "multi_gpu"` |

---

## 🚀 使用方法

### 示例1：随机模式 + 导出进度

```bash
# 运行1小时随机碰撞，结束后导出进度统计
python key_collision_cli.py \
  -t 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa \
  -m random \
  --duration 3600 \
  --export-progress progress.json
```

### 示例2：范围模式 + 同时导出进度和匹配结果

```bash
# 扫描指定私钥范围，导出进度和匹配结果
python key_collision_cli.py \
  -t 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa \
  -m range \
  --start 1 \
  --end FFFFFFFFFFFF \
  --export-progress progress.json \
  --export-matches matches.json
```

### 示例3：仅导出匹配结果（GPU加速）

```bash
# 使用GPU加速，仅保存找到的匹配记录
python key_collision_cli.py \
  -f targets.txt \
  -m random \
  --use-gpu \
  --export-matches found_keys.json
```

### 示例4：组合使用（长时间运行 + 断点续传 + 完整导出）

```bash
# 24小时运行，启用断点续传，导出全部数据
python key_collision_cli.py \
  -f targets.txt \
  -m random \
  --use-gpu \
  --checkpoint \
  --dedup \
  --duration 86400 \
  --sensitive-mode masked \
  --export-progress daily_progress.json \
  --export-matches daily_matches.json
```

### 示例5：多GPU + 范围扫描 + 导出

```bash
# 多GPU并行扫描，导出进度和匹配
python key_collision_cli.py \
  -f targets.txt \
  -m range \
  --start 100000000 \
  --end FFFFFFFFFFFFFFFF \
  --multi-gpu \
  --export-progress multi_gpu_progress.json \
  --export-matches multi_gpu_matches.json
```

---

## 📄 JSON输出格式

### `--export-progress` 输出格式

导出文件包含本次运行的完整进度快照。

**字段说明**

| 字段名 | 类型 | 说明 | 示例值 |
|--------|------|------|--------|
| `timestamp` | float | Unix时间戳（秒） | `1745548800.123` |
| `mode` | string | 碰撞模式 | `"random"` / `"range"` / `"brute_force"` |
| `engine_type` | string | 引擎类型 | `"cpu"` / `"gpu"` / `"multi_gpu"` |
| `total_checked` | int | 总检查次数 | `1234567` |
| `elapsed_seconds` | float | 运行时长（秒） | `3600.5` |
| `elapsed_formatted` | string | 格式化时长 | `"1:00:00"` |
| `speed` | string | 格式化速度 | `"15.0K/s"` |
| `matches_count` | int | 匹配数量 | `0` |
| `matches` | array | 匹配结果列表（见下方） | `[]` |
| `total_range` ⚠️ | int | 总搜索范围（仅 range/brute_force 模式） | `1099511627775` |
| `progress_percent` ⚠️ | float | 完成百分比，最大100.0（仅 range/brute_force 模式） | `12.34` |

> ⚠️ 带此标记的字段仅在 `range` 或 `brute_force` 模式下存在。

**输出示例（随机模式）**

```json
{
  "timestamp": 1745548800.123456,
  "mode": "random",
  "engine_type": "gpu",
  "total_checked": 54000000,
  "elapsed_seconds": 3600.5,
  "elapsed_formatted": "1:00:00",
  "speed": "15.0K/s",
  "matches_count": 0,
  "matches": []
}
```

**输出示例（范围模式，含进度）**

```json
{
  "timestamp": 1745548800.456789,
  "mode": "range",
  "engine_type": "gpu",
  "total_checked": 13434,
  "elapsed_seconds": 600.0,
  "elapsed_formatted": "0:10:00",
  "speed": "22.4/s",
  "matches_count": 1,
  "matches": [
    {
      "address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
      "private_key": "0000000000000000000000000000000000000000000000000000000000000001",
      "wif": "KwDiBf89QgGbjEhKnhXJuH7LrciVrZi3qYjgd9M7rFU73sVHnoWn"
    }
  ],
  "total_range": 1099511627775,
  "progress_percent": 0.001221
}
```

---

### `--export-matches` 输出格式

专用于导出匹配结果，结构更简洁。

**字段说明**

| 字段名 | 类型 | 说明 | 示例值 |
|--------|------|------|--------|
| `timestamp` | float | 导出时的Unix时间戳 | `1745548800.789` |
| `total_matches` | int | 匹配总数 | `2` |
| `matches` | array | 匹配记录列表 | 见下方 |

**`matches` 数组每条记录字段**

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `address` | string | 匹配的比特币地址 |
| `private_key` | string | 私钥十六进制字符串（受 `--sensitive-mode` 影响） |
| `wif` | string | WIF格式私钥（受 `--sensitive-mode` 影响） |

**输出示例**

```json
{
  "timestamp": 1745548800.789012,
  "total_matches": 2,
  "matches": [
    {
      "address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
      "private_key": "0000000000000000000000000000000000000000000000000000000000000001",
      "wif": "KwDiBf89QgGbjEhKnhXJuH7LrciVrZi3qYjgd9M7rFU73sVHnoWn"
    },
    {
      "address": "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2",
      "private_key": "0000000000000000000000000000000000000000000000000000000000000002",
      "wif": "KwDiBf89QgGbjEhKnhXJuH7LrciVrZi3qYjgd9M7rFU73NVn..."
    }
  ]
}
```

> 💡 **脱敏说明**：配合 `--sensitive-mode masked` 时，`private_key` 仅显示首尾各8位，其余用 `*` 掩码；`--sensitive-mode hash_only` 时显示为 `[SHA256:xxxx...]` 哈希摘要。

---

## 🐍 数据分析示例

以下Python脚本演示如何读取导出的JSON文件进行简单统计分析：

```python
#!/usr/bin/env python3
"""分析BTC碰撞引擎导出的进度和匹配数据"""

import json
from pathlib import Path


def analyze_progress(progress_file: str) -> None:
    """分析进度导出文件，输出速度趋势和关键统计"""
    path = Path(progress_file)
    if not path.exists():
        print(f"[错误] 文件不存在: {progress_file}")
        return

    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print("=" * 50)
    print("📊 进度统计摘要")
    print("=" * 50)
    print(f"  碰撞模式    : {data['mode']}")
    print(f"  引擎类型    : {data['engine_type']}")
    print(f"  总检查次数  : {data['total_checked']:,}")
    print(f"  运行时长    : {data['elapsed_formatted']}")
    print(f"  当前速度    : {data['speed']}")
    print(f"  匹配数量    : {data['matches_count']}")

    # 范围模式专属
    if 'progress_percent' in data:
        print(f"  扫描进度    : {data['progress_percent']:.4f}%")
        print(f"  总搜索范围  : {data['total_range']:,}")

    # 计算平均速度（次/秒）
    if data['elapsed_seconds'] > 0:
        avg_speed = data['total_checked'] / data['elapsed_seconds']
        print(f"  平均速度    : {avg_speed:,.0f} 次/秒")

        # 范围模式下估算剩余时间
        if 'total_range' in data and data['progress_percent'] < 100:
            remaining = data['total_range'] - data['total_checked']
            eta_seconds = remaining / avg_speed
            eta_hours = eta_seconds / 3600
            print(f"  预计剩余    : {eta_hours:,.1f} 小时")

    print()


def analyze_matches(matches_file: str) -> None:
    """分析匹配导出文件，输出匹配汇总信息"""
    path = Path(matches_file)
    if not path.exists():
        print(f"[错误] 文件不存在: {matches_file}")
        return

    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print("=" * 50)
    print("🎯 匹配结果汇总")
    print("=" * 50)
    print(f"  总匹配数    : {data['total_matches']}")

    if data['total_matches'] == 0:
        print("  （本次运行未发现匹配）")
        return

    print()
    for i, match in enumerate(data['matches'], 1):
        print(f"  [{i}] 地址   : {match['address']}")
        print(f"      私钥   : {match['private_key']}")
        print(f"      WIF    : {match['wif']}")
        print()

    # 统计涉及的唯一地址数量
    unique_addresses = {m['address'] for m in data['matches']}
    print(f"  涉及唯一地址数: {len(unique_addresses)}")


if __name__ == '__main__':
    # 修改此处为实际文件路径
    analyze_progress('progress.json')
    analyze_matches('matches.json')
```

**运行方式**

```bash
python analyze_export.py
```

---

## ⚠️ 注意事项

1. **文件会被覆盖**
   每次运行使用相同导出路径时，旧文件将被直接覆盖，不会追加。如需保留历史记录，请在路径中加入时间戳，例如：`--export-progress progress_$(date +%Y%m%d_%H%M%S).json`（Linux/macOS）。

2. **确保磁盘空间充足**
   单次进度文件体积通常较小（< 1MB），但若 `matches` 列表非常大，文件可能显著增大。建议在长时间运行前确认目标磁盘有足够空间。

3. **路径权限**
   确保指定的导出路径对当前用户可写。建议使用相对路径（写入项目目录）或提前创建目标目录。

4. **建议搭配 `--sensitive-mode` 使用**
   导出文件中会包含私钥信息，强烈建议在不需要完整私钥时使用 `--sensitive-mode masked` 或 `--sensitive-mode hash_only`，以降低敏感数据泄露风险：

   ```bash
   python key_collision_cli.py -f targets.txt -m random \
     --sensitive-mode masked \
     --export-matches matches.json
   ```

5. **仅在运行结束时写入**
   导出操作在碰撞引擎停止后执行（正常退出或 `--duration` 到期），中途 `Ctrl+C` 强制中断**不保证**导出文件被写入，建议配合 `--duration` 参数使用以确保正常退出。

---

## 📚 相关参考

- 完整参数帮助: `python key_collision_cli.py --help`
- CLI快速参考: [CLI_QUICK_REFERENCE.md](CLI_QUICK_REFERENCE.md)
- GPU引擎指南: [gpu-engine-guide.md](gpu-engine-guide.md)
- 配置说明: [CONFIG.md](CONFIG.md)

---

**更新日期**: 2026-04-25
**版本**: v4.2.2

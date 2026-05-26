# 国际化(i18n)使用指南

> 版本: v4.5.1 | 最后更新: 2026-05-21

## 概述

BTC 碰撞引擎支持多语言界面，当前支持中文（zh_CN）和英文（en_US）。
国际化功能由 `src/i18n` 模块提供，核心组件包括：

- **`Translator`**：核心翻译器，负责加载 JSON 语言文件、嵌套键访问、参数替换和自动回退

- **`detect_system_language`**：跨平台语言自动检测，支持 Windows/Linux/macOS

- **`_t()`**：全局翻译快捷函数，是调用翻译的主要入口

语言设置支持多种方式，按优先级从高到低依次生效（详见[语言检测优先级](#5-语言检测优先级)）。

---

## 1. 快速开始

### 命令行指定语言

使用 `--language` 参数在启动时指定界面语言：

```bash
# 使用英文界面
python key_collision_cli.py --language en_US -t <地址> -m random

# 使用中文界面（默认）
python key_collision_cli.py --language zh_CN -t <地址> -m random

```

> `--language` 参数仅支持 `zh_CN` 和 `en_US` 两个值。

### 环境变量设置

通过 `BTC_LANGUAGE` 环境变量永久或临时设置语言，优先级高于系统语言自动检测：

```bash
# Windows PowerShell
$env:BTC_LANGUAGE = "en_US"
python key_collision_cli.py -t <地址> -m random

# Windows CMD
set BTC_LANGUAGE=en_US
python key_collision_cli.py -t <地址> -m random

# Linux / macOS
export BTC_LANGUAGE=en_US
python key_collision_cli.py -t <地址> -m random

```

### 配置文件设置

在 `config.json` 中配置 `i18n` 节，设置默认语言及回退语言：

```json
{
  "i18n": {
    "language": "zh_CN",
    "_comment_language": "界面语言：auto=自动检测系统语言, zh_CN, en_US",
    "fallback_language": "en_US",
    "_comment_fallback_language": "回退语言，当指定语言找不到翻译时使用"
  }
}

```

`language` 字段支持以下值：

| 值 | 说明 |
|----|------|
| `auto` | 自动检测系统语言（默认） |
| `zh_CN` | 强制使用简体中文 |
| `en_US` | 强制使用英文 |

---

## 2. 支持的语言

| 语言代码 | 语言名称 | 语言文件 | 状态 |
|----------|----------|----------|------|
| `zh_CN`  | 简体中文 | `src/i18n/locales/zh_CN.json` | ✅ 完整支持 |
| `en_US`  | 英文（美国） | `src/i18n/locales/en_US.json` | ✅ 完整支持 |

两个语言文件均包含约 700 行翻译条目，覆盖所有模块（CLI、GPU、碰撞引擎、监控系统等）。

---

## 3. 开发者指南

### 使用翻译函数

在代码中导入并使用 `_t()` 快捷函数：

```python
from src.i18n import _t

# 基本用法
print(_t("common.success"))       # 输出：成功（或 Success）
print(_t("cli.commands.start"))   # 输出：启动碰撞引擎

# 访问嵌套键（通过点分隔符）
print(_t("cli.help.description"))  # 输出：BTC碰撞引擎 - 高性能比特币地址碰撞检测工具

```

### 参数替换

`_t()` 支持通过关键字参数进行字符串格式化：

```python
from src.i18n import _t

# 单参数替换
msg = _t("platform.check.os_supported", os_name="Windows")
# 输出：操作系统检查通过: Windows

# 多参数替换
msg = _t("collision.progress", checked=1000000, speed="500K", elapsed="2s")
# 输出：已检测: 1,000,000 个密钥 | 速度: 500K Keys/s | 用时: 2s

# 错误消息
msg = _t("errors.file_not_found", path="/tmp/addresses.txt")
# 输出：文件未找到: /tmp/addresses.txt

```

> 若参数替换失败（键名不匹配），`_t()` 会记录警告日志并返回原始未格式化的字符串，不会抛出异常。

### 运行时切换语言

```python
from src.i18n import set_language, get_language, get_supported_languages

# 查询当前语言
current = get_language()           # 返回如 "zh_CN"

# 查询支持的语言列表
langs = get_supported_languages()  # 返回 ["zh_CN", "en_US"]

# 切换语言（线程安全）
set_language("en_US")
print(_t("common.success"))        # 输出：Success

set_language("zh_CN")
print(_t("common.success"))        # 输出：成功

```

### 直接使用 Translator 类

```python
from src.i18n import Translator

# 创建独立翻译器实例（适合隔离场景）
t = Translator(language="en_US")
print(t.translate("cli.commands.stop"))   # Stop collision engine
print(t.translate("gpu.init_success", name="NVIDIA RTX 4090"))
# 输出：GPU initialized: NVIDIA RTX 4090

# 切换语言
t.set_language("zh_CN")
print(t.translate("gpu.init_success", name="NVIDIA RTX 4090"))
# 输出：GPU初始化成功: NVIDIA RTX 4090

```

### 添加新翻译条目

向现有语言文件添加新条目：

1. 在 `src/i18n/locales/zh_CN.json` 中添加中文条目：

```json
{
  "mymodule": {
    "init_done": "我的模块初始化完成",
    "process_item": "正在处理: {item_name}"
  }
}

```

1. 在 `src/i18n/locales/en_US.json` 中添加对应英文条目：

```json
{
  "mymodule": {
    "init_done": "My module initialized",
    "process_item": "Processing: {item_name}"
  }
}

```

1. 在代码中使用新翻译键：

```python
from src.i18n import _t

print(_t("mymodule.init_done"))
print(_t("mymodule.process_item", item_name="block_001"))

```

---

## 4. 翻译键命名规范

翻译键使用**点分隔的层级命名**，格式为 `<模块>.<子模块>.<条目>`。
当前顶层命名空间及含义如下：

| 前缀 | 模块 | 说明 |
|------|------|------|
| `common.*` | 通用消息 | 通用词汇：成功、错误、加载中等 |
| `cli.*` | CLI 界面 | 命令、选项、帮助信息、验证消息等 |
| `platform.*` | 平台检测 | 操作系统检查、路径检测、权限验证等 |
| `gpu.*` | GPU 相关 | GPU 设备检测、初始化、内核编译、内存池等 |
| `collision.*` | 碰撞引擎 | 碰撞进度、结果、统计数据等 |
| `config.*` | 配置管理 | 配置加载、保存、验证、各配置段名称等 |
| `monitoring.*` | 监控系统 | 监控启停、告警、指标、报告等 |
| `logging.*` | 日志系统 | 日志文件操作、轮转、归档等 |
| `checkpoint.*` | 断点续传 | 检查点创建、加载、恢复等 |
| `address.*` | 地址管理 | 地址加载、验证、布隆过滤器等 |
| `crypto.*` | 密码学 | 密钥生成、WIF 编码、公钥推导等 |
| `benchmark.*` | 基准测试 | 测试启动、结果、各模块性能等 |
| `export.*` | 数据导出 | 导出格式、字段、统计等 |
| `security.*` | 安全功能 | 密钥锁定、安全模式、审计日志等 |
| `errors.*` | 错误消息 | 文件不存在、权限拒绝、GPU 错误等 |

**命名约定**：

- 使用小写字母和下划线

- 层级不超过 3 层（如 `gpu.multi_gpu.enabled`）

- 条目名称应为名词或动词短语，准确描述含义

- 参数占位符使用 `{snake_case}` 格式（如 `{file_path}`、`{error_msg}`）

---

## 5. 语言检测优先级

系统在初始化时按以下顺序确定界面语言，一旦找到有效设置即停止检测：

```
优先级（高 → 低）

1. 环境变量 BTC_LANGUAGE
   └─ 设置此变量可覆盖所有其他设置

2. --language 命令行参数
   └─ 在 CLI 启动时通过 set_language() 生效

3. Python locale 模块
   └─ 读取操作系统 locale 配置

4. 系统语言自动检测
   ├─ Windows: 调用 ctypes.windll.kernel32.GetUserDefaultUILanguage()
   └─ Linux/macOS: 读取 LANG / LC_ALL / LC_MESSAGES / LANGUAGE 环境变量

5. 回退到 en_US
   └─ 当上述所有方式均无法确定语言时使用

```

**语言代码规范化**：系统会自动将各种格式的语言代码规范化，例如：

| 输入格式 | 规范化结果 |
|----------|-----------|
| `zh-CN` | `zh_CN` |
| `zh` | `zh_CN` |
| `chinese (simplified)` | `zh_CN` |
| `2052`（Windows LANGID） | `zh_CN` |
| `en_GB` | `en_US` |
| `en` | `en_US` |

---

## 6. 添加新语言支持

如需为项目添加新语言（如日文 `ja_JP`），请按以下步骤操作：

### 步骤 1：创建语言文件

参照 `src/i18n/locales/en_US.json` 的结构，在 `locales/` 目录下创建新文件：

```
src/i18n/locales/ja_JP.json

```

确保包含所有顶层命名空间（`common`、`cli`、`platform` 等），未翻译的条目会自动回退到英文。

### 步骤 2：更新语言检测模块

在 `src/i18n/language_detector.py` 的 `_SUPPORTED_LANGUAGES` 列表中添加新语言代码：

```python
_SUPPORTED_LANGUAGES = ["zh_CN", "en_US", "ja_JP"]  # 添加 ja_JP

```

在 `_LANG_MAP` 字典中添加系统语言代码映射：

```python
_LANG_MAP = {
    # ... 现有条目 ...
    # 日文
    "ja_jp": "ja_JP",
    "ja": "ja_JP",
    "japanese": "ja_JP",
    "1041": "ja_JP",   # Windows LANGID: 日语
}

```

### 步骤 3：验证新语言

```python
from src.i18n import Translator, get_supported_languages

# 验证语言文件能正确加载
t = Translator(language="ja_JP")
print(t.translate("common.success"))  # 应显示日文翻译

# 验证出现在支持列表中
print(get_supported_languages())  # 应包含 "ja_JP"

```

---

## 7. 常见问题

### Q1：翻译键不存在时会发生什么？

`_t()` 具有三级回退机制：

1. **当前语言**（如 `zh_CN`）：查找对应翻译

2. **回退到英文**（`en_US`）：若当前语言缺少该键，自动使用英文翻译

3. **硬编码默认值**：若英文翻译也不存在，返回硬编码的少量通用条目

4. **返回键名**：最终兜底，直接返回键名（如 `"my.missing.key"`）

因此，`_t()` **永远不会抛出异常**，即使键名不存在也能正常运行。

### Q2：如何确认当前生效的语言？

```python
from src.i18n import get_language
print(get_language())  # 输出如 "zh_CN"

```

或在命令行中：

```bash
python -c "from src.i18n import get_language; print(get_language())"

```

### Q3：在多线程环境下切换语言是否安全？

是的，`Translator` 类的所有公开方法均通过 `threading.Lock` 实现了线程安全保护，可以在多线程环境中安全调用 `set_language()`。

### Q4：语言文件修改后需要重启吗？

是的，语言文件在首次使用时加载并缓存。若在运行时修改了语言文件，需要重启程序才能生效。若需热重载，可创建新的 `Translator` 实例。

### Q5：Windows 中文系统为何显示英文？

可能原因及解决方法：

1. **`BTC_LANGUAGE` 被显式设置为 `en_US`**：检查并清除该环境变量

2. **Windows API 调用失败**：系统会回退到读取 `LANG` 等环境变量，若均未设置则使用 `en_US`

3. **强制指定英文**：检查 config.json 中的 `i18n.language` 是否被设为 `en_US`

手动强制使用中文：

```bash
$env:BTC_LANGUAGE = "zh_CN"
python key_collision_cli.py --language zh_CN

```

### Q6：如何在 Docker 容器中设置语言？

在 `docker-compose.yml` 或 Dockerfile 中设置环境变量：

```yaml
# docker-compose.yml
services:
  btc-engine:
    environment:
      - BTC_LANGUAGE=zh_CN

```

```dockerfile
# Dockerfile
ENV BTC_LANGUAGE=zh_CN

```

---

## 参考

- **源码**：[`src/i18n/`](../src/i18n/)

  - [`__init__.py`](../src/i18n/__init__.py) — 公共 API 导出

  - [`translator.py`](../src/i18n/translator.py) — 核心翻译器

  - [`language_detector.py`](../src/i18n/language_detector.py) — 语言检测

  - [`locales/zh_CN.json`](../src/i18n/locales/zh_CN.json) — 中文翻译

  - [`locales/en_US.json`](../src/i18n/locales/en_US.json) — 英文翻译

- **相关文档**：

  - [跨平台兼容性指南](cross-platform-compatibility.md)

  - [CLI 快速参考](CLI_QUICK_REFERENCE.md)

  - [配置使用示例](config-usage-examples.md)

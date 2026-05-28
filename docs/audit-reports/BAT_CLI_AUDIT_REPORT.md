# CLI/BAT 脚本审核报告

**审核日期**: 2026-05-12  
**审核类型**: 脚本整理与冗余消除  
**审核结果**: 完成

---

## 一、BAT 脚本分析

### 1.1 现有脚本清单

| 脚本 | 行数 | 功能 | 状态 |
|------|------|------|------|
| `common.bat` | 108 | 共享库函数 | [OK] 保留 |
| `install.bat` | 150 | 安装程序 | [OK] 保留 |
| `start.bat` | 135 | 交互菜单 | [OK] 重构 |
| `start_async_optimized.bat` | 47 | GPU异步启动 | [OK] 保留 |
| `start_engine.bat` | 7 | 快速启动重定向 | [OK] 简化为重定向 |
| `tools/cleanup_scheduler.bat` | 26 | 清理调度 | [OK] 保留 |
| `tools/fix_console_encoding.bat` | 36 | UTF-8编码设置 | [OK] 优化 |
| `tools/run_utf8.bat` | 14 | UTF-8命令包装 | [OK] 精简 |

### 1.2 问题识别

1. **代码重复**：`start.bat` 有内联代码，可使用 `common.bat` 函数

2. **功能重叠**：`start_engine.bat` 与 `start.bat` 功能重复

3. **UTF-8脚本冗余**：`fix_console_encoding.bat` 和 `run_utf8.bat` 有重复代码

### 1.3 优化措施

#### 1. 重构 `start.bat`

- 使用 `common.bat` 共享库

- 消除代码重复

- 菜单选项优化（移除重复的 Quick Run，添加 GPU Async Mode）

#### 2. 简化 `start_engine.bat`

```batch

@echo off
echo [INFO] Redirecting to main menu (start.bat)...
start "" cmd /c "start.bat"

```

现在作为快速启动重定向器使用。

#### 3. 优化 UTF-8 脚本

- `fix_console_encoding.bat`: 添加参考 `run_utf8.bat` 的提示

- `run_utf8.bat`: 精简为核心功能

### 1.4 优化后效果

| 指标 | 优化前 | 优化后 | 改进 |
|------|--------|--------|------|
| start.bat 代码行数 | 152 | 135 | -11% |
| start_engine.bat 代码行数 | 92 | 7 | -92% |
| UTF-8脚本总行数 | 61 | 50 | -18% |

---

## 二、CLI 文档分析

### 2.1 文档清单

**活跃文档**:

- `CLI_GUIDE.md` (8.43 KB) - 完整使用指南

- `docs/user-docs/cli_export_guide.md` (11.13 KB) - 导出指南

**已归档文档**:

- `docs/CLI_AUDIT_SUMMARY.md` (5.58 KB) → `docs/archive/history/`

- `docs/CLI_QUICK_REFERENCE.md` (4.58 KB) → `docs/archive/history/`

### 2.2 冗余消除

移除了内容重叠的文档：

- `CLI_AUDIT_SUMMARY.md` - 审计总结（历史文档）

- `CLI_QUICK_REFERENCE.md` - 快速参考（主要内容已被 `CLI_GUIDE.md` 覆盖）

### 2.3 文档更新

- 更新 `docs/DOCUMENT_INDEX.md` 统计信息

- 添加归档文档记录

---

## 三、目录结构

```

btc-collision-engine/
├── common.bat              # 共享库 (108行)
├── install.bat             # 安装程序 (150行)
├── start.bat               # 交互菜单 (135行) [重构]
├── start_async_optimized.bat # GPU异步 (47行)
├── start_engine.bat        # 重定向器 (7行) [简化]
├── tools/
│   ├── cleanup_scheduler.bat    # 清理调度 (26行)
│   ├── fix_console_encoding.bat  # UTF-8设置 (36行) [优化]
│   └── run_utf8.bat             # UTF-8包装 (14行) [精简]
└── docs/
    ├── CLI_GUIDE.md              # 活跃: 完整指南
    └── archive/history/
        ├── CLI_AUDIT_SUMMARY.md      # 归档: 审核总结
        └── CLI_QUICK_REFERENCE.md    # 归档: 快速参考

```

---

## 四、变更记录

| 日期 | 操作 | 详情 |
|------|------|------|
| 2026-05-12 | 重构 start.bat | 使用 common.bat，消除代码重复 |
| 2026-05-12 | 简化 start_engine.bat | 转为重定向脚本 |
| 2026-05-12 | 优化 UTF-8 脚本 | 精简代码，添加互相引用 |
| 2026-05-12 | 归档 CLI 文档 | CLI_AUDIT_SUMMARY.md, CLI_QUICK_REFERENCE.md |
| 2026-05-12 | 更新文档索引 | DOCUMENT_INDEX.md |

---

**审核完成**: 2026-05-12

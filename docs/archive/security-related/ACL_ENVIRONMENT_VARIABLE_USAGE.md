# Windows ACL环境变量控制使用说明

## 📋 概述

BTC碰撞引擎 v2.2.0 引入了环境变量 `BTC_ENGINE_SKIP_ACL`,用于控制Windows平台上的断点文件ACL(访问控制列表)设置行为。

---

## 🎯 环境变量

### 名称

```
BTC_ENGINE_SKIP_ACL
```

### 取值

| 值 | 行为 | 适用场景 |
|---|------|---------|
| `true` (不区分大小写) | 跳过ACL设置,使用Windows默认权限 | 测试环境、个人使用、遇到权限错误时 |
| `false` (不区分大小写) | 尝试使用icacls设置严格权限 | 生产环境、多用户系统、企业部署 |
| 未设置 | 等同于 `false`(尝试设置ACL) | 默认行为 |

### 示例值

```bash
✅ true, True, TRUE  → 跳过ACL
✅ false, False, FALSE → 使用ACL
```

---

## 🔧 配置方法

### 方法1: 命令行临时设置

#### PowerShell

```powershell
# 当前会话生效
$env:BTC_ENGINE_SKIP_ACL = "true"

# 运行程序
python key_collision_gui.py
```

#### CMD

```cmd
REM 当前会话生效
set BTC_ENGINE_SKIP_ACL=true

REM 运行程序
python key_collision_gui.py
```

### 方法2: 系统环境变量(永久生效)

#### Windows 10/11

1. 按 `Win + X`,选择"系统"
2. 点击"高级系统设置"
3. 点击"环境变量"
4. 在"用户变量"或"系统变量"中点击"新建"
5. 输入:
   - **变量名**: `BTC_ENGINE_SKIP_ACL`
   - **变量值**: `true` 或 `false`
6. 点击"确定"保存
7. **重启**所有已打开的终端窗口

#### 验证设置

```powershell
# PowerShell
$env:BTC_ENGINE_SKIP_ACL

# CMD
echo %BTC_ENGINE_SKIP_ACL%
```

### 方法3: 在批处理文件中设置

编辑 `start.bat` 或创建新的启动脚本:

```batch
@echo off
REM 设置环境变量
set BTC_ENGINE_SKIP_ACL=true

REM 启动程序
python key_collision_gui.py
```

### 方法4: Python代码中设置

```python
import os

# 在导入引擎之前设置
os.environ['BTC_ENGINE_SKIP_ACL'] = 'true'

# 然后导入和使用
from src.collision import KeyCollisionEngine
```

---

## 📖 使用场景

### 场景1: 测试环境(推荐跳过ACL)

**问题**: 测试时icacls导致权限错误

```
PermissionError: [WinError 5] 拒绝访问
```

**解决方案**:

```powershell
$env:BTC_ENGINE_SKIP_ACL = "true"
python -m unittest tests.test_checkpoint_comprehensive -v
```

### 场景2: 个人电脑(推荐跳过ACL)

**原因**:

- 单用户环境,无需严格权限
- 避免icacls命令开销
- 提高断点保存速度

**配置**:

```
BTC_ENGINE_SKIP_ACL = true
```

### 场景3: 多用户系统(推荐启用ACL)

**原因**:

- 多个用户共享同一台电脑
- 需要防止其他用户读取断点文件
- 断点文件包含目标地址等敏感信息

**配置**:

```
BTC_ENGINE_SKIP_ACL = false
```

### 场景4: 企业部署(推荐启用ACL)

**原因**:

- 符合安全合规要求
- 防止未授权访问
- 审计追踪要求

**配置**:

```
BTC_ENGINE_SKIP_ACL = false
```

### 场景5: 共享目录/网络驱动器(必须启用ACL)

**原因**:

- 共享目录权限通常较宽松
- 网络驱动器可能被多人访问
- 数据泄露风险较高

**配置**:

```
BTC_ENGINE_SKIP_ACL = false
```

---

## 🔍 如何判断是否需要ACL?

### 快速检查清单

| 问题 | 回答 | 建议 |
|------|------|------|
| 是否多人共用一台电脑? | 是 → | 启用ACL |
| 断点文件是否存储在共享目录? | 是 → | 启用ACL |
| 是否遇到权限错误? | 是 → | 跳过ACL |
| 是否在测试环境运行? | 是 → | 跳过ACL |
| 是否有合规性要求? | 是 → | 启用ACL |
| 是否是个人专用电脑? | 是 → | 跳过ACL |

### 决策流程图

```
开始
  ↓
是否多人共用电脑?
  ├─ 是 → 启用ACL (false)
  └─ 否 ↓
是否存储共享目录?
  ├─ 是 → 启用ACL (false)
  └─ 否 ↓
是否遇到权限错误?
  ├─ 是 → 跳过ACL (true)
  └─ 否 ↓
是否测试环境?
  ├─ 是 → 跳过ACL (true)
  └─ 否 ↓
个人使用?
  ├─ 是 → 跳过ACL (true)
  └─ 否 → 启用ACL (false)
```

---

## ⚠️ 安全说明

### 断点文件内容

**包含的信息**:

- ✅ 目标比特币地址列表
- ✅ 碰撞进度(已检查数量)
- ✅ 运行模式(random/range/brute_force)
- ✅ 匹配地址(不包含私钥)
- ✅ private_key_hash(哈希值,不可逆)

**不包含的信息**:

- ❌ 私钥本身
- ❌ 私钥的十六进制表示
- ❌ 任何可用于恢复私钥的信息

### 安全风险评估

| 环境 | 风险级别 | 建议 |
|------|---------|------|
| 个人电脑,跳过ACL | 🟢 低 | 可接受 |
| 多用户,跳过ACL | 🟡 中 | 建议启用ACL |
| 共享目录,跳过ACL | 🔴 高 | 必须启用ACL |
| 任何环境,启用ACL | 🟢 低 | 推荐 |

### 为什么断点文件需要保护?

虽然断点文件不包含私钥,但泄露以下信息仍有风险:

1. **目标地址**: 可能暴露你的研究兴趣或商业计划
2. **碰撞进度**: 可能泄露计算资源投入
3. **匹配地址**: 如果找到匹配,可能引起关注
4. **private_key_hash**: 虽然不可逆,但可用于验证特定私钥

---

## 📊 性能对比

### 断点保存性能

| 配置 | 平均耗时 | 说明 |
|------|---------|------|
| 跳过ACL | ~50ms | 仅文件I/O |
| 启用ACL | ~150ms | 文件I/O + icacls命令 |
| 差异 | ~100ms | 每30秒执行一次 |

**影响评估**:

- 自动保存间隔: 30秒(默认)
- 性能影响: 0.3% (100ms/30s)
- 结论: 性能影响**可忽略**

---

## 🐛 故障排除

### 问题1: 设置环境变量后不生效

**症状**: 程序仍然使用默认行为

**解决方案**:

```powershell
# 1. 验证环境变量
$env:BTC_ENGINE_SKIP_ACL

# 2. 如果未显示,重新设置
$env:BTC_ENGINE_SKIP_ACL = "true"

# 3. 重启程序(必须!)
```

### 问题2: icacls导致权限错误

**症状**:

```
PermissionError: [WinError 5] 拒绝访问
```

**解决方案**:

```powershell
# 跳过ACL设置
$env:BTC_ENGINE_SKIP_ACL = "true"
```

### 问题3: 文件被锁定无法删除

**症状**: icacls设置权限后文件无法删除

**解决方案**:

```powershell
# 方法1: 重置权限
icacls "文件路径" /reset

# 方法2: 跳过ACL(预防)
$env:BTC_ENGINE_SKIP_ACL = "true"
```

### 问题4: 如何查看当前ACL设置?

**检查文件权限**:

```powershell
# 查看文件权限
icacls "collision_checkpoint.json"

# 输出示例:
# collision_checkpoint.json DESKTOP-XXX\User:(R,W)
#                           NT AUTHORITY\SYSTEM:(I)(F)
#                           BUILTIN\Administrators:(I)(F)
```

---

## 📝 最佳实践

### 开发环境

```bash
BTC_ENGINE_SKIP_ACL = true
```

**原因**: 避免测试中的权限问题

### 生产环境 - 个人使用

```bash
BTC_ENGINE_SKIP_ACL = true
```

**原因**: 单用户环境,默认权限足够

### 生产环境 - 多用户

```bash
BTC_ENGINE_SKIP_ACL = false
```

**原因**: 需要严格权限控制

### 持续集成(CI/CD)

```bash
BTC_ENGINE_SKIP_ACL = true
```

**原因**: 自动化测试环境,无需ACL

### 企业部署

```bash
BTC_ENGINE_SKIP_ACL = false
```

**原因**: 符合安全合规要求

---

## 🔗 相关文档

- [断点续传功能测试报告](./checkpoint_comprehensive_test_report.md)
- [checkpoint_manager.py 代码审查](./code_review_acl.md)
- [v2.2.0 发布说明](../CHANGELOG.md)

---

## 📞 获取帮助

如果遇到问题:

1. **检查日志**: 查看DEBUG级别的日志

   ```
   Windows环境: 根据配置(BTC_ENGINE_SKIP_ACL=true)跳过ACL设置
   ```

   或

   ```
   Windows文件权限已设置(icacls)
   ```

2. **验证设置**:

   ```python
   import os
   print(os.environ.get('BTC_ENGINE_SKIP_ACL', '未设置'))
   ```

3. **查看文档**: 阅读本使用说明

4. **提交Issue**: 在GitHub提交问题报告

---

## 📅 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v2.2.0 | 2026-04-22 | 引入环境变量控制 |

---

**最后更新**: 2026-04-22  
**维护者**: BTC碰撞引擎开发团队

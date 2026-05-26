# Git 提交规范

> **版本**: v4.2.2 | **更新日期**: 2026-05-15 | **适用范围**: btc-collision-engine 代码仓库

---

## 1. Conventional Commits 格式

所有提交消息必须遵循 [Conventional Commits](https://www.conventionalcommits.org/zh-hans/) 规范：

```
<type>(<scope>): <description>

[可选的正文]

[可选的脚注]
```

### 1.1 类型（type）

| 类型 | 说明 | 示例 |
|------|------|------|
| `feat` | 新增功能 | `feat(gpu): 添加多GPU设备并发支持` |
| `fix` | 修复缺陷 | `fix(collision): 修复batch_size超出上限时的截断逻辑` |
| `docs` | 文档更新 | `docs(standards): 补充代码规范文档` |
| `refactor` | 代码重构（不改变功能）| `refactor(core): 提取密钥生成为独立模块` |
| `test` | 测试相关 | `test(gpu): 添加GPU Mock工厂模式测试` |
| `chore` | 构建/工具/维护 | `chore(deps): 升级coincurve到18.0.0` |
| `perf` | 性能优化 | `perf(kernel): 优化OpenCL内核编译缓存` |
| `style` | 代码风格（不影响逻辑）| `style: black格式化全部源码` |
| `ci` | CI/CD 配置 | `ci: 添加GitHub Actions工作流` |

### 1.2 范围（scope）

常用范围（与项目目录结构对应）：

| scope | 对应模块 | 说明 |
|-------|---------|------|
| `core` | `src/core/` | 核心密码学、密钥生成 |
| `collision` | `src/collision/` | 碰撞引擎 |
| `gpu` | `src/gpu/` | GPU 加速引擎 |
| `cli` | `src/cli/` | 命令行交互 |
| `monitoring` | `src/monitoring/` | 监控与告警 |
| `config` | `src/config/` | 配置管理 |
| `utils` | `src/utils/` | 工具函数 |
| `docs` | `docs/` | 项目文档 |
| `deps` | 依赖文件 | requirements.txt, pyproject.toml |

### 1.3 描述（description）

- 使用中文编写
- 不超过 50 个字符
- 使用现在时、祈使语气（"添加"而非"添加了"）
- 结尾不加句号

---

## 2. 提交消息模板和示例

### 2.1 提交消息模板

```
<type>(<scope>): <简短描述>

<详细说明（可选）>
- 变更点1
- 变更点2

<关联信息（可选）>
Refs: #<issue编号>
```

### 2.2 完整示例

#### 功能新增

```
feat(gpu): 添加Intel Arc A770专项适配配置

- 添加uint32 workaround标志用于Intel内核编译
- 配置默认batch_size为262144
- 添加GPUProfileLoader自动识别Intel设备

Refs: #42
```

#### 缺陷修复

```
fix(core): 修复密钥生成器在低熵环境下的弱密钥风险

P1-3修复: 添加熵池健康检查，Windows下通过CryptGenRandom
获取熵估计值，低于阈值时发出警告并暂停生成。

- 新增 _check_entropy_health() 方法
- 新增 entropy_check_enabled / min_entropy_bits 配置项
- 添加低熵环境自动告警逻辑
```

#### 文档更新

```
docs(standards): 补充代码规范与测试规范文档

- 新增 development_code_standards.md（Python代码规范）
- 新增 development_test_standards.md（测试规范）
- 新增 git_commit_standards.md（Git提交规范）
```

#### 重构

```
refactor(gpu): 提取GPU Mock为独立工厂模式

将分散在各测试文件中的GPU Mock代码提取到
tests/gpu_mock_factory.py，统一管理：
- GPUMockFactory 类提供标准化 Mock 对象
- 预置 NVIDIA/AMD/Intel 设备配置
- 一站式 patch_gpu_collision_engine() 上下文管理器
```

### 2.3 不合规示例

```
# ❌ 无类型前缀
修复了batch_size的bug

# ❌ 描述过于模糊
fix: 修复问题

# ❌ 混合中英文
fix(core): fix entropy check

# ❌ 一个提交包含多个不相关变更
feat: 添加GPU支持 + 修复地址解析 + 更新README
```

---

## 3. 分支策略

### 3.1 分支命名

| 分支类型 | 命名格式 | 说明 | 示例 |
|---------|---------|------|------|
| 主干 | `main` | 生产就绪代码 | — |
| 开发 | `develop` | 开发集成分支 | — |
| 功能 | `feature/<scope>-<描述>` | 新功能开发 | `feature/gpu-intel-arc` |
| 修复 | `hotfix/<版本>-<描述>` | 紧急修复 | `hotfix/3.1.1-batch-size` |
| 发布 | `release/<版本号>` | 版本发布准备 | `release/3.1.2` |

### 3.2 分支工作流

```
main ──────────────────────────────────── 合并 ──► tag: v4.2.1
  │                                            │
  └── develop ──────────────── merge ──────────┘
        │                           │
        ├── feature/gpu-intel-arc ──┘
        ├── feature/cli-audit ──────┘
        └── feature/health-check ───┘
```

**规则**：

1. `main` 分支始终可部署，禁止直接推送
2. 所有变更通过 PR 合并到 `develop`，再从 `develop` 合并到 `main`
3. 紧急修复从 `main` 创建 `hotfix/` 分支，修复后同时合并回 `main` 和 `develop`
4. 功能分支从 `develop` 创建，完成后提 PR 回 `develop`
5. 功能分支生命周期不超过 2 周，长期分支需定期 rebase

### 3.3 分支保护

- `main`：强制 PR 审查 + 通过 CI
- `develop`：强制 PR 审查 + 通过 CI
- 功能分支：无保护，开发者自管

---

## 4. 版本标签命名

### 4.1 语义化版本（SemVer）

格式：`vX.Y.Z`

| 位 | 含义 | 变更时机 |
|----|------|---------|
| X（主版本）| 不兼容的 API 变更 | 架构重构、接口大改 |
| Y（次版本）| 向后兼容的功能新增 | 新增 GPU 厂商支持、新增 CLI 命令 |
| Z（修订号）| 向后兼容的缺陷修复 | Bug 修复、性能优化、文档更新 |

### 4.2 项目版本历史（参考 CHANGELOG.md）

```
v4.2.1 - 2026-04-25   清理与维护（删除临时文件、修复重复导入）
v4.2.1 - 2026-04-23   新增自动化安装、健康检查、数据清理
v4.2.1 - ...          新增功能版本
v4.2.1 - ...          主版本升级
```

### 4.3 打标签流程

```bash
# 1. 确认 develop 分支所有变更已合并到 main
git checkout main
git pull origin main

# 2. 更新 pyproject.toml 中的 version 字段
# version = "3.1.2"

# 3. 提交版本号变更
git commit -m "chore: bump version to 3.1.2"

# 4. 创建带注释的标签
git tag -a v4.2.1 -m "Release v4.2.1: 清理与维护"

# 5. 推送标签
git push origin v4.2.1
```

---

## 5. PR 合并策略

### 5.1 PR 模板

```markdown
## 变更说明
<!-- 简述本次变更的目的和内容 -->

## 变更类型
- [ ] feat: 新功能
- [ ] fix: 缺陷修复
- [ ] refactor: 重构
- [ ] docs: 文档
- [ ] test: 测试
- [ ] chore: 构建/工具

## 影响范围
<!-- 列出受影响的模块 -->

## 测试验证
- [ ] 单元测试通过
- [ ] 集成测试通过
- [ ] 手动验证通过

## 关联 Issue
<!-- Closes #xxx / Refs #xxx -->
```

### 5.2 合并方式

| 方式 | 使用场景 | 说明 |
|------|---------|------|
| **Squash Merge** | 功能分支 → `develop` | 压缩为一个提交，保持历史整洁 |
| **Merge Commit** | `develop` → `main` | 保留完整历史，便于回溯 |
| **Rebase Merge** | 不推荐 | 仅在特殊情况下使用 |

### 5.3 审查要求

- 至少 1 人 Review 通过
- CI 全部通过（lint + test + coverage）
- 无合并冲突
- CHANGELOG.md 已更新（功能/修复类 PR）

---

## 6. CHANGELOG.md 维护规范

### 6.1 格式

遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，与项目现有格式一致：

```markdown
## [X.Y.Z] - YYYY-MM-DD

### 新增
- 新功能描述（引用文件路径或 Issue 编号）

### 修复
- 缺陷修复描述

### 变更
- 行为变更描述

### 清理与维护
- 清理、重构、文档更新等
```

### 6.2 分类规则

| 分类 | 说明 | 示例 |
|------|------|------|
| **新增** | 新增功能、模块、接口 | 新增 GPU 厂商预设、新增 CLI 命令 |
| **修复** | Bug 修复 | 修复批次大小溢出、修复地址解析错误 |
| **变更** | 向后兼容的行为变更 | 调整默认 batch_size、修改配置格式 |
| **清理与维护** | 非功能性变更 | 删除临时文件、修复重复导入、文档更新 |

### 6.3 维护时机

- **功能/修复 PR**：在 PR 中同步更新 CHANGELOG.md 的 `[Unreleased]` 部分
- **版本发布时**：将 `[Unreleased]` 替换为具体版本号和日期
- **条目格式**：每条变更一行，以 `-` 开头，可附带文件路径或 Issue 编号

```markdown
### 新增

- 🚀 **Windows安装脚本** (`scripts/install/install.bat`): 7步自动化安装流程
- 🏥 **健康检查模块** (`src/utils/health_check.py`): 依赖验证、磁盘空间检查

### 修复

- 修复 `src/collision/types.py` 中重复的 typing 导入
- 修复 `src/gpu/device.py` 中厂商识别逻辑错误（Refs: #38）
```

---

## 7. 提交前检查清单

每次提交前确认：

- [ ] 提交消息符合 Conventional Commits 格式
- [ ] 一个提交只做一件事（不混合功能/修复/重构）
- [ ] 代码通过 `black` 格式化和 `flake8` 检查
- [ ] 相关测试通过（`pytest tests/ -v`）
- [ ] 功能/修复类变更已更新 CHANGELOG.md
- [ ] 无调试代码残留（`print()`、`breakpoint()`、临时文件路径）
- [ ] 敏感信息未提交（私钥、密码、API Token）

---

*参考文件*：

- `CHANGELOG.md` — 版本历史与变更记录
- `pyproject.toml` — 当前版本号 `version = "5.0.0"`
- `.github/workflows/ci.yml` — CI 工作流配置
- `.pre-commit-config.yaml` — 提交前自动检查

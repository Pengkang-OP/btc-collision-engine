# 文档管理工作流指南

> **版本**: v1.2.0 | **创建日期**: 2026-04-21  
> **目的**: 建立文档自动化、版本管理和更新检查的完整工作流


## 目录

- [📋 目录](#-目录)
- [文档自动化生成机制](#文档自动化生成机制)
  - [1. API文档自动生成](#1-api文档自动生成)
    - [从代码注释生成API文档](#从代码注释生成api文档)
- [自动化脚本](#自动化脚本)
- [2. CHANGELOG自动生成](#2-changelog自动生成)
    - [从Git Commits生成](#从git-commits生成)
- [半自动生成脚本](#半自动生成脚本)
- [3. 文档索引自动更新](#3-文档索引自动更新)
- [文档版本管理规范](#文档版本管理规范)
  - [1. 文档版本标识](#1-文档版本标识)
- [2. 版本同步策略](#2-版本同步策略)
    - [文档版本与代码版本关联](#文档版本与代码版本关联)
    - [版本更新检查清单](#版本更新检查清单)
  - [3. 文档变更追踪](#3-文档变更追踪)
    - [使用Git追踪文档变更](#使用git追踪文档变更)
- [文档变更日志](#文档变更日志)
- [文档变更记录](#文档变更记录)
  - [4. 文档归档策略](#4-文档归档策略)
    - [何时归档文档](#何时归档文档)
    - [归档流程](#归档流程)
- [文档更新检查清单](#文档更新检查清单)
  - [日常更新检查清单](#日常更新检查清单)
    - [小更新 (<30%内容变更)](#小更新-30内容变更)
    - [大更新 (≥30%内容变更)](#大更新-30内容变更)
  - [版本发布检查清单](#版本发布检查清单)
    - [必检项](#必检项)
    - [选检项](#选检项)
  - [定期检查清单](#定期检查清单)
    - [每月检查](#每月检查)
    - [每季度检查](#每季度检查)
- [工具使用指南](#工具使用指南)
  - [1. 文档质量检查工具](#1-文档质量检查工具)
- [2. 断裂链接检查工具](#2-断裂链接检查工具)
- [3. 文档统计工具](#3-文档统计工具)
- [CI/CD集成](#cicd集成)
  - [GitHub Actions配置](#github-actions配置)
  - [Pre-commit Hook集成](#pre-commit-hook集成)
- [最佳实践](#最佳实践)
  - [1. 文档编写最佳实践](#1-文档编写最佳实践)
  - [2. 文档维护最佳实践](#2-文档维护最佳实践)
  - [3. 工具使用最佳实践](#3-工具使用最佳实践)
- [相关文档](#相关文档)
---

## 📋 目录

- [文档自动化生成机制](#文档自动化生成机制)
- [文档版本管理规范](#文档版本管理规范)
- [文档更新检查清单](#文档更新检查清单)
- [工具使用指南](#工具使用指南)
- [CI/CD集成](#cicd集成)

---

## 文档自动化生成机制

### 1. API文档自动生成

#### 从代码注释生成API文档

项目使用docstring标准，可以自动生成API文档：

```bash
# 安装pdoc3
pip install pdoc3

# 生成API文档
pdoc --html --output-dir docs/api src/

# 查看生成的文档
# 打开 docs/api/src/index.html
```markdown

## 自动化脚本

```python
#!/usr/bin/env python
# tools/generate_api_docs.py
"""自动生成API文档"""

import subprocess
import sys
from pathlib import Path

def generate_api_docs():
    """生成API文档"""
    output_dir = Path("docs/api")
    output_dir.mkdir(exist_ok=True)
    
    cmd = [
        sys.executable, "-m", "pdoc",
        "--html",
        "--output-dir", str(output_dir),
        "src/"
    ]
    
    print("🔧 正在生成API文档...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        print(f"✅ API文档已生成: {output_dir}")
    else:
        print(f"❌ 生成失败: {result.stderr}")
        sys.exit(1)

if __name__ == "__main__":
    generate_api_docs()
```markdown

## 2. CHANGELOG自动生成

#### 从Git Commits生成

```bash
# 安装git-changelog
pip install git-changelog

# 生成CHANGELOG
git-changelog --output CHANGELOG.md

# 或自定义格式
git-changelog \
  --convention conventional \
  --parse-refs \
  --output CHANGELOG.md
```markdown

## 半自动生成脚本

```python
#!/usr/bin/env python
# tools/generate_changelog.py
"""从git commits生成CHANGELOG草稿"""

import subprocess
from datetime import datetime

def get_commits_since(tag):
    """获取指定tag之后的commits"""
    cmd = [
        "git", "log", f"{tag}..HEAD",
        "--pretty=format:%h %s (%an, %ad)",
        "--date=short"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout.strip().split('\n')

def categorize_commits(commits):
    """按类型分类commits"""
    categories = {
        'feat': [],
        'fix': [],
        'docs': [],
        'refactor': [],
        'other': []
    }
    
    for commit in commits:
        if 'feat:' in commit.lower():
            categories['feat'].append(commit)
        elif 'fix:' in commit.lower():
            categories['fix'].append(commit)
        elif 'docs:' in commit.lower():
            categories['docs'].append(commit)
        elif 'refactor:' in commit.lower():
            categories['refactor'].append(commit)
        else:
            categories['other'].append(commit)
    
    return categories

def generate_changelog_draft():
    """生成CHANGELOG草稿"""
    commits = get_commits_since("v1.2.0")
    categories = categorize_commits(commits)
    
    print(f"# [未发布] - {datetime.now().strftime('%Y-%m-%d')}\n")
    
    if categories['feat']:
        print("### 新增\n")
        for commit in categories['feat']:
            print(f"- {commit}")
        print()
    
    if categories['fix']:
        print("### 修复\n")
        for commit in categories['fix']:
            print(f"- {commit}")
        print()
    
    if categories['docs']:
        print("### 文档\n")
        for commit in categories['docs']:
            print(f"- {commit}")
        print()

if __name__ == "__main__":
    generate_changelog_draft()
```markdown

## 3. 文档索引自动更新

```python
#!/usr/bin/env python
# tools/update_doc_index.py
"""自动更新DOCUMENT_INDEX.md"""

import re
from pathlib import Path
from datetime import datetime

def scan_docs(docs_dir="docs"):
    """扫描文档目录"""
    docs_path = Path(docs_dir)
    doc_files = list(docs_path.glob("*.md"))
    
    doc_info = []
    for doc_file in doc_files:
        if doc_file.name == "DOCUMENT_INDEX.md":
            continue
        
        content = doc_file.read_text(encoding='utf-8')
        
        # 提取标题
        title_match = re.search(r'^#\s+(.+)', content, re.MULTILINE)
        title = title_match.group(1) if title_match else doc_file.name
        
        # 提取版本信息
        version_match = re.search(r'[*]*[*]版本[*]*[*]:\s*(v?[\d.]+)', content)
        version = version_match.group(1) if version_match else "未知"
        
        # 提取更新日期
        date_match = re.search(r'[*]*[*]最后更新[*]*[*]:\s*([\d-]+)', content)
        date = date_match.group(1) if date_match else "未知"
        
        doc_info.append({
            'file': doc_file.name,
            'title': title,
            'version': version,
            'date': date,
            'size': f"{doc_file.stat().st_size / 1024:.1f}KB"
        })
    
    return doc_info

def update_index(doc_info):
    """更新DOCUMENT_INDEX.md"""
    print("📋 文档扫描结果:\n")
    
    for doc in sorted(doc_info, key=lambda x: x['file']):
        print(f"📄 {doc['file']}")
        print(f"   标题: {doc['title']}")
        print(f"   版本: {doc['version']}")
        print(f"   更新: {doc['date']}")
        print(f"   大小: {doc['size']}")
        print()
    
    print(f"\n✅ 共扫描 {len(doc_info)} 个文档")
    print(f"📅 扫描时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    doc_info = scan_docs()
    update_index(doc_info)
```python

---

## 文档版本管理规范

### 1. 文档版本标识

每个核心文档应在开头包含版本信息：

```markdown
# 文档标题

> **版本**: v1.2.0 | **最后更新**: 2026-04-21  
> **适用代码版本**: >= v1.2.0  
> **面向**: 用户/开发者/维护者
```markdown

## 2. 版本同步策略

#### 文档版本与代码版本关联

| 代码版本 | 文档操作 | 说明 |
|---------|---------|------|
| 主版本号变更 (1.x → 2.0) | 全面审查和更新 | 可能有破坏性变更 |
| 次版本号变更 (1.1 → 1.2) | 更新新增功能文档 | 向下兼容的功能新增 |
| 修订号变更 (1.1.1 → 1.1.2) | 更新修复相关文档 | 向下兼容的问题修正 |

#### 版本更新检查清单

当代码版本更新时：

- [ ] 更新所有文档的版本标识
- [ ] 检查新增功能的文档
- [ ] 检查修改功能的文档
- [ ] 检查弃用功能的文档
- [ ] 更新CHANGELOG.md
- [ ] 更新README.md（如需要）
- [ ] 更新DOCUMENT_INDEX.md

### 3. 文档变更追踪

#### 使用Git追踪文档变更

```bash
# 查看文档的完整历史
git log --follow -- docs/architecture.md

# 查看特定版本的文档
git show v1.2.0:docs/architecture.md

# 比较两个版本的文档差异
git diff v1.1.0..v1.2.0 -- docs/architecture.md

# 查看谁修改了文档
git blame docs/architecture.md
```markdown

## 文档变更日志

为重要文档维护变更日志：

```markdown
## 文档变更记录

| 版本 | 日期 | 变更内容 | 作者 |
|------|------|---------|------|
| v1.2.0 | 2026-04-21 | 全面重构，添加GPU架构 | @author |
| v1.1.0 | 2026-03-15 | 添加监控系统章节 | @author |
| v1.0.0 | 2026-01-01 | 初始版本 | @author |
```yaml

### 4. 文档归档策略

#### 何时归档文档

- 功能已移除或重大重构
- 文档内容已过时且不再适用
- 有更好的替代文档
- 团队达成共识

#### 归档流程

1. 评估文档价值和历史意义
2. 移动至 `docs/archive/` 目录
3. 在文档开头添加归档标记：

```markdown
> ⚠️ **归档文档**: 本文档已归档，仅供参考。  
> **归档日期**: 2026-04-21  
> **替代文档**: [新文档链接](new-doc.md)
```python

4. 更新DOCUMENT_INDEX.md
5. 在CHANGELOG.md中记录

---

## 文档更新检查清单

### 日常更新检查清单

#### 小更新 (<30%内容变更)

- [ ] 更新文档版本号和日期
- [ ] 检查链接有效性
- [ ] 验证代码示例
- [ ] 确认与代码同步
- [ ] 提交PR并说明变更

#### 大更新 (≥30%内容变更)

- [ ] 创建Issue讨论更新计划
- [ ] 更新文档结构（如需要）
- [ ] 重写或新增内容
- [ ] 更新所有示例和截图
- [ ] 更新版本兼容性说明
- [ ] 更新CHANGELOG.md
- [ ] 更新DOCUMENT_INDEX.md
- [ ] 提交完整审查流程

### 版本发布检查清单

当发布新版本时：

#### 必检项

- [ ] 更新所有核心文档的版本标识
- [ ] 检查新增功能的文档覆盖
- [ ] 检查修改功能的文档更新
- [ ] 检查弃用功能的文档标记
- [ ] 验证所有文档链接
- [ ] 运行文档质量检查工具
- [ ] 运行断裂链接检查工具
- [ ] 更新CHANGELOG.md
- [ ] 更新README.md版本徽章
- [ ] 更新DOCUMENT_INDEX.md统计

#### 选检项

- [ ] 生成新的API文档
- [ ] 更新架构图和流程图
- [ ] 更新截图和示例
- [ ] 添加迁移指南（如需要）
- [ ] 添加升级指南（如需要）
- [ ] 更新常见问题
- [ ] 更新故障排除指南

### 定期检查清单

#### 每月检查

- [ ] 运行文档质量检查
- [ ] 检查断裂链接
- [ ] 更新过期内容
- [ ] 收集用户反馈
- [ ] 统计文档使用数据

#### 每季度检查

- [ ] 全面文档审查
- [ ] 更新文档规范
- [ ] 优化工具脚本
- [ ] 培训新审查者
- [ ] 回顾和改进流程

---

## 工具使用指南

### 1. 文档质量检查工具

```bash
# 基本使用
python tools/check_document_quality.py

# 输出示例:
# 🔍 开始检查文档质量...
# 
# 📁 找到 32 个核心文档
# 
# ✅ architecture.md - 质量评分: 9.5/10
# ✅ api-reference.md - 质量评分: 9.2/10
# ⚠️  getting-started.md - 质量评分: 7.8/10
#    ⚠️  建议添加版本信息
# 
# ============================================================
# 📊 文档质量检查报告
# ============================================================
# 
# 核心文档总数: 32
# 平均质量评分: 8.9/10
# 
# 质量分布:
#   ✅ 优秀 (≥8.5): 28 个
#   ⚠️  良好 (7.0-8.4): 4 个
#   ❌ 需改进 (<7.0): 0 个
# 
# 总体评价: ✅ 优秀
# ============================================================
```markdown

## 2. 断裂链接检查工具

```bash
# 基本使用（仅检查内部链接）
python tools/check_broken_links.py

# 检查外部链接（耗时）
python tools/check_broken_links.py --check-external

# 指定文档目录
python tools/check_broken_links.py --docs-dir docs

# 输出示例:
# 🔍 开始检查文档链接...
# 
# 📁 找到 75 个文档
# 
# ============================================================
# 📊 链接检查报告
# ============================================================
# 
# 📁 检查文件数: 75
# 🔗 总链接数: 1,234
# ❌ 断裂链接: 3
# 
# ⚠️  断裂链接详情:
# 
# 📄 architecture.md:
#    行 45: [旧链接](old-file.md)
#       原因: 文件不存在: /path/to/old-file.md
# 
# 📄 api-reference.md:
#    行 120: [外部链接](https://example.com/404)
#       原因: HTTP 404
# 
# ============================================================
```markdown

## 3. 文档统计工具

```bash
# 生成文档统计报告
python tools/generate_doc_stats.py

# 输出示例:
# 📊 文档统计报告 - 2026-04-21
# 
# 核心文档: 32个
# 归档文档: 43个
# 总行数: 45,678
# 总大小: 1.2MB
# 平均质量评分: 8.9/10
# 断裂链接: 3个
# 
# 文档分类:
#   - 快速开始: 3个
#   - 架构设计: 5个
#   - 功能文档: 18个
#   - 配置部署: 2个
#   - 界面使用: 1个
#   - 故障排除: 1个
# 
# 最近更新:
#   - DOCUMENT_INDEX.md (2026-04-21)
#   - CHANGELOG.md (2026-04-21)
#   - README.md (2026-04-21)
```python

---

## CI/CD集成

### GitHub Actions配置

创建 `.github/workflows/doc-check.yml`:

```yaml
name: Document Quality Check

on:
  pull_request:
    paths:
      - 'docs/**'
      - '*.md'
      - 'tools/check_*.py'
  schedule:
    # 每周一早上9点运行
    - cron: '0 9 * * 1'

jobs:
  check-docs:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      
      - name: Install dependencies
        run: |
          pip install requests
      
      - name: Check Document Quality
        run: python tools/check_document_quality.py
      
      - name: Check Broken Links
        run: python tools/check_broken_links.py
      
      - name: Generate Stats
        run: python tools/generate_doc_stats.py
      
      - name: Upload Results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: doc-check-results
          path: doc-results/
```markdown

### Pre-commit Hook集成

在 `.pre-commit-config.yaml` 中添加：

```yaml
repos:
  # ... 其他hooks ...
  
  - repo: local
    hooks:
      - id: check-document-quality
        name: Check Document Quality
        entry: python tools/check_document_quality.py
        language: system
        files: 'docs/.*\.md$'
        pass_filenames: false
      
      - id: check-broken-links
        name: Check Broken Links
        entry: python tools/check_broken_links.py
        language: system
        files: 'docs/.*\.md$'
        pass_filenames: false
```

---

## 最佳实践

### 1. 文档编写最佳实践

- ✅ 先写大纲，再填充内容
- ✅ 使用模板保持一致性
- ✅ 包含完整可运行的示例
- ✅ 定期更新保持时效性
- ✅ 使用工具和自动化检查质量

### 2. 文档维护最佳实践

- ✅ 小变更直接PR，大变更先讨论
- ✅ 使用检查清单确保质量
- ✅ 及时响应审查意见
- ✅ 保持文档与代码同步
- ✅ 定期回顾和改进流程

### 3. 工具使用最佳实践

- ✅ 在提交前运行质量检查
- ✅ 在PR中附带检查报告
- ✅ 定期运行全量检查
- ✅ 持续改进工具脚本
- ✅ 集成到CI/CD流程

---

## 相关文档

- [CONTRIBUTING.md](../CONTRIBUTING.md) - 贡献指南
- [DOCUMENT_REVIEW_PROCESS.md](DOCUMENT_REVIEW_PROCESS.md) - 文档审查流程
- [DOCUMENT_INDEX.md](DOCUMENT_INDEX.md) - 文档索引
- [CHANGELOG.md](../CHANGELOG.md) - 变更日志

---

**文档版本**: v1.0  
**创建日期**: 2026-04-21  
**最后更新**: 2026-04-21  
**维护者**: BTC Collision Team

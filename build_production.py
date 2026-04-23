#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BTC碰撞引擎 - 生产环境打包脚本

功能:
- 清理开发和测试文件
- 只保留生产环境必需文件
- 打包到指定目录
- 生成版本信息文件

使用方法:
    python build_production.py --output F:\Qoder\btc-collision-tools
"""

import os
import sys
import shutil
import argparse
import json
import subprocess
from pathlib import Path
from datetime import datetime


# 生产环境必需的文件/目录
PRODUCTION_INCLUDE = [
    # 核心应用
    "key_collision.py",
    "key_collision_cli.py",
    # M-NEW3修复: key_collision_gui.py 已移除，项目转为纯 CLI 架构
    "start.bat",
    
    # 配置文件
    "config.json",
    "config.example.json",
    "config.intel_arc.json",
    "config.optimized.json",
    "requirements.txt",
    "requirements.lock",
    "valid_addresses.txt",
    
    # 源代码
    "src/",
    
    # 文档
    "README.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "docs/",
    
    # 工具
    "tools/utf8_helper.py",
    "tools/retry_helper.py",
    
    # 脚本
    "scripts/",
]

# 需要排除的文件/目录
PRODUCTION_EXCLUDE = [
    # 版本控制
    ".git/",
    ".github/",
    
    # Python缓存
    "__pycache__/",
    "*.pyc",
    "*.pyo",
    ".pytest_cache/",
    ".benchmarks/",
    
    # 测试相关
    "tests/",
    "test_*.py",
    "test_*.txt",
    "test_*.log",
    "test_data/",
    "test_results/",
    
    # 开发工具文档
    "docs/archive/",
    "tools/test_*.py",
    "tools/check_*.py",
    "tools/fix_*.py",
    "tools/add_*.py",
    "tools/batch_*.py",
    "tools/permanent_*.ps1",
    "tools/run_utf8.*",
    "tools/setup_*.ps1",
    "tools/configure_*.py",
    "tools/diagnose_*.py",
    "tools/monitor_*.py",
    "tools/realtime_*.py",
    "tools/live_*.py",
    "tools/quality_*.py",
    "tools/collect_*.py",
    "tools/optimize_*.py",
    "tools/update_*.py",
    "tools/scoring_*.json",
    "tools/pre-commit-docs.sh",
    "tools/CODE_REVIEW_*.md",
    "tools/UTF8_*.md",
    "tools/README.md",
    
    # 日志和数据
    "logs/",
    "data_logs/",
    "monitoring_data/",
    "*.log",
    
    # IDE配置
    ".vscode/",
    ".qoder/",
    ".qodo/",
    ".trae/",
    "*.swp",
    "*.swo",
    
    # 其他
    "build/",
    "dist/",
    "*.egg-info/",
    ".env",
    ".env.local",
]


def get_git_info():
    """获取Git版本信息"""
    try:
        # 获取当前commit hash
        commit_hash = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL
        ).decode().strip()
        
        # 获取简短hash
        short_hash = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL
        ).decode().strip()
        
        # 获取最近标签
        try:
            tag = subprocess.check_output(
                ["git", "describe", "--tags", "--abbrev=0"],
                stderr=subprocess.DEVNULL
            ).decode().strip()
        except:
            tag = "v2.2.0"
        
        # 获取提交数量
        commit_count = subprocess.check_output(
            ["git", "rev-list", "--count", "HEAD"],
            stderr=subprocess.DEVNULL
        ).decode().strip()
        
        # 获取分支名
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            stderr=subprocess.DEVNULL
        ).decode().strip()
        
        return {
            "commit_hash": commit_hash,
            "short_hash": short_hash,
            "tag": tag,
            "commit_count": commit_count,
            "branch": branch,
        }
    except Exception as e:
        print(f"⚠️  无法获取Git信息: {e}")
        return {
            "commit_hash": "unknown",
            "short_hash": "unknown",
            "tag": "v2.2.0",
            "commit_count": "unknown",
            "branch": "unknown",
        }


def should_exclude(filepath: Path, base_dir: Path) -> bool:
    """判断文件是否应该排除"""
    rel_path = filepath.relative_to(base_dir)
    rel_str = str(rel_path).replace('\\', '/')
    
    for pattern in PRODUCTION_EXCLUDE:
        # 目录匹配
        if pattern.endswith('/'):
            dir_name = pattern.rstrip('/')
            if rel_str == dir_name or rel_str.startswith(dir_name + '/'):
                return True
        # 通配符匹配
        elif '*' in pattern:
            import fnmatch
            if fnmatch.fnmatch(rel_str, pattern) or fnmatch.fnmatch(filepath.name, pattern):
                return True
        # 精确匹配
        else:
            if rel_str == pattern:
                return True
    
    return False


def copy_production_files(source_dir: Path, target_dir: Path):
    """复制生产环境文件"""
    copied_count = 0
    skipped_count = 0
    total_size = 0
    
    print(f"\n📦 开始复制生产环境文件...")
    print(f"   源目录: {source_dir}")
    print(f"   目标目录: {target_dir}")
    print()
    
    for item in source_dir.iterdir():
        if should_exclude(item, source_dir):
            skipped_count += 1
            continue
        
        target_item = target_dir / item.relative_to(source_dir)
        
        try:
            if item.is_dir():
                if target_item.exists():
                    shutil.rmtree(target_item)
                shutil.copytree(item, target_item)
                copied_count += 1
            else:
                target_item.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, target_item)
                copied_count += 1
                total_size += item.stat().st_size
        except Exception as e:
            print(f"  ⚠️  复制失败 {item.name}: {e}")
    
    return copied_count, skipped_count, total_size


def generate_version_info(target_dir: Path, git_info: dict):
    """生成版本信息文件"""
    version_info = {
        "version": git_info["tag"],
        "build_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "git": git_info,
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "platform": sys.platform,
    }
    
    version_file = target_dir / "VERSION.json"
    with open(version_file, "w", encoding="utf-8") as f:
        json.dump(version_info, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ 版本信息已生成: {version_file}")
    return version_info


def generate_release_notes(target_dir: Path, version_info: dict):
    """生成发布说明"""
    release_notes = f"""# BTC碰撞引擎 生产环境版本

## 版本信息

- **版本号**: {version_info['version']}
- **构建时间**: {version_info['build_time']}
- **Git Commit**: {version_info['git']['short_hash']}
- **Python版本**: {version_info['python_version']}
- **平台**: {version_info['platform']}

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置文件

复制并编辑配置文件:

```bash
copy config.example.json config.json
```

编辑 `config.json` 设置您的参数。

### 3. 运行

**命令行模式**:
```bash
python key_collision_cli.py
```

**直接运行**:
```bash
start.bat
```

## 目录结构

```
btc-collision-engine/
├── key_collision.py          # 主程序
├── key_collision_cli.py      # CLI入口
# M-NEW3修复: key_collision_gui.py 已移除，项目转为纯 CLI 架构
├── start.bat                 # Windows启动脚本
├── config.json               # 配置文件
├── requirements.txt          # Python依赖
├── src/                      # 源代码
├── docs/                     # 文档
├── tools/                    # 工具脚本
└── scripts/                  # 辅助脚本
```

## 系统要求

- Python 3.8+
- Windows 10/11 或 Linux
- (可选) OpenCL兼容的GPU

## 文档

- 完整文档: `docs/` 目录
- 变更日志: `CHANGELOG.md`
- 贡献指南: `CONTRIBUTING.md`

## 技术支持

如有问题,请参考:
- `docs/troubleshooting.md` - 故障排除
- `docs/getting-started.md` - 入门指南

---

**构建时间**: {version_info['build_time']}
**版本**: {version_info['version']}
"""
    
    notes_file = target_dir / "RELEASE_NOTES.md"
    with open(notes_file, "w", encoding="utf-8") as f:
        f.write(release_notes)
    
    print(f"✅ 发布说明已生成: {notes_file}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="BTC碰撞引擎生产环境打包工具")
    parser.add_argument(
        "--output",
        required=True,
        help="输出目录路径"
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="清理已存在的输出目录"
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="自动确认所有提示"
    )
    
    args = parser.parse_args()
    
    source_dir = Path(__file__).parent.absolute()
    target_dir = Path(args.output)
    
    print("=" * 80)
    print("🚀 BTC碰撞引擎 - 生产环境打包工具")
    print("=" * 80)
    
    # 获取Git信息
    print("\n📋 获取版本信息...")
    git_info = get_git_info()
    print(f"   版本: {git_info['tag']}")
    print(f"   Commit: {git_info['short_hash']}")
    print(f"   分支: {git_info['branch']}")
    
    # 清理目标目录
    if target_dir.exists():
        if args.clean or args.yes:
            print(f"\n🧹 清理目标目录: {target_dir}")
            try:
                shutil.rmtree(target_dir)
            except PermissionError:
                # Windows .git目录权限问题,使用命令行删除
                import subprocess
                subprocess.run(["cmd", "/c", "rmdir", "/s", "/q", str(target_dir)], 
                             capture_output=True)
        else:
            print(f"\n⚠️  目标目录已存在: {target_dir}")
            response = input("   是否继续? (y/n): ")
            if response.lower() != "y":
                print("❌ 取消打包")
                return
            shutil.rmtree(target_dir)
    
    # 创建目标目录
    target_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n✅ 创建目标目录: {target_dir}")
    
    # 复制文件
    copied, skipped, size = copy_production_files(source_dir, target_dir)
    
    # 生成版本信息
    version_info = generate_version_info(target_dir, git_info)
    
    # 生成发布说明
    generate_release_notes(target_dir, version_info)
    
    # 打印总结
    print("\n" + "=" * 80)
    print("✅ 打包完成!")
    print("=" * 80)
    print(f"\n📊 统计信息:")
    print(f"   复制文件/目录: {copied}")
    print(f"   跳过文件/目录: {skipped}")
    print(f"   总大小: {size / 1024 / 1024:.2f} MB")
    print(f"\n📁 输出目录: {target_dir}")
    print(f"\n🎯 下一步:")
    print(f"   1. 在输出目录中安装依赖: pip install -r requirements.txt")
    print(f"   2. 编辑配置文件: config.json")
    print(f"   3. 运行程序: python key_collision_cli.py")  # M-NEW3修复: 更新为CLI入口
    print("=" * 80)


if __name__ == "__main__":
    main()

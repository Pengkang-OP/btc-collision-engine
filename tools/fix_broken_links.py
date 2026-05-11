#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
断裂链接修复工具

自动修复文档中的断裂链接：
1. 更新指向已删除文档的链接
2. 修正错误的相对路径
3. 修复file://协议链接

使用方法:
    python tools/fix_broken_links.py [--dry-run]
"""

import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple
from urllib.parse import urlparse

# 修复Windows控制台编码问题 - 使用共享模块
from tools.utf8_helper import setup_windows_utf8
setup_windows_utf8()


# 已删除文档到归档文档的映射（保留作为后备）
DELETED_TO_ARCHIVE = {
    'data-logging-guide.md': 'archive/日志相关/',
    'factory-function-guide.md': 'archive/代码质量/',
    'gpu-engine-optimization.md': 'archive/GPU优化/',
}

# 文件名到实际路径的映射（保留作为后备）
FILE_PATH_MAP = {
    # 安全相关文档
    '2026-04-20_SecureKeyManager优化报告.md': 'docs/archive/安全相关/2026-04-20_SecureKeyManager优化报告.md',
    '2026-04-20_SecureKeyManager审查修复.md': 'docs/archive/安全相关/2026-04-20_SecureKeyManager审查修复.md',
    '2026-04-20_SecureKeyManager测试报告.md': 'docs/archive/安全相关/2026-04-20_SecureKeyManager测试报告.md',
}


def auto_detect_archive_path(filename: str, docs_dir: Path) -> str | None:
    """自动扫描archive目录查找文件

    Args:
        filename: 文件名
        docs_dir: 文档目录路径

    Returns:
        相对于docs_dir的路径，如果未找到则返回None
    """
    archive_dir = docs_dir / 'archive'
    if not archive_dir.exists():
        return None

    # 递归搜索所有子目录
    for md_file in archive_dir.rglob(filename):
        return str(md_file.relative_to(docs_dir))

    return None


def find_markdown_links(content: str) -> List[Tuple[int, str, str, str]]:
    """查找所有Markdown链接

    Returns:
        List of (line_num, full_match, link_text, link_url)
    """
    pattern = r'\[([^\]]+)\]\(([^)]+)\)'
    links = []

    lines = content.split('\n')
    for line_num, line in enumerate(lines, 1):
        for match in re.finditer(pattern, line):
            link_text = match.group(1)
            link_url = match.group(2)
            links.append((line_num, match.group(0), link_text, link_url))

    return links


def is_broken_link(link_url: str, docs_dir: Path, current_file: Path) -> bool:
    """检查链接是否断裂"""
    # 跳过外部链接
    if link_url.startswith(('http://', 'https://', 'mailto:', '#')):
        return False

    # 跳过file://协议（稍后单独处理）
    if link_url.startswith('file://'):
        return True

    # 解析链接
    parsed = urlparse(link_url)
    file_path = parsed.path

    # 移除锚点
    file_path = file_path.split('#')[0]

    if not file_path:
        return False

    # 检查文件是否存在
    # 相对路径
    if not file_path.startswith('/'):
        target_path = (current_file.parent / file_path).resolve()
    else:
        target_path = (docs_dir.parent / file_path.lstrip('/')).resolve()

    return not target_path.exists()


def fix_file_protocol_link(link_url: str) -> str:
    """修复file://协议链接"""
    if not link_url.startswith('file://'):
        return link_url

    # 提取文件路径
    file_path = link_url[7:]  # 移除 file://

    # 提取文件名
    file_name = Path(file_path).name

    # 查找是否在FILE_PATH_MAP中
    if file_name in FILE_PATH_MAP:
        return FILE_PATH_MAP[file_name]

    # 尝试在docs目录中查找
    docs_dir = Path('docs')
    for md_file in docs_dir.rglob(file_name):
        # 返回相对路径
        return str(md_file.relative_to(docs_dir))

    # 无法修复，返回原链接
    return link_url


def fix_relative_path(link_url: str, current_file: Path, docs_dir: Path) -> str:
    """修复错误的相对路径"""
    # 解析链接
    parsed = urlparse(link_url)
    file_path = parsed.path.split('#')[0]
    anchor = '#' + parsed.path.split('#')[1] if '#' in parsed.path else ''

    if not file_path:
        return link_url

    file_name = Path(file_path).name

    # 1. 优先尝试自动检测archive目录
    auto_path = auto_detect_archive_path(file_name, docs_dir)
    if auto_path:
        return auto_path + anchor

    # 2. 检查FILE_PATH_MAP（后备）
    if file_name in FILE_PATH_MAP:
        archive_path = FILE_PATH_MAP[file_name]
        # 计算相对于docs目录的路径
        if archive_path.startswith('docs/'):
            return archive_path[5:] + anchor  # 移除 'docs/' 前缀
        return archive_path + anchor

    # 3. 检查DELETED_TO_ARCHIVE（后备）
    if file_name in DELETED_TO_ARCHIVE:
        archive_prefix = DELETED_TO_ARCHIVE[file_name]
        return archive_prefix + file_name + anchor

    return link_url


def fix_links_in_file(file_path: Path, docs_dir: Path, dry_run: bool = False) -> Dict:
    """修复单个文件中的链接

    Returns:
        修复统计信息
    """
    content = file_path.read_text(encoding='utf-8')
    links = find_markdown_links(content)

    fixes = []
    fixed_count = 0

    for line_num, full_match, link_text, link_url in links:
        # 检查file://协议
        if link_url.startswith('file://'):
            new_url = fix_file_protocol_link(link_url)
            if new_url != link_url:
                fixes.append({
                    'line': line_num,
                    'old': full_match,
                    'new': f'[{link_text}]({new_url})',
                    'type': 'file_protocol'
                })
                fixed_count += 1
                continue

        # 检查是否断裂
        if is_broken_link(link_url, docs_dir, file_path):
            new_url = fix_relative_path(link_url, file_path, docs_dir)
            if new_url != link_url:
                fixes.append({
                    'line': line_num,
                    'old': full_match,
                    'new': f'[{link_text}]({new_url})',
                    'type': 'relative_path'
                })
                fixed_count += 1

    # 执行修复
    if fixes and not dry_run:
        lines = content.split('\n')
        # 从后向前修复，避免行号变化
        for fix in reversed(fixes):
            line_idx = fix['line'] - 1
            lines[line_idx] = lines[line_idx].replace(fix['old'], fix['new'])

        file_path.write_text('\n'.join(lines), encoding='utf-8')

    return {
        'file': file_path.name,
        'total_links': len(links),
        'broken_links': fixed_count,
        'fixes': fixes
    }


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='断裂链接修复工具')
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='仅显示修复计划，不实际修改文件'
    )
    parser.add_argument(
        '--docs-dir',
        default='docs',
        help='文档目录路径 (默认: docs)'
    )

    args = parser.parse_args()

    docs_dir = Path(args.docs_dir)
    if not docs_dir.exists():
        print(f"❌ 文档目录不存在: {docs_dir}")
        sys.exit(1)

    print("🔧 开始修复断裂链接...\n")

    if args.dry_run:
        print("⚠️  模拟运行模式 - 不会修改文件\n")

    md_files = list(docs_dir.glob("*.md"))
    md_files = [f for f in md_files if 'archive' not in str(f)]

    total_broken = 0
    total_fixed = 0
    file_results = []

    for md_file in sorted(md_files):
        result = fix_links_in_file(md_file, docs_dir, args.dry_run)

        if result['broken_links'] > 0:
            total_broken += result['broken_links']
            total_fixed += result['broken_links']
            file_results.append(result)

            if not args.dry_run:
                print(f"✅ {result['file']}: 修复 {result['broken_links']} 个链接")
            else:
                print(f"📄 {result['file']}: 将修复 {result['broken_links']} 个链接")

                # 显示修复详情
                for fix in result['fixes'][:3]:  # 只显示前3个
                    print(f"   行 {fix['line']}: {fix['type']}")
                    print(f"   - {fix['old'][:60]}...")
                    print(f"   + {fix['new'][:60]}...")

                if len(result['fixes']) > 3:
                    print(f"   ... 还有 {len(result['fixes']) - 3} 个修复")

    print(f"\n{'=' * 60}")
    print(f"📊 断裂链接修复报告")
    print(f"{'=' * 60}")

    print(f"\n📁 扫描文件: {len(md_files)}")
    print(f"🔗 总链接数: {sum(r['total_links'] for r in file_results)}")
    print(f"❌ 断裂链接: {total_broken}")
    print(f"✅ 已修复: {total_fixed}")

    if file_results:
        print(f"\n修复详情:")
        for result in sorted(file_results, key=lambda x: -x['broken_links']):
            print(f"  📄 {result['file']}: {result['broken_links']} 个")

    print(f"\n{'=' * 60}")

    if args.dry_run:
        print(f"\n💡 这是模拟运行。移除 --dry-run 参数以实际修复。")
    else:
        print(f"\n✅ 修复完成！共修复 {total_fixed} 个断裂链接。")

    return total_fixed


if __name__ == "__main__":
    main()

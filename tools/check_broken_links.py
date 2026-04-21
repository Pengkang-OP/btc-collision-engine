#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
断裂链接检查工具

检查所有Markdown文档中的链接是否有效：
- 内部文件链接
- 锚点链接
- 外部HTTP链接（可选）

使用方法:
    python tools/check_broken_links.py
"""

import os
import re
import sys
import io
import ctypes
import requests
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Set
from dataclasses import dataclass
from urllib.parse import urlparse

# 修复Windows控制台编码问题 - 使用共享模块`nfrom tools.utf8_helper import setup_windows_utf8`nsetup_windows_utf8()


@dataclass
class LinkInfo:
    """链接信息"""
    file: str
    line: int
    text: str
    url: str
    link_type: str  # 'internal', 'anchor', 'external'


@dataclass
class BrokenLink:
    """断裂链接"""
    link: LinkInfo
    reason: str


class BrokenLinkChecker:
    """断裂链接检查器"""
    
    def __init__(self, docs_dir: str = "docs", check_external: bool = False):
        self.docs_dir = Path(docs_dir)
        self.check_external = check_external
        self.broken_links: List[BrokenLink] = []
        self.total_links = 0
        self.checked_files = 0
        
    def check_all(self):
        """检查所有文档"""
        print("🔍 开始检查文档链接...\n")
        
        md_files = list(self.docs_dir.glob("*.md"))
        # 也包括子目录中的md文件
        md_files.extend(list(self.docs_dir.rglob("*.md")))
        # 去重
        md_files = list(set(md_files))
        
        print(f"📁 找到 {len(md_files)} 个文档\n")
        
        for md_file in sorted(md_files):
            self.check_file(md_file)
        
        self.print_summary()
        
        return self.broken_links
    
    def check_file(self, file_path: Path):
        """检查单个文件"""
        try:
            content = file_path.read_text(encoding='utf-8')
            lines = content.split('\n')
            self.checked_files += 1
            
            # 查找所有Markdown链接
            links = self.extract_links(content, str(file_path))
            self.total_links += len(links)
            
            # 检查每个链接
            for link in links:
                self.check_link(link, file_path.parent)
                
        except Exception as e:
            print(f"❌ 读取文件失败 {file_path}: {e}")
    
    def extract_links(self, content: str, file_path: str) -> List[LinkInfo]:
        """提取文档中的所有链接"""
        links = []
        lines = content.split('\n')
        
        # Markdown链接: [text](url)
        link_pattern = r'\[([^\]]+)\]\(([^)]+)\)'
        
        for line_num, line in enumerate(lines, 1):
            # 跳过代码块中的链接
            if line.strip().startswith('```'):
                continue
            
            for match in re.finditer(link_pattern, line):
                text = match.group(1)
                url = match.group(2)
                
                # 跳过图片链接（单独处理）
                if line[max(0, match.start()-1)] == '!':
                    continue
                
                # 确定链接类型
                if url.startswith(('http://', 'https://')):
                    link_type = 'external'
                elif url.startswith('#'):
                    link_type = 'anchor'
                elif url.startswith('mailto:') or url.startswith('tel:'):
                    link_type = 'special'
                else:
                    link_type = 'internal'
                
                links.append(LinkInfo(
                    file=file_path,
                    line=line_num,
                    text=text,
                    url=url,
                    link_type=link_type
                ))
        
        return links
    
    def check_link(self, link: LinkInfo, base_dir: Path):
        """检查单个链接"""
        if link.link_type == 'external':
            self.check_external_link(link)
        elif link.link_type == 'anchor':
            self.check_anchor_link(link)
        elif link.link_type == 'internal':
            self.check_internal_link(link, base_dir)
    
    def check_internal_link(self, link: LinkInfo, base_dir: Path):
        """检查内部链接"""
        # 分离文件路径和锚点
        parts = link.url.split('#')
        file_path = parts[0]
        anchor = parts[1] if len(parts) > 1 else None
        
        if not file_path:
            # 纯锚点链接，在同一文件中查找
            return
        
        # 计算目标文件路径
        if file_path.startswith('/'):
            # 绝对路径（相对于项目根目录）
            target_path = (self.docs_dir.parent / file_path[1:]).resolve()
        else:
            # 相对路径
            target_path = (base_dir / file_path).resolve()
        
        # 检查文件是否存在
        if not target_path.exists():
            self.broken_links.append(BrokenLink(
                link=link,
                reason=f"文件不存在: {target_path}"
            ))
            return
        
        # 如果有锚点，检查锚点是否存在
        if anchor:
            self.check_anchor_in_file(link, target_path, anchor)
    
    def check_anchor_link(self, link: LinkInfo):
        """检查锚点链接"""
        anchor = link.url[1:]  # 移除#
        file_path = Path(link.file)
        
        self.check_anchor_in_file(link, file_path, anchor)
    
    def check_anchor_in_file(self, link: LinkInfo, file_path: Path, anchor: str):
        """检查文件中的锚点是否存在"""
        try:
            content = file_path.read_text(encoding='utf-8')
            
            # 将锚点转换为小写（Markdown锚点通常是小写）
            anchor_lower = anchor.lower()
            
            # 查找匹配的标题
            # Markdown标题: # Title 或 ## Title
            heading_pattern = r'#{1,6}\s+(.+)'
            
            found = False
            for match in re.finditer(heading_pattern, content):
                heading = match.group(1).strip()
                # 转换为锚点格式（小写，空格替换为连字符）
                heading_anchor = re.sub(r'[^\w\s-]', '', heading).lower()
                heading_anchor = re.sub(r'\s+', '-', heading_anchor)
                
                if heading_anchor == anchor_lower:
                    found = True
                    break
            
            if not found:
                self.broken_links.append(BrokenLink(
                    link=link,
                    reason=f"锚点不存在: #{anchor}"
                ))
                
        except Exception as e:
            self.broken_links.append(BrokenLink(
                link=link,
                reason=f"读取文件失败: {e}"
            ))
    
    def check_external_link(self, link: LinkInfo):
        """检查外部链接"""
        if not self.check_external:
            return  # 默认不检查外部链接（耗时）
        
        try:
            response = requests.head(link.url, timeout=5, allow_redirects=True)
            
            if response.status_code >= 400:
                self.broken_links.append(BrokenLink(
                    link=link,
                    reason=f"HTTP {response.status_code}"
                ))
        except requests.RequestException as e:
            self.broken_links.append(BrokenLink(
                link=link,
                reason=f"请求失败: {str(e)}"
            ))
    
    def print_summary(self):
        """打印总结报告"""
        print("=" * 60)
        print("📊 链接检查报告")
        print("=" * 60)
        
        print(f"\n📁 检查文件数: {self.checked_files}")
        print(f"🔗 总链接数: {self.total_links}")
        print(f"❌ 断裂链接: {len(self.broken_links)}")
        
        if self.broken_links:
            print(f"\n⚠️  断裂链接详情:\n")
            
            # 按文件分组
            by_file: Dict[str, List[BrokenLink]] = {}
            for broken in self.broken_links:
                file_name = Path(broken.link.file).name
                if file_name not in by_file:
                    by_file[file_name] = []
                by_file[file_name].append(broken)
            
            for file_name, links in sorted(by_file.items()):
                print(f"📄 {file_name}:")
                for broken in links:
                    print(f"   行 {broken.link.line}: [{broken.link.text}]({broken.link.url})")
                    print(f"      原因: {broken.reason}")
                print()
        else:
            print(f"\n✅ 所有链接都有效！")
        
        print("=" * 60)


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='检查Markdown文档中的断裂链接')
    parser.add_argument(
        '--check-external',
        action='store_true',
        help='检查外部HTTP链接（耗时）'
    )
    parser.add_argument(
        '--docs-dir',
        default='docs',
        help='文档目录路径 (默认: docs)'
    )
    
    args = parser.parse_args()
    
    # 从项目根目录运行
    project_root = Path(__file__).parent.parent
    docs_dir = project_root / args.docs_dir
    
    if not docs_dir.exists():
        print(f"❌ 文档目录不存在: {docs_dir}")
        sys.exit(1)
    
    checker = BrokenLinkChecker(str(docs_dir), args.check_external)
    broken_links = checker.check_all()
    
    # 返回退出码（如果有断裂链接则返回非0）
    sys.exit(1 if broken_links else 0)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分页管理模块

提供分页功能，用于显示大量数据，如匹配结果、性能数据和错误日志。
"""

from typing import List, Any, Optional, Callable


class PaginationManager:
    """分页管理器

    用于处理和显示大量数据的分页功能，支持:
    - 匹配结果分页显示
    - 性能数据分页显示
    - 错误日志分页显示
    - 自定义数据分页显示
    """

    def __init__(self, items: List[Any], page_size: int = 10) -> None:
        """初始化分页管理器

        Args:
            items: 要分页的数据列表
            page_size: 每页显示的项目数量
        """
        self.items = items
        self.page_size = page_size
        self.current_page = 1
        self.total_pages = (len(items) + page_size - 1) // page_size

    def get_current_page_items(self) -> List[Any]:
        """获取当前页的数据

        Returns:
            当前页的数据列表
        """
        start = (self.current_page - 1) * self.page_size
        end = start + self.page_size
        return self.items[start:end]

    def next_page(self) -> bool:
        """切换到下一页

        Returns:
            是否成功切换到下一页
        """
        if self.current_page < self.total_pages:
            self.current_page += 1
            return True
        return False

    def previous_page(self) -> bool:
        """切换到上一页

        Returns:
            是否成功切换到上一页
        """
        if self.current_page > 1:
            self.current_page -= 1
            return True
        return False

    def go_to_page(self, page: int) -> bool:
        """跳转到指定页

        Args:
            page: 页码

        Returns:
            是否成功跳转到指定页
        """
        if 1 <= page <= self.total_pages:
            self.current_page = page
            return True
        return False

    def get_pagination_info(self) -> dict:
        """获取分页信息

        Returns:
            分页信息字典
        """
        return {
            "current_page": self.current_page,
            "total_pages": self.total_pages,
            "total_items": len(self.items),
            "page_size": self.page_size,
            "has_next": self.current_page < self.total_pages,
            "has_previous": self.current_page > 1,
        }

    def display_page(self, item_formatter: Callable[[Any], str], title: str = "") -> None:
        """显示当前页的数据

        Args:
            item_formatter: 用于格式化每个项目的函数
            title: 显示的标题
        """
        from src.cli.output import CLIOutput

        output = CLIOutput.get_instance()

        if title:
            output.header(title)

        items = self.get_current_page_items()
        info = self.get_pagination_info()

        if not items:
            output.info("没有数据")
            return

        for i, item in enumerate(items, start=(info["current_page"] - 1) * info["page_size"] + 1):
            output.print(f"{i}. {item_formatter(item)}")

        # 显示分页信息
        pagination_str = (
            f"页 {info['current_page']}/{info['total_pages']} (共 {info['total_items']} 项)"
        )
        output.print(f"\n{pagination_str}")

        # 显示导航选项
        nav_options = []
        if info["has_previous"]:
            nav_options.append("[P] 上一页")
        if info["has_next"]:
            nav_options.append("[N] 下一页")
        nav_options.append("[Q] 退出")

        if nav_options:
            output.print(" ".join(nav_options))


def display_paginated_results(results: List[dict], title: str = "匹配结果") -> None:
    """分页显示匹配结果

    Args:
        results: 匹配结果列表
        title: 显示的标题
    """
    from src.cli.output import CLIOutput

    output = CLIOutput.get_instance()

    if not results:
        output.info("没有匹配结果")
        return

    def format_match(item: dict) -> str:
        address = item.get("address", "N/A")
        timestamp = item.get("timestamp", 0)
        match_index = item.get("match_index", 0)
        private_key_hash = item.get("private_key_hash", "N/A")

        import time

        time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))

        return f"地址: {address} | 时间: {time_str} | 索引: {match_index} | 私钥哈希: {private_key_hash}"

    paginator = PaginationManager(results, page_size=5)

    while True:
        paginator.display_page(format_match, title)

        # 等待用户输入
        user_input = input("请输入选项: ").strip().upper()

        if user_input == "P":
            paginator.previous_page()
        elif user_input == "N":
            paginator.next_page()
        elif user_input == "Q":
            break
        elif user_input.isdigit():
            page = int(user_input)
            paginator.go_to_page(page)


def display_paginated_performance(data: List[dict], title: str = "性能数据") -> None:
    """分页显示性能数据

    Args:
        data: 性能数据列表
        title: 显示的标题
    """
    from src.cli.output import CLIOutput

    output = CLIOutput.get_instance()

    if not data:
        output.info("没有性能数据")
        return

    def format_performance(item: dict) -> str:
        timestamp = item.get("timestamp", 0)
        speed = item.get("speed", 0)
        total_checked = item.get("total_checked", 0)
        gpu_usage = item.get("gpu_usage", 0)
        memory_used = item.get("memory_used", 0)

        import time

        time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))

        return f"时间: {time_str} | 速度: {speed:,}/s | 总尝试: {total_checked:,} | GPU: {gpu_usage}% | 内存: {memory_used}MB"

    paginator = PaginationManager(data, page_size=8)

    while True:
        paginator.display_page(format_performance, title)

        # 等待用户输入
        user_input = input("请输入选项: ").strip().upper()

        if user_input == "P":
            paginator.previous_page()
        elif user_input == "N":
            paginator.next_page()
        elif user_input == "Q":
            break
        elif user_input.isdigit():
            page = int(user_input)
            paginator.go_to_page(page)


def display_paginated_errors(errors: List[dict], title: str = "错误日志") -> None:
    """分页显示错误日志

    Args:
        errors: 错误日志列表
        title: 显示的标题
    """
    from src.cli.output import CLIOutput

    output = CLIOutput.get_instance()

    if not errors:
        output.info("没有错误日志")
        return

    def format_error(item: dict) -> str:
        timestamp = item.get("timestamp", 0)
        error_type = item.get("error_type", "Unknown")
        message = item.get("message", "No message")
        details = item.get("details", "")

        import time

        time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))

        if details:
            return f"时间: {time_str} | 类型: {error_type} | 消息: {message} | 详情: {details}"
        else:
            return f"时间: {time_str} | 类型: {error_type} | 消息: {message}"

    paginator = PaginationManager(errors, page_size=6)

    while True:
        paginator.display_page(format_error, title)

        # 等待用户输入
        user_input = input("请输入选项: ").strip().upper()

        if user_input == "P":
            paginator.previous_page()
        elif user_input == "N":
            paginator.next_page()
        elif user_input == "Q":
            break
        elif user_input.isdigit():
            page = int(user_input)
            paginator.go_to_page(page)

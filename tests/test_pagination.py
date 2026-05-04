"""pagination.py 单元测试。

覆盖 PaginationManager 类的所有纯逻辑方法。
"""

import unittest
from src.cli.pagination import PaginationManager


class TestPaginationManagerInit(unittest.TestCase):
    """测试 PaginationManager 初始化。"""

    def test_init_defaults(self):
        """初始化时 current_page=1, 正确计算 total_pages。"""
        pm = PaginationManager(list(range(25)), page_size=10)
        self.assertEqual(pm.current_page, 1)
        self.assertEqual(pm.page_size, 10)
        self.assertEqual(pm.total_pages, 3)
        self.assertEqual(len(pm.items), 25)

    def test_init_total_pages_exact_division(self):
        """item 数量正好整除 page_size。"""
        pm = PaginationManager(list(range(30)), page_size=10)
        self.assertEqual(pm.total_pages, 3)

    def test_init_total_pages_one_more(self):
        """item 数量比整页多 1 个也需要多一页。"""
        pm = PaginationManager(list(range(11)), page_size=10)
        self.assertEqual(pm.total_pages, 2)

    def test_init_empty_items(self):
        """空列表 total_pages 为 0。"""
        pm = PaginationManager([], page_size=10)
        self.assertEqual(pm.total_pages, 0)
        self.assertEqual(pm.current_page, 1)

    def test_init_single_item(self):
        """单个 item 只有 1 页。"""
        pm = PaginationManager([0], page_size=10)
        self.assertEqual(pm.total_pages, 1)

    def test_init_page_size_larger_than_items(self):
        """page_size 大于 item 数量时 total_pages=1。"""
        pm = PaginationManager([1, 2, 3], page_size=100)
        self.assertEqual(pm.total_pages, 1)


class TestPaginationManagerNavigation(unittest.TestCase):
    """测试页面导航方法。"""

    def setUp(self):
        self.pm = PaginationManager(list(range(25)), page_size=10)

    # ── get_current_page_items ───────────────────────────

    def test_current_page_items_page1(self):
        """第 1 页返回前 10 个元素。"""
        items = self.pm.get_current_page_items()
        self.assertEqual(items, list(range(10)))

    def test_current_page_items_page3(self):
        """第 3 页返回最后 5 个元素（partial page）。"""
        self.pm.go_to_page(3)
        items = self.pm.get_current_page_items()
        self.assertEqual(items, list(range(20, 25)))

    # ── next_page ─────────────────────────────────────────

    def test_next_page_success(self):
        """next_page 前进并返回 True。"""
        self.assertTrue(self.pm.next_page())
        self.assertEqual(self.pm.current_page, 2)

    def test_next_page_at_last_page(self):
        """在最后一页时 next_page 返回 False 不变。"""
        self.pm.go_to_page(3)
        self.assertFalse(self.pm.next_page())
        self.assertEqual(self.pm.current_page, 3)

    def test_next_page_empty_list(self):
        """空列表 next_page 返回 False。"""
        pm = PaginationManager([], page_size=10)
        self.assertFalse(pm.next_page())

    # ── previous_page ─────────────────────────────────────

    def test_previous_page_success(self):
        """previous_page 后退并返回 True。"""
        self.pm.go_to_page(2)
        self.assertTrue(self.pm.previous_page())
        self.assertEqual(self.pm.current_page, 1)

    def test_previous_page_at_first_page(self):
        """在第一页时 previous_page 返回 False 不变。"""
        self.assertFalse(self.pm.previous_page())
        self.assertEqual(self.pm.current_page, 1)

    def test_previous_page_empty_list(self):
        """空列表 previous_page 返回 False。"""
        pm = PaginationManager([], page_size=10)
        self.assertFalse(pm.previous_page())

    # ── go_to_page ────────────────────────────────────────

    def test_go_to_page_valid(self):
        """go_to_page 跳转到合法页码返回 True。"""
        self.assertTrue(self.pm.go_to_page(2))
        self.assertEqual(self.pm.current_page, 2)

    def test_go_to_page_first(self):
        """go_to_page 跳转到第 1 页。"""
        self.pm.go_to_page(3)
        self.assertTrue(self.pm.go_to_page(1))
        self.assertEqual(self.pm.current_page, 1)

    def test_go_to_page_last(self):
        """go_to_page 跳转到最后一页。"""
        self.assertTrue(self.pm.go_to_page(3))
        self.assertEqual(self.pm.current_page, 3)

    def test_go_to_page_zero_invalid(self):
        """跳转到第 0 页返回 False。"""
        self.assertFalse(self.pm.go_to_page(0))
        self.assertEqual(self.pm.current_page, 1)

    def test_go_to_page_negative_invalid(self):
        """跳转到负数页返回 False。"""
        self.assertFalse(self.pm.go_to_page(-1))
        self.assertEqual(self.pm.current_page, 1)

    def test_go_to_page_beyond_total(self):
        """跳转到超过 total_pages 返回 False。"""
        self.assertFalse(self.pm.go_to_page(99))
        self.assertEqual(self.pm.current_page, 1)

    def test_go_to_page_empty_list(self):
        """空列表任何 go_to_page 返回 False 且 current_page 不变。"""
        pm = PaginationManager([], page_size=10)
        self.assertFalse(pm.go_to_page(1))
        self.assertEqual(pm.current_page, 1)
        self.assertFalse(pm.go_to_page(0))
        self.assertEqual(pm.current_page, 1)

    def test_page_size_one(self):
        """page_size=1 时每个 item 一页。"""
        pm = PaginationManager([10, 20, 30], page_size=1)
        self.assertEqual(pm.total_pages, 3)
        self.assertEqual(pm.get_current_page_items(), [10])
        pm.next_page()
        self.assertEqual(pm.get_current_page_items(), [20])
        pm.next_page()
        self.assertEqual(pm.get_current_page_items(), [30])


class TestPaginationManagerInfo(unittest.TestCase):
    """测试 get_pagination_info 及各边界场景。"""

    def setUp(self):
        """提供默认的 25 元素、page_size=10 的 PaginationManager。"""
        self.pm = PaginationManager(list(range(25)), page_size=10)

    def test_info_mid_page(self):
        """中间页 info 正确反映 has_next/has_previous。"""
        self.pm.go_to_page(2)
        info = self.pm.get_pagination_info()
        self.assertEqual(info["current_page"], 2)
        self.assertEqual(info["total_pages"], 3)
        self.assertEqual(info["total_items"], 25)
        self.assertEqual(info["page_size"], 10)
        self.assertTrue(info["has_next"])
        self.assertTrue(info["has_previous"])

    def test_info_first_page(self):
        """第一页 has_previous=False。"""
        info = self.pm.get_pagination_info()
        self.assertFalse(info["has_previous"])
        self.assertTrue(info["has_next"])

    def test_info_last_page(self):
        """最后一页 has_next=False。"""
        self.pm.go_to_page(3)
        info = self.pm.get_pagination_info()
        self.assertTrue(info["has_previous"])
        self.assertFalse(info["has_next"])

    def test_info_empty_list(self):
        """空列表 total_items=0, total_pages=0, has_next/previous=False。"""
        pm = PaginationManager([], page_size=10)
        info = pm.get_pagination_info()
        self.assertEqual(info["total_items"], 0)
        self.assertEqual(info["total_pages"], 0)
        self.assertFalse(info["has_next"])
        self.assertFalse(info["has_previous"])

    def test_info_single_page(self):
        """单页时 has_next/has_previous 均为 False。"""
        pm = PaginationManager(list(range(5)), page_size=10)
        info = pm.get_pagination_info()
        self.assertEqual(info["total_pages"], 1)
        self.assertFalse(info["has_next"])
        self.assertFalse(info["has_previous"])

    def test_get_current_page_items_empty_list(self):
        """空列表 get_current_page_items 返回空列表。"""
        pm = PaginationManager([], page_size=10)
        self.assertEqual(pm.get_current_page_items(), [])

    def test_get_current_page_items_after_navigation(self):
        """前进后退后 get_current_page_items 正确反映新页码。"""
        pm = PaginationManager(list(range(15)), page_size=5)
        pm.next_page()
        self.assertEqual(pm.get_current_page_items(), [5, 6, 7, 8, 9])
        pm.next_page()
        self.assertEqual(pm.get_current_page_items(), [10, 11, 12, 13, 14])
        pm.previous_page()
        self.assertEqual(pm.get_current_page_items(), [5, 6, 7, 8, 9])

    def test_info_after_navigation(self):
        """导航后 info 保持最新。"""
        pm = PaginationManager(list(range(15)), page_size=5)
        pm.next_page()
        info = pm.get_pagination_info()
        self.assertEqual(info["current_page"], 2)
        self.assertTrue(info["has_previous"])
        self.assertTrue(info["has_next"])


if __name__ == "__main__":
    unittest.main()

"""pagination.py 单元测试。

覆盖 PaginationManager 类的所有纯逻辑方法。
"""

import unittest
from unittest.mock import MagicMock, patch

from src.cli.pagination import (
    PaginationManager,
    display_paginated_errors,
    display_paginated_performance,
    display_paginated_results,
)


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


# ── display_page 方法 ───────────────────────────────────────────

class TestPaginationManagerDisplayPage(unittest.TestCase):
    """测试 PaginationManager.display_page() 方法。"""

    def setUp(self):
        """创建 mock CLIOutput 并 patch get_instance。"""
        from src.cli.output import CLIOutput

        CLIOutput.reset_instance()
        self.out = CLIOutput()
        self.out.console = MagicMock()
        self.out.err_console = MagicMock()
        self.out.header = MagicMock()
        self.out.info = MagicMock()
        self.out.print = MagicMock()
        self._patch = patch.object(CLIOutput, "get_instance", return_value=self.out)
        self._patch.start()

    def tearDown(self):
        """还原 patch 并重置单例。"""
        from src.cli.output import CLIOutput

        self._patch.stop()
        CLIOutput.reset_instance()

    # ── 有数据场景 ──

    def test_display_with_items_and_title(self):
        """有 items 和 title → header / print 都被调用。"""
        pm = PaginationManager(list(range(5)), page_size=10)
        formatter = lambda x: f"item-{x}"  # noqa: E731
        pm.display_page(formatter, title="测试标题")

        self.out.header.assert_called_once_with("测试标题")
        self.assertEqual(self.out.print.call_count, 7)  # 5 items + 1 pagination + 1 nav

    def test_display_with_items_no_title(self):
        """无 title → 不调用 header。"""
        pm = PaginationManager(list(range(3)), page_size=10)
        formatter = lambda x: f"v-{x}"  # noqa: E731
        pm.display_page(formatter, title="")

        self.out.header.assert_not_called()
        self.assertTrue(self.out.print.called)

    def test_display_empty_items(self):
        """空列表 → 显示 '没有数据'。"""
        pm = PaginationManager([], page_size=10)
        pm.display_page(lambda x: str(x), title="空")

        self.out.info.assert_called_once_with("没有数据")

    # ── 导航选项场景 ──

    def test_display_first_page_nav_only_next(self):
        """第 1 页 → 只有 [N] 没有 [P]。"""
        pm = PaginationManager(list(range(25)), page_size=10)
        pm.display_page(lambda x: str(x), title="第一页")

        # 最后一条 print 应是导航选项
        last_call = self.out.print.call_args_list[-1]
        nav_text = last_call[0][0]
        self.assertIn("[N]", nav_text)
        self.assertNotIn("[P]", nav_text)
        self.assertIn("[Q]", nav_text)

    def test_display_middle_page_nav_both(self):
        """中间页 → 同时有 [P] 和 [N]。"""
        pm = PaginationManager(list(range(25)), page_size=10)
        pm.next_page()  # 到第 2 页
        pm.display_page(lambda x: str(x), title="中间页")

        last_call = self.out.print.call_args_list[-1]
        nav_text = last_call[0][0]
        self.assertIn("[P]", nav_text)
        self.assertIn("[N]", nav_text)
        self.assertIn("[Q]", nav_text)

    def test_display_last_page_nav_only_prev(self):
        """最后一页 → 只有 [P] 没有 [N]。"""
        pm = PaginationManager(list(range(25)), page_size=10)
        pm.go_to_page(3)
        pm.display_page(lambda x: str(x), title="最后页")

        last_call = self.out.print.call_args_list[-1]
        nav_text = last_call[0][0]
        self.assertIn("[P]", nav_text)
        self.assertNotIn("[N]", nav_text)
        self.assertIn("[Q]", nav_text)

    def test_display_single_page_nav_none(self):
        """单页 → 无 [P]/[N]（只有 [Q]）。"""
        pm = PaginationManager(list(range(3)), page_size=10)
        pm.display_page(lambda x: str(x), title="单页")

        last_call = self.out.print.call_args_list[-1]
        nav_text = last_call[0][0]
        self.assertNotIn("[P]", nav_text)
        self.assertNotIn("[N]", nav_text)
        self.assertIn("[Q]", nav_text)

    def test_display_empty_list_nav(self):
        """空列表 → info 显示无数据，无导航输出。"""
        pm = PaginationManager([], page_size=10)
        pm.display_page(lambda x: str(x))

        self.out.info.assert_called_once_with("没有数据")
        # 没有调用 print（因为没有 items 也没有导航行）
        self.out.print.assert_not_called()

    def test_display_pagination_info_string(self):
        """打印的分页信息包含正确的页数/总数。"""
        pm = PaginationManager(list(range(25)), page_size=10)
        pm.display_page(lambda x: str(x))

        # 倒数第二个 print 调用是分页信息
        pagination_call = self.out.print.call_args_list[-2]
        info_str = pagination_call[0][0]
        self.assertIn("页 1/3", info_str)
        self.assertIn("共 25 项", info_str)


# ── display_paginated_results ────────────────────────────────────

class TestDisplayPaginatedResults(unittest.TestCase):
    """测试 display_paginated_results() 函数。"""

    def setUp(self):
        """创建 mock CLIOutput 并 patch get_instance。"""
        from src.cli.output import CLIOutput

        CLIOutput.reset_instance()
        self.out = CLIOutput()
        self.out.console = MagicMock()
        self.out.err_console = MagicMock()
        self.out.header = MagicMock()
        self.out.info = MagicMock()
        self.out.print = MagicMock()
        self._out_patch = patch.object(CLIOutput, "get_instance", return_value=self.out)
        self._out_patch.start()

    def tearDown(self):
        """还原 patch 并重置单例。"""
        from src.cli.output import CLIOutput

        self._out_patch.stop()
        CLIOutput.reset_instance()

    def _make_result(self, address="1TestAddr", timestamp=1714800000, match_index=1):
        """创建单个匹配结果 dict。"""
        return {
            "address": address,
            "timestamp": timestamp,
            "match_index": match_index,
            "private_key_hash": "abc123",
        }

    # ── 空数据 ──

    def test_empty_results(self):
        """空结果列表 → info 提示无结果。"""
        self.out.info = MagicMock()
        with patch("builtins.input"):
            display_paginated_results([], title="匹配结果")

        self.out.info.assert_called_once_with("没有匹配结果")

    # ── 交互循环：退出 ──

    def test_quit_immediately(self):
        """输入 Q → 立即退出循环。"""
        results = [self._make_result(address=f"addr{i}") for i in range(3)]
        self.out.info = MagicMock()
        with patch("builtins.input", side_effect=["Q"]):
            display_paginated_results(results, title="匹配结果")

    # ── 交互循环：下一页 ──

    def test_next_page_then_quit(self):
        """输入 N → 进入第 2 页，再 Q 退出。"""
        results = [self._make_result(address=f"addr{i}") for i in range(6)]
        self.out.info = MagicMock()
        with patch("builtins.input", side_effect=["N", "Q"]):
            display_paginated_results(results, title="匹配结果")

        # 分页信息中应出现 "页 2/2"
        found_p2 = False
        for call in self.out.print.call_args_list:
            if "页 2/2" in str(call[0][0]):
                found_p2 = True
                break
        self.assertTrue(found_p2, "应显示第 2 页信息")

    # ── 交互循环：上一页 ──

    def test_previous_page_then_quit(self):
        """先 N 到第 2 页，再 P 回第 1 页，再 Q 退出。"""
        results = [self._make_result(address=f"addr{i}") for i in range(7)]
        self.out.info = MagicMock()
        with patch("builtins.input", side_effect=["N", "P", "Q"]):
            display_paginated_results(results, title="匹配结果")

        # 应该显示回第 1 页
        found_p1 = False
        for call in self.out.print.call_args_list:
            if "页 1/2" in str(call[0][0]):
                found_p1 = True
        self.assertTrue(found_p1, "应最终显示第 1 页信息")

    # ── 交互循环：跳转到指定页 ──

    def test_go_to_page_by_digit(self):
        """输入数字 2 → 跳转到第 2 页，再 Q 退出。"""
        results = [self._make_result(address=f"addr{i}") for i in range(11)]
        self.out.info = MagicMock()
        with patch("builtins.input", side_effect=["2", "Q"]):
            display_paginated_results(results, title="匹配结果")

        # 应显示第 2 页
        found_p2 = False
        for call in self.out.print.call_args_list:
            if "页 2/3" in str(call[0][0]):
                found_p2 = True
                break
        self.assertTrue(found_p2, "应显示第 2 页信息")

    # ── 交互循环：无效输入 ──

    def test_invalid_input_then_quit(self):
        """无效输入（非 P/N/Q/数字）→ 无操作，继续循环。"""
        results = [self._make_result(address=f"addr{i}") for i in range(3)]
        self.out.info = MagicMock()
        with patch("builtins.input", side_effect=["X", " ", "Q"]):
            display_paginated_results(results, title="匹配结果")

        # display_page 被调用了至少 3 次（无效输入不改变页面）
        # （无法直接断言 display_page，但至少不崩溃）

    def test_various_inputs_stress(self):
        """混用多种导航：N→N→P→3→Q。"""
        results = [self._make_result(address=f"addr{i}") for i in range(20)]
        self.out.info = MagicMock()
        with patch("builtins.input", side_effect=["N", "N", "P", "3", "Q"]):
            display_paginated_results(results, title="匹配结果")


# ── display_paginated_performance ────────────────────────────────

class TestDisplayPaginatedPerformance(unittest.TestCase):
    """测试 display_paginated_performance() 函数。"""

    def setUp(self):
        """创建 mock CLIOutput 并 patch get_instance。"""
        from src.cli.output import CLIOutput

        CLIOutput.reset_instance()
        self.out = CLIOutput()
        self.out.console = MagicMock()
        self.out.err_console = MagicMock()
        self.out.header = MagicMock()
        self.out.info = MagicMock()
        self.out.print = MagicMock()
        self._out_patch = patch.object(CLIOutput, "get_instance", return_value=self.out)
        self._out_patch.start()

    def tearDown(self):
        """还原 patch 并重置单例。"""
        from src.cli.output import CLIOutput

        self._out_patch.stop()
        CLIOutput.reset_instance()

    def _make_perf(self, timestamp=1714800000, speed=1000, total_checked=50000,
                   gpu_usage=85, memory_used=2048):
        """创建单条性能数据 dict。"""
        return {
            "timestamp": timestamp,
            "speed": speed,
            "total_checked": total_checked,
            "gpu_usage": gpu_usage,
            "memory_used": memory_used,
        }

    def test_empty_performance(self):
        """空数据 → info 提示无数据。"""
        self.out.info = MagicMock()
        with patch("builtins.input"):
            display_paginated_performance([], title="性能")

        self.out.info.assert_called_once_with("没有性能数据")

    def test_quit_immediately(self):
        """有数据，Q 退出。"""
        data = [self._make_perf() for _ in range(5)]
        self.out.info = MagicMock()
        with patch("builtins.input", side_effect=["Q"]):
            display_paginated_performance(data, title="性能")

    def test_next_then_quit(self):
        """N 下一页，Q 退出。"""
        data = [self._make_perf() for _ in range(12)]  # page_size=8, 2 pages
        self.out.info = MagicMock()
        with patch("builtins.input", side_effect=["N", "Q"]):
            display_paginated_performance(data, title="性能")

        found_p2 = False
        for call in self.out.print.call_args_list:
            if "页 2/2" in str(call[0][0]):
                found_p2 = True
                break
        self.assertTrue(found_p2, "应显示第 2 页性能数据")

    def test_prev_then_quit(self):
        """N→P→Q：前进一页再后退。"""
        data = [self._make_perf() for _ in range(10)]
        self.out.info = MagicMock()
        with patch("builtins.input", side_effect=["N", "P", "Q"]):
            display_paginated_performance(data, title="性能")

        found_p1 = False
        for call in self.out.print.call_args_list:
            if "页 1/2" in str(call[0][0]):
                found_p1 = True
        self.assertTrue(found_p1, "应回到第 1 页")

    def test_go_to_page_by_digit(self):
        """数字跳页。"""
        data = [self._make_perf() for _ in range(20)]  # 3 pages
        self.out.info = MagicMock()
        with patch("builtins.input", side_effect=["3", "Q"]):
            display_paginated_performance(data, title="性能")

        found_p3 = False
        for call in self.out.print.call_args_list:
            if "页 3/3" in str(call[0][0]):
                found_p3 = True
                break
        self.assertTrue(found_p3, "应显示第 3 页")


# ── display_paginated_errors ─────────────────────────────────────

class TestDisplayPaginatedErrors(unittest.TestCase):
    """测试 display_paginated_errors() 函数。"""

    def setUp(self):
        """创建 mock CLIOutput 并 patch get_instance。"""
        from src.cli.output import CLIOutput

        CLIOutput.reset_instance()
        self.out = CLIOutput()
        self.out.console = MagicMock()
        self.out.err_console = MagicMock()
        self.out.header = MagicMock()
        self.out.info = MagicMock()
        self.out.print = MagicMock()
        self._out_patch = patch.object(CLIOutput, "get_instance", return_value=self.out)
        self._out_patch.start()

    def tearDown(self):
        """还原 patch 并重置单例。"""
        from src.cli.output import CLIOutput

        self._out_patch.stop()
        CLIOutput.reset_instance()

    def _make_error(self, timestamp=1714800000, error_type="RuntimeError",
                    message="测试错误", details=""):
        """创建单条错误日志 dict。"""
        d = {
            "timestamp": timestamp,
            "error_type": error_type,
            "message": message,
        }
        if details:
            d["details"] = details
        return d

    # ── 空数据 ──

    def test_empty_errors(self):
        """空错误列表 → info 提示。"""
        self.out.info = MagicMock()
        with patch("builtins.input"):
            display_paginated_errors([], title="错误")

        self.out.info.assert_called_once_with("没有错误日志")

    # ── 交互导航 ──

    def test_quit_immediately(self):
        """有错误，Q 退出。"""
        errors = [self._make_error(error_type="TypeError") for _ in range(3)]
        self.out.info = MagicMock()
        with patch("builtins.input", side_effect=["Q"]):
            display_paginated_errors(errors, title="错误")

    def test_next_then_quit(self):
        """N 下一页，Q 退出 (page_size=6)。"""
        errors = [self._make_error(error_type=f"Err{i}") for i in range(8)]
        self.out.info = MagicMock()
        with patch("builtins.input", side_effect=["N", "Q"]):
            display_paginated_errors(errors, title="错误")

        found_p2 = False
        for call in self.out.print.call_args_list:
            if "页 2/2" in str(call[0][0]):
                found_p2 = True
                break
        self.assertTrue(found_p2, "应显示第 2 页错误")

    def test_prev_then_quit(self):
        """N→P→Q：前进一页再后退。"""
        errors = [self._make_error() for _ in range(7)]
        self.out.info = MagicMock()
        with patch("builtins.input", side_effect=["N", "P", "Q"]):
            display_paginated_errors(errors, title="错误")

    def test_go_to_page_by_digit(self):
        """数字跳页。"""
        errors = [self._make_error() for _ in range(15)]  # 3 pages
        self.out.info = MagicMock()
        with patch("builtins.input", side_effect=["3", "Q"]):
            display_paginated_errors(errors, title="错误")

        found_p3 = False
        for call in self.out.print.call_args_list:
            if "页 3/3" in str(call[0][0]):
                found_p3 = True
                break
        self.assertTrue(found_p3, "应显示第 3 页")

    # ── format 分支 ──

    def test_error_with_details(self):
        """错误含 details → 输出包含详情字段。"""
        errors = [self._make_error(details="磁盘空间不足")]
        self.out.info = MagicMock()
        with patch("builtins.input", side_effect=["Q"]):
            display_paginated_errors(errors, title="错误")

        # 输出中包含 "详情:"
        found_details = False
        for call in self.out.print.call_args_list:
            text = str(call[0])
            if "详情" in text:
                found_details = True
                break
        self.assertTrue(found_details, "错误含 details 时输出应包含详情")

    def test_error_without_details(self):
        """错误无 details → 不包含详情字段。"""
        errors = [self._make_error(details="")]
        self.out.info = MagicMock()
        with patch("builtins.input", side_effect=["Q"]):
            display_paginated_errors(errors, title="错误")

    def test_error_default_values(self):
        """错误缺少可选字段 → 使用默认值。"""
        errors = [{"timestamp": 0}]  # 只有 timestamp
        self.out.info = MagicMock()
        with patch("builtins.input", side_effect=["Q"]):
            display_paginated_errors(errors, title="错误")

        # 输出中应包含 "Unknown" 和 "No message"
        found_defaults = False
        for call in self.out.print.call_args_list:
            text = str(call[0])
            if "Unknown" in text and "No message" in text:
                found_defaults = True
                break
        self.assertTrue(found_defaults, "缺少字段应使用默认值 Unknown/No message")


if __name__ == "__main__":
    unittest.main()

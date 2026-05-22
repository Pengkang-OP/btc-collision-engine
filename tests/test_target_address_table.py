"""BitcoinTargetTable 单元测试 - 覆盖文件加载、边界条件、清理等路径"""

import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from src.core.target_address_table import BitcoinTargetTable


class TestBitcoinTargetTableAddTargetEdgeCases(unittest.TestCase):
    """add_target 边界条件测试"""

    def setUp(self):
        self.table = BitcoinTargetTable()

    def test_add_target_invalid_hash160_length(self):
        """hash160 长度不为 20 字节时抛出 ValueError"""
        with self.assertRaises(ValueError) as ctx:
            self.table.add_target(
                wif="5HueCGU8rMjxEXxiPuD5BDku4MkFqeZyd4dZ1jvhTVqvbTLvyTJ",
                address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
                hash160=b"\x00" * 19,
            )
        self.assertIn("20", str(ctx.exception))

    def test_add_target_table_full(self):
        """目标地址表已满时抛出 ValueError"""
        small_table = BitcoinTargetTable(max_size=1)
        hash160 = b"\x01" * 20
        small_table.add_target(
            wif="5HueCGU8rMjxEXxiPuD5BDku4MkFqeZyd4dZ1jvhTVqvbTLvyTJ",
            address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            hash160=hash160,
        )
        with self.assertRaises(ValueError) as ctx:
            small_table.add_target(
                wif="5HueCGU8rMjxEXxiPuD5BDku4MkFqeZyd4dZ1jvhTVqvbTLvyTJ",
                address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
                hash160=b"\x02" * 20,
            )
        self.assertIn("已满", str(ctx.exception))


class TestBitcoinTargetTableLoadFromWifList(unittest.TestCase):
    """load_from_wif_list 测试"""

    def setUp(self):
        self.table = BitcoinTargetTable()

    @patch("src.core.target_address_table.OptimizedP2PKHAddressGenerator")
    @patch("src.core.target_address_table.WIF")
    def test_load_from_wif_list_success(self, mock_wif, mock_generator_cls):
        """成功从 WIF 列表加载目标地址"""
        # Mock WIF.decode
        mock_wif.decode.side_effect = [
            (b"\x01" * 32, True),
            (b"\x02" * 32, False),
        ]

        # Mock generator
        mock_gen = MagicMock()
        mock_gen.generate_from_private_key.side_effect = [
            "1Address1",
            "1Address2",
        ]
        mock_gen.private_key_to_public_key.side_effect = [
            b"\x04" + b"\x00" * 64,
            b"\x04" + b"\x11" * 64,
        ]
        mock_generator_cls.return_value = mock_gen

        # Mock HashUtils.hash160
        with patch("src.core.target_address_table.HashUtils") as mock_hash:
            mock_hash.hash160.side_effect = [
                b"\xaa" * 20,
                b"\xbb" * 20,
            ]
            count = self.table.load_from_wif_list(["wif1", "wif2"])

        self.assertEqual(count, 2)
        self.assertEqual(len(self.table._hash160_set), 2)
        stats = self.table.get_statistics()
        self.assertEqual(stats["total_targets"], 2)

    @patch("src.core.target_address_table.OptimizedP2PKHAddressGenerator")
    @patch("src.core.target_address_table.WIF")
    def test_load_from_wif_list_with_errors(self, mock_wif, mock_generator_cls):
        """部分 WIF 解码失败时跳过并继续"""
        mock_wif.decode.side_effect = [
            ValueError("bad wif"),
            (b"\x02" * 32, False),
        ]

        mock_gen = MagicMock()
        mock_gen.generate_from_private_key.return_value = "1Address2"
        mock_gen.private_key_to_public_key.return_value = b"\x04" + b"\x11" * 64
        mock_generator_cls.return_value = mock_gen

        with patch("src.core.target_address_table.HashUtils") as mock_hash:
            mock_hash.hash160.return_value = b"\xbb" * 20
            count = self.table.load_from_wif_list(["bad_wif", "good_wif"])

        self.assertEqual(count, 1)
        self.assertEqual(len(self.table._hash160_set), 1)

    @patch("src.core.target_address_table.OptimizedP2PKHAddressGenerator")
    @patch("src.core.target_address_table.WIF")
    def test_load_from_wif_list_all_errors(self, mock_wif, mock_generator_cls):
        """全部解码失败时返回 0"""
        mock_wif.decode.side_effect = ValueError("all bad")

        mock_gen = MagicMock()
        mock_generator_cls.return_value = mock_gen

        count = self.table.load_from_wif_list(["bad1", "bad2"])
        self.assertEqual(count, 0)
        self.assertEqual(len(self.table._hash160_set), 0)


class TestBitcoinTargetTableLoadFromFile(unittest.TestCase):
    """load_from_file 测试"""

    def setUp(self):
        self.table = BitcoinTargetTable()

    def test_load_from_file_not_found(self):
        """文件不存在时抛出 FileNotFoundError"""
        with self.assertRaises(FileNotFoundError):
            self.table.load_from_file("/nonexistent/path/targets.json")

    def test_load_from_file_unsupported_format(self):
        """不支持的文件格式抛出 ValueError"""
        with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as f:
            f.write(b"<data></data>")
            tmp_path = f.name
        try:
            with self.assertRaises(ValueError) as ctx:
                self.table.load_from_file(tmp_path)
            self.assertIn("不支持", str(ctx.exception))
        finally:
            os.unlink(tmp_path)

    @patch.object(BitcoinTargetTable, "load_from_wif_list")
    def test_load_from_json_list_format(self, mock_load):
        """JSON 列表格式加载"""
        mock_load.return_value = 3
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False, encoding="utf-8") as f:
            json.dump(["wif1", "wif2", "wif3"], f)
            tmp_path = f.name
        try:
            count = self.table.load_from_file(tmp_path)
            self.assertEqual(count, 3)
            mock_load.assert_called_once_with(["wif1", "wif2", "wif3"])
        finally:
            os.unlink(tmp_path)

    @patch.object(BitcoinTargetTable, "load_from_wif_list")
    def test_load_from_json_dict_format(self, mock_load):
        """JSON 字典格式（含 targets 键）加载"""
        mock_load.return_value = 2
        data = {"targets": [{"wif": "wA"}, {"wif": "wB"}, {"other": "x"}]}
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False, encoding="utf-8") as f:
            json.dump(data, f)
            tmp_path = f.name
        try:
            count = self.table.load_from_file(tmp_path)
            self.assertEqual(count, 2)
            mock_load.assert_called_once_with(["wA", "wB"])
        finally:
            os.unlink(tmp_path)

    @patch.object(BitcoinTargetTable, "load_from_wif_list")
    def test_load_from_json_invalid_format(self, mock_load):
        """JSON 格式无效时抛出 ValueError"""
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False, encoding="utf-8") as f:
            json.dump({"not_targets": 123}, f)
            tmp_path = f.name
        try:
            with self.assertRaises(ValueError) as ctx:
                self.table.load_from_file(tmp_path)
            self.assertIn("无效", str(ctx.exception))
        finally:
            os.unlink(tmp_path)

    @patch.object(BitcoinTargetTable, "load_from_wif_list")
    def test_load_from_csv(self, mock_load):
        """CSV 文件加载（含不含 wif 列的行）"""
        mock_load.return_value = 2
        with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False, encoding="utf-8") as f:
            f.write("wif,extra\nw1,x\nw2,y\n")
            tmp_path = f.name
        try:
            count = self.table.load_from_file(tmp_path)
            self.assertEqual(count, 2)
            mock_load.assert_called_once_with(["w1", "w2"])
        finally:
            os.unlink(tmp_path)

    @patch.object(BitcoinTargetTable, "load_from_wif_list")
    def test_load_from_csv_no_wif_column(self, mock_load):
        """CSV 文件无 wif 列时跳过所有行"""
        mock_load.return_value = 0
        with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False, encoding="utf-8") as f:
            f.write("name,value\nnone,1\n")
            tmp_path = f.name
        try:
            count = self.table.load_from_file(tmp_path)
            self.assertEqual(count, 0)
            mock_load.assert_called_once_with([])
        finally:
            os.unlink(tmp_path)

    @patch.object(BitcoinTargetTable, "load_from_wif_list")
    def test_load_from_txt(self, mock_load):
        """TXT 文件加载（每行一个 WIF）"""
        mock_load.return_value = 3
        with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False, encoding="utf-8") as f:
            f.write("  w1  \nw2\n\nw3\n")
            tmp_path = f.name
        try:
            count = self.table.load_from_file(tmp_path)
            self.assertEqual(count, 3)
            mock_load.assert_called_once_with(["w1", "w2", "w3"])
        finally:
            os.unlink(tmp_path)


class TestBitcoinTargetTableClear(unittest.TestCase):
    """clear 测试"""

    def setUp(self):
        self.table = BitcoinTargetTable()

    def test_clear_empties_table(self):
        """清空目标地址表"""
        for i in range(5):
            h = i.to_bytes(20, "big")
            self.table.add_target(
                wif=f"wif_{i}",
                address=f"1Addr{i}",
                hash160=h,
            )
        self.assertEqual(self.table.get_statistics()["total_targets"], 5)

        self.table.clear()
        self.assertEqual(self.table.get_statistics()["total_targets"], 0)
        self.assertEqual(len(self.table._hash160_set), 0)
        self.assertEqual(len(self.table._target_map), 0)

    def test_clear_empty_table(self):
        """清空空表不报错"""
        self.table.clear()
        self.assertEqual(self.table.get_statistics()["total_targets"], 0)


class TestBitcoinTargetTableCheckMatch(unittest.TestCase):
    """check_match 边界测试"""

    def setUp(self):
        self.table = BitcoinTargetTable()

    def test_check_match_no_match(self):
        """不匹配时返回 (False, None)"""
        is_match, info = self.table.check_match(b"\x00" * 20)
        self.assertFalse(is_match)
        self.assertIsNone(info)

    def test_check_match_success(self):
        """匹配时返回 (True, info_dict)"""
        h = b"\x01" * 20
        self.table.add_target(wif="w", address="a", hash160=h)
        is_match, info = self.table.check_match(h)
        self.assertTrue(is_match)
        self.assertIsNotNone(info)
        self.assertEqual(info["wif"], "w")
        self.assertEqual(info["address"], "a")


class TestBitcoinTargetTableStatistics(unittest.TestCase):
    """get_statistics 测试"""

    def setUp(self):
        self.table = BitcoinTargetTable(max_size=100)

    def test_get_statistics_empty(self):
        """空表统计"""
        stats = self.table.get_statistics()
        self.assertEqual(stats["total_targets"], 0)
        self.assertEqual(stats["max_capacity"], 100)
        self.assertEqual(stats["usage_percent"], 0.0)

    def test_get_statistics_with_data(self):
        """有数据时的统计"""
        for i in range(5):
            self.table.add_target(
                wif=f"w{i}",
                address=f"a{i}",
                hash160=i.to_bytes(20, "big"),
            )
        stats = self.table.get_statistics()
        self.assertEqual(stats["total_targets"], 5)
        self.assertAlmostEqual(stats["usage_percent"], 5.0)


class TestBitcoinTargetTableLogging(unittest.TestCase):
    """日志相关边界测试"""

    def setUp(self):
        self.table = BitcoinTargetTable(max_size=100000)

    @patch("src.core.target_address_table.OptimizedP2PKHAddressGenerator")
    @patch("src.core.target_address_table.WIF")
    def test_load_from_wif_list_logging_at_boundary(self, mock_wif, mock_generator_cls):
        """10000 个边界时输出日志（验证不崩溃）"""
        mock_wif.decode.return_value = (b"\x01" * 32, True)
        mock_gen = MagicMock()
        mock_gen.generate_from_private_key.return_value = "1Addr"
        mock_gen.private_key_to_public_key.return_value = b"\x04" + b"\x00" * 64
        mock_generator_cls.return_value = mock_gen

        with patch("src.core.target_address_table.HashUtils") as mock_hash:
            mock_hash.hash160.side_effect = [i.to_bytes(20, "big") for i in range(10001)]
            wif_list = [f"wif_{i}" for i in range(10001)]
            count = self.table.load_from_wif_list(wif_list)

        self.assertEqual(count, 10001)


if __name__ == "__main__":
    unittest.main()

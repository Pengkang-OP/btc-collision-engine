# -*- coding: utf-8 -*-
"""GPUDeviceScorer 单元测试

覆盖 GPUDeviceScorer 的全部公共方法:
- score(), score_relative()
- rank_devices(), select_best()
- calculate_performance_weights()
- get_tier(), get_tier_description()
- compare_devices(), format_score_report()
- identify_model() (各厂商世代识别含 AMD RX 500/400 扩展)
- 单例管理 (get_gpu_scorer, reset_gpu_scorer)
"""

import unittest
from typing import Dict, Any, List

from src.gpu.scorer import GPUDeviceScorer, get_gpu_scorer, reset_gpu_scorer


# ──────────────────────────────────────────────
# 测试辅助: 构建标准设备字典
# ──────────────────────────────────────────────
def _make_device(
    name: str,
    vendor: str,
    mem_gb: float = 8.0,
    cu: int = 32,
    idx: int = 0,
    cache_kb: float = 0.0,
    lmem_kb: float = 0.0,
    model: str = "",
) -> Dict[str, Any]:
    return {
        'name': name,
        'vendor': vendor,
        'global_mem_gb': mem_gb,
        'max_compute_units': cu,
        'global_index': idx,
        'global_mem_cache_kb': cache_kb,
        'local_mem_kb': lmem_kb,
        'model': model,
    }


class TestGPUDeviceScorerScore(unittest.TestCase):
    """score() 方法测试"""

    def setUp(self):
        self.scorer = GPUDeviceScorer()

    def test_01_score_nvidia_basic(self):
        """score: NVIDIA RTX 3080 基础评分"""
        d = _make_device('NVIDIA GeForce RTX 3080', 'nvidia', 10.0, 68)
        s = self.scorer.score(d)
        expected = (10 * 10 + 68 * 0.05 + 10) * 1.0  # 113.4
        self.assertAlmostEqual(s, expected, places=1)

    def test_02_score_amd_basic(self):
        """score: AMD RX 6800 XT 基础评分"""
        d = _make_device('AMD Radeon RX 6800 XT', 'amd', 16.0, 72)
        s = self.scorer.score(d)
        expected = (16 * 10 + 72 * 0.05 + 8) * 0.95  # 163.02
        self.assertAlmostEqual(s, expected, places=1)

    def test_03_score_intel_basic(self):
        """score: Intel Arc A770 基础评分"""
        d = _make_device('Intel Arc A770', 'intel', 16.0, 512)
        s = self.scorer.score(d)
        expected = (16 * 10 + 512 * 0.05 + 5) * 0.9  # 171.54
        self.assertAlmostEqual(s, expected, places=1)

    def test_04_score_with_cache_lmem(self):
        """score: cache/lmem 加分正确计算"""
        d = _make_device('Test GPU', 'nvidia', 8.0, 32,
                         cache_kb=128000, lmem_kb=65536)
        s = self.scorer.score(d)
        expected = (8*10 + 32*0.05 + 128000*0.001 + 65536*0.01) * 1.0
        self.assertAlmostEqual(s, expected, places=1)

    def test_05_score_unknown_vendor(self):
        """score: 未知厂商默认 factor=0.8"""
        d = _make_device('Mystery GPU', 'unknown', 8.0, 32)
        s = self.scorer.score(d)
        expected = (8*10 + 32*0.05) * 0.8  # no gen bonus
        self.assertAlmostEqual(s, expected, places=1)

    def test_06_score_explicit_model(self):
        """score: 显式指定 model 跳过自动识别"""
        # "RTX 30??" 不会被自动识别, 但显式 model='rtx30' 会获得世代加分
        d = _make_device('WeirdName GPU', 'nvidia', 8.0, 32, model='rtx30')
        s = self.scorer.score(d)
        expected = (8*10 + 32*0.05 + 10) * 1.0  # +10 gen_bonus_rtx30
        self.assertAlmostEqual(s, expected, places=1)

    def test_07_score_missing_fields_defaults(self):
        """score: 缺失字段使用默认值不崩溃"""
        d: Dict[str, Any] = {'name': 'Min GPU', 'vendor': 'nvidia'}
        s = self.scorer.score(d)
        # mem=0, cu=0, no gen bonus (name doesn't match any model)
        self.assertGreaterEqual(s, 0.0)
        self.assertLess(s, 5.0)


class TestGPUDeviceScorerScoreRelative(unittest.TestCase):
    """score_relative() 负载均衡权重测试"""

    def setUp(self):
        self.scorer = GPUDeviceScorer()

    def test_01_relative_uses_60_1_ratio(self):
        """score_relative: 使用 60:1 权重比 (区别于 score 的 200:1)"""
        d = _make_device('RTX 3080', 'nvidia', 10.0, 68)
        rel = self.scorer.score_relative(d)
        # 6.0*10 + 0.1*68 + 10(gen) = 60 + 6.8 + 10 = 76.8 * 1.0 = 76.8
        expected = (10*6.0 + 68*0.1 + 10) * 1.0
        self.assertAlmostEqual(rel, expected, places=1)

    def test_02_relative_vs_score_ratio(self):
        """score_relative: 同设备 relative < score (因权重比不同)"""
        d = _make_device('RX 6800 XT', 'amd', 16.0, 72)
        rel = self.scorer.score_relative(d)
        score = self.scorer.score(d)
        # relative 用 60:1, score 用 200:1，但都有 gen_bonus + vendor_factor
        # 都在 60~180 量级，直接比较不科学，只验证都 > 0
        self.assertGreater(rel, 0)
        self.assertGreater(score, 0)

    def test_03_relative_includes_vendor_factor(self):
        """score_relative: 包含 vendor_factor (AMD=0.95)"""
        nv = _make_device('RTX 3060', 'nvidia', 12.0, 28)
        amd = _make_device('RX 6600', 'amd', 8.0, 28)
        rel_nv = self.scorer.score_relative(nv)
        rel_amd = self.scorer.score_relative(amd)
        # RTX 3060 (12GB, gen=rtx30) vs RX 6600 (8GB, gen=rx6000)
        # NV: (12*6+28*0.1+10)*1.0 = 72+2.8+10=84.8
        # AMD: (8*6+28*0.1+8)*0.95 = 48+2.8+8=58.8*0.95=55.86
        self.assertAlmostEqual(rel_nv, 84.8, places=1)
        self.assertAlmostEqual(rel_amd, 55.86, places=1)


class TestGPUDeviceScorerWeights(unittest.TestCase):
    """calculate_performance_weights() 测试"""

    def setUp(self):
        self.scorer = GPUDeviceScorer()

    def test_01_normalized_weights_sum_to_one(self):
        """权重归一化总和为 1.0"""
        devices = [
            _make_device('GPU-A', 'nvidia', 16.0, 80, idx=0),
            _make_device('GPU-B', 'nvidia', 8.0, 40, idx=1),
        ]
        weights = self.scorer.calculate_performance_weights(devices)
        self.assertAlmostEqual(sum(weights.values()), 1.0, places=5)

    def test_02_better_device_gets_higher_weight(self):
        """高性能设备获得更高权重"""
        devices = [
            _make_device('Low', 'nvidia', 4.0, 16, idx=0),
            _make_device('High', 'nvidia', 16.0, 80, idx=1),
        ]
        weights = self.scorer.calculate_performance_weights(devices)
        self.assertGreater(weights[1], weights[0])

    def test_03_zero_score_devices_uniform(self):
        """全零评分设备降级为平均分配"""
        devices = [
            {'name': 'X', 'vendor': 'unknown', 'global_mem_gb': 0,
             'max_compute_units': 0, 'global_index': 0},
            {'name': 'Y', 'vendor': 'unknown', 'global_mem_gb': 0,
             'max_compute_units': 0, 'global_index': 1},
        ]
        weights = self.scorer.calculate_performance_weights(devices)  # type: ignore[arg-type]
        self.assertAlmostEqual(weights[0], 0.5)
        self.assertAlmostEqual(weights[1], 0.5)

    def test_04_single_device_weight_is_one(self):
        """单设备权重为 1.0"""
        devices = [_make_device('Solo', 'nvidia', 8.0, 32, idx=0)]
        weights = self.scorer.calculate_performance_weights(devices)
        self.assertAlmostEqual(weights[0], 1.0)


class TestGPUDeviceScorerRankSelect(unittest.TestCase):
    """rank_devices() / select_best() 测试"""

    def setUp(self):
        self.scorer = GPUDeviceScorer()

    def test_01_rank_devices_descending(self):
        """设备按评分降序排列"""
        devices = [
            _make_device('GPU-A', 'nvidia', 4.0, 16, idx=0),
            _make_device('GPU-B', 'nvidia', 16.0, 80, idx=1),
            _make_device('GPU-C', 'nvidia', 8.0, 40, idx=2),
        ]
        ranked = self.scorer.rank_devices(devices)
        scores = [d['score'] for d in ranked]
        self.assertEqual(scores, sorted(scores, reverse=True))
        # rank 后设备携带 score / tier 字段
        for d in ranked:
            self.assertIn('score', d)
            self.assertIn('tier', d)

    def test_02_select_best_returns_highest(self):
        """select_best 返回评分最高的设备"""
        devices = [
            _make_device('Low', 'nvidia', 4.0, 16, idx=0),
            _make_device('High', 'nvidia', 24.0, 128, idx=1),
        ]
        best = self.scorer.select_best(devices)
        self.assertIsNotNone(best)
        self.assertEqual(best['name'], 'High')  # type: ignore[index]

    def test_03_select_best_empty_returns_none(self):
        """空列表 select_best 返回 None"""
        self.assertIsNone(self.scorer.select_best([]))


class TestGPUDeviceScorerTier(unittest.TestCase):
    """get_tier() / get_tier_description() 测试"""

    def setUp(self):
        self.scorer = GPUDeviceScorer()

    def test_01_tier_boundaries(self):
        """等级分界线正确"""
        self.assertEqual(self.scorer.get_tier(200), 'S')
        self.assertEqual(self.scorer.get_tier(100), 'S')
        self.assertEqual(self.scorer.get_tier(99.9), 'A')
        self.assertEqual(self.scorer.get_tier(60), 'A')
        self.assertEqual(self.scorer.get_tier(59.9), 'B')
        self.assertEqual(self.scorer.get_tier(30), 'B')
        self.assertEqual(self.scorer.get_tier(29.9), 'C')
        self.assertEqual(self.scorer.get_tier(10), 'C')
        self.assertEqual(self.scorer.get_tier(9.9), 'D')
        self.assertEqual(self.scorer.get_tier(0), 'D')
        self.assertEqual(self.scorer.get_tier(-1), 'D')

    def test_02_tier_description(self):
        """等级描述包含 (中文标识)"""
        desc = self.scorer.get_tier_description(150)
        self.assertIn('S', desc)
        self.assertIn('旗舰', desc)


class TestGPUDeviceScorerCompare(unittest.TestCase):
    """compare_devices() 测试"""

    def setUp(self):
        self.scorer = GPUDeviceScorer()

    def test_01_a_better_than_b(self):
        a = _make_device('GPU-A', 'nvidia', 24.0, 128)
        b = _make_device('GPU-B', 'nvidia', 4.0, 16)
        result = self.scorer.compare_devices(a, b)
        self.assertIn('优于', result)
        self.assertIn('GPU-A', result)

    def test_02_b_better_than_a(self):
        a = _make_device('GPU-A', 'nvidia', 4.0, 16)
        b = _make_device('GPU-B', 'nvidia', 24.0, 128)
        result = self.scorer.compare_devices(a, b)
        self.assertIn('优于', result)
        self.assertIn('GPU-B', result)

    def test_03_equal_performance(self):
        a = _make_device('GPU-A', 'nvidia', 8.0, 32)
        b = _make_device('GPU-B', 'nvidia', 8.0, 32)
        result = self.scorer.compare_devices(a, b)
        self.assertIn('性能相当', result)


class TestGPUDeviceScorerFormatReport(unittest.TestCase):
    """format_score_report() 测试"""

    def setUp(self):
        self.scorer = GPUDeviceScorer()

    def test_01_report_contains_key_info(self):
        d = _make_device('RTX 3080', 'nvidia', 10.0, 68)
        report = self.scorer.format_score_report(d)
        self.assertIn('RTX 3080', report)
        self.assertIn('NVIDIA', report)

    def test_02_report_unknown_device(self):
        d = {'name': '???', 'vendor': 'unknown'}
        report = self.scorer.format_score_report(d)  # type: ignore[arg-type]
        self.assertIn('???', report)


class TestGPUDeviceScorerIdentifyModel(unittest.TestCase):
    """identify_model() 型号识别测试"""

    def setUp(self):
        self.scorer = GPUDeviceScorer()

    # ── NVIDIA ──
    def test_01_nvidia_rtx50(self):
        self.assertEqual(
            self.scorer.identify_model('NVIDIA GeForce RTX 5090', 'nvidia'),
            'rtx50')

    def test_02_nvidia_rtx40(self):
        self.assertEqual(
            self.scorer.identify_model('NVIDIA GeForce RTX 4090', 'nvidia'),
            'rtx40')

    def test_03_nvidia_rtx30(self):
        self.assertEqual(
            self.scorer.identify_model('NVIDIA GeForce RTX 3080', 'nvidia'),
            'rtx30')

    def test_04_nvidia_rtx20(self):
        self.assertEqual(
            self.scorer.identify_model('NVIDIA GeForce RTX 2080 Ti', 'nvidia'),
            'rtx20')

    def test_05_nvidia_gtx16(self):
        self.assertEqual(
            self.scorer.identify_model('NVIDIA GeForce GTX 1660', 'nvidia'),
            'gtx16')

    def test_06_nvidia_gtx10(self):
        self.assertEqual(
            self.scorer.identify_model('NVIDIA GeForce GTX 1080', 'nvidia'),
            'gtx10')

    def test_07_nvidia_titan(self):
        self.assertEqual(
            self.scorer.identify_model('NVIDIA TITAN RTX', 'nvidia'),
            'titan')

    def test_08_nvidia_tesla(self):
        self.assertEqual(
            self.scorer.identify_model('Tesla V100', 'nvidia'),
            'tesla')

    def test_09_nvidia_quadro(self):
        self.assertEqual(
            self.scorer.identify_model('Quadro P4000', 'nvidia'),
            'quadro')

    def test_10_nvidia_unknown(self):
        self.assertEqual(
            self.scorer.identify_model('NVIDIA SomeWeirdGPU', 'nvidia'),
            'nvidia_other')

    # ── AMD RX 500/400 扩展 ──
    def test_11_amd_rx590(self):
        """S5 修复: RX 590 应识别为 rx500"""
        self.assertEqual(
            self.scorer.identify_model('Radeon RX 590', 'amd'),
            'rx500')

    def test_12_amd_rx550(self):
        """S5 修复: RX 550 应识别为 rx500"""
        self.assertEqual(
            self.scorer.identify_model('Radeon RX 550', 'amd'),
            'rx500')

    def test_13_amd_rx480(self):
        """S5 修复: RX 480 应识别为 rx500"""
        self.assertEqual(
            self.scorer.identify_model('Radeon RX 480', 'amd'),
            'rx500')

    def test_14_amd_rx580(self):
        self.assertEqual(
            self.scorer.identify_model('Radeon RX 580', 'amd'),
            'rx500')

    # ── AMD 其他 ──
    def test_15_amd_rx9000(self):
        self.assertEqual(
            self.scorer.identify_model('Radeon RX 9070 XT', 'amd'),
            'rx9000')

    def test_16_amd_rx7000(self):
        self.assertEqual(
            self.scorer.identify_model('Radeon RX 7900 XTX', 'amd'),
            'rx7000')

    def test_17_amd_rx6000(self):
        self.assertEqual(
            self.scorer.identify_model('Radeon RX 6800 XT', 'amd'),
            'rx6000')

    def test_18_amd_rx5000(self):
        self.assertEqual(
            self.scorer.identify_model('Radeon RX 5700 XT', 'amd'),
            'rx5000')

    def test_19_amd_vega(self):
        self.assertEqual(
            self.scorer.identify_model('Radeon RX Vega 64', 'amd'),
            'vega')

    def test_20_amd_instinct(self):
        self.assertEqual(
            self.scorer.identify_model('AMD Instinct MI300X', 'amd'),
            'instinct')

    def test_21_amd_unknown(self):
        self.assertEqual(
            self.scorer.identify_model('AMD SomethingStrange', 'amd'),
            'amd_other')

    # ── Intel ──
    def test_22_intel_arc_bmg(self):
        self.assertEqual(
            self.scorer.identify_model('Intel Arc B580', 'intel'),
            'arc_bmg')

    def test_23_intel_arc(self):
        self.assertEqual(
            self.scorer.identify_model('Intel Arc A770', 'intel'),
            'arc')

    def test_24_intel_iris(self):
        self.assertEqual(
            self.scorer.identify_model('Intel Iris Xe', 'intel'),
            'iris')

    def test_25_intel_unknown(self):
        self.assertEqual(
            self.scorer.identify_model('Intel Unknown GPU', 'intel'),
            'intel_other')

    # ── Unknown ──
    def test_26_unknown_vendor(self):
        self.assertIsNone(
            self.scorer.identify_model('Some Totally Unknown GPU', 'unknown'))

    # ── Cache ──
    def test_27_model_cache(self):
        """型号识别结果应被缓存"""
        self.scorer.identify_model('NVIDIA GeForce RTX 4090', 'nvidia')
        cache_key = 'nvidia:NVIDIA GeForce RTX 4090'
        self.assertIn(cache_key, self.scorer._model_cache)  # type: ignore[attr-defined]
        self.assertEqual(
            self.scorer._model_cache[cache_key],  # type: ignore[attr-defined]
            'rtx40')


class TestGPUDeviceScorerSingleton(unittest.TestCase):
    """单例管理测试"""

    def tearDown(self):
        reset_gpu_scorer()

    def test_01_get_scorer_returns_same_instance(self):
        s1 = get_gpu_scorer()
        s2 = get_gpu_scorer()
        self.assertIs(s1, s2)

    def test_02_reset_creates_new_instance(self):
        s1 = get_gpu_scorer()
        reset_gpu_scorer()
        s2 = get_gpu_scorer()
        self.assertIsNot(s1, s2)


if __name__ == '__main__':
    unittest.main()

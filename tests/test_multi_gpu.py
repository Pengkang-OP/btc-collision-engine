# -*- coding: utf-8 -*-
"""多GPU功能单元测试"""

import unittest
from unittest.mock import Mock, patch
from typing import Dict, List


class TestGPUDeviceSelector(unittest.TestCase):
    """测试GPU设备选择器"""
    
    def setUp(self):
        """测试准备"""
        from src.gpu.selector import GPUDeviceSelector
        self.selector = GPUDeviceSelector()
    
    def test_score_device_nvidia(self):
        """测试NVIDIA设备评分"""
        device = {
            'global_index': 0,
            'name': 'NVIDIA GeForce GTX 1660 Ti',
            'vendor': 'nvidia',
            'global_mem_gb': 6.0,
            'max_compute_units': 24
        }
        
        score = self.selector.score_device(device)
        
        # 预期: (6*10 + 24*0.05) * 1.0 = 61.2
        expected = (6.0 * 10.0 + 24 * 0.05) * 1.0
        self.assertAlmostEqual(score, expected, places=1)
    
    def test_score_device_intel(self):
        """测试Intel设备评分"""
        device = {
            'global_index': 1,
            'name': 'Intel Arc A770',
            'vendor': 'intel',
            'global_mem_gb': 16.0,
            'max_compute_units': 512
        }
        
        score = self.selector.score_device(device)
        
        # 预期: (16*10 + 512*0.05) * 0.9 = 167.04
        expected = (16.0 * 10.0 + 512 * 0.05) * 0.9
        self.assertAlmostEqual(score, expected, places=1)
    
    def test_select_best_device(self):
        """测试选择最佳设备"""
        devices = [
            {
                'global_index': 0,
                'name': 'GPU 0',
                'vendor': 'nvidia',
                'global_mem_gb': 6.0,
                'max_compute_units': 24,
                'score': 61.2
            },
            {
                'global_index': 1,
                'name': 'GPU 1',
                'vendor': 'intel',
                'global_mem_gb': 16.0,
                'max_compute_units': 512,
                'score': 167.04
            }
        ]
        
        best = self.selector.select_best_device(devices)
        
        self.assertEqual(best['global_index'], 1)
        self.assertEqual(best['score'], 167.04)


class TestGPULoadBalancer(unittest.TestCase):
    """测试GPU负载均衡器"""
    
    def setUp(self):
        """测试准备"""
        from src.gpu.load_balancer import GPULoadBalancer
        
        self.devices = [
            {
                'global_index': 0,
                'name': 'GPU 0',
                'vendor': 'nvidia',
                'global_mem_gb': 6.0,
                'max_compute_units': 24
            },
            {
                'global_index': 1,
                'name': 'GPU 1',
                'vendor': 'intel',
                'global_mem_gb': 16.0,
                'max_compute_units': 512
            }
        ]
    
    def test_performance_weights(self):
        """测试性能权重计算"""
        from src.gpu.load_balancer import GPULoadBalancer
        
        balancer = GPULoadBalancer(self.devices, strategy='performance')
        weights = balancer.calculate_weights()
        
        # 权重总和应为1
        total = sum(weights.values())
        self.assertAlmostEqual(total, 1.0, places=2)
        
        # GPU 1(16GB)权重应大于GPU 0(6GB)
        self.assertGreater(weights[1], weights[0])
    
    def test_equal_weights(self):
        """测试平均分配权重"""
        from src.gpu.load_balancer import GPULoadBalancer
        
        balancer = GPULoadBalancer(self.devices, strategy='equal')
        weights = balancer.calculate_weights()
        
        # 所有权重应相等
        self.assertAlmostEqual(weights[0], 0.5, places=2)
        self.assertAlmostEqual(weights[1], 0.5, places=2)
    
    def test_assign_key_range(self):
        """测试私钥范围分配"""
        from src.gpu.load_balancer import GPULoadBalancer
        
        balancer = GPULoadBalancer(self.devices, strategy='equal')
        start, end = balancer.assign_key_range(1000000, device_idx=0)
        
        # 50%权重应分配500K keys
        self.assertEqual(end - start, 500000)


class TestGPUAutoConfigurator(unittest.TestCase):
    """测试GPU自动调优器"""
    
    def setUp(self):
        """测试准备"""
        from src.gpu.auto_config import GPUAutoConfigurator
        self.configurator = GPUAutoConfigurator()
    
    def test_nvidia_config(self):
        """测试NVIDIA配置"""
        device = {
            'vendor': 'nvidia',
            'global_mem_gb': 8.0
        }
        
        config = self.configurator.get_nvidia_config(device)
        
        self.assertEqual(config['use_uint32_workaround'], False)
        self.assertEqual(config['use_fast_math'], True)
        self.assertIn(config['batch_size'], [32768, 65536, 131072])
    
    def test_intel_config(self):
        """测试Intel配置（v3.1.0: Arc A770 16GB优化为1048576）"""
        device = {
            'vendor': 'intel',
            'global_mem_gb': 16.0
        }
        
        config = self.configurator.get_intel_config(device)
        
        self.assertEqual(config['use_uint32_workaround'], True)
        self.assertEqual(config['use_fast_math'], False)
        # v3.1.0优化: Arc A770(16GB)使用1048576批次; 低显存设备使用更小批次
        self.assertIn(config['batch_size'], [65536, 131072, 262144, 1048576])

    def test_configure_for_device_intel_full_vendor_name(self):
        """测试完整厂商名称路由 - Intel(R) Corporation 应走 INTEL_ARC_CONFIG"""
        device = {
            'vendor': 'Intel(R) Corporation',
            'name': 'Intel(R) Arc(TM) A770 Graphics',
            'global_mem_size': 15 * 1024 ** 3
        }
        config = self.configurator.configure_for_device(device)
        self.assertTrue(config['enable_async'],          "Intel Arc 应启用异步执行")
        self.assertTrue(config['use_uint32_workaround'], "Intel Arc 应启用uint32 workaround")
        self.assertFalse(config['use_fast_math'],         "Intel Arc 应禁用快速数学")
        self.assertEqual(config['batch_size'], 1048576,   "Intel Arc A770(≥15GB) 应使用1048576批次(v3.1.0优化)")

    def test_configure_for_device_amd_full_vendor_name(self):
        """测试完整厂商名称路由 - Advanced Micro Devices, Inc. 应走 AMD_CONFIG"""
        device = {
            'vendor': 'Advanced Micro Devices, Inc.',
            'name': 'AMD Radeon RX 6800 XT',
            'global_mem_size': 16 * 1024 ** 3
        }
        config = self.configurator.configure_for_device(device)
        self.assertTrue(config['enable_async'],           "AMD GPU 应启用异步执行")
        self.assertFalse(config['use_uint32_workaround'], "AMD GPU 不需要uint32 workaround")

    def test_configure_for_device_unknown_vendor(self):
        """测试未知厂商应回退到保守配置"""
        device = {
            'vendor': 'SomeUnknownVendor',
            'name': 'Unknown GPU',
            'global_mem_size': 4 * 1024 ** 3
        }
        config = self.configurator.configure_for_device(device)
        self.assertFalse(config['enable_async'],          "未知厂商应禁用异步执行")
        self.assertFalse(config['use_uint32_workaround'], "未知厂商应禁用uint32 workaround")


class TestGPUConfigValidator(unittest.TestCase):
    """测试GPU配置验证器"""
    
    def setUp(self):
        """测试准备"""
        from src.gpu.config_validator import GPUConfigValidator
        self.validator = GPUConfigValidator()
    
    def test_valid_config(self):
        """测试有效配置"""
        config = {
            'mode': 'multi',
            'device_indices': [0, 1],
            'load_balancing': 'performance',
            'auto_tuning': True,
            'per_device_config': {}
        }
        
        is_valid, errors = self.validator.validate_config(config)
        
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
    
    def test_invalid_mode(self):
        """测试无效模式"""
        config = {
            'mode': 'invalid',
            'device_indices': [0]
        }
        
        is_valid, errors = self.validator.validate_config(config)
        
        self.assertFalse(is_valid)
        self.assertTrue(any('模式' in err or 'mode' in err for err in errors))
    
    def test_suggest_config_multi(self):
        """测试多GPU配置建议"""
        devices = [
            {
                'global_index': 0,
                'vendor': 'nvidia',
                'global_mem_gb': 6.0,
                'score': 61.2
            },
            {
                'global_index': 1,
                'vendor': 'intel',
                'global_mem_gb': 16.0,
                'score': 167.04
            }
        ]
        
        config = self.validator.suggest_config(devices, mode='multi')
        
        self.assertEqual(config['mode'], 'multi')
        self.assertEqual(config['device_indices'], [0, 1])
        self.assertEqual(config['load_balancing'], 'performance')


if __name__ == '__main__':
    unittest.main()

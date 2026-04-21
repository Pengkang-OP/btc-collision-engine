#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GPUDeviceHelper单元测试

测试src.gpu.device_helper模块的所有功能。

测试覆盖:
- RESOURCE_ERROR_KEYWORDS类常量
- handle_gpu_batch_error()错误处理方法
- is_resource_error()判断方法
- get_device_capabilities()设备能力查询
"""

import pytest
import logging
from unittest.mock import Mock
from src.gpu.device_helper import GPUDeviceHelper


# P2修复：提取FakeGPUDevice类消除重复代码
class FakeGPUDevice:
    """Fake GPU设备，用于测试get_device_capabilities()
    
    使用kwargs动态设置属性，未设置的属性不存在（而非None），
    让GPUDeviceHelper.get_device_capabilities()使用getattr的默认值。
    
    使用示例:
        >>> # 空设备（所有属性使用默认值）
        >>> device = FakeGPUDevice()
        >>> 
        >>> # 部分属性
        >>> device = FakeGPUDevice(
        ...     max_work_group_size=1024,
        ...     max_compute_units=40
        ... )
        >>> 
        >>> # 完整属性
        >>> device = FakeGPUDevice(
        ...     max_work_group_size=512,
        ...     max_compute_units=20,
        ...     global_mem_size=8_000_000_000,
        ...     local_mem_size=65536,
        ...     enable_async_execution=True
        ... )
    """
    
    def __init__(self, **kwargs):
        """初始化FakeGPU设备
        
        Args:
            **kwargs: 设备属性（max_work_group_size, max_compute_units, etc.）
        """
        # 只设置提供的属性，未提供的属性不存在
        # 这样getattr(device, attr, default)会使用default值
        if 'max_work_group_size' in kwargs:
            self.max_work_group_size = kwargs['max_work_group_size']
        if 'max_compute_units' in kwargs:
            self.max_compute_units = kwargs['max_compute_units']
        if 'global_mem_size' in kwargs:
            self.global_mem_size = kwargs['global_mem_size']
        if 'local_mem_size' in kwargs:
            self.local_mem_size = kwargs['local_mem_size']
        if 'enable_async_execution' in kwargs:
            self.enable_async_execution = kwargs['enable_async_execution']


class TestResourceErrorKeywords:
    """测试RESOURCE_ERROR_KEYWORDS类常量
    
    测试策略:
    - 验证类常量存在且为列表
    - 测试包含8个关键词
    - 验证每个关键词都是小写
    - 确保无重复关键词
    
    关键词列表:
    - out of resources: OpenCL通用资源不足
    - memory: 内存相关错误
    - out of memory: 内存耗尽
    - allocation failed: 分配失败
    - insufficient: 资源不足
    - resource exhausted: 资源耗尽
    - cl_out_of_resources: OpenCL特定错误
    - cl_mem_object_allocation_failure: OpenCL内存分配失败
    """
    
    def test_keywords_exists(self):
        """测试类常量存在"""
        assert hasattr(GPUDeviceHelper, 'RESOURCE_ERROR_KEYWORDS')
    
    def test_keywords_is_list(self):
        """测试类常量是列表"""
        assert isinstance(GPUDeviceHelper.RESOURCE_ERROR_KEYWORDS, list)
    
    def test_keywords_count(self):
        """测试关键词数量"""
        assert len(GPUDeviceHelper.RESOURCE_ERROR_KEYWORDS) == 8
    
    def test_keywords_contains_out_of_resources(self):
        """测试包含out of resources关键词"""
        assert "out of resources" in GPUDeviceHelper.RESOURCE_ERROR_KEYWORDS
    
    def test_keywords_contains_memory(self):
        """测试包含memory关键词"""
        assert "memory" in GPUDeviceHelper.RESOURCE_ERROR_KEYWORDS
    
    def test_keywords_contains_out_of_memory(self):
        """测试包含out of memory关键词"""
        assert "out of memory" in GPUDeviceHelper.RESOURCE_ERROR_KEYWORDS
    
    def test_keywords_contains_allocation_failed(self):
        """测试包含allocation failed关键词"""
        assert "allocation failed" in GPUDeviceHelper.RESOURCE_ERROR_KEYWORDS
    
    def test_keywords_contains_insufficient(self):
        """测试包含insufficient关键词"""
        assert "insufficient" in GPUDeviceHelper.RESOURCE_ERROR_KEYWORDS
    
    def test_keywords_contains_resource_exhausted(self):
        """测试包含resource exhausted关键词"""
        assert "resource exhausted" in GPUDeviceHelper.RESOURCE_ERROR_KEYWORDS
    
    def test_keywords_contains_cl_out_of_resources(self):
        """测试包含OpenCL特定关键词"""
        assert "cl_out_of_resources" in GPUDeviceHelper.RESOURCE_ERROR_KEYWORDS
    
    def test_keywords_contains_cl_mem_object_allocation_failure(self):
        """测试包含OpenCL内存分配失败关键词"""
        assert "cl_mem_object_allocation_failure" in GPUDeviceHelper.RESOURCE_ERROR_KEYWORDS
    
    def test_keywords_all_lowercase(self):
        """测试所有关键词都是小写"""
        for keyword in GPUDeviceHelper.RESOURCE_ERROR_KEYWORDS:
            assert keyword == keyword.lower()
    
    def test_keywords_no_duplicates(self):
        """测试无重复关键词"""
        assert len(GPUDeviceHelper.RESOURCE_ERROR_KEYWORDS) == len(
            set(GPUDeviceHelper.RESOURCE_ERROR_KEYWORDS)
        )


class TestHandleGPUBatchError:
    """测试handle_gpu_batch_error()错误处理方法
    
    测试策略:
    - 测试6种异常类型（RuntimeError, ValueError, TypeError, OverflowError, Exception）
    - 验证资源错误和非资源错误的区分
    - 测试不同计算模式（random, scan, brute）
    - 验证stats对象调用正确
    - 测试日志记录内容
    - 确保总是返回True
    
    异常分类:
    - 资源错误: RuntimeError/ValueError包含关键词
    - 数据错误: TypeError/OverflowError (WIF编码错误)
    - 未知错误: 其他Exception (记录完整堆栈)
    """
    
    def test_handle_runtime_error_resource_error(self, caplog):
        """测试处理RuntimeError资源错误"""
        error = RuntimeError("out of memory")
        stats = Mock()
        
        with caplog.at_level(logging.ERROR):
            result = GPUDeviceHelper.handle_gpu_batch_error("random", error, stats)
        
        assert result is True
        stats.record_gpu_error.assert_called_once_with(is_resource_error=True)
        assert "资源不足" in caplog.text
    
    def test_handle_runtime_error_non_resource_error(self, caplog):
        """测试处理RuntimeError非资源错误"""
        error = RuntimeError("some other error")
        stats = Mock()
        
        with caplog.at_level(logging.ERROR):
            result = GPUDeviceHelper.handle_gpu_batch_error("random", error, stats)
        
        assert result is True
        stats.record_gpu_error.assert_called_once_with(is_resource_error=False)
        assert "运行时错误" in caplog.text
    
    def test_handle_value_error_resource_error(self, caplog):
        """测试处理ValueError资源错误"""
        error = ValueError("allocation failed")
        stats = Mock()
        
        with caplog.at_level(logging.ERROR):
            result = GPUDeviceHelper.handle_gpu_batch_error("scan", error, stats)
        
        assert result is True
        stats.record_gpu_error.assert_called_once_with(is_resource_error=True)
    
    def test_handle_type_error(self, caplog):
        """测试处理TypeError"""
        error = TypeError("invalid type")
        stats = Mock()
        
        with caplog.at_level(logging.ERROR):
            result = GPUDeviceHelper.handle_gpu_batch_error("brute", error, stats)
        
        assert result is True
        stats.record_gpu_error.assert_called_once_with(is_resource_error=False)
        stats.record_wif_encode_error.assert_called_once()
        assert "数据错误" in caplog.text
    
    def test_handle_overflow_error(self, caplog):
        """测试处理OverflowError"""
        error = OverflowError("value too large")
        stats = Mock()
        
        with caplog.at_level(logging.ERROR):
            result = GPUDeviceHelper.handle_gpu_batch_error("random", error, stats)
        
        assert result is True
        stats.record_gpu_error.assert_called_once_with(is_resource_error=False)
        stats.record_wif_encode_error.assert_called_once()
    
    def test_handle_unknown_error(self, caplog):
        """测试处理未知错误"""
        error = Exception("unknown error")
        stats = Mock()
        
        with caplog.at_level(logging.ERROR):
            result = GPUDeviceHelper.handle_gpu_batch_error("random", error, stats)
        
        assert result is True
        stats.record_gpu_error.assert_called_once_with(is_resource_error=False)
        assert "未知错误" in caplog.text
    
    def test_handle_error_without_stats(self, caplog):
        """测试处理错误时stats为None"""
        error = RuntimeError("out of resources")
        
        with caplog.at_level(logging.ERROR):
            result = GPUDeviceHelper.handle_gpu_batch_error("random", error, None)
        
        assert result is True
        # 不应抛出异常
    
    def test_handle_error_different_modes(self, caplog):
        """测试不同模式下的错误处理"""
        modes = ["random", "scan", "brute"]
        
        for mode in modes:
            error = RuntimeError("test error")
            stats = Mock()
            
            with caplog.at_level(logging.ERROR):
                result = GPUDeviceHelper.handle_gpu_batch_error(mode, error, stats)
            
            assert result is True
            assert mode in caplog.text
    
    def test_handle_error_memory_keyword(self, caplog):
        """测试memory关键词匹配"""
        error = RuntimeError("insufficient memory")
        stats = Mock()
        
        with caplog.at_level(logging.ERROR):
            result = GPUDeviceHelper.handle_gpu_batch_error("random", error, stats)
        
        assert result is True
        stats.record_gpu_error.assert_called_once_with(is_resource_error=True)
    
    def test_handle_error_cl_out_of_resources(self, caplog):
        """测试OpenCL cl_out_of_resources关键词"""
        error = RuntimeError("CL_OUT_OF_RESOURCES")
        stats = Mock()
        
        with caplog.at_level(logging.ERROR):
            result = GPUDeviceHelper.handle_gpu_batch_error("random", error, stats)
        
        assert result is True
        stats.record_gpu_error.assert_called_once_with(is_resource_error=True)
    
    def test_handle_error_case_insensitive(self, caplog):
        """测试关键词匹配不区分大小写"""
        error = RuntimeError("OUT OF MEMORY")
        stats = Mock()
        
        with caplog.at_level(logging.ERROR):
            result = GPUDeviceHelper.handle_gpu_batch_error("random", error, stats)
        
        assert result is True
        stats.record_gpu_error.assert_called_once_with(is_resource_error=True)
    
    def test_handle_error_always_returns_true(self):
        """测试总是返回True"""
        errors = [
            RuntimeError("error 1"),
            ValueError("error 2"),
            TypeError("error 3"),
            Exception("error 4")
        ]
        
        for error in errors:
            result = GPUDeviceHelper.handle_gpu_batch_error("random", error, None)
            assert result is True


class TestIsResourceError:
    """测试is_resource_error()资源错误判断方法
    
    测试策略:
    - 测试8个资源关键词的匹配
    - 验证不区分大小写
    - 测试关键词在不同位置（开头/中间/结尾）
    - 验证非资源错误返回False
    - 测试不同异常类型
    
    判断规则:
    - 只接受RuntimeError和ValueError
    - 错误消息包含RESOURCE_ERROR_KEYWORDS中的任一关键词
    - 不区分大小写匹配
    """
    
    def test_runtime_error_resource_error(self):
        """测试RuntimeError资源错误"""
        error = RuntimeError("out of memory")
        assert GPUDeviceHelper.is_resource_error(error) is True
    
    def test_runtime_error_non_resource_error(self):
        """测试RuntimeError非资源错误"""
        error = RuntimeError("some other error")
        assert GPUDeviceHelper.is_resource_error(error) is False
    
    def test_value_error_resource_error(self):
        """测试ValueError资源错误"""
        error = ValueError("allocation failed")
        assert GPUDeviceHelper.is_resource_error(error) is True
    
    def test_type_error_not_resource_error(self):
        """测试TypeError不是资源错误"""
        error = TypeError("invalid type")
        assert GPUDeviceHelper.is_resource_error(error) is False
    
    def test_exception_not_resource_error(self):
        """测试普通Exception不是资源错误"""
        error = Exception("unknown")
        assert GPUDeviceHelper.is_resource_error(error) is False
    
    def test_out_of_resources_keyword(self):
        """测试out of resources关键词"""
        error = RuntimeError("cl_out_of_resources")
        assert GPUDeviceHelper.is_resource_error(error) is True
    
    def test_memory_keyword(self):
        """测试memory关键词"""
        error = RuntimeError("insufficient memory")
        assert GPUDeviceHelper.is_resource_error(error) is True
    
    def test_out_of_memory_keyword(self):
        """测试out of memory关键词"""
        error = RuntimeError("out of memory")
        assert GPUDeviceHelper.is_resource_error(error) is True
    
    def test_allocation_failed_keyword(self):
        """测试allocation failed关键词"""
        error = RuntimeError("allocation failed")
        assert GPUDeviceHelper.is_resource_error(error) is True
    
    def test_insufficient_keyword(self):
        """测试insufficient关键词"""
        error = RuntimeError("insufficient resources")
        assert GPUDeviceHelper.is_resource_error(error) is True
    
    def test_resource_exhausted_keyword(self):
        """测试resource exhausted关键词"""
        error = RuntimeError("resource exhausted")
        assert GPUDeviceHelper.is_resource_error(error) is True
    
    def test_cl_mem_object_allocation_failure_keyword(self):
        """测试cl_mem_object_allocation_failure关键词"""
        error = RuntimeError("cl_mem_object_allocation_failure")
        assert GPUDeviceHelper.is_resource_error(error) is True
    
    def test_case_insensitive_matching(self):
        """测试不区分大小写匹配"""
        error = RuntimeError("OUT OF MEMORY")
        assert GPUDeviceHelper.is_resource_error(error) is True
    
    def test_error_message_in_middle(self):
        """测试关键词在消息中间"""
        error = RuntimeError("Error: out of memory during allocation")
        assert GPUDeviceHelper.is_resource_error(error) is True
    
    def test_error_message_at_start(self):
        """测试关键词在消息开头"""
        error = RuntimeError("out of resources: cannot allocate")
        assert GPUDeviceHelper.is_resource_error(error) is True
    
    def test_error_message_at_end(self):
        """测试关键词在消息结尾"""
        error = RuntimeError("Failed: allocation failed")
        assert GPUDeviceHelper.is_resource_error(error) is True


class TestGetDeviceCapabilities:
    """测试get_device_capabilities()设备能力查询方法
    
    测试策略:
    - 测试完整属性设置
    - 测试部分属性设置
    - 测试缺失属性（使用默认值）
    - 验证返回字典包含所有键
    - 测试默认值正确性
    - 验证大数值处理
    
    返回字段:
    - max_work_group_size: 最大工作组大小 (默认256)
    - max_compute_units: 计算单元数 (默认1)
    - global_mem_size: 全局内存大小 (默认0)
    - local_mem_size: 局部内存大小 (默认0)
    - enable_async_execution: 是否支持异步执行 (默认False)
    """
    
    def test_get_capabilities_with_all_attributes(self):
        """测试获取完整设备能力"""
        device = Mock()
        device.max_work_group_size = 512
        device.max_compute_units = 20
        device.global_mem_size = 8_000_000_000
        device.local_mem_size = 65536
        device.enable_async_execution = True
        
        caps = GPUDeviceHelper.get_device_capabilities(device)
        
        assert caps['max_work_group_size'] == 512
        assert caps['max_compute_units'] == 20
        assert caps['global_mem_size'] == 8_000_000_000
        assert caps['local_mem_size'] == 65536
        assert caps['enable_async_execution'] is True
    
    def test_get_capabilities_with_missing_attributes(self):
        """测试获取设备能力（缺少属性）"""
        # P2修复：使用FakeGPUDevice替代重复的类定义
        device = FakeGPUDevice()
        
        caps = GPUDeviceHelper.get_device_capabilities(device)
        
        assert caps['max_work_group_size'] == 256  # 默认值
        assert caps['max_compute_units'] == 1  # 默认值
        assert caps['global_mem_size'] == 0  # 默认值
        assert caps['local_mem_size'] == 0  # 默认值
        assert caps['enable_async_execution'] is False  # 默认值
    
    def test_get_capabilities_with_partial_attributes(self):
        """测试获取设备能力（部分属性）"""
        # P2修复：使用FakeGPUDevice替代重复的类定义
        device = FakeGPUDevice(
            max_work_group_size=1024,
            max_compute_units=40
            # 其他属性未设置，使用默认值
        )
        
        caps = GPUDeviceHelper.get_device_capabilities(device)
        
        assert caps['max_work_group_size'] == 1024
        assert caps['max_compute_units'] == 40
        assert caps['global_mem_size'] == 0  # 默认值
        assert caps['local_mem_size'] == 0  # 默认值
        assert caps['enable_async_execution'] is False  # 默认值
    
    def test_get_capabilities_returns_dict(self):
        """测试返回字典类型"""
        device = Mock()
        caps = GPUDeviceHelper.get_device_capabilities(device)
        
        assert isinstance(caps, dict)
    
    def test_get_capabilities_has_all_keys(self):
        """测试返回字典包含所有键"""
        device = Mock()
        caps = GPUDeviceHelper.get_device_capabilities(device)
        
        expected_keys = [
            'max_work_group_size',
            'max_compute_units',
            'global_mem_size',
            'local_mem_size',
            'enable_async_execution'
        ]
        
        for key in expected_keys:
            assert key in caps
    
    def test_get_capabilities_default_values(self):
        """测试默认值正确"""
        # P2修复：使用FakeGPUDevice替代重复的类定义
        device = FakeGPUDevice()
        
        caps = GPUDeviceHelper.get_device_capabilities(device)
        
        assert caps['max_work_group_size'] == 256
        assert caps['max_compute_units'] == 1
        assert caps['global_mem_size'] == 0
        assert caps['local_mem_size'] == 0
        assert caps['enable_async_execution'] is False
    
    def test_get_capabilities_large_values(self):
        """测试大数值设备能力"""
        device = Mock()
        device.max_work_group_size = 2048
        device.max_compute_units = 100
        device.global_mem_size = 32_000_000_000
        device.local_mem_size = 131072
        device.enable_async_execution = True
        
        caps = GPUDeviceHelper.get_device_capabilities(device)
        
        assert caps['max_work_group_size'] == 2048
        assert caps['max_compute_units'] == 100
        assert caps['global_mem_size'] == 32_000_000_000
        assert caps['local_mem_size'] == 131072


class TestGPUDeviceHelperIntegration:
    """测试GPUDeviceHelper集成场景
    
    测试策略:
    - 测试方法组合使用
    - 验证错误处理与资源错误判断的一致性
    - 测试设备能力查询后的实际使用
    - 验证静态方法的独立性
    
    集成场景:
    - handle_gpu_batch_error + is_resource_error
    - get_device_capabilities + 使用返回值
    - 静态方法独立调用
    """
    
    def test_handle_error_and_check_resource_error(self, caplog):
        """测试处理错误并检查是否资源错误"""
        error = RuntimeError("out of memory")
        stats = Mock()
        
        with caplog.at_level(logging.ERROR):
            result = GPUDeviceHelper.handle_gpu_batch_error("random", error, stats)
        
        assert result is True
        assert GPUDeviceHelper.is_resource_error(error) is True
    
    def test_handle_non_resource_error_and_check(self, caplog):
        """测试处理非资源错误并检查"""
        error = RuntimeError("some other error")
        stats = Mock()
        
        with caplog.at_level(logging.ERROR):
            result = GPUDeviceHelper.handle_gpu_batch_error("random", error, stats)
        
        assert result is True
        assert GPUDeviceHelper.is_resource_error(error) is False
    
    def test_get_capabilities_and_use_values(self):
        """测试获取设备能力并使用值"""
        device = Mock()
        device.max_work_group_size = 512
        device.max_compute_units = 20
        
        caps = GPUDeviceHelper.get_device_capabilities(device)
        
        # 使用设备能力
        batch_size = caps['max_work_group_size'] * caps['max_compute_units']
        assert batch_size == 10240
    
    def test_static_methods_are_independent(self):
        """测试静态方法相互独立"""
        # is_resource_error不依赖handle_gpu_batch_error
        error = RuntimeError("out of memory")
        
        assert GPUDeviceHelper.is_resource_error(error) is True
        
        # 直接调用handle_gpu_batch_error
        result = GPUDeviceHelper.handle_gpu_batch_error("random", error, None)
        assert result is True


class TestGPUDeviceHelperEdgeCases:
    """测试GPUDeviceHelper边界情况
    
    测试策略:
    - 测试空错误消息
    - 测试超长错误消息（10000+字符）
    - 测试特殊字符和Unicode
    - 测试多个关键词同时出现
    - 测试关键词作为单词的一部分
    - 测试设备属性为None
    
    边界场景:
    - 空字符串
    - 20000+字符长消息
    - 特殊字符: @#$%^&*()
    - Unicode: 中文、日文等
    - 多个关键词重叠
    - None属性值
    """
    
    def test_empty_error_message(self):
        """测试空错误消息"""
        error = RuntimeError("")
        assert GPUDeviceHelper.is_resource_error(error) is False
    
    def test_very_long_error_message(self):
        """测试非常长的错误消息"""
        error_msg = "A" * 10000 + "out of memory" + "B" * 10000
        error = RuntimeError(error_msg)
        assert GPUDeviceHelper.is_resource_error(error) is True
    
    def test_error_with_special_characters(self):
        """测试包含特殊字符的错误消息"""
        error = RuntimeError("Error: out of memory! @#$%^&*()")
        assert GPUDeviceHelper.is_resource_error(error) is True
    
    def test_error_with_unicode(self):
        """测试包含Unicode的错误消息"""
        error = RuntimeError("错误: out of memory 内存不足")
        assert GPUDeviceHelper.is_resource_error(error) is True
    
    def test_multiple_keywords_in_message(self):
        """测试消息包含多个关键词"""
        error = RuntimeError("out of memory: allocation failed")
        assert GPUDeviceHelper.is_resource_error(error) is True
    
    def test_keyword_as_part_of_word(self):
        """测试关键词作为单词的一部分"""
        error = RuntimeError("memory_usage is high")
        assert GPUDeviceHelper.is_resource_error(error) is True  # 包含"memory"
    
    def test_device_with_none_values(self):
        """测试设备属性为None"""
        device = Mock()
        device.max_work_group_size = None
        device.max_compute_units = None
        
        caps = GPUDeviceHelper.get_device_capabilities(device)
        
        # getattr的默认值应该被使用
        assert caps['max_work_group_size'] is None
        assert caps['max_compute_units'] is None

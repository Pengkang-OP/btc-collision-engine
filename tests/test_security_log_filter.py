#!/usr/bin/env python3
"""安全日志过滤器全面测试

测试SecurityLogFilter的各种场景：
1. 私钥十六进制格式检测
2. WIF格式私钥检测
3. 原始字节格式检测
4. 带0x前缀的私钥检测
5. 日志参数中的私钥检测
6. 掩码处理验证
7. 便捷函数测试
"""
import pytest
import logging
import hashlib
from logging.handlers import MemoryHandler
from src.utils.security_log_filter import (
    SecurityLogFilter,
    sanitize_private_key_for_log,
    log_safe_error,
    log_safe_debug
)


class TestSecurityLogFilter:
    """安全日志过滤器核心测试"""
    
    def setup_method(self):
        """设置测试环境"""
        self.filter = SecurityLogFilter(
            name='test_security_filter',
            mask_private_keys=True,
            mask_wif=True
        )
    
    def test_hex_private_key_detection(self):
        """测试64位十六进制私钥检测"""
        # 标准64位十六进制私钥
        test_key = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
        message = f"Found private key: {test_key}"
        
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='test.py',
            lineno=1,
            msg=message,
            args=(),
            exc_info=None
        )
        
        self.filter.filter(record)
        
        # 验证私钥被掩码
        assert test_key not in record.msg
        assert '[PRIVATE_KEY:' in record.msg
        assert '...]' in record.msg
    
    def test_hex_private_key_with_0x_prefix(self):
        """测试带0x前缀的私钥检测"""
        test_key = "0xa1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
        message = f"Key: {test_key}"
        
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='test.py',
            lineno=1,
            msg=message,
            args=(),
            exc_info=None
        )
        
        self.filter.filter(record)
        
        # 验证私钥被掩码（格式：[PRIVATE_KEY:hash...])
        assert test_key not in record.msg
        assert '[PRIVATE_KEY' in record.msg  # 不要求冒号后内容
    
    def test_wif_private_key_detection(self):
        """测试WIF格式私钥检测"""
        # WIF格式（以5开头）
        test_wif = "5Kb8kLf9zgWQnogidDA76MzPL6TsZZY36hWXMssSzNydYXYB9KF"
        message = f"WIF: {test_wif}"
        
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='test.py',
            lineno=1,
            msg=message,
            args=(),
            exc_info=None
        )
        
        self.filter.filter(record)
        
        # 验证WIF被掩码（格式：[WIF_PRIVATE_KEY]）
        assert test_wif not in record.msg
        assert '[WIF_PRIVATE_KEY]' in record.msg
    
    def test_wif_compressed_key_detection(self):
        """测试压缩WIF格式检测（以K/L开头）"""
        # 压缩WIF（以K开头）
        test_wif = "KxFC1jmwwCoACiCAWZ3eXa96mBM6tb3TYzGmf6YwgdGWZgawvrtJ"
        message = f"Compressed WIF: {test_wif}"
        
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='test.py',
            lineno=1,
            msg=message,
            args=(),
            exc_info=None
        )
        
        self.filter.filter(record)
        
        assert test_wif not in record.msg
        assert '[WIF_PRIVATE_KEY]' in record.msg
    
    def test_raw_bytes_key_detection(self):
        """测试原始字节格式私钥检测"""
        # 32字节的原始表示
        test_raw = "b'\\x01\\x02\\x03\\x04\\x05\\x06\\x07\\x08\\x09\\x0a\\x0b\\x0c\\x0d\\x0e\\x0f\\x10\\x11\\x12\\x13\\x14\\x15\\x16\\x17\\x18\\x19\\x1a\\x1b\\x1c\\x1d\\x1e\\x1f\\x20'"
        message = f"Raw key: {test_raw}"
        
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='test.py',
            lineno=1,
            msg=message,
            args=(),
            exc_info=None
        )
        
        self.filter.filter(record)
        
        # 验证原始字节被掩码（格式：[RAW_PRIVATE_KEY]）
        assert '[RAW_PRIVATE_KEY]' in record.msg
    
    def test_multiple_keys_in_message(self):
        """测试消息中包含多个私钥"""
        key1 = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
        key2 = "b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3"
        message = f"Keys: {key1} and {key2}"
        
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='test.py',
            lineno=1,
            msg=message,
            args=(),
            exc_info=None
        )
        
        self.filter.filter(record)
        
        # 验证两个私钥都被掩码
        assert key1 not in record.msg
        assert key2 not in record.msg
        assert record.msg.count('[PRIVATE_KEY:') == 2
    
    def test_no_false_positives(self):
        """测试无误报（普通文本不应被掩码）"""
        message = "Processing batch 12345, found 10 matches"
        
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='test.py',
            lineno=1,
            msg=message,
            args=(),
            exc_info=None
        )
        
        self.filter.filter(record)
        
        # 验证消息未被修改
        assert record.msg == message
    
    def test_mask_consistency(self):
        """测试掩码一致性（相同私钥应产生相同掩码）"""
        test_key = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
        
        message1 = f"Key1: {test_key}"
        message2 = f"Key2: {test_key}"
        
        record1 = logging.LogRecord(
            name='test', level=logging.INFO, pathname='test.py', lineno=1,
            msg=message1, args=(), exc_info=None
        )
        record2 = logging.LogRecord(
            name='test', level=logging.INFO, pathname='test.py', lineno=1,
            msg=message2, args=(), exc_info=None
        )
        
        self.filter.filter(record1)
        self.filter.filter(record2)
        
        # 提取掩码部分
        mask1 = record1.msg.split('[PRIVATE_KEY:')[1].split('...]')[0]
        mask2 = record2.msg.split('[PRIVATE_KEY:')[1].split('...]')[0]
        
        # 验证掩码一致
        assert mask1 == mask2


class TestLogRecordArgs:
    """测试日志参数中的私钥检测"""
    
    def setup_method(self):
        """设置测试环境"""
        self.filter = SecurityLogFilter(
            name='test_security_filter',
            mask_private_keys=True,
            mask_wif=True
        )
    
    def test_dict_args_with_private_key(self):
        """测试字典参数中的私钥"""
        test_key = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
        message = "Found key: %(key)s"
        
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='test.py',
            lineno=1,
            msg=message,
            args={'key': test_key},
            exc_info=None
        )
        
        self.filter.filter(record)
        
        # 验证参数中的私钥被掩码
        assert record.args['key'] != test_key
        assert '[PRIVATE_KEY:' in record.args['key']
    
    def test_tuple_args_with_private_key(self):
        """测试元组参数中的私钥"""
        test_key = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
        message = "Found key: %s"
        
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='test.py',
            lineno=1,
            msg=message,
            args=(test_key,),
            exc_info=None
        )
        
        self.filter.filter(record)
        
        # 验证参数中的私钥被掩码
        assert record.args[0] != test_key
        assert '[PRIVATE_KEY:' in record.args[0]


class TestMasking:
    """测试掩码处理"""
    
    def setup_method(self):
        """设置测试环境"""
        self.filter = SecurityLogFilter(
            name='test_security_filter',
            mask_private_keys=True,
            mask_wif=True
        )
    
    def test_mask_key_format(self):
        """测试私钥掩码格式"""
        test_key = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
        masked = self.filter._mask_key(test_key)
        
        # 验证格式
        assert masked.startswith('[PRIVATE_KEY:')
        assert masked.endswith('...]')
        
        # 验证包含SHA256哈希前16位
        expected_hash = hashlib.sha256(test_key.encode()).hexdigest()[:16]
        assert expected_hash in masked
    
    def test_mask_wif_format(self):
        """测试WIF掩码格式"""
        test_wif = "5Kb8kLf9zgWQnogidDA76MzPL6TsZZY36hWXMssSzNydYXYB9KF"
        masked = self.filter._mask_wif(test_wif)
        
        # 验证格式
        assert masked.startswith('[WIF:')
        assert masked.endswith('...]')
        
        # 验证包含SHA256哈希前16位
        expected_hash = hashlib.sha256(test_wif.encode()).hexdigest()[:16]
        assert expected_hash in masked
    
    def test_mask_raw_key_format(self):
        """测试原始字节掩码格式"""
        test_raw = "b'\\x01\\x02\\x03\\x04\\x05\\x06\\x07\\x08\\x09\\x0a\\x0b\\x0c\\x0d\\x0e\\x0f\\x10\\x11\\x12\\x13\\x14\\x15\\x16\\x17\\x18\\x19\\x1a\\x1b\\x1c\\x1d\\x1e\\x1f\\x20'"
        masked = self.filter._mask_raw_key(test_raw)
        
        # 验证格式
        assert masked.startswith('[RAW_KEY:')
        assert masked.endswith('...]')


class TestConvenienceFunctions:
    """测试便捷函数"""
    
    def test_sanitize_private_key_for_log(self):
        """测试私钥安全处理函数"""
        test_key = b'\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f\x20'
        
        result = sanitize_private_key_for_log(test_key)
        
        # 验证格式
        assert result.startswith('[KEY_HASH:')
        assert result.endswith(']')
        
        # 验证包含正确的哈希
        expected_hash = hashlib.sha256(test_key).hexdigest()[:16]
        assert expected_hash in result
    
    def test_sanitize_different_keys(self):
        """测试不同私钥产生不同哈希"""
        key1 = b'\x01' * 32
        key2 = b'\x02' * 32
        
        result1 = sanitize_private_key_for_log(key1)
        result2 = sanitize_private_key_for_log(key2)
        
        # 验证哈希不同
        assert result1 != result2


class TestLogSafeFunctions:
    """测试安全日志便捷函数"""
    
    def test_log_safe_error(self):
        """测试log_safe_error函数"""
        import logging
        from io import StringIO
        
        # 创建测试logger
        logger = logging.getLogger('test_safe_error')
        logger.setLevel(logging.ERROR)
        
        # 添加安全过滤器
        security_filter = SecurityLogFilter(
            name='test_error_filter',
            mask_private_keys=True,
            mask_wif=True
        )
        logger.addFilter(security_filter)
        
        # 添加stream handler
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        logger.addHandler(handler)
        
        # 记录包含私钥的错误
        test_key = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
        log_safe_error(logger, f"Error with key: {test_key}")
        
        # 验证日志被过滤
        log_output = stream.getvalue()
        assert test_key not in log_output
        assert '[PRIVATE_KEY' in log_output
        
        # 清理
        logger.removeFilter(security_filter)
        logger.removeHandler(handler)
    
    def test_log_safe_debug(self):
        """测试log_safe_debug函数"""
        import logging
        from io import StringIO
        
        logger = logging.getLogger('test_safe_debug')
        logger.setLevel(logging.DEBUG)
        
        # 添加安全过滤器
        security_filter = SecurityLogFilter(
            name='test_debug_filter',
            mask_private_keys=True,
            mask_wif=True
        )
        logger.addFilter(security_filter)
        
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        logger.addHandler(handler)
        
        test_key = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
        log_safe_debug(logger, f"Debug key: {test_key}")
        
        log_output = stream.getvalue()
        assert test_key not in log_output
        assert '[PRIVATE_KEY' in log_output
        
        logger.removeFilter(security_filter)
        logger.removeHandler(handler)


class TestEdgeCases:
    """测试边界情况"""
    
    def setup_method(self):
        """设置测试环境"""
        self.filter = SecurityLogFilter(
            name='test_security_filter',
            mask_private_keys=True,
            mask_wif=True
        )
    
    def test_empty_message(self):
        """测试空消息"""
        record = logging.LogRecord(
            name='test', level=logging.INFO, pathname='test.py', lineno=1,
            msg='', args=(), exc_info=None
        )
        
        # 不应抛出异常
        result = self.filter.filter(record)
        assert result is True
        assert record.msg == ''
    
    def test_non_string_message(self):
        """测试非字符串消息"""
        record = logging.LogRecord(
            name='test', level=logging.INFO, pathname='test.py', lineno=1,
            msg=12345, args=(), exc_info=None
        )
        
        # 不应抛出异常
        result = self.filter.filter(record)
        assert result is True
    
    def test_very_long_message(self):
        """测试超长消息"""
        # 包含私钥的超长消息
        test_key = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
        message = "A" * 10000 + test_key + "B" * 10000
        
        record = logging.LogRecord(
            name='test', level=logging.INFO, pathname='test.py', lineno=1,
            msg=message, args=(), exc_info=None
        )
        
        self.filter.filter(record)
        
        # 验证私钥被掩码
        assert test_key not in record.msg
    
    def test_case_insensitive_hex(self):
        """测试十六进制大小写不敏感"""
        # 大写
        test_key_upper = "A1B2C3D4E5F6A1B2C3D4E5F6A1B2C3D4E5F6A1B2C3D4E5F6A1B2C3D4E5F6A1B2"
        # 小写
        test_key_lower = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
        
        message = f"Keys: {test_key_upper} and {test_key_lower}"
        
        record = logging.LogRecord(
            name='test', level=logging.INFO, pathname='test.py', lineno=1,
            msg=message, args=(), exc_info=None
        )
        
        self.filter.filter(record)
        
        # 验证两个私钥都被掩码
        assert test_key_upper not in record.msg
        assert test_key_lower not in record.msg
        assert record.msg.count('[PRIVATE_KEY:') == 2
    
    def test_partial_key_not_masked(self):
        """测试部分私钥不应被掩码（少于64位）"""
        partial_key = "a1b2c3d4e5f6"  # 只有14位
        message = f"Partial: {partial_key}"
        
        record = logging.LogRecord(
            name='test', level=logging.INFO, pathname='test.py', lineno=1,
            msg=message, args=(), exc_info=None
        )
        
        self.filter.filter(record)
        
        # 验证部分私钥未被掩码
        assert partial_key in record.msg
    
    def test_no_args(self):
        """测试没有参数的日志记录"""
        message = "Simple message without args"
        
        record = logging.LogRecord(
            name='test', level=logging.INFO, pathname='test.py', lineno=1,
            msg=message, args=None, exc_info=None
        )
        
        # 不应抛出异常
        result = self.filter.filter(record)
        assert result is True


class TestIntegration:
    """集成测试 - 真实日志系统"""
    
    def test_filter_integration_with_logger(self):
        """测试过滤器与日志记录器集成"""
        # 创建测试日志记录器
        logger = logging.getLogger('test_integration')
        logger.setLevel(logging.DEBUG)
        
        # 添加过滤器
        security_filter = SecurityLogFilter(
            name='integration_test',
            mask_private_keys=True,
            mask_wif=True
        )
        logger.addFilter(security_filter)
        
        # 添加内存handler
        handler = logging.MemoryHandler(capacity=100)
        logger.addHandler(handler)
        
        # 记录包含私钥的消息
        test_key = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
        logger.info(f"Found private key: {test_key}")
        
        # 验证消息被过滤
        handler.flush()
        assert len(handler.buffer) > 0
        log_record = handler.buffer[0]
        assert test_key not in log_record.msg
        assert '[PRIVATE_KEY:' in log_record.msg
        
        # 清理
        logger.removeFilter(security_filter)
        logger.removeHandler(handler)
    
    def test_multiple_filters(self):
        """测试多个过滤器协同工作"""
        logger = logging.getLogger('test_multiple_filters')
        logger.setLevel(logging.DEBUG)
        
        # 添加安全过滤器
        security_filter = SecurityLogFilter(
            name='security',
            mask_private_keys=True,
            mask_wif=True
        )
        logger.addFilter(security_filter)
        
        # 添加自定义过滤器
        class CustomFilter(logging.Filter):
            def filter(self, record):
                record.msg = f"[CUSTOM] {record.msg}"
                return True
        
        custom_filter = CustomFilter()
        logger.addFilter(custom_filter)
        
        # 添加内存handler
        handler = logging.MemoryHandler(capacity=100)
        logger.addHandler(handler)
        
        # 记录消息
        test_key = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
        logger.info(f"Key: {test_key}")
        
        # 验证两个过滤器都生效
        handler.flush()
        log_record = handler.buffer[0]
        assert '[CUSTOM]' in log_record.msg
        assert test_key not in log_record.msg
        assert '[PRIVATE_KEY:' in log_record.msg
        
        # 清理
        logger.removeFilter(security_filter)
        logger.removeFilter(custom_filter)
        logger.removeHandler(handler)


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])

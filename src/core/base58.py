# -*- coding: utf-8 -*-
"""Base58编解码工具"""
from .hash_utils import HashUtils


class Base58:
    """
    Base58 编解码工具
    
    实现Base58和Base58Check编码，用于比特币地址和私钥的表示。
    Base58字符集: 123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz
    不包含: 0, O, I, l
    """
    
    ALPHABET = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
    BASE = len(ALPHABET)
    
    @staticmethod
    def encode(data: bytes) -> str:
        """
        将字节串编码为Base58字符串
        
        参数:
            data: 输入字节串
            
        返回:
            Base58编码的字符串
        """
        if not data:
            return ''
        
        # 计算前导零的数量
        leading_zeros = len(data) - len(data.lstrip(b'\x00'))
        
        # 将字节串转换为整数
        num = int.from_bytes(data, 'big')
        
        # 转换为Base58
        result = []
        while num > 0:
            num, rem = divmod(num, Base58.BASE)
            result.append(Base58.ALPHABET[rem])
        
        # 反转结果并添加前导零（用'1'表示）
        return '1' * leading_zeros + ''.join(reversed(result))
    
    @staticmethod
    def decode(s: str) -> bytes:
        """
        将Base58字符串解码为字节串
        
        参数:
            s: Base58编码的字符串
            
        返回:
            解码后的字节串
        
        异常:
            ValueError: 当字符串包含无效Base58字符时
        """
        if not s:
            return b''
        
        # 计算前导'1'的数量
        leading_ones = len(s) - len(s.lstrip('1'))
        
        # 将Base58转换为整数（同时验证字符）
        num = 0
        for c in s:
            if c not in Base58.ALPHABET:
                raise ValueError(f"无效的Base58字符: '{c}'")
            num = num * Base58.BASE + Base58.ALPHABET.index(c)
        
        # 将整数转换为字节串
        if num == 0:
            result = b''
        else:
            result = num.to_bytes((num.bit_length() + 7) // 8, 'big')
        
        # 添加前导零
        return b'\x00' * leading_ones + result
    
    @staticmethod
    def check_encode(version: int, payload: bytes) -> str:
        """
        Base58Check编码
        
        步骤:
        1. 前缀: 版本字节
        2. 载荷: 数据
        3. 校验和: 双SHA-256的前4字节
        4. 编码: 前缀 + 载荷 + 校验和 的Base58编码
        
        参数:
            version: 版本字节（整数）
            payload: 载荷数据
            
        返回:
            Base58Check编码的字符串
        """
        # 组合版本和载荷
        data = bytes([version]) + payload
        
        # 计算校验和（双SHA-256的前4字节）
        checksum = HashUtils.double_sha256(data)[:4]
        
        # 编码完整数据
        return Base58.encode(data + checksum)
    
    @staticmethod
    def check_decode(s: str) -> tuple:
        """
        Base58Check解码
        
        步骤:
        1. 解码: Base58字符串解码为字节串
        2. 分离: 版本字节 + 载荷 + 校验和
        3. 验证: 计算校验和并验证
        
        参数:
            s: Base58Check编码的字符串
            
        返回:
            (version, payload) 元组
        
        异常:
            ValueError: 当校验和验证失败时
        """
        # 空字符串检查
        if not s:
            raise ValueError("空的Base58Check字符串")
        
        # 解码Base58字符串
        data = Base58.decode(s)
        
        # 最小长度检查
        if len(data) < 5:
            raise ValueError("Base58Check数据过短（至少需要5字节: 1字节版本 + 0+载荷 + 4字节校验和）")
        
        # 分离版本、载荷和校验和
        version = data[0]
        payload = data[1:-4]
        checksum = data[-4:]
        
        # 验证校验和
        expected_checksum = HashUtils.double_sha256(bytes([version]) + payload)[:4]
        if checksum != expected_checksum:
            raise ValueError("Base58Check校验和验证失败")
        
        return version, payload

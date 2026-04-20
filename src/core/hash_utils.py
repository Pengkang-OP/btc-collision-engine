# -*- coding: utf-8 -*-
"""哈希工具类"""
import hashlib


class HashUtils:
    """
    哈希工具类
    
    提供比特币中使用的各种哈希函数，包括SHA-256、RIPEMD-160和Hash160。
    """
    
    @staticmethod
    def sha256(data: bytes) -> bytes:
        """
        计算SHA-256哈希
        
        参数:
            data: 输入字节串
            
        返回:
            32字节SHA-256哈希值
        """
        return hashlib.sha256(data).digest()
    
    @staticmethod
    def ripemd160(data: bytes) -> bytes:
        """
        计算RIPEMD-160哈希
        
        参数:
            data: 输入字节串
            
        返回:
            20字节RIPEMD-160哈希值
        """
        return hashlib.new('ripemd160', data).digest()
    
    @staticmethod
    def hash160(data: bytes) -> bytes:
        """
        计算Hash160 = RIPEMD160(SHA256(data))
        
        参数:
            data: 输入字节串
            
        返回:
            20字节Hash160值
        """
        return HashUtils.ripemd160(HashUtils.sha256(data))
    
    @staticmethod
    def double_sha256(data: bytes) -> bytes:
        """
        计算双SHA-256哈希
        
        参数:
            data: 输入字节串
            
        返回:
            32字节双SHA-256哈希值
        """
        return HashUtils.sha256(HashUtils.sha256(data))

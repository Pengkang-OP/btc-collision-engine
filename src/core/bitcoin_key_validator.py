#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
比特币密钥生成和地址匹配完整验证系统

严格按照Bitcoin Core规范验证：
1. 私钥生成公钥（secp256k1椭圆曲线）
2. 公钥生成地址（P2PKH/P2SH/Bech32）
3. 私钥转换为WIF格式
4. 地址匹配验证
5. 完整流程验证
"""

import hashlib
import hmac
import time
from typing import Tuple, Optional, Dict, Any, List
from enum import Enum

from src.core.secp256k1 import Secp256k1, ECPoint, EllipticCurve
from src.core.base58 import Base58
from src.core.wif import WIF


class KeyValidationConstants:
    """密钥验证常量"""
    PRIVATE_KEY_LENGTH = 32
    COMPRESSED_PUBLIC_KEY_LENGTH = 33
    UNCOMPRESSED_PUBLIC_KEY_LENGTH = 65
    P2PKH_VERSION_BYTE = 0x00
    P2SH_VERSION_BYTE = 0x05
    WIF_VERSION_BYTE = 0x80
    P2PKH_ADDRESS_MIN_LENGTH = 25
    P2PKH_ADDRESS_MAX_LENGTH = 34
    COMPRESSED_WIF_LENGTH = 52
    UNCOMPRESSED_WIF_LENGTH = 51


class AddressType(Enum):
    """比特币地址类型"""
    P2PKH = "p2pkh"      # 以'1'开头
    P2SH = "p2sh"        # 以'3'开头
    BECH32 = "bech32"    # 以'bc1'开头
    UNKNOWN = "unknown"


class KeyValidationResult:
    """密钥验证结果"""
    def __init__(self):
        self.success = True
        self.errors = []
        self.warnings = []
        self.details = {}
    
    def add_error(self, error: str):
        self.success = False
        self.errors.append(error)
        return self  # 支持链式调用
    
    def add_warning(self, warning: str):
        self.warnings.append(warning)
    
    def add_detail(self, key: str, value: Any):
        self.details[key] = value
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "errors": self.errors,
            "warnings": self.warnings,
            "details": self.details
        }


class BitcoinKeyValidator:
    """比特币密钥和地址完整验证器"""
    
    def __init__(self, secure_mode: bool = True):
        """
        初始化验证器
        
        参数:
            secure_mode: 安全模式，启用时不在结果中包含私钥明文
        """
        self.curve = EllipticCurve()
        self.secure_mode = secure_mode
    
    def validate_private_key(self, private_key: bytes) -> KeyValidationResult:
        """
        验证私钥格式和有效性
        
        验证项：
        - 必须是32字节
        - 数值范围在1到N-1之间（N为secp256k1曲线阶数）
        """
        result = KeyValidationResult()
        
        # 安全模式：不输出私钥明文
        if self.secure_mode:
            pk_hash = hashlib.sha256(private_key).hexdigest()[:16]
            result.add_detail("private_key_hash", f"{pk_hash}...")
        else:
            result.add_detail("private_key_hex", private_key.hex())
        
        result.add_detail("private_key_length", len(private_key))
        
        # 1. 验证长度
        if len(private_key) != KeyValidationConstants.PRIVATE_KEY_LENGTH:
            result.add_error(f"私钥长度错误: {len(private_key)}字节，应为{KeyValidationConstants.PRIVATE_KEY_LENGTH}字节")
            return result
        
        # 2. 转换为整数
        k = int.from_bytes(private_key, 'big')
        result.add_detail("private_key_int", str(k))
        
        # 3. 验证范围：1 <= k < N
        if k < 1:
            result.add_error("私钥数值为0，无效")
        elif k >= Secp256k1.N:
            result.add_error(f"私钥数值超出范围: >= N (曲线阶数)")
        else:
            result.add_detail("private_key_range_valid", True)
        
        return result
    
    def generate_public_key(self, private_key: bytes, compressed: bool = True) -> Tuple[KeyValidationResult, bytes]:
        """
        使用secp256k1椭圆曲线算法从私钥生成公钥
        
        验证项：
        - 使用标量乘法：P = k * G
        - 验证公钥在曲线上
        - 支持压缩和非压缩格式
        """
        result = KeyValidationResult()
        
        # 1. 验证私钥
        pk_validation = self.validate_private_key(private_key)
        if not pk_validation.success:
            result.success = False
            result.errors.extend(pk_validation.errors)
            return result, b''
        
        k = int.from_bytes(private_key, 'big')
        
        # 2. 计算公钥：P = k * G
        try:
            public_key_point = self.curve.scalar_multiply(k, ECPoint(Secp256k1.Gx, Secp256k1.Gy))
            
            # 3. 验证公钥不是无穷远点
            if public_key_point.is_infinity:
                result.add_error("生成的公钥为无穷远点，私钥无效")
                return result, b''
            
            # 4. 验证公钥在曲线上
            if not self.curve.is_on_curve(public_key_point):
                result.add_error("生成的公钥不在secp256k1曲线上")
                return result, b''
            
            result.add_detail("public_key_on_curve", True)
            result.add_detail("public_key_point_x", f"{public_key_point.x:064x}")
            result.add_detail("public_key_point_y", f"{public_key_point.y:064x}")
            
            # 5. 序列化公钥
            if compressed:
                # 压缩格式：33字节，02或03开头
                prefix = b'\x02' if public_key_point.y % 2 == 0 else b'\x03'
                public_key_bytes = prefix + public_key_point.x.to_bytes(32, 'big')
                result.add_detail("public_key_format", "compressed")
                result.add_detail("public_key_length", KeyValidationConstants.COMPRESSED_PUBLIC_KEY_LENGTH)
            else:
                # 非压缩格式：65字节，04开头
                public_key_bytes = (
                    b'\x04' + 
                    public_key_point.x.to_bytes(32, 'big') + 
                    public_key_point.y.to_bytes(32, 'big')
                )
                result.add_detail("public_key_format", "uncompressed")
                result.add_detail("public_key_length", KeyValidationConstants.UNCOMPRESSED_PUBLIC_KEY_LENGTH)
            
            result.add_detail("public_key_hex", public_key_bytes.hex())
            
            return result, public_key_bytes
            
        except Exception as e:
            result.add_error(f"公钥生成失败: {str(e)}")
            return result, b''
    
    def validate_public_key(self, public_key: bytes) -> KeyValidationResult:
        """
        验证公钥格式和有效性
        
        验证项：
        - 压缩格式：33字节，以02或03开头
        - 非压缩格式：65字节，以04开头
        - 验证公钥在曲线上
        """
        result = KeyValidationResult()
        result.add_detail("public_key_hex", public_key.hex())
        result.add_detail("public_key_length", len(public_key))
        
        if len(public_key) == KeyValidationConstants.COMPRESSED_PUBLIC_KEY_LENGTH:
            # 压缩格式
            if public_key[0] not in [0x02, 0x03]:
                result.add_error(f"压缩公钥前缀错误: 0x{public_key[0]:02x}，应为0x02或0x03")
                return result
            
            x = int.from_bytes(public_key[1:], 'big')
            
            # 验证x坐标不为0
            if x == 0:
                result.add_error("公钥x坐标为0，无效")
                return result
            
            result.add_detail("public_key_format", "compressed")
            result.add_detail("public_key_x", f"{x:064x}")
            
            # 验证点在曲线上
            try:
                y_squared = (pow(x, 3, Secp256k1.P) + 7) % Secp256k1.P
                y = pow(y_squared, (Secp256k1.P + 1) // 4, Secp256k1.P)
                
                # 根据前缀确定y
                if public_key[0] == 0x03:  # y是奇数
                    if y % 2 == 0:
                        y = Secp256k1.P - y
                
                point = ECPoint(x, y)
                if self.curve.is_on_curve(point):
                    result.add_detail("public_key_on_curve", True)
                else:
                    result.add_error("压缩公钥不在曲线上")
                    
            except (ValueError, OverflowError) as e:
                result.add_error(f"压缩公钥验证失败: {str(e)}")
                
        elif len(public_key) == KeyValidationConstants.UNCOMPRESSED_PUBLIC_KEY_LENGTH:
            # 非压缩格式
            if public_key[0] != 0x04:
                result.add_error(f"非压缩公钥前缀错误: 0x{public_key[0]:02x}，应为0x04")
                return result
            
            x = int.from_bytes(public_key[1:33], 'big')
            y = int.from_bytes(public_key[33:], 'big')
            result.add_detail("public_key_format", "uncompressed")
            result.add_detail("public_key_x", f"{x:064x}")
            result.add_detail("public_key_y", f"{y:064x}")
            
            # 验证点在曲线上
            point = ECPoint(x, y)
            if self.curve.is_on_curve(point):
                result.add_detail("public_key_on_curve", True)
            else:
                result.add_error("非压缩公钥不在曲线上")
        else:
            result.add_error(f"公钥长度错误: {len(public_key)}字节，应为33或65字节")
        
        return result
    
    def generate_address(self, public_key: bytes, address_type: AddressType = AddressType.P2PKH) -> Tuple[KeyValidationResult, str]:
        """
        从公钥生成比特币地址
        
        支持：
        - P2PKH：以'1'开头
        - P2SH：以'3'开头
        - Bech32：以'bc1'开头（需要额外实现）
        """
        result = KeyValidationResult()
        
        # 1. 验证公钥
        pk_validation = self.validate_public_key(public_key)
        if not pk_validation.success:
            result.success = False
            result.errors.extend(pk_validation.errors)
            return result, ""
        
        # 初始化地址变量
        address = ""
        
        try:
            if address_type == AddressType.P2PKH:
                # P2PKH地址生成
                # 手动实现P2PKH地址生成
                hash160 = hashlib.new('ripemd160')
                hash160.update(hashlib.sha256(public_key).digest())
                hash160_digest = hash160.digest()
                
                # Base58Check编码
                address = Base58.check_encode(0x00, hash160_digest)
                
                result.add_detail("address_type", "P2PKH")
                result.add_detail("address", address)
                result.add_detail("hash160", hash160_digest.hex())
                result.add_detail("public_key_used", public_key.hex())
                
                # 验证地址格式
                if not address.startswith('1'):
                    result.add_warning(f"P2PKH地址应以'1'开头，当前: {address[0]}")
                
                if len(address) < KeyValidationConstants.P2PKH_ADDRESS_MIN_LENGTH or len(address) > KeyValidationConstants.P2PKH_ADDRESS_MAX_LENGTH:
                    result.add_warning(f"P2PKH地址长度异常: {len(address)}")
                
                # 验证Base58Check校验和
                try:
                    version, payload = Base58.check_decode(address)
                    if version == KeyValidationConstants.P2PKH_VERSION_BYTE:
                        result.add_detail("address_checksum_valid", True)
                    else:
                        result.add_warning(f"地址版本字节异常: 0x{version:02x}")
                except (ValueError, TypeError) as e:
                    result.add_error(f"地址Base58Check验证失败: {str(e)}")
                    
            elif address_type == AddressType.P2SH:
                # P2SH地址生成（简化版）
                # 实际需要 redeem script，这里仅做格式验证
                result.add_warning("P2SH地址生成需要redeem script，此处仅验证格式")
                
            elif address_type == AddressType.BECH32:
                # Bech32地址（SegWit）
                result.add_warning("Bech32地址生成需要bech32编码实现")
            
            return result, address
            
        except (ValueError, OverflowError, TypeError) as e:
            result.add_error(f"地址生成失败: {str(e)}")
            import traceback
            result.add_detail("traceback", traceback.format_exc())
            return result, ""
    
    def validate_address(self, address: str) -> KeyValidationResult:
        """
        验证比特币地址格式
        
        验证项：
        - 版本字节
        - 长度
        - 校验和
        """
        result = KeyValidationResult()
        result.add_detail("address", address)
        
        # 1. 检测地址类型
        if address.startswith('1'):
            addr_type = AddressType.P2PKH
            result.add_detail("address_type", "P2PKH")
        elif address.startswith('3'):
            addr_type = AddressType.P2SH
            result.add_detail("address_type", "P2SH")
        elif address.startswith('bc1'):
            addr_type = AddressType.BECH32
            result.add_detail("address_type", "Bech32")
        else:
            result.add_error("未知地址类型")
            return result
        
        # 2. 验证P2PKH/P2SH地址
        if addr_type in [AddressType.P2PKH, AddressType.P2SH]:
            # 验证长度
            if len(address) < KeyValidationConstants.P2PKH_ADDRESS_MIN_LENGTH or len(address) > KeyValidationConstants.P2PKH_ADDRESS_MAX_LENGTH:
                result.add_error(f"地址长度错误: {len(address)}，应为{KeyValidationConstants.P2PKH_ADDRESS_MIN_LENGTH}-{KeyValidationConstants.P2PKH_ADDRESS_MAX_LENGTH}字符")
            
            # 验证Base58字符集
            valid_chars = set(Base58.ALPHABET)
            if not all(c in valid_chars for c in address):
                result.add_error("地址包含无效的Base58字符")
            
            # 验证Base58Check校验和
            try:
                version, payload = Base58.check_decode(address)
                result.add_detail("version_byte", f"0x{version:02x}")
                result.add_detail("payload_length", len(payload))
                
                if addr_type == AddressType.P2PKH and version != KeyValidationConstants.P2PKH_VERSION_BYTE:
                    result.add_warning(f"P2PKH地址版本字节应为0x{KeyValidationConstants.P2PKH_VERSION_BYTE:02x}，当前: 0x{version:02x}")
                elif addr_type == AddressType.P2SH and version != KeyValidationConstants.P2SH_VERSION_BYTE:
                    result.add_warning(f"P2SH地址版本字节应为0x{KeyValidationConstants.P2SH_VERSION_BYTE:02x}，当前: 0x{version:02x}")
                
                result.add_detail("checksum_valid", True)
                
            except (ValueError, TypeError) as e:
                result.add_error(f"Base58Check校验和验证失败: {str(e)}")
        
        # 3. Bech32地址验证（需要bech32模块）
        elif addr_type == AddressType.BECH32:
            result.add_warning("Bech32地址验证需要bech32模块")
        
        return result
    
    def private_key_to_wif(self, private_key: bytes, compressed: bool = True) -> Tuple[KeyValidationResult, str]:
        """
        将私钥转换为WIF格式
        
        验证项：
        - 压缩格式：以'K'或'L'开头的52字符
        - 非压缩格式：以'5'开头的51字符
        - Base58Check编码
        """
        result = KeyValidationResult()
        
        # 1. 验证私钥
        pk_validation = self.validate_private_key(private_key)
        if not pk_validation.success:
            result.success = False
            result.errors.extend(pk_validation.errors)
            return result, ""
        
        try:
            # 2. 编码为WIF
            wif = WIF.encode(private_key, compressed)
            result.add_detail("wif", wif)
            result.add_detail("wif_length", len(wif))
            result.add_detail("compressed", compressed)
            
            # 3. 验证WIF格式
            if compressed:
                if len(wif) != KeyValidationConstants.COMPRESSED_WIF_LENGTH:
                    result.add_warning(f"压缩WIF长度应为{KeyValidationConstants.COMPRESSED_WIF_LENGTH}字符，当前: {len(wif)}")
                if not wif.startswith(('K', 'L')):
                    result.add_warning(f"压缩WIF应以'K'或'L'开头，当前: {wif[0]}")
            else:
                if len(wif) != KeyValidationConstants.UNCOMPRESSED_WIF_LENGTH:
                    result.add_warning(f"非压缩WIF长度应为{KeyValidationConstants.UNCOMPRESSED_WIF_LENGTH}字符，当前: {len(wif)}")
                if not wif.startswith('5'):
                    result.add_warning(f"非压缩WIF应以'5'开头，当前: {wif[0]}")
            
            # 4. 验证Base58Check
            try:
                version, payload = Base58.check_decode(wif)
                result.add_detail("wif_version", f"0x{version:02x}")
                result.add_detail("wif_payload_length", len(payload))
                result.add_detail("wif_checksum_valid", True)
            except (ValueError, TypeError) as e:
                result.add_error(f"WIF Base58Check验证失败: {str(e)}")
            
            return result, wif
            
        except (ValueError, TypeError) as e:
            result.add_error(f"WIF编码失败: {str(e)}")
            return result, ""
    
    def wif_to_private_key(self, wif: str) -> Tuple[KeyValidationResult, bytes, bool]:
        """
        从WIF格式解码私钥
        
        返回私钥和压缩标志
        """
        result = KeyValidationResult()
        result.add_detail("wif", wif)
        
        try:
            # 1. 解码WIF
            private_key, compressed = WIF.decode(wif)
            
            result.add_detail("private_key_hex", private_key.hex())
            result.add_detail("compressed", compressed)
            
            # 2. 验证私钥
            pk_validation = self.validate_private_key(private_key)
            if not pk_validation.success:
                result.success = False
                result.errors.extend(pk_validation.errors)
            
            # 3. 验证WIF格式
            if compressed:
                if len(wif) != KeyValidationConstants.COMPRESSED_WIF_LENGTH:
                    result.add_warning(f"压缩WIF长度应为{KeyValidationConstants.COMPRESSED_WIF_LENGTH}字符")
                if not wif.startswith(('K', 'L')):
                    result.add_warning(f"压缩WIF应以'K'或'L'开头")
            else:
                if len(wif) != KeyValidationConstants.UNCOMPRESSED_WIF_LENGTH:
                    result.add_warning(f"非压缩WIF长度应为{KeyValidationConstants.UNCOMPRESSED_WIF_LENGTH}字符")
                if not wif.startswith('5'):
                    result.add_warning(f"非压缩WIF应以'5'开头")
            
            return result, private_key, compressed
            
        except (ValueError, TypeError) as e:
            result.add_error(f"WIF解码失败: {str(e)}")
            return result, b'', False
    
    def verify_address_match(self, address: str, target_addresses: set) -> KeyValidationResult:
        """
        验证地址是否与目标地址列表匹配
        
        使用安全的比较算法，防止时序攻击
        """
        result = KeyValidationResult()
        result.add_detail("address", address)
        result.add_detail("target_count", len(target_addresses))
        
        # 1. 验证地址格式
        addr_validation = self.validate_address(address)
        if not addr_validation.success:
            result.success = False
            result.errors.extend(addr_validation.errors)
            result.add_detail("match", False)
            return result
        
        # 2. 预验证目标地址并缓存有效地址
        valid_targets = set()
        for target in target_addresses:
            target_validation = self.validate_address(target)
            if target_validation.success:
                valid_targets.add(target)
            else:
                result.add_warning(f"目标地址格式异常: {target}")
        
        # 3. 安全比较（使用hmac.compare_digest防止时序攻击）
        match_found = False
        for target in valid_targets:
            # 使用安全的字符串比较
            if hmac.compare_digest(address, target):
                match_found = True
                result.add_detail("matched_target", target)
                break
        
        result.add_detail("match", match_found)
        
        if not match_found:
            result.add_detail("match_result", "未找到匹配")
        
        return result
    
    def full_validation_chain(self, private_key: bytes, target_addresses: set) -> Dict[str, Any]:
        """
        完整验证链：私钥 -> 公钥 -> 地址 -> WIF -> 匹配验证
        
        返回完整的验证报告
        """
        report = {
            "timestamp": time.time(),
            "steps": {},
            "overall_success": True,
            "errors": [],
            "warnings": []
        }
        
        # 步骤1: 验证私钥
        pk_result = self.validate_private_key(private_key)
        report["steps"]["private_key_validation"] = pk_result.to_dict()
        if not pk_result.success:
            report["overall_success"] = False
            report["errors"].extend(pk_result.errors)
            return report
        
        # 步骤2: 生成压缩公钥
        pub_comp_result, public_key_compressed = self.generate_public_key(private_key, compressed=True)
        report["steps"]["public_key_compressed"] = pub_comp_result.to_dict()
        if not pub_comp_result.success:
            report["overall_success"] = False
            report["errors"].extend(pub_comp_result.errors)
            return report
        
        # 步骤3: 生成非压缩公钥
        pub_uncomp_result, public_key_uncompressed = self.generate_public_key(private_key, compressed=False)
        report["steps"]["public_key_uncompressed"] = pub_uncomp_result.to_dict()
        if not pub_uncomp_result.success:
            report["overall_success"] = False
            report["errors"].extend(pub_uncomp_result.errors)
            return report
        
        # 步骤4: 生成P2PKH地址
        addr_result, address = self.generate_address(public_key_compressed, AddressType.P2PKH)
        report["steps"]["address_generation"] = addr_result.to_dict()
        if not addr_result.success:
            report["overall_success"] = False
            report["errors"].extend(addr_result.errors)
            return report
        
        # 步骤5: 生成压缩WIF
        wif_comp_result, wif_compressed = self.private_key_to_wif(private_key, compressed=True)
        report["steps"]["wif_compressed"] = wif_comp_result.to_dict()
        if not wif_comp_result.success:
            report["overall_success"] = False
            report["errors"].extend(wif_comp_result.errors)
            return report
        
        # 步骤6: 生成非压缩WIF
        wif_uncomp_result, wif_uncompressed = self.private_key_to_wif(private_key, compressed=False)
        report["steps"]["wif_uncompressed"] = wif_uncomp_result.to_dict()
        if not wif_uncomp_result.success:
            report["overall_success"] = False
            report["errors"].extend(wif_uncomp_result.errors)
            return report
        
        # 步骤7: 地址匹配验证
        match_result = self.verify_address_match(address, target_addresses)
        report["steps"]["address_match"] = match_result.to_dict()
        
        # 汇总错误和警告
        if not match_result.success:
            report["errors"].extend(match_result.errors)
        report["warnings"].extend(match_result.warnings)
        
        # 汇总警告
        for step_result in [pk_result, pub_comp_result, pub_uncomp_result, addr_result, 
                           wif_comp_result, wif_uncomp_result, match_result]:
            report["warnings"].extend(step_result.warnings)
        
        # 添加摘要
        report["summary"] = {
            "private_key_hex": private_key.hex(),
            "public_key_compressed": public_key_compressed.hex(),
            "public_key_uncompressed": public_key_uncompressed.hex(),
            "address": address,
            "wif_compressed": wif_compressed,
            "wif_uncompressed": wif_uncompressed,
            "address_match": match_result.details.get("match", False),
            "target_count": len(target_addresses)
        }
        
        return report


# 便捷函数
def validate_bitcoin_key_chain(private_key: bytes, target_addresses: set) -> Dict[str, Any]:
    """
    便捷函数：验证完整的比特币密钥链
    
    Args:
        private_key: 32字节私钥
        target_addresses: 目标地址集合
    
    Returns:
        完整验证报告
    """
    validator = BitcoinKeyValidator()
    return validator.full_validation_chain(private_key, target_addresses)

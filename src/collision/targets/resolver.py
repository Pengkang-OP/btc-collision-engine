"""增强版目标地址解析器

支持多种比特币地址和密钥格式的自动识别与转换:
- P2PKH地址(以'1'开头的标准比特币地址)
- P2SH地址(以'3'开头的脚本哈希地址)
- Bech32地址(以'bc1'开头的原生SegWit地址)
- WIF私钥(以'5'/'K'/'L'开头的Wallet Import Format)
- 压缩公钥(66字符hex, 02/03前缀)
- 非压缩公钥(130字符hex, 04前缀)
- Hash160(40字符hex)

所有格式在解析后统一转换为P2PKH地址用于碰撞检测。

优化特性:
- LRU缓存加速重复地址解析
- 批量解析减少函数调用开销
- 增强的格式检测支持更多地址类型
- 跨平台文件编码兼容
"""
import os
import logging
from typing import List, Set, Optional, Tuple, Dict, Union
from ...core.address_generator import P2PKHAddressGenerator
from ...core.base58 import Base58
from .cache import AddressCache

# 导入日志配置
from ...utils import init_logging, get_configured_logger
from ...utils.encoding_utils import EncodingUtils

# 初始化日志系统
init_logging()
# v2.2.1修复: Python的logging.Logger本身是线程安全的，无需ThreadSafeLogger包装
logger = get_configured_logger("TargetResolver", thread_safe=False)


class TargetResolver:
    """增强版目标地址解析器
    
    解析多种格式的目标,统一转换为 P2PKH 地址集合。
    内置缓存机制优化重复解析性能。
    
    示例:
        >>> resolver = TargetResolver(enable_cache=True)
        >>> address = resolver.resolve('1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa')
        >>> addresses = resolver.resolve_multiple(['1A1z...', '5KJvs...'])
    """
    
    def __init__(self, enable_cache: bool = True, cache_max_size: int = 10000):
        """
        初始化目标地址解析器
        
        参数:
            enable_cache: 是否启用缓存,默认True
            cache_max_size: 缓存最大容量,默认10000条目
        """
        self.generator = P2PKHAddressGenerator()
        
        # 解析缓存
        self.cache = AddressCache(
            lru_size=cache_max_size,
            enable_stats=True
        ) if enable_cache else None
        
        logger.info(f"TargetResolver 初始化: 缓存={'启用' if enable_cache else '禁用'}, "
                   f"缓存容量={cache_max_size if enable_cache else 'N/A'}")
    
    @staticmethod
    def detect_format(input_str: str) -> str:
        """
        自动检测输入格式
        
        参数:
            input_str: 输入字符串
            
        返回:
            格式类型: 'address', 'p2sh_address', 'bech32_address', 'wif', 
                     'pubkey_compressed', 'pubkey_uncompressed', 'hash160', 'unknown'
        """
        input_str = input_str.strip()
        
        if not input_str:
            return 'unknown'
        
        # P2PKH地址: 以'1'开头, 25-34字符, Base58字符集
        if input_str.startswith('1') and 25 <= len(input_str) <= 34:
            valid_chars = set(Base58.ALPHABET)
            if all(c in valid_chars for c in input_str):
                return 'address'
        
        # P2SH地址: 以'3'开头, 25-34字符
        if input_str.startswith('3') and 25 <= len(input_str) <= 34:
            valid_chars = set(Base58.ALPHABET)
            if all(c in valid_chars for c in input_str):
                return 'p2sh_address'
        
        # Bech32地址: 以'bc1'开头
        if input_str.lower().startswith('bc1'):
            # 区分SegWit v0和Taproot
            if input_str.lower().startswith('bc1p'):
                return 'taproot_address'  # Taproot (P2TR, BIP-0341)
            return 'bech32_address'  # SegWit v0 (P2WPKH/P2WSH)
        
        # WIF: 以'5'开头(非压缩,51字符) 或 'K'/'L'开头(压缩,52字符)
        if input_str.startswith('5') and len(input_str) == 51:
            valid_chars = set(Base58.ALPHABET)
            if all(c in valid_chars for c in input_str):
                return 'wif'
        
        if input_str.startswith(('K', 'L')) and len(input_str) == 52:
            valid_chars = set(Base58.ALPHABET)
            if all(c in valid_chars for c in input_str):
                return 'wif'
        
        # 压缩公钥: 66字符hex, 以02/03开头
        if len(input_str) == 66 and input_str.startswith(('02', '03')):
            try:
                bytes.fromhex(input_str)
                return 'pubkey_compressed'
            except ValueError:
                pass
        
        # 非压缩公钥: 130字符hex, 以04开头
        if len(input_str) == 130 and input_str.startswith('04'):
            try:
                bytes.fromhex(input_str)
                return 'pubkey_uncompressed'
            except ValueError:
                pass
        
        # Hash160: 40字符hex
        if len(input_str) == 40:
            try:
                bytes.fromhex(input_str)
                return 'hash160'
            except ValueError:
                pass
        
        return 'unknown'
    
    def resolve_multiple(self, inputs: List[str]) -> Dict[str, Optional[str]]:
        """resolve_batch的别名方法,保持向后兼容
        
        注意: 此方法只返回有效结果(过滤掉None)
        """
        all_results = self.resolve_batch(inputs)
        # 过滤掉None结果,只返回有效解析的地址
        return {k: v for k, v in all_results.items() if v is not None}
    
    def resolve(self, input_str: str) -> Optional[str]:
        """
        将任意格式输入解析为 P2PKH 地址,解析失败返回 None
        
        参数:
            input_str: 输入字符串(地址、WIF、公钥等)
            
        返回:
            P2PKH地址,解析失败返回None
        """
        input_str = input_str.strip()
        
        # 检查缓存(使用get方法以统计命中率)
        if self.cache:
            cached_result = self.cache.get(input_str)
            if cached_result:
                logger.debug(f"缓存命中: {input_str[:15]}...")
                return cached_result
        
        fmt = self.detect_format(input_str)
        logger.debug(f"格式检测: {fmt}, 输入={input_str[:20]}...")
        
        try:
            if fmt == 'address':
                # 验证Base58Check校验和
                version, payload = Base58.check_decode(input_str)
                if version == 0x00:
                    result = input_str
                    # 存入缓存
                    if self.cache:
                        self.cache.put(input_str, result)
                    logger.debug(f"P2PKH地址验证成功: {result[:15]}...")
                    return result
                logger.debug(f"P2PKH地址版本不匹配: version=0x{version:02x}")
                return None
            
            elif fmt == 'p2sh_address':
                # P2SH地址转换为等效的P2PKH表示（仅用于碰撞检测）
                # 注意：P2SH和P2PKH是不同的脚本类型，这里只提取Hash160进行匹配
                try:
                    version, payload = Base58.check_decode(input_str)
                    if version == 0x05:  # P2SH版本字节
                        # 将P2SH的Hash160转换为P2PKH地址格式（仅用于匹配）
                        # 这在碰撞检测中是合理的，因为我们只关心Hash160匹配
                        address = Base58.check_encode(0x00, payload)
                        if self.cache:
                            self.cache.put(input_str, address)
                        logger.debug(f"P2SH地址转换: {input_str} -> {address}")
                        return address
                    logger.warning(f"P2SH地址版本不匹配: version=0x{version:02x}, 地址={input_str}")
                    return None
                except ValueError as e:
                    # 校验和验证失败或格式错误
                    logger.warning(f"P2SH地址校验失败: {input_str} - {e}")
                    return None
                except Exception as e:
                    # 未知异常
                    logger.error(f"P2SH地址转换异常: {input_str} - {type(e).__name__}: {e}")
                    return None
            
            elif fmt == 'bech32_address':
                # Bech32地址转换（需要bech32库）
                try:
                    import bech32
                    
                    # Bech32要求全大写或全小写，不允许混合大小写
                    if input_str != input_str.lower() and input_str != input_str.upper():
                        logger.warning(f"Bech32地址大小写混合（无效格式）: {input_str}")
                        return None
                    
                    # 解析Bech32地址
                    hrp, data = bech32.bech32_decode(input_str)
                    if hrp is None or data is None:
                        logger.warning(f"Bech32地址解码失败: {input_str}")
                        return None
                    
                    # data[0]是版本号，data[1:]才是真正的witness program
                    if len(data) < 2:
                        logger.warning(f"Bech32地址数据过短: {input_str}")
                        return None
                    
                    version = data[0]
                    witness_data = data[1:]
                    
                    # 转换witness program（20字节=P2WPKH, 32字节=P2WSH）
                    witness_bytes = bech32.convertbits(witness_data, 5, 8, False)
                    if not witness_bytes:
                        logger.warning(f"Bech32 witness转换失败: {input_str}")
                        return None
                    
                    # 区分P2WPKH和P2WSH
                    addr_type = None
                    if len(witness_bytes) == 20:
                        addr_type = "P2WPKH"
                        logger.debug(f"检测到{addr_type}地址 ({len(witness_bytes)}字节witness): {input_str[:20]}...")
                    elif len(witness_bytes) == 32:
                        addr_type = "P2WSH"
                        logger.debug(f"检测到{addr_type}地址 ({len(witness_bytes)}字节witness): {input_str[:20]}...")
                    else:
                        logger.warning(
                            f"Bech32 witness长度无效: {len(witness_bytes)}字节 "
                            f"(期望20=P2WPKH或32=P2WSH), 地址={input_str}"
                        )
                        return None
                    
                    witness_hash = bytes(witness_bytes)
                    
                    # 将witness hash转换为P2PKH地址（用于碰撞匹配）
                    address = Base58.check_encode(0x00, witness_hash)
                    
                    if self.cache:
                        self.cache.put(input_str, address)
                    
                    logger.debug(f"Bech32地址转换: {input_str} -> {address}")
                    return address
                    
                except ImportError:
                    logger.warning(
                        f"Bech32地址需要bech32库支持: pip install bech32, 输入: {input_str}"
                    )
                    return None
                except Exception as e:
                    logger.error(f"Bech32地址转换异常: {input_str} - {type(e).__name__}: {e}")
                    return None
            
            elif fmt == 'taproot_address':
                # Taproot地址（bc1p开头，BIP-0341）
                # Taproot使用x-only公钥和Schnorr签名，转换逻辑复杂
                # 当前版本暂不支持，仅记录日志
                logger.warning(
                    f"Taproot地址暂不支持转换: {input_str}\n"
                    f"Taproot (P2TR) 使用x-only公钥和Schnorr签名 (BIP-0341/0342)\n"
                    f"需要额外实现Taproot地址解析逻辑"
                )
                return None
            
            elif fmt == 'wif':
                # WIF解码 -> 推导公钥 -> 推导地址
                from ...core.wif import WIF
                private_key, compressed = WIF.decode(input_str)
                public_key = self.generator.private_key_to_public_key(private_key, compressed=compressed)
                address = self.generator.public_key_to_address(public_key)
                
                # 存入缓存
                if self.cache:
                    self.cache.put(input_str, address)
                
                logger.debug(f"WIF解析成功: {input_str[:10]}... -> {address[:15]}... (compressed={compressed})")
                return address
            
            elif fmt == 'pubkey_compressed':
                # 压缩公钥 -> hash160 -> Base58Check(0x00, hash160) -> 地址
                public_key = bytes.fromhex(input_str)
                address = self.generator.public_key_to_address(public_key)
                
                # 存入缓存
                if self.cache:
                    self.cache.put(input_str, address)
                
                logger.debug(f"压缩公钥解析成功: {input_str[:10]}... -> {address[:15]}...")
                return address
            
            elif fmt == 'pubkey_uncompressed':
                # 非压缩公钥 -> hash160 -> Base58Check(0x00, hash160) -> 地址
                public_key = bytes.fromhex(input_str)
                address = self.generator.public_key_to_address(public_key)
                
                # 存入缓存
                if self.cache:
                    self.cache.put(input_str, address)
                
                logger.debug(f"非压缩公钥解析成功: {input_str[:10]}... -> {address[:15]}...")
                return address
            
            elif fmt == 'hash160':
                # Hash160 -> Base58Check(0x00, hash160) -> 地址
                from ...core.hash_utils import HashUtils
                hash160 = bytes.fromhex(input_str)
                address = HashUtils.hash160_to_address(hash160)
                
                # 存入缓存
                if self.cache:
                    self.cache.put(input_str, address)
                
                logger.debug(f"Hash160解析成功: {input_str[:10]}... -> {address[:15]}...")
                return address
            
            else:
                logger.warning(f"未知输入格式: {input_str[:20]}...")
                return None
                
        except Exception as e:
            logger.error(f"地址解析失败: 输入={input_str[:20]}..., 格式={fmt}, 错误={e}", exc_info=True)
            return None
    
    def resolve_batch(self, inputs: List[str]) -> Dict[str, Optional[str]]:
        """
        批量解析多个输入字符串
        
        参数:
            inputs: 输入字符串列表
            
        返回:
            字典 {输入: P2PKH地址}
        """
        logger.info(f"开始批量解析: 总数={len(inputs)}")
        
        results = {}
        to_resolve = []
        cache_hits = 0
        
        # 第一遍:检查缓存
        for inp in inputs:
            if self.cache and inp in self.cache:
                results[inp] = self.cache.get(inp)
                cache_hits += 1
            else:
                to_resolve.append(inp)
        
        logger.debug(f"批量解析缓存命中: {cache_hits}/{len(inputs)} ({(cache_hits/len(inputs)*100) if len(inputs) > 0 else 0:.1f}%)")
        
        # 第二遍:解析未缓存的
        if to_resolve:
            logger.debug(f"需要解析的地址数: {len(to_resolve)}")
            for inp in to_resolve:
                results[inp] = self.resolve(inp)
        
        success_count = sum(1 for v in results.values() if v is not None)
        logger.info(f"批量解析完成: 总数={len(inputs)}, 成功={success_count}, "
                   f"失败={len(inputs)-success_count}, 缓存命中={cache_hits}")
        
        return results
    
    def load_from_file(self, filepath: str) -> Set[str]:
        """
        从文件加载目标地址集合
        
        参数:
            filepath: 文件路径
            
        返回:
            有效P2PKH地址集合
        """
        addresses: Set[str] = set()
        
        # 安全检查: 防止路径遍历攻击
        real_path = os.path.realpath(filepath)
        allowed_dirs = [
            os.path.abspath(os.getcwd()),
            os.path.abspath(os.environ.get('TEMP', '/tmp')),
            os.path.abspath(os.environ.get('TMP', '/tmp')),
        ]
        if not any(real_path.startswith(allowed_dir) for allowed_dir in allowed_dirs):
            logger.error(f"安全警告:路径遍历攻击检测 - 路径超出允许范围: {real_path}")
            return addresses
        
        # 检查文件是否存在
        if not os.path.exists(real_path):
            logger.error(f"文件不存在: {real_path}")
            return addresses
        
        # 检查文件大小
        file_size = os.path.getsize(real_path)
        if file_size > 100 * 1024 * 1024:  # 100MB
            logger.error(f"文件过大(>100MB): {real_path}, 大小={file_size/1024/1024:.1f}MB")
            return addresses
        
        logger.info(f"开始从文件加载目标地址: {real_path}, 大小={file_size/1024:.1f}KB")
        
        # 安全读取文件
        try:
            line_count: int = 0
            max_lines: int = 1_000_000  # 最多100万行
            batch_inputs = []
            batch_size = 100
            valid_count = 0
            invalid_count = 0
            comment_count = 0
            empty_count = 0
            
            # 使用统一的编码检测工具读取文件
            try:
                lines = EncodingUtils.read_file_lines(real_path, try_multiple=True)
            except Exception as e:
                logger.error(f"文件读取失败: {real_path}, 错误={e}")
                return addresses
            
            for line in lines:
                line_count += 1
                
                if line_count > max_lines:
                    logger.warning(f"超过最大行数限制({max_lines}),停止读取")
                    break
                
                line = line.strip()
                
                # 跳过空行和注释
                if not line:
                    empty_count += 1
                    continue
                if line.startswith('#'):
                    comment_count += 1
                    continue
                
                batch_inputs.append(line)
                
                # 批量解析
                if len(batch_inputs) >= batch_size:
                    batch_results = self.resolve_batch(batch_inputs)
                    for inp, addr in batch_results.items():
                        if addr:
                            addresses.add(addr)
                            valid_count += 1
                        else:
                            invalid_count += 1
                    batch_inputs.clear()
                    
                    # 进度日志
                    if len(addresses) > 0 and len(addresses) % 10000 == 0:
                        logger.info(f"加载进度: 已处理{line_count}行, 有效地址={len(addresses)}")
            
            # 处理剩余的行
            if batch_inputs:
                batch_results = self.resolve_batch(batch_inputs)
                for inp, addr in batch_results.items():
                    if addr:
                        addresses.add(addr)
                        valid_count += 1
                    else:
                        invalid_count += 1
            
            logger.info(f"文件加载完成: 文件={real_path}, 总行数={line_count}, "
                       f"有效地址={len(addresses)}, 无效={invalid_count}, "
                       f"注释={comment_count}, 空行={empty_count}")
            
        except PermissionError:
            logger.error(f"文件权限错误,无法读取: {real_path}")
        except Exception as e:
            logger.error(f"文件读取异常: {real_path}, 错误={e}", exc_info=True)
        
        return addresses
    
    def get_cache_stats(self) -> Optional[Dict]:
        """
        获取缓存统计信息
        
        返回:
            缓存统计信息字典,未启用缓存返回空字典
        """
        if self.cache:
            stats = self.cache.get_stats()
            logger.debug(f"缓存统计: {stats}")
            return stats
        return {}
    
    def clear_cache(self) -> None:
        """清空缓存"""
        if self.cache:
            self.cache.clear()
            logger.info("缓存已清空")
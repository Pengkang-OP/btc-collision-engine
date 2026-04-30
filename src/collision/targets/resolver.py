"""增强版目标地址解析器

支持多种比特币地址和密钥格式的自动识别与转换:
- P2PKH地址(以'1'开头的标准比特币地址)
- P2SH地址(以'3'开头的脚本哈希地址)
- Bech32地址(以'bc1q'开头的原生SegWit地址, BIP-173)
- Bech32m地址(以'bc1p'开头的Taproot地址, BIP-350)
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
- 内置Bech32/Bech32m编解码，无需外部bech32库
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


# ---------------------------------------------------------------------------
# 内置 Bech32 / Bech32m 编解码  (BIP-173 / BIP-350)
# 不依赖外部 bech32 库，完整实现多项RFC验证
# ---------------------------------------------------------------------------

_BECH32_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
_BECH32_CHARSET_MAP = {c: i for i, c in enumerate(_BECH32_CHARSET)}

_BECH32_CONST = 1  # bech32  校验常量 (BIP-173)
_BECH32M_CONST = 0x2BC830A3  # bech32m 校验常量 (BIP-350)


def _bech32_polymod(values: list) -> int:
    """Bech32/Bech32m 多项式校验模运算"""
    generator = [0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3]
    chk = 1
    for value in values:
        top = chk >> 25
        chk = (chk & 0x1FFFFFF) << 5 ^ value
        for i in range(5):
            chk ^= generator[i] if ((top >> i) & 1) else 0
    return chk


def _bech32_hrp_expand(hrp: str) -> list:
    """扩展 HRP 为校验运算所需格式"""
    return [ord(c) >> 5 for c in hrp] + [0] + [ord(c) & 31 for c in hrp]


def _bech32_verify_checksum(hrp: str, data: list) -> Optional[int]:
    """验证 Bech32/Bech32m 校验和，返回编码常量 (1=bech32, 0x2bc830a3=bech32m) 或 None"""
    const = _bech32_polymod(_bech32_hrp_expand(hrp) + data)
    if const == _BECH32_CONST:
        return _BECH32_CONST
    if const == _BECH32M_CONST:
        return _BECH32M_CONST
    return None


def _convertbits(data, from_bits: int, to_bits: int, pad: bool = True) -> Optional[list]:
    """5-bit <-> 8-bit 位转换（BIP-173 convertbits）"""
    acc = 0
    bits = 0
    result = []
    maxv = (1 << to_bits) - 1
    max_acc = (1 << (from_bits + to_bits - 1)) - 1
    for value in data:
        if value < 0 or (value >> from_bits):
            return None
        acc = ((acc << from_bits) | value) & max_acc
        bits += from_bits
        while bits >= to_bits:
            bits -= to_bits
            result.append((acc >> bits) & maxv)
    if pad:
        if bits:
            result.append((acc << (to_bits - bits)) & maxv)
    elif bits >= from_bits or ((acc << (to_bits - bits)) & maxv):
        return None
    return result


def bech32_decode(bech: str) -> Tuple[Optional[str], Optional[list], Optional[int]]:
    """解码 Bech32/Bech32m 字符串

    Args:
        bech: 要解码的字符串

    Returns:
        (hrp, data_5bit, encoding_const) 三元组，失败时返回 (None, None, None)
        encoding_const: 1=bech32, 0x2bc830a3=bech32m
    """
    # BIP-173: 禁止大小写混合
    if bech.lower() != bech and bech.upper() != bech:
        return None, None, None
    bech = bech.lower()

    # 最大长度限制
    if len(bech) > 90:
        return None, None, None

    # 找分隔符 '1'
    pos = bech.rfind("1")
    if pos < 1 or pos + 7 > len(bech):
        return None, None, None

    hrp = bech[:pos]
    data_part = bech[pos + 1 :]

    # 验证字符集
    if not all(c in _BECH32_CHARSET_MAP for c in data_part):
        return None, None, None

    decoded = [_BECH32_CHARSET_MAP[c] for c in data_part]
    enc = _bech32_verify_checksum(hrp, decoded)
    if enc is None:
        return None, None, None

    return hrp, decoded[:-6], enc


def decode_segwit_address(hrp: str, addr: str) -> Tuple[Optional[int], Optional[bytes]]:
    """解码 SegWit 地址，提取 witness version 和 witness program

    支持:
    - P2WPKH: witness version=0, 20字节 witness program (bc1q)
    - P2WSH:  witness version=0, 32字节 witness program (bc1q)
    - P2TR:   witness version=1, 32字节 witness program (bc1p, Taproot)

    Args:
        hrp: 人类可读部分 ('bc'=主网, 'tb'=测试网)
        addr: 完整 bech32/bech32m 地址字符串

    Returns:
        (witness_version, witness_program_bytes), 失败返回 (None, None)
    """
    hrp_got, data, enc = bech32_decode(addr)
    if hrp_got is None or hrp_got != hrp.lower():
        return None, None
    if not data or len(data) < 1:
        return None, None

    witness_version = data[0]
    if witness_version > 16:
        return None, None

    # witness_version=0 必须使用 bech32，version>=1 必须使用 bech32m
    if witness_version == 0 and enc != _BECH32_CONST:
        return None, None
    if witness_version != 0 and enc != _BECH32M_CONST:
        return None, None

    witness_program = _convertbits(data[1:], 5, 8, False)
    if witness_program is None:
        return None, None

    prog_len = len(witness_program)
    # P2WPKH=20, P2WSH=32, P2TR=32
    if witness_version == 0 and prog_len not in (20, 32):
        return None, None
    if witness_version == 1 and prog_len != 32:
        return None, None
    if prog_len < 2 or prog_len > 40:
        return None, None

    return witness_version, bytes(witness_program)


class TargetResolver:
    """增强版目标地址解析器

    解析多种格式的目标,统一转换为 P2PKH 地址集合。
    内置缓存机制优化重复解析性能。

    示例:
        >>> resolver = TargetResolver(enable_cache=True)
        >>> address = resolver.resolve('1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa')
        >>> addresses = resolver.resolve_multiple(['1A1z...', '5KJvs...'])
    """

    MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024  # 最大文件大小: 100MB
    MAX_LINES = 1_000_000  # 最大行数: 100万行
    BATCH_SIZE = 100  # 批量解析大小

    def __init__(
        self,
        enable_cache: bool = True,
        cache_max_size: int = 10000,
        max_file_size_bytes: int = MAX_FILE_SIZE_BYTES,
        max_lines: int = MAX_LINES,
        batch_size: int = BATCH_SIZE,
    ) -> None:
        """
        初始化目标地址解析器

        参数:
            enable_cache: 是否启用缓存,默认True
            cache_max_size: 缓存最大容量,默认10000条目
            max_file_size_bytes: 最大文件大小(字节),默认100MB
            max_lines: 最大行数限制,默认100万行
            batch_size: 批量解析大小,默认100
        """
        self.generator = P2PKHAddressGenerator()

        # 解析缓存
        self.cache = (
            AddressCache(lru_size=cache_max_size, enable_stats=True) if enable_cache else None
        )

        # 文件加载配置
        self._max_file_size_bytes = max_file_size_bytes
        self._max_lines = max_lines
        self._batch_size = batch_size

        logger.info(
            f"TargetResolver 初始化: 缓存={'启用' if enable_cache else '禁用'}, "
            f"缓存容量={cache_max_size if enable_cache else 'N/A'}, "
            f"最大文件大小={max_file_size_bytes//(1024*1024)}MB, "
            f"最大行数={max_lines}"
        )

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
            return "unknown"

        # P2PKH地址: 以'1'开头, 25-34字符, Base58字符集
        if input_str.startswith("1") and 25 <= len(input_str) <= 34:
            valid_chars = set(Base58.ALPHABET)
            if all(c in valid_chars for c in input_str):
                return "address"

        # P2SH地址: 以'3'开头, 25-34字符
        if input_str.startswith("3") and 25 <= len(input_str) <= 34:
            valid_chars = set(Base58.ALPHABET)
            if all(c in valid_chars for c in input_str):
                return "p2sh_address"

        # Bech32地址: 以'bc1'开头
        if input_str.lower().startswith("bc1"):
            # 区分SegWit v0和Taproot
            if input_str.lower().startswith("bc1p"):
                return "taproot_address"  # Taproot (P2TR, BIP-0341)
            return "bech32_address"  # SegWit v0 (P2WPKH/P2WSH)

        # WIF: 以'5'开头(非压缩,51字符) 或 'K'/'L'开头(压缩,52字符)
        if input_str.startswith("5") and len(input_str) == 51:
            valid_chars = set(Base58.ALPHABET)
            if all(c in valid_chars for c in input_str):
                return "wif"

        if input_str.startswith(("K", "L")) and len(input_str) == 52:
            valid_chars = set(Base58.ALPHABET)
            if all(c in valid_chars for c in input_str):
                return "wif"

        # 压缩公钥: 66字符hex, 以02/03开头
        if len(input_str) == 66 and input_str.startswith(("02", "03")):
            try:
                bytes.fromhex(input_str)
                return "pubkey_compressed"
            except ValueError:
                pass

        # 非压缩公钥: 130字符hex, 以04开头
        if len(input_str) == 130 and input_str.startswith("04"):
            try:
                bytes.fromhex(input_str)
                return "pubkey_uncompressed"
            except ValueError:
                pass

        # Hash160: 40字符hex
        if len(input_str) == 40:
            try:
                bytes.fromhex(input_str)
                return "hash160"
            except ValueError:
                pass

        return "unknown"

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
            if fmt == "address":
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

            elif fmt == "p2sh_address":
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

            elif fmt == "bech32_address":
                # Bech32地址转换 (BIP-173, 内置编解码，无需外部库)
                try:
                    # 提取 HRP（bc=主网, tb=测试网）并解码 witness program
                    hrp = "bc" if input_str.lower().startswith("bc1") else "tb"
                    witness_version, witness_program = decode_segwit_address(hrp, input_str)

                    if witness_version is None or witness_program is None:
                        logger.warning(f"Bech32地址解码失败: {input_str}")
                        return None

                    # 仅支持 witness version 0 (P2WPKH/P2WSH)
                    if witness_version != 0:
                        logger.warning(
                            f"bech32_address格式仅支持witness version 0, 当前={witness_version}: {input_str}"
                        )
                        return None

                    prog_len = len(witness_program)
                    if prog_len == 20:
                        addr_type = "P2WPKH"
                    elif prog_len == 32:
                        addr_type = "P2WSH"
                    else:
                        logger.warning(
                            f"Bech32 witness长度无效: {prog_len}字节 "
                            f"(期望20=P2WPKH或32=P2WSH), 地址={input_str}"
                        )
                        return None

                    logger.debug(
                        f"检测到{addr_type}地址 ({prog_len}字节witness): {input_str[:30]}..."
                    )

                    # 将 witness hash 转换为 P2PKH 地址（用于碰撞匹配）
                    address = Base58.check_encode(0x00, witness_program)

                    if self.cache:
                        self.cache.put(input_str, address)

                    logger.debug(f"Bech32地址转换: {input_str} -> {address}")
                    return address

                except Exception as e:
                    logger.error(f"Bech32地址转换异常: {input_str} - {type(e).__name__}: {e}")
                    return None

            elif fmt == "taproot_address":
                # Taproot地址 (bc1p开头, BIP-350, Bech32m, witness version 1)
                try:
                    hrp = "bc" if input_str.lower().startswith("bc1") else "tb"
                    witness_version, witness_program = decode_segwit_address(hrp, input_str)

                    if witness_version is None or witness_program is None:
                        logger.warning(f"Taproot地址解码失败: {input_str}")
                        return None

                    if witness_version != 1:
                        logger.warning(
                            f"taproot_address格式期望witness version 1, 当前={witness_version}: {input_str}"
                        )
                        return None

                    if len(witness_program) != 32:
                        logger.warning(
                            f"Taproot witness program应为32字节, 实际={len(witness_program)}字节"
                        )
                        return None

                    # 将32字节 x-only 公钥作为 witness hash 转换为匹配地址
                    address = Base58.check_encode(0x00, witness_program)

                    if self.cache:
                        self.cache.put(input_str, address)

                    logger.debug(f"Taproot(P2TR)地址转换: {input_str} -> {address}")
                    return address

                except Exception as e:
                    logger.error(f"Taproot地址转换异常: {input_str} - {type(e).__name__}: {e}")
                    return None

            elif fmt == "wif":
                # WIF解码 -> 推导公钥 -> 推导地址
                from ...core.wif import WIF

                private_key, compressed = WIF.decode(input_str)
                public_key = self.generator.private_key_to_public_key(
                    private_key, compressed=compressed
                )
                address = self.generator.public_key_to_address(public_key)

                # 存入缓存
                if self.cache:
                    self.cache.put(input_str, address)

                logger.debug(
                    f"WIF解析成功: {input_str[:10]}... -> {address[:15]}... (compressed={compressed})"
                )
                return address

            elif fmt == "pubkey_compressed":
                # 压缩公钥 -> hash160 -> Base58Check(0x00, hash160) -> 地址
                public_key = bytes.fromhex(input_str)
                address = self.generator.public_key_to_address(public_key)

                # 存入缓存
                if self.cache:
                    self.cache.put(input_str, address)

                logger.debug(f"压缩公钥解析成功: {input_str[:10]}... -> {address[:15]}...")
                return address

            elif fmt == "pubkey_uncompressed":
                # 非压缩公钥 -> hash160 -> Base58Check(0x00, hash160) -> 地址
                public_key = bytes.fromhex(input_str)
                address = self.generator.public_key_to_address(public_key)

                # 存入缓存
                if self.cache:
                    self.cache.put(input_str, address)

                logger.debug(f"非压缩公钥解析成功: {input_str[:10]}... -> {address[:15]}...")
                return address

            elif fmt == "hash160":
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
            logger.error(
                f"地址解析失败: 输入={input_str[:20]}..., 格式={fmt}, 错误={e}", exc_info=True
            )
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

        # 第一遍:检查缓存（统一使用cache.get()方法，确保统计一致性）
        for inp in inputs:
            cached_result = self.cache.get(inp) if self.cache else None
            if cached_result is not None:
                results[inp] = cached_result
            else:
                to_resolve.append(inp)

        logger.debug(
            f"批量解析缓存命中: {len(results)}/{len(inputs)} ({(len(results)/len(inputs)*100) if len(inputs) > 0 else 0:.1f}%)"
        )

        # 第二遍:解析未缓存的
        if to_resolve:
            logger.debug(f"需要解析的地址数: {len(to_resolve)}")
            for inp in to_resolve:
                results[inp] = self.resolve(inp)  # type: ignore[assignment]

        success_count = sum(1 for v in results.values() if v is not None)
        cache_hits = len(results) - len(to_resolve)
        logger.info(
            f"批量解析完成: 总数={len(inputs)}, 成功={success_count}, "
            f"失败={len(inputs)-success_count}, 缓存命中={cache_hits}"
        )

        return results  # type: ignore[return-value]

    def load_from_file(self, filepath: str) -> Set[str]:
        """
        从文件加载目标地址集合

        参数:
            filepath: 文件路径

        返回:
            有效P2PKH地址集合
        """
        addresses: Set[str] = set()

        # 获取真实路径
        real_path = os.path.realpath(filepath)

        # 检查文件是否存在
        if not os.path.exists(real_path):
            logger.error(f"文件不存在: {real_path}")
            return addresses

        # 检查文件大小（使用配置参数）
        file_size = os.path.getsize(real_path)
        if file_size > self._max_file_size_bytes:
            max_size_mb = self._max_file_size_bytes // (1024 * 1024)
            logger.error(
                f"文件过大(>{max_size_mb}MB): {real_path}, 大小={file_size/1024/1024:.1f}MB"
            )
            return addresses

        logger.info(f"开始从文件加载目标地址: {real_path}, 大小={file_size/1024:.1f}KB")

        # 安全读取文件
        try:
            line_count: int = 0
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

            batch_inputs = []

            for line in lines:
                line_count += 1

                # 使用配置的最大行数限制
                if line_count > self._max_lines:
                    logger.warning(f"超过最大行数限制({self._max_lines}),停止读取")
                    break

                line = line.strip()

                # 跳过空行和注释
                if not line:
                    empty_count += 1
                    continue
                if line.startswith("#"):
                    comment_count += 1
                    continue

                batch_inputs.append(line)

                # 批量解析（使用配置的批量大小）
                if len(batch_inputs) >= self._batch_size:
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

            logger.info(
                f"文件加载完成: 文件={real_path}, 总行数={line_count}, "
                f"有效地址={len(addresses)}, 无效={invalid_count}, "
                f"注释={comment_count}, 空行={empty_count}"
            )

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

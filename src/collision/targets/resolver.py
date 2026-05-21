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

地址格式(P2PKH/P2SH/Bech32/Taproot)仅做小写标准化，保持原格式；
密钥格式(WIF/公钥/Hash160)推导为对应的P2PKH地址。

注意: 当前引擎仅生成P2PKH地址进行碰撞检测，
P2SH/Bech32(P2WSH)/Taproot等非P2PKH目标必然无法匹配。

优化特性:
- LRU缓存加速重复地址解析
- 批量解析减少函数调用开销
- 增强的格式检测支持更多地址类型
- 跨平台文件编码兼容
- 内置Bech32/Bech32m编解码，由统一模块 src.utils.bech32_codec 提供
"""

import os

from ...core.address_generator import P2PKHAddressGenerator
from ...core.base58 import Base58

# 导入日志配置
from ...utils import get_configured_logger
from ...utils.encoding_utils import EncodingUtils
from .cache import AddressCache

# v4.2.1修复: Python的logging.Logger本身是线程安全的，无需ThreadSafeLogger包装
logger = get_configured_logger("TargetResolver", thread_safe=False)


from ...utils.bech32_codec import decode_segwit_address


class TargetResolver:
    """增强版目标地址解析器

    解析多种格式的目标:
    - 地址格式(P2PKH/P2SH): 保持原始大小写（Base58 校验和大小写敏感，小写化会破坏校验和）
    - Bech32/Taproot: 小写标准化
    - 密钥格式(WIF/公钥/Hash160): 推导为对应P2PKH地址
    内置缓存机制优化重复解析性能。

    注意: 当前引擎仅生成P2PKH地址进行碰撞检测,
    P2SH/Bech32(P2WSH)/Taproot等非P2PKH目标必然无法匹配。

    示例:
        >>> resolver = TargetResolver(enable_cache=True)
        >>> address = resolver.resolve('1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa')
        >>> addresses = resolver.resolve_multiple(['1A1z...', '5KJvs...'])
    """

    MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024  # 最大文件大小: 100MB
    MAX_LINES = 1_000_000  # 最大行数: 100万行
    BATCH_SIZE = 100  # 批量解析大小
    # SUGGESTION-6: 类级别常量避免重复创建
    _BASE58_VALID_CHARS = frozenset(Base58.ALPHABET)

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
        self.cache = AddressCache(lru_size=cache_max_size, enable_stats=True) if enable_cache else None

        # 文件加载配置
        self._max_file_size_bytes = max_file_size_bytes
        self._max_lines = max_lines
        self._batch_size = batch_size

        # 不支持类型统计 (P2SH/P2WSH/Taproot等密码学上无法匹配的类型)
        self._unsupported_types: set[str] = set()

        logger.info(
            f"TargetResolver 初始化: 缓存={'启用' if enable_cache else '禁用'}, "
            f"缓存容量={cache_max_size if enable_cache else 'N/A'}, "
            f"最大文件大小={max_file_size_bytes // (1024 * 1024)}MB, "
            f"最大行数={max_lines}"
        )

    @staticmethod
    def detect_format(input_str: str) -> str:
        """
        自动检测输入格式

        参数:
            input_str: 输入字符串

        返回:
            格式类型: 'address', 'p2sh_address', 'bech32_address', 'taproot_address', 'wif',
                     'pubkey_compressed', 'pubkey_uncompressed', 'hash160', 'unknown'
        """
        input_str = input_str.strip()

        if not input_str:
            return "unknown"

        # SUGGESTION-6: 使用类级别常量优化性能
        valid_chars = TargetResolver._BASE58_VALID_CHARS

        # P2PKH地址: 以'1'开头, 25-34字符, Base58字符集
        if (
            input_str.startswith("1")
            and 25 <= len(input_str) <= 34
            and all(c in valid_chars for c in input_str)
        ):
            return "address"

        # P2SH地址: 以'3'开头, 25-34字符
        if (
            input_str.startswith("3")
            and 25 <= len(input_str) <= 34
            and all(c in valid_chars for c in input_str)
        ):
            return "p2sh_address"

        # Bech32地址: 以'bc1'开头 (主网) 或 'tb1'开头 (测试网)
        if input_str.lower().startswith("bc1") or input_str.lower().startswith("tb1"):
            # 区分SegWit v0和Taproot
            if input_str.lower().startswith("bc1p") or input_str.lower().startswith("tb1p"):
                return "taproot_address"  # Taproot (P2TR, BIP-0341)
            return "bech32_address"  # SegWit v0 (P2WPKH/P2WSH)

        # WIF: 以'5'开头(非压缩,51字符) 或 'K'/'L'开头(压缩,52字符)
        if (
            input_str.startswith("5")
            and len(input_str) == 51
            and all(c in valid_chars for c in input_str)
        ):
            return "wif"

        if (
            input_str.startswith(("K", "L"))
            and len(input_str) == 52
            and all(c in valid_chars for c in input_str)
        ):
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

    def resolve_multiple(self, inputs: list[str]) -> dict[str, str | None]:
        """resolve_batch的别名方法,保持向后兼容

        注意: 此方法只返回有效结果(过滤掉None)
        """
        all_results = self.resolve_batch(inputs)
        # 过滤掉None结果,只返回有效解析的地址
        return {k: v for k, v in all_results.items() if v is not None}

    # ========================================================================
    # 辅助函数 - 拆分自 resolve
    # ========================================================================

    def _resolve_p2pkh_address(self, input_str: str) -> str | None:
        """解析P2PKH地址 — 仅格式验证,保留原始大小写"""
        try:
            version, payload = Base58.check_decode(input_str)
            if version == 0x00:
                # Base58 编码大小写敏感,不可小写化,否则校验和失效
                if self.cache:
                    self.cache.put(input_str, input_str)
                logger.debug(f"P2PKH地址验证成功: {input_str[:15]}...")
                return input_str
            logger.debug(f"P2PKH地址版本不匹配: version=0x{version:02x}")
            return None
        except ValueError:
            return None

    def _resolve_p2sh_address(self, input_str: str) -> str | None:
        """解析P2SH地址

        P2SH 地址的 payload 是 hash160(redeemScript)，而非 hash160(pubkey)。
        碰撞引擎通过随机私钥 → 公钥 → hash160(pubkey) → P2PKH地址 进行匹配，
        P2SH 的脚本哈希与此路径在密码学上不相关，无法匹配。
        因此 P2SH 目标地址不可用于碰撞检测，返回 None 并记录警告。
        """
        try:
            version, _payload = Base58.check_decode(input_str)
            if version == 0x05:
                logger.warning(
                    f"P2SH地址 '{input_str[:20]}...' 无法用于碰撞匹配: "
                    f"P2SH的payload=hash160(redeemScript)与引擎生成的hash160(pubkey)不相关，"
                    f"密码学上不可能匹配。请使用P2PKH地址(1开头)或私钥/公钥。"
                )
                # 记录到不支持类型统计
                self._unsupported_types.add("p2sh_address")
                return None
            logger.warning(f"P2SH地址版本不匹配: version=0x{version:02x}")
            return None
        except ValueError:
            logger.warning(f"P2SH地址校验失败: {input_str}")
            return None

    def _resolve_bech32_address(self, input_str: str) -> str | None:
        """解析Bech32地址 (SegWit v0)

        P2WPKH (20字节 witness): witness_program = hash160(pubkey)，
        与引擎生成的 hash160(pubkey) 路径相同 → 可匹配 ✅

        P2WSH (32字节 witness): witness_program = sha256(redeemScript)，
        与引擎生成的 hash160(pubkey) 路径不同 → 不可匹配 ❌
        """
        try:
            hrp = "bc" if input_str.lower().startswith("bc1") else "tb"
            witness_version, witness_program = decode_segwit_address(hrp, input_str)
            if witness_version is None or witness_program is None:
                logger.warning(f"Bech32地址解码失败: {input_str}")
                return None
            if witness_version != 0:
                logger.warning(f"仅支持witness version 0, 当前={witness_version}")
                return None
            prog_len = len(witness_program)
            if prog_len == 20:
                # P2WPKH (v0, 20字节): witness program = pubkey_hash (Hash160)
                # 转换为 Legacy P2PKH 地址以便引擎进行碰撞匹配
                from ...core.hash_utils import HashUtils

                p2pkh_addr = HashUtils.hash160_to_address(witness_program)
                if self.cache:
                    self.cache.put(input_str, p2pkh_addr)
                logger.debug(f"P2WPKH地址转换: {input_str} -> {p2pkh_addr}")
                return p2pkh_addr
            elif prog_len == 32:
                # P2WSH: witness_program = sha256(redeemScript) → 不可匹配
                logger.warning(
                    f"P2WSH地址 '{input_str[:25]}...' 无法用于碰撞匹配: "
                    f"P2WSH的witness program=sha256(redeemScript)与引擎生成的hash160(pubkey)不相关，"
                    f"密码学上不可能匹配。请使用P2WPKH地址(20字节witness)或P2PKH地址(1开头)。"
                )
                self._unsupported_types.add("p2wsh_address")
                return None
            else:
                logger.warning(f"Bech32 witness长度无效: {prog_len}字节")
                return None
        except ValueError as e:
            logger.error(f"Bech32地址转换异常: {input_str} - {type(e).__name__}: {e}")
            return None

    def _resolve_taproot_address(self, input_str: str) -> str | None:
        """解析Taproot地址 (P2TR, BIP-0341)

        Taproot 的 witness program 是 32字节 x-only 公钥（Schnorr签名用），
        而非 hash160(pubkey)。碰撞引擎通过 hash160(pubkey) → P2PKH地址 匹配，
        与 Taproot 的 x-only 公钥路径在密码学上不相关，无法匹配。
        """
        try:
            hrp = "bc" if input_str.lower().startswith("bc1") else "tb"
            witness_version, witness_program = decode_segwit_address(hrp, input_str)
            if witness_version is None or witness_program is None:
                logger.warning(f"Taproot地址解码失败: {input_str}")
                return None
            if witness_version != 1:
                logger.warning(f"Taproot期望witness version 1, 当前={witness_version}")
                return None
            if len(witness_program) != 32:
                logger.warning("Taproot witness program应为32字节")
                return None
            logger.warning(
                f"Taproot地址 '{input_str[:25]}...' 无法用于碰撞匹配: "
                f"Taproot的witness program=x-only公钥(32字节)与引擎生成的hash160(pubkey)不相关，"
                f"密码学上不可能匹配。请使用P2PKH地址(1开头)或私钥/公钥。"
            )
            self._unsupported_types.add("taproot_address")
            return None
        except ValueError as e:
            logger.error(f"Taproot地址转换异常: {input_str} - {type(e).__name__}: {e}")
            return None

    def _resolve_wif(self, input_str: str) -> str | None:
        """解析WIF私钥"""
        try:
            from ...core.wif import WIF

            private_key, compressed = WIF.decode(input_str)
            public_key = self.generator.private_key_to_public_key(private_key, compressed=compressed)
            address = self.generator.public_key_to_address(public_key)
            if self.cache:
                self.cache.put(input_str, address)
            logger.debug(f"WIF解析成功: {input_str[:10]}... -> {address[:15]}...")
            return address
        except ValueError as e:
            logger.error(f"WIF解析异常: {input_str} - {type(e).__name__}: {e}")
            return None

    def _resolve_pubkey(self, input_str: str) -> str | None:
        """解析公钥"""
        try:
            public_key = bytes.fromhex(input_str)
            address = self.generator.public_key_to_address(public_key)
            if self.cache:
                self.cache.put(input_str, address)
            logger.debug(f"公钥解析成功: {input_str[:10]}... -> {address[:15]}...")
            return address
        except ValueError as e:
            logger.error(f"公钥解析异常: {input_str} - {type(e).__name__}: {e}")
            return None

    def _resolve_hash160(self, input_str: str) -> str | None:
        """解析Hash160"""
        try:
            from ...core.hash_utils import HashUtils

            hash160 = bytes.fromhex(input_str)
            address = HashUtils.hash160_to_address(hash160)
            if self.cache:
                self.cache.put(input_str, address)
            logger.debug(f"Hash160解析成功: {input_str[:10]}... -> {address[:15]}...")
            return address
        except ValueError as e:
            logger.error(f"Hash160解析异常: {input_str} - {type(e).__name__}: {e}")
            return None

    def resolve(self, input_str: str) -> str | None:
        """
        将任意格式输入解析为地址字符串,解析失败返回 None

        - 地址格式(P2PKH/P2SH): 保持原始大小写,Base58校验和大小写敏感
        - Bech32/Taproot: 小写标准化
        - 密钥格式(WIF/公钥/Hash160): 推导为对应的P2PKH地址

        注意: 当前引擎仅生成P2PKH地址进行碰撞检测,
        P2SH/Bech32(P2WSH)/Taproot等非P2PKH目标必然无法匹配。
        """
        input_str = input_str.strip()

        # 检查缓存
        if self.cache:
            cached_result = self.cache.get(input_str)
            if cached_result:
                logger.debug(f"缓存命中: {input_str[:15]}...")
                return cached_result

        fmt = self.detect_format(input_str)
        logger.debug(f"格式检测: {fmt}, 输入={input_str[:20]}...")

        # 根据格式选择解析方法
        resolvers = {
            "address": self._resolve_p2pkh_address,
            "p2sh_address": self._resolve_p2sh_address,
            "bech32_address": self._resolve_bech32_address,
            "taproot_address": self._resolve_taproot_address,
            "wif": self._resolve_wif,
            "pubkey_compressed": self._resolve_pubkey,
            "pubkey_uncompressed": self._resolve_pubkey,
            "hash160": self._resolve_hash160,
        }

        resolver = resolvers.get(fmt)
        if resolver:
            return resolver(input_str)

        logger.warning(f"未知输入格式: {input_str[:20]}...")
        return None

    def resolve_batch(self, inputs: list[str]) -> dict[str, str | None]:
        """
        批量解析多个输入字符串

        参数:
            inputs: 输入字符串列表

        返回:
            字典 {输入: P2PKH地址}
        """
        logger.info(f"开始批量解析: 总数={len(inputs)}")

        results: dict[str, str | None] = {}
        to_resolve: list[str] = []

        # 第一遍:检查缓存
        for inp in inputs:
            cached_result = self.cache.get(inp) if self.cache else None
            if cached_result is not None:
                results[inp] = cached_result
            else:
                to_resolve.append(inp)

        hit_rate = (len(results) / len(inputs) * 100) if len(inputs) > 0 else 0
        logger.debug(f"批量解析缓存命中: {len(results)}/{len(inputs)} ({hit_rate:.1f}%)")

        # 第二遍:直接解析未缓存的（跳过 resolve() 中的缓存检查，提升性能）
        if to_resolve:
            logger.debug(f"需要解析的地址数: {len(to_resolve)}")
            # 预构建解析器映射
            resolvers = {
                "address": self._resolve_p2pkh_address,
                "p2sh_address": self._resolve_p2sh_address,
                "bech32_address": self._resolve_bech32_address,
                "taproot_address": self._resolve_taproot_address,
                "wif": self._resolve_wif,
                "pubkey_compressed": self._resolve_pubkey,
                "pubkey_uncompressed": self._resolve_pubkey,
                "hash160": self._resolve_hash160,
            }
            for inp in to_resolve:
                inp = inp.strip()
                fmt = self.detect_format(inp)
                resolver = resolvers.get(fmt)
                if resolver:
                    results[inp] = resolver(inp)
                else:
                    results[inp] = None

        success_count = sum(1 for v in results.values() if v is not None)
        cache_hits = len(results) - len(to_resolve)
        logger.info(
            f"批量解析完成: 总数={len(inputs)}, 成功={success_count}, "
            f"失败={len(inputs) - success_count}, 缓存命中={cache_hits}"
        )

        return results

    def _process_batch(
        self,
        batch_inputs: list[str],
        addresses: set[str],
        valid_count: int,
        invalid_count: int,
    ) -> tuple[int, int]:
        """处理一批目标输入，返回 (valid_count, invalid_count)"""
        batch_results = self.resolve_batch(batch_inputs)
        for _inp, addr in batch_results.items():
            if addr:
                addresses.add(addr)
                valid_count += 1
            else:
                invalid_count += 1
        return valid_count, invalid_count

    def load_from_file(self, filepath: str) -> set[str]:
        """
        从文件加载目标地址集合

        参数:
            filepath: 文件路径

        返回:
            有效地址字符串集合(小写标准化)
        """
        addresses: set[str] = set()
        real_path = os.path.realpath(filepath)

        if not os.path.exists(real_path):
            logger.error(f"文件不存在: {real_path}")
            return addresses

        file_size = os.path.getsize(real_path)
        if file_size > self._max_file_size_bytes:
            max_size_mb = self._max_file_size_bytes // (1024 * 1024)
            logger.error(
                f"文件过大(>{max_size_mb}MB): {real_path}, 大小={file_size / 1024 / 1024:.1f}MB"
            )
            return addresses

        logger.info(f"开始从文件加载目标地址: {real_path}, 大小={file_size / 1024:.1f}KB")

        try:
            line_count: int = 0
            valid_count = 0
            invalid_count = 0
            comment_count = 0
            empty_count = 0

            try:
                lines = EncodingUtils.read_file_lines(real_path, try_multiple=True)
            except (OSError, UnicodeDecodeError) as e:
                logger.error(f"文件读取失败: {real_path}, 错误={e}")
                return addresses

            batch_inputs: list[str] = []

            for line in lines:
                line_count += 1
                if line_count > self._max_lines:
                    logger.warning(f"超过最大行数限制({self._max_lines}),停止读取")
                    break

                line = line.strip()
                if not line:
                    empty_count += 1
                    continue
                if line.startswith("#"):
                    comment_count += 1
                    continue

                batch_inputs.append(line)
                if len(batch_inputs) >= self._batch_size:
                    valid_count, invalid_count = self._process_batch(
                        batch_inputs, addresses, valid_count, invalid_count
                    )
                    batch_inputs.clear()
                    if len(addresses) > 0 and len(addresses) % 10000 == 0:
                        logger.info(f"加载进度: 已处理{line_count}行, 有效地址={len(addresses)}")

            if batch_inputs:
                valid_count, invalid_count = self._process_batch(
                    batch_inputs, addresses, valid_count, invalid_count
                )

            logger.info(
                f"文件加载完成: 文件={real_path}, 总行数={line_count}, "
                f"有效地址={len(addresses)}, 无效={invalid_count}, "
                f"注释={comment_count}, 空行={empty_count}"
            )

            # 报告密码学上不支持的类型
            unsupported = self.get_unsupported_types()
            if unsupported:
                unsupported_summary = ", ".join(
                    f"{k}={v}" for k, v in sorted(unsupported.items())
                )
                logger.warning(
                    f"密码学上不支持匹配的输入类型: {unsupported_summary}. "
                    f"这些地址/格式因密码学路径不同无法通过私钥碰撞匹配，已自动跳过。"
                    f"支持的类型: P2PKH地址(1开头)、WIF私钥、压缩/非压缩公钥、Hash160(hash160(pubkey))、P2WPKH Bech32(20字节witness)。"
                )

        except PermissionError:
            logger.error(f"文件权限错误,无法读取: {real_path}")
        except (OSError, ValueError, TypeError) as e:
            logger.error(f"文件读取异常: {real_path}, 错误={e}", exc_info=True)

        return addresses

    @staticmethod
    def analyze_target_formats(targets: set[str]) -> dict[str, int]:
        """分析目标地址集的格式分布

        按地址前缀识别格式并统计数量,用于启动时向用户展示
        目标格式兼容性信息。

        注意:
            此方法假设输入已通过 TargetResolver 解析验证,
            仅做前缀快速分类,不做深度格式校验(如 Base58 字符集、
            checksum 验证等)。
            unknown 类别包含 testnet 地址(2/tb1 前缀)等非主网
            标准格式,这些地址不会被引擎匹配。

        参数:
            targets: 已解析的目标地址集合(Base58 地址保留原始大小写,Bech32 小写)

        返回:
            格式→数量映射,如 {'p2pkh': 100, 'p2sh': 5, 'bech32': 3}
        """
        counts: dict[str, int] = {
            "p2pkh": 0,
            "p2sh": 0,
            "bech32": 0,
            "taproot": 0,
            "unknown": 0,
        }
        for addr in list(targets):
            if not addr:
                continue
            if addr.startswith("bc1p"):
                counts["taproot"] += 1
            elif addr.startswith("bc1"):
                counts["bech32"] += 1
            elif addr.startswith("3"):
                counts["p2sh"] += 1
            elif addr.startswith("1"):
                counts["p2pkh"] += 1
            else:
                counts["unknown"] += 1
        return counts

    def get_cache_stats(self) -> dict | None:
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

    def get_unsupported_types(self) -> dict[str, int]:
        """获取密码学上不支持匹配的输入类型统计

        返回:
            字典 {类型名: 计数}，例如 {'p2sh_address': 3, 'taproot_address': 1}

        可用于向用户报告哪些输入格式因密码学路径不同而无法用于碰撞匹配。
        """
        from collections import Counter

        return dict(Counter(self._unsupported_types))

    def clear_unsupported_stats(self) -> None:
        """清空不支持类型统计"""
        self._unsupported_types.clear()

    def clear_cache(self) -> None:
        """清空缓存"""
        if self.cache:
            self.cache.clear()
            logger.info("缓存已清空")

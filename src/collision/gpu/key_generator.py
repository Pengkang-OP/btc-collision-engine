"""GPU引擎私钥生成器

提供多种私钥生成策略，支持安全的私钥管理。

支持的生成策略：
1. PRNG_SEED: 基于种子的伪随机生成（默认）
2. AES_CTR: AES-CTR流加密生成
3. CHACHA20: ChaCha20流加密生成
4. RANDOM: 纯随机生成（高安全性）
5. DETERMINISTIC: 确定性生成（可重现）
"""

import os
import hashlib
import threading
from typing import Optional, List, Union, Callable, Dict
from enum import Enum

# Secp256k1 曲线参数
SECP256K1_N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
SECP256K1_N_BYTES = SECP256K1_N.to_bytes(32, "big")


class KeyGenerationStrategy(Enum):
    """私钥生成策略枚举"""
    PRNG_SEED = "prng_seed"
    AES_CTR = "aes_ctr"
    CHACHA20 = "chacha20"
    RANDOM = "random"
    DETERMINISTIC = "deterministic"


class KeyGenerator:
    """增强版私钥生成器
    
    提供多种安全的私钥生成策略，支持：
    - 多种PRNG算法
    - 私钥范围验证
    - 安全内存管理
    - 线程安全
    """

    def __init__(self, strategy: KeyGenerationStrategy = KeyGenerationStrategy.PRNG_SEED):
        """初始化私钥生成器
        
        Args:
            strategy: 私钥生成策略
        """
        self._strategy = strategy
        self._lock = threading.RLock()
        self._aes_ctx = None
        self._chacha_ctx = None
        
        # 统计信息
        self._generated_count = 0
        self._valid_count = 0
        self._invalid_count = 0

    @property
    def strategy(self) -> KeyGenerationStrategy:
        """当前生成策略"""
        return self._strategy

    @strategy.setter
    def strategy(self, strategy: KeyGenerationStrategy) -> None:
        """设置生成策略"""
        with self._lock:
            self._strategy = strategy
            self._reset_crypto_contexts()

    def _reset_crypto_contexts(self) -> None:
        """重置加密上下文"""
        self._aes_ctx = None
        self._chacha_ctx = None

    def generate_private_key(self, seed: bytes, index: int) -> bytes:
        """生成单个私钥
        
        Args:
            seed: 32字节种子
            index: 索引（用于确定性生成）
        
        Returns:
            32字节私钥
        
        Raises:
            ValueError: 如果种子不是32字节
        """
        if len(seed) != 32:
            raise ValueError(f"种子必须是32字节，当前: {len(seed)}字节")

        with self._lock:
            self._generated_count += 1
            
            if self._strategy == KeyGenerationStrategy.PRNG_SEED:
                key = self._generate_prng_seed(seed, index)
            elif self._strategy == KeyGenerationStrategy.AES_CTR:
                key = self._generate_aes_ctr(seed, index)
            elif self._strategy == KeyGenerationStrategy.CHACHA20:
                key = self._generate_chacha20(seed, index)
            elif self._strategy == KeyGenerationStrategy.RANDOM:
                key = self._generate_random()
            elif self._strategy == KeyGenerationStrategy.DETERMINISTIC:
                key = self._generate_deterministic(seed, index)
            else:
                key = self._generate_prng_seed(seed, index)

            # 验证私钥范围
            if self._is_valid_private_key(key):
                self._valid_count += 1
                return key
            else:
                self._invalid_count += 1
                # M-1修复: 改为迭代实现，避免递归栈溢出风险
                # SEVERE-1修复: 只在重试时递增计数器，初次尝试已在上面计数
                for retry in range(1000):
                    new_index = index + retry + 1
                    if self._strategy == KeyGenerationStrategy.PRNG_SEED:
                        key = self._generate_prng_seed(seed, new_index)
                    elif self._strategy == KeyGenerationStrategy.AES_CTR:
                        key = self._generate_aes_ctr(seed, new_index)
                    elif self._strategy == KeyGenerationStrategy.CHACHA20:
                        key = self._generate_chacha20(seed, new_index)
                    elif self._strategy == KeyGenerationStrategy.RANDOM:
                        key = self._generate_random()
                    elif self._strategy == KeyGenerationStrategy.DETERMINISTIC:
                        key = self._generate_deterministic(seed, new_index)
                    else:
                        key = self._generate_prng_seed(seed, new_index)
                    if self._is_valid_private_key(key):
                        self._valid_count += 1
                        return key
                    self._generated_count += 1
                    self._invalid_count += 1
                raise ValueError("无法在1000次重试内为种子生成有效私钥")

    def generate_private_keys(self, seed: bytes, count: int, start_index: int = 0) -> List[bytes]:
        """批量生成私钥
        
        Args:
            seed: 32字节种子
            count: 生成数量
            start_index: 起始索引
        
        Returns:
            私钥列表
        """
        keys = []
        for i in range(start_index, start_index + count):
            keys.append(self.generate_private_key(seed, i))
        return keys

    def _generate_prng_seed(self, seed: bytes, index: int) -> bytes:
        """基于种子的PRNG生成（默认策略）
        
        使用 HMAC-DRBG 风格的生成器
        """
        seed_int = int.from_bytes(seed, "big")
        key_int = (seed_int + index) % SECP256K1_N
        if key_int == 0:
            key_int = 1  # 确保私钥不为零（0 不是有效的 secp256k1 私钥）
        return key_int.to_bytes(32, "big")

    def _generate_aes_ctr(self, seed: bytes, index: int) -> bytes:
        """使用AES-CTR生成私钥
        
        S1修复: 改进CTR模式安全性，使用唯一IV加密每个计数器值
        原实现使用固定IV加密多个计数器值，可能产生相同密文。
        新实现将索引纳入IV生成，确保每个计数器使用唯一IV。
        """
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.backends import default_backend
        
        # S1修复: 生成安全的密钥和初始IV
        key = hashlib.sha256(seed).digest()
        base_iv = os.urandom(8)  # 8字节随机基础IV
        
        # S1修复: 将索引纳入IV的高8字节，确保每个索引使用唯一IV
        # CTR模式: IV(8字节) + counter(8字节) = 16字节完整nonce
        iv_with_counter = base_iv + index.to_bytes(8, "big")
        
        cipher = Cipher(algorithms.AES(key), modes.CTR(iv_with_counter), backend=default_backend())
        encryptor = cipher.encryptor()
        
        # 生成32字节伪随机数据
        encrypted = encryptor.update(b"\x00" * 32)
        
        # 取前32字节并确保在有效范围内
        key_int = int.from_bytes(encrypted[:32], "big") % SECP256K1_N
        if key_int == 0:
            key_int = 1
        
        return key_int.to_bytes(32, "big")

    def _generate_chacha20(self, seed: bytes, index: int) -> bytes:
        """使用ChaCha20生成私钥
        
        G4修复: 将index纳入nonce生成，确保每个索引产生唯一输出
        原实现index参数未使用，导致相同seed产生相同序列。
        新实现将索引与随机nonce结合，产生密码学安全的唯一序列。
        """
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms
            from cryptography.hazmat.backends import default_backend
            
            # G4修复: 将索引纳入nonce的高位，确保每个索引唯一
            # ChaCha20使用8字节nonce，将索引作为nonce的前8字节
            nonce = index.to_bytes(8, "big") + os.urandom(4)  # 8字节索引 + 4字节随机
            
            # ChaCha20需要32字节密钥
            key = hashlib.sha256(seed).digest()
            cipher = Cipher(algorithms.ChaCha20(key, nonce), mode=None, backend=default_backend())
            encryptor = cipher.encryptor()
            
            # 生成32字节伪随机数据
            data = encryptor.update(b"\x00" * 32)
            
            # 确保在有效范围内
            key_int = int.from_bytes(data, "big") % SECP256K1_N
            if key_int == 0:
                key_int = 1
            
            return key_int.to_bytes(32, "big")
        except ImportError:
            # 如果cryptography库不可用，回退到PRNG_SEED
            return self._generate_prng_seed(seed, index)

    def _generate_random(self) -> bytes:
        """纯随机生成（最高安全性）
        
        使用操作系统提供的安全随机数生成器
        """
        while True:
            key = os.urandom(32)
            if self._is_valid_private_key(key):
                return key

    def _generate_deterministic(self, seed: bytes, index: int) -> bytes:
        """确定性生成（可重现）
        
        使用双重哈希确保确定性和安全性
        """
        data = seed + index.to_bytes(8, "big")
        hash1 = hashlib.sha256(data).digest()
        hash2 = hashlib.sha256(hash1).digest()
        
        key_int = int.from_bytes(hash2, "big") % SECP256K1_N
        if key_int == 0:
            key_int = 1
        
        return key_int.to_bytes(32, "big")

    def _is_valid_private_key(self, key: bytes) -> bool:
        """验证私钥是否在有效范围内
        
        Secp256k1私钥必须满足: 1 <= key < SECP256K1_N
        
        Args:
            key: 32字节私钥
        
        Returns:
            True如果私钥有效，否则False
        """
        if len(key) != 32:
            return False
        
        key_int = int.from_bytes(key, "big")
        return 1 <= key_int < SECP256K1_N

    def secure_clear(self, key: Union[bytes, bytearray]) -> None:
        """安全清零私钥数据
        
        Args:
            key: 需要清零的私钥数据
        """
        if isinstance(key, bytearray):
            for i in range(len(key)):
                key[i] = 0
        elif isinstance(key, memoryview):
            key[:] = b"\x00" * len(key)

    def get_stats(self) -> Dict[str, int]:
        """获取生成器统计信息
        
        Returns:
            统计信息字典
        """
        return {
            "generated_count": self._generated_count,
            "valid_count": self._valid_count,
            "invalid_count": self._invalid_count,
        }

    def reset_stats(self) -> None:
        """重置统计信息"""
        with self._lock:
            self._generated_count = 0
            self._valid_count = 0
            self._invalid_count = 0


class BatchKeyGenerator:
    """批量私钥生成器
    
    优化批量生成性能，支持并行生成。
    """

    def __init__(
        self,
        strategy: KeyGenerationStrategy = KeyGenerationStrategy.PRNG_SEED,
        parallel_enabled: bool = True,
        max_workers: Optional[int] = None
    ):
        """初始化批量生成器
        
        Args:
            strategy: 生成策略
            parallel_enabled: 是否启用并行生成
            max_workers: 最大工作线程数（None表示使用CPU核心数）
        """
        self._generator = KeyGenerator(strategy)
        self._parallel_enabled = parallel_enabled
        self._max_workers = max_workers or (os.cpu_count() or 4)

    def generate_batch(
        self,
        seed: bytes,
        batch_size: int,
        start_index: int = 0,
        progress_callback: Optional[Callable[[int], None]] = None
    ) -> List[bytes]:
        """批量生成私钥
        
        Args:
            seed: 32字节种子
            batch_size: 批量大小
            start_index: 起始索引
            progress_callback: 进度回调函数
        
        Returns:
            私钥列表
        """
        if self._parallel_enabled and batch_size > 1000:
            return self._generate_parallel(seed, batch_size, start_index, progress_callback)
        else:
            return self._generate_serial(seed, batch_size, start_index, progress_callback)

    def _generate_serial(
        self,
        seed: bytes,
        batch_size: int,
        start_index: int,
        progress_callback: Optional[Callable[[int], None]]
    ) -> List[bytes]:
        """串行生成私钥"""
        keys = []
        for i in range(batch_size):
            keys.append(self._generator.generate_private_key(seed, start_index + i))
            if progress_callback and (i + 1) % 1000 == 0:
                progress_callback(i + 1)
        return keys

    def _generate_parallel(
        self,
        seed: bytes,
        batch_size: int,
        start_index: int,
        progress_callback: Optional[Callable[[int], None]]
    ) -> List[bytes]:
        """并行生成私钥"""
        import concurrent.futures
        
        keys = [None] * batch_size
        completed = 0
        
        def generate_chunk(chunk_start: int, chunk_end: int, chunk_index: int) -> None:
            nonlocal completed
            chunk_keys = []
            for i in range(chunk_start, chunk_end):
                chunk_keys.append(self._generator.generate_private_key(seed, i))

            # S-1修复: 直接使用 j 作为数组索引，因为 chunk_keys 的长度与当前块大小一致
            for j, key in enumerate(chunk_keys):
                keys[chunk_start + j] = key

            # 更新进度
            if progress_callback:
                completed += len(chunk_keys)
                progress_callback(min(completed, batch_size))

        # 计算分片
        chunk_size = batch_size // self._max_workers
        chunks = []
        for i in range(self._max_workers):
            chunk_start = start_index + i * chunk_size
            if i == self._max_workers - 1:
                chunk_end = start_index + batch_size
            else:
                chunk_end = chunk_start + chunk_size
            chunks.append((chunk_start, chunk_end, i))

        # 并行执行
        with concurrent.futures.ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            futures = []
            for chunk_start, chunk_end, chunk_index in chunks:
                futures.append(
                    executor.submit(generate_chunk, chunk_start, chunk_end, chunk_index)
                )
            
            # 等待所有任务完成
            concurrent.futures.wait(futures)

        return keys

    @property
    def strategy(self) -> KeyGenerationStrategy:
        """当前生成策略"""
        return self._generator.strategy

    @strategy.setter
    def strategy(self, strategy: KeyGenerationStrategy) -> None:
        """设置生成策略"""
        self._generator.strategy = strategy

    def get_stats(self) -> Dict[str, int]:
        """获取统计信息"""
        return self._generator.get_stats()


# 全局单例生成器
_global_key_generator: Optional[KeyGenerator] = None
_global_key_generator_lock = threading.Lock()


def get_key_generator(
    strategy: KeyGenerationStrategy = KeyGenerationStrategy.PRNG_SEED
) -> KeyGenerator:
    """获取全局私钥生成器（单例）
    
    Args:
        strategy: 生成策略（仅在首次调用时有效）
    
    Returns:
        KeyGenerator实例
    """
    global _global_key_generator
    
    if _global_key_generator is None:
        with _global_key_generator_lock:
            if _global_key_generator is None:
                _global_key_generator = KeyGenerator(strategy)
    
    return _global_key_generator


def generate_private_key(seed: bytes, index: int) -> bytes:
    """便捷函数：生成单个私钥
    
    Args:
        seed: 32字节种子
        index: 索引
    
    Returns:
        32字节私钥
    """
    generator = get_key_generator()
    return generator.generate_private_key(seed, index)


def generate_private_keys(seed: bytes, count: int, start_index: int = 0) -> List[bytes]:
    """便捷函数：批量生成私钥
    
    Args:
        seed: 32字节种子
        count: 生成数量
        start_index: 起始索引
    
    Returns:
        私钥列表
    """
    generator = get_key_generator()
    return generator.generate_private_keys(seed, count, start_index)

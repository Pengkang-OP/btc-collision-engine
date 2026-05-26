# BTC项目性能优化文档

> **版本**: v3.2.0 | **最后更新**: 2026-04-26  
> **面向**: 开发者

## 目录

- [1. 概述](#1-概述)

- [2. 性能基准](#2-性能基准)

  - [2.1 测试环境](#21-测试环境)

  - [2.2 性能指标](#22-性能指标)

    - [2.2.1 纯Python后端](#221-纯python后端)

    - [2.2.2 Coincurve后端（推荐）](#222-coincurve后端推荐)

  - [2.3 性能瓶颈分析](#23-性能瓶颈分析)

- [3. 后端选择优化](#3-后端选择优化)

  - [3.1 Coincurve后端安装](#31-coincurve后端安装)

- [3.2 性能对比](#32-性能对比)

  - [3.3 后端切换方法](#33-后端切换方法)

- [4. 当前优化策略](#4-当前优化策略)

  - [4.1 批量处理](#41-批量处理)

  - [4.2 线程池并行处理](#42-线程池并行处理)

  - [4.3 批量处理优化（新增）](#43-批量处理优化新增)

    - [4.3.1 _batch_size参数调优](#431-_batch_size参数调优)

    - [4.3.2 进度回调限流机制](#432-进度回调限流机制)

- [4.3.3 减少锁竞争策略](#433-减少锁竞争策略)

- [4.4 内存优化](#44-内存优化)

  - [3.3 去重过滤器](#33-去重过滤器)

  - [3.4 进度控制优化](#34-进度控制优化)

  - [3.5 内存预分配](#35-内存预分配)

- [4. 椭圆曲线运算优化](#4-椭圆曲线运算优化)

  - [4.1 当前实现分析](#41-当前实现分析)

  - [4.2 优化方向](#42-优化方向)

    - [4.2.1 使用NumPy向量化](#421-使用numpy向量化)

    - [4.2.2 使用C扩展](#422-使用c扩展)

- [4.2.3 预计算表](#423-预计算表)

  - [4.3 模运算优化](#43-模运算优化)

- [5. 哈希运算优化](#5-哈希运算优化)

  - [5.1 当前实现](#51-当前实现)

  - [5.2 批量哈希](#52-批量哈希)

- [6. Base58编码优化](#6-base58编码优化)

  - [6.1 当前实现分析](#61-当前实现分析)

  - [6.2 优化方案](#62-优化方案)

    - [6.2.1 使用数组预分配](#621-使用数组预分配)

    - [6.2.2 使用查表法](#622-使用查表法)

- [7. 内存优化](#7-内存优化)

  - [7.1 内存使用分析](#71-内存使用分析)

  - [7.2 使用__slots__](#72-使用__slots__)

  - [7.3 布隆过滤器](#73-布隆过滤器)

- [8. I/O优化](#8-io优化)

  - [8.1 CSV导出优化](#81-csv导出优化)

  - [8.2 断点保存优化](#82-断点保存优化)

- [9. GPU加速](#9-gpu加速)

  - [9.1 可行性分析](#91-可行性分析)

  - [9.2 预期性能](#92-预期性能)

  - [9.3 实现挑战](#93-实现挑战)

- [10. 性能监控](#10-性能监控)

  - [10.1 性能指标收集](#101-性能指标收集)

  - [10.2 实时监控](#102-实时监控)

- [11. 优化建议汇总](#11-优化建议汇总)

  - [11.1 短期优化（已实现）](#111-短期优化已实现)

  - [11.2 中期优化](#112-中期优化)

  - [11.3 长期优化](#113-长期优化)

- [12. 性能测试脚本](#12-性能测试脚本)

- [13. 目标地址管理优化](#13-目标地址管理优化)

  - [13.1 地址解析缓存](#131-地址解析缓存)

- [13.2 批量处理优化](#132-批量处理优化)

- [13.3 大规模地址集匹配](#133-大规模地址集匹配)

- [13.4 文件加载优化](#134-文件加载优化)

- [14. 总结](#14-总结)

## 1. 概述

本文档分析BTC项目的性能特点、瓶颈和可能的优化方案。项目支持多后端（纯Python和coincurve），通过多种策略优化性能。

**核心优化策略**:

- 多后端支持（coincurve加速3-5x）

- 批量处理和本地缓存

- 线程池并行处理

- 双缓冲去重过滤器

- 进度回调限流

- 数据日志系统优化

## 2. 性能基准

### 2.1 测试环境

**硬件配置**:

- CPU: Intel Core i7-10700K @ 3.8GHz (8核16线程)

- 内存: 32GB DDR4

- 存储: NVMe SSD

**软件配置**:

- Python 3.11

- Windows 11 / Ubuntu 22.04

### 2.2 性能指标

#### 2.2.1 纯Python后端

| 操作 | 单线程性能 | 多线程性能(8核) |
|------|-----------|----------------|
| 私钥生成 | ~50,000/秒 | ~400,000/秒 |
| 公钥生成 | ~2,000/秒 | ~16,000/秒 |
| 地址生成 | ~1,800/秒 | ~14,000/秒 |
| 碰撞检测 | ~1,500/秒 | ~12,000/秒 |

#### 2.2.2 Coincurve后端（推荐）

| 操作 | 单线程性能 | 多线程性能(8核) |
|------|-----------|----------------|
| 私钥生成 | ~50,000/秒 | ~400,000/秒 |
| 公钥生成 | ~5,000/秒 | ~40,000/秒 |
| 地址生成 | ~4,500/秒 | ~36,000/秒 |
| 碰撞检测 | ~4,000/秒 | ~32,000/秒 |

**性能提升**: coincurve后端在公钥生成和地址生成方面提供**3-5x**性能提升。

### 2.3 性能瓶颈分析

```python
地址生成流程性能分析:
┌─────────────────────────────────────────────────────────────┐
│ 步骤              时间占比    优化潜力                      │
├─────────────────────────────────────────────────────────────┤
│ 私钥生成          1%          低 (已使用secrets)            │
│ 椭圆曲线乘法      75%         高 (纯Python实现)             │
│ SHA-256          5%          低 (hashlib C实现)             │
│ RIPEMD-160       5%          低 (OpenSSL实现)               │
│ Base58编码       10%         中 (Python大整数运算)          │
│ 校验和计算       4%          低 (hashlib C实现)             │
└─────────────────────────────────────────────────────────────┘

```

**主要瓶颈**: 椭圆曲线标量乘法（纯Python实现）

## 3. 后端选择优化

### 3.1 Coincurve后端安装

**步骤**:

```bash
# 安装coincurve（libsecp256k1的Python绑定）
pip install coincurve>=18.0.0

# 验证安装
python -c "import coincurve; print(coincurve.__version__)"

```python

**依赖**:

- libsecp256k1（会自动下载预编译版本）

- 编译器（如果需要从源码编译）

## 3.2 性能对比

| 指标 | PurePython | Coincurve | 提升倍数 |
|------|-----------|-----------|---------|
| 公钥生成 | ~2,000/秒 | ~5,000/秒 | 2.5x |
| 地址生成 | ~1,800/秒 | ~4,500/秒 | 2.5x |
| 碰撞检测 | ~1,500/秒 | ~4,000/秒 | 2.7x |
| 内存占用 | 低 | 中 | - |

### 3.3 后端切换方法

**自动切换**:

```python
from src.core.crypto_backend import crypto_manager

# crypto_manager会自动选择最佳后端
public_key = crypto_manager.generate_public_key(private_key, compressed=True)

```python

**手动指定**:

```python
from src.core.crypto_backend import CoincurveBackend, PurePythonBackend

# 使用coincurve后端
backend = CoincurveBackend()
public_key = backend.generate_public_key(private_key, compressed=True)

# 使用纯Python后端
backend = PurePythonBackend()
public_key = backend.generate_public_key(private_key, compressed=True)

```markdown

## 4. 当前优化策略

### 4.1 批量处理

**原理**: 减少函数调用开销和锁竞争

**代码实现**:

```python
def _random_search_worker(self, worker_id: int = 0) -> int:
    """随机碰撞模式的工作线程函数（优化版）"""
    local_count = 0
    local_matches = []
    
    while not self._stop_event.is_set():
        # 批量生成和检查
        for _ in range(self._batch_size):  # batch_size = 1000
            if self._stop_event.is_set():
                break
            
            # 生成随机私钥
            private_key = secrets.token_bytes(32)
            k = int.from_bytes(private_key, 'big')
            if k < 1 or k >= Secp256k1.N:
                continue
            
            # 去重检查
            if not self.dedup_filter.check_and_add(private_key):
                continue
            
            # 生成地址
            address, compressed_pub, _ = self.generator.generate_address(private_key)
            local_count += 1
            
            # 检查匹配
            if address in self.targets:
                from ..core.wif import WIF
                wif = WIF.encode(private_key, compressed=True)
                local_matches.append((private_key, address, wif))
                
                # 批量提交匹配结果
                if len(local_matches) >= 10:
                    for pk, addr, wif_str in local_matches:
                        self.stats.add_match(pk, addr)
                    if self.on_match:
                        for pk, addr, wif_str in local_matches:
                            self.on_match(pk, addr, wif_str)
                    local_matches.clear()
            
            # 定期让出时间片
            if local_count % 100 == 0:
                time.sleep(0)
        
        # 每批处理完后检查是否需要让出
        time.sleep(0)
    
    # 提交剩余的匹配结果
    if local_matches:
        for pk, addr, wif_str in local_matches:
            self.stats.add_match(pk, addr)
        if self.on_match:
            for pk, addr, wif_str in local_matches:
                self.on_match(pk, addr, wif_str)
    
    return local_count

```python

**优化效果**:

- 批量处理减少锁竞争

- 本地缓存减少共享状态更新

- 批量提交匹配结果减少回调开销

### 4.2 线程池并行处理

**原理**: 利用多核CPU并行生成私钥

**代码实现**:

```python
def random_search(self):
    """随机碰撞模式 - 使用线程池并行生成私钥并比对"""
    # 确定工作线程数
    num_workers = self.max_workers or (os.cpu_count() or 4)
    
    # 创建线程池
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
        self._executor = executor
        
        # 提交初始任务
        futures = {executor.submit(self._random_search_worker, i): i 
                  for i in range(num_workers)}
        
        while not self._stop_event.is_set() and futures:
            # 等待至少一个任务完成
            done, _ = concurrent.futures.wait(
                futures, 
                timeout=0.1,
                return_when=concurrent.futures.FIRST_COMPLETED
            )

```python

**线程数选择**:
| CPU核心数 | 推荐线程数 | 说明 |
|-----------|-----------|------|
| 4核 | 4-8 | 考虑超线程 |
| 8核 | 8-16 | 最佳性能区间 |

**注意事项**:

- Python GIL限制：CPU密集型操作无法完全并行

- 线程数过多会导致上下文切换开销

- 推荐：线程数 = CPU核心数

### 4.3 批量处理优化（新增）

#### 4.3.1 _batch_size参数调优

**默认值**: `_batch_size = 1000`

**调优建议**:
| 场景 | 推荐值 | 说明 |
|------|--------|------|
| 低内存 | 500 | 减少内存占用 |
| 标准 | 1000 | 平衡性能和内存 |
| 高性能 | 2000 | 减少锁竞争，增加内存 |

**影响**:

- 较大的batch_size：减少锁竞争，但增加内存占用

- 较小的batch_size：更频繁的进度更新，但增加锁竞争

#### 4.3.2 进度回调限流机制

**实现**:

```python
# 进度回调最小间隔（秒）
self._progress_interval_sec = 0.5
self._last_progress_time = 0.0

# 限流逻辑
current_time = time.time()
if current_time - self._last_progress_time >= self._progress_interval_sec:
    if self.on_progress:
        self.on_progress(self.stats)
    self._last_progress_time = current_time

```python

**效果**:

- 避免过于频繁的回调（每次检查都触发）

- 减少UI刷新开销

- 降低日志记录频率

## 4.3.3 减少锁竞争策略

1. **本地缓存**: 工作线程使用`local_matches`和`local_count`

2. **批量提交**: 每批处理完后一次性更新共享状态

3. **分离锁**: 计数器、匹配列表、去重过滤器使用独立锁

4. **实时计数器**: `_live_range_count`无锁进度更新

**代码示例**:

```python
# 工作线程本地缓存
local_matches = []
local_count = 0

for private_key in batch:
    # 处理逻辑...
    local_count += 1
    if match:
        local_matches.append(match)

# 批量提交（减少锁竞争）
with self._count_lock:
    self.stats.total_checked += local_count
    self.stats.matches.extend(local_matches)

```markdown

## 4.4 内存优化

| 16核+ | 16-32 | 避免过多上下文切换 |

### 3.3 去重过滤器

**原理**: 使用布隆过滤器或哈希集合避免重复计算

**代码实现**:

```python
class DeduplicationFilter:
    """去重过滤器 - 使用哈希集合避免重复检查"""
    
    def __init__(self, max_size: int = 1_000_000, enabled: bool = True):
        self.max_size = max_size
        self.enabled = enabled
        self._filter = set()
        self._lock = threading.Lock()
    
    def check_and_add(self, private_key: bytes) -> bool:
        """检查并添加私钥，返回True表示新私钥"""
        if not self.enabled:
            return True
        
        with self._lock:
            if len(self._filter) >= self.max_size:
                # 达到上限，清空过滤器
                self._filter.clear()
            
            if private_key in self._filter:
                return False
            
            self._filter.add(private_key)
            return True

```python

**性能影响**:

- 启用去重: 减少约5-10%重复计算

- 内存占用: 约100MB/百万条目

### 3.4 进度控制优化

**原理**: 减少UI更新频率，避免界面卡顿

**代码实现**:

```python
def _batch_generate_worker(self, count: int):
    """批量生成工作线程"""
    for i in range(count):
        private_key = self.generator.generate_private_key()
        address, compressed_pk, _ = self.generator.generate_address(private_key)
        wif = WIF.encode(private_key, compressed=True)
        
        result = {
            'index': i + 1,
            'private_key_hex': private_key.hex(),
            'private_key_wif': wif,
            'public_key': compressed_pk.hex(),
            'address': address
        }
        self.batch_results.append(result)
        
        # 使用 after 确保线程安全，控制更新频率
        if (i + 1) % 10 == 0 or i == count - 1:
            self.root.after(0, self._update_batch_ui, i + 1, count, result)

```markdown

### 3.5 内存预分配

**原理**: 预分配内存减少动态分配开销

**代码实现**:

```python
# 预分配结果列表
self.batch_results = []
self.batch_results.reserve(count)  # 如果可能

# 使用数组而非列表（大量数据时）
import array
results = array.array('Q', [0]) * count

```markdown

## 4. 椭圆曲线运算优化

### 4.1 当前实现分析

**标准双倍-加法算法**:

```python
def scalar_multiply(self, k: int, point: ECPoint) -> ECPoint:
    result = ECPoint(None, None, self.curve)
    addend = point.copy()
    
    while k > 0:
        if k & 1:
            result = self.point_add(result, addend)
        addend = self.point_add(addend, addend)
        k >>= 1
    
    return result

```python

**性能瓶颈**:

- Python大整数运算开销

- 频繁的函数调用

- 对象创建开销

### 4.2 优化方向

#### 4.2.1 使用NumPy向量化

**适用场景**: 批量公钥生成

```python
import numpy as np

def batch_scalar_multiply_numpy(private_keys: np.ndarray, points: np.ndarray) -> np.ndarray:
    """使用NumPy批量计算标量乘法"""
    # 将椭圆曲线运算转换为矩阵运算
    # 注意：需要特殊处理模运算
    pass

```python

**限制**: 

- 模运算难以向量化

- 仅适用于特定场景

#### 4.2.2 使用C扩展

**方案**: 将热点代码用C/Cython实现

```cython
# ecc.pyx
cdef class EllipticCurve:
    cdef unsigned long long p
    
    cpdef scalar_multiply(self, unsigned long long k, ECPoint point):
        # C级别实现
        cdef ECPoint result = ECPoint(0, 0)
        # ...
        return result

```python

**预期性能提升**: 10-100倍

## 4.2.3 预计算表

**原理**: 预先计算常用点的倍数

```python
class EllipticCurve:
    def __init__(self):
        # 预计算G的倍数
        self.precomputed = {}
        G = ECPoint(Secp256k1.Gx, Secp256k1.Gy)
        for i in range(256):
            self.precomputed[i] = self.scalar_multiply(2**i, G)
    
    def fast_scalar_multiply(self, k: int) -> ECPoint:
        """使用预计算表加速"""
        result = ECPoint(None, None)
        for i in range(256):
            if k & (1 << i):
                result = self.point_add(result, self.precomputed[i])
        return result

```python

**内存占用**: 256 × 64字节 ≈ 16KB

### 4.3 模运算优化

**当前实现**:

```python
def mod_inverse(self, a: int, m: int) -> int:
    # 扩展欧几里得算法
    t, new_t = 0, 1
    r, new_r = m, a
    
    while new_r != 0:
        quotient = r // new_r
        t, new_t = new_t, t - quotient * new_t
        r, new_r = new_r, r - quotient * new_r
    
    if t < 0:
        t = t + m
    
    return t

```python

**优化方案**:

- 使用Montgomery约减

- 使用Barrett约减

- 使用预计算表

## 5. 哈希运算优化

### 5.1 当前实现

**使用hashlib**:

```python
@staticmethod
def sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()

```python

**性能特点**:

- 底层使用OpenSSL实现

- 已经是C级别优化

- 进一步优化空间有限

### 5.2 批量哈希

**场景**: 批量地址验证

```python
def batch_hash160(public_keys: List[bytes]) -> List[bytes]:
    """批量计算Hash160"""
    results = []
    for pk in public_keys:
        results.append(HashUtils.hash160(pk))
    return results

```markdown

## 6. Base58编码优化

### 6.1 当前实现分析

**编码算法**:

```python
@staticmethod
def encode(data: bytes) -> str:
    leading_zeros = len(data) - len(data.lstrip(b'\x00'))
    num = int.from_bytes(data, 'big')
    
    result = []
    while num > 0:
        num, rem = divmod(num, Base58.BASE)
        result.append(Base58.ALPHABET[rem])
    
    return '1' * leading_zeros + ''.join(reversed(result))

```python

**性能瓶颈**:

- 大整数除法开销

- 字符串拼接开销

### 6.2 优化方案

#### 6.2.1 使用数组预分配

```python
@staticmethod
def encode_optimized(data: bytes) -> str:
    leading_zeros = len(data) - len(data.lstrip(b'\x00'))
    num = int.from_bytes(data, 'big')
    
    # 预分配数组
    result = [''] * 50  # 最大可能长度
    idx = 0
    
    while num > 0:
        num, rem = divmod(num, Base58.BASE)
        result[idx] = Base58.ALPHABET[rem]
        idx += 1
    
    return '1' * leading_zeros + ''.join(reversed(result[:idx]))

```markdown

#### 6.2.2 使用查表法

```python
# 预计算查找表
BASE58_TABLE = [Base58.ALPHABET[i] for i in range(58)]

```markdown

## 7. 内存优化

### 7.1 内存使用分析

| 组件 | 内存占用 | 优化空间 |
|------|----------|----------|
| 椭圆曲线点 | 64字节/点 | 使用__slots__ |
| 去重过滤器 | 100MB/百万条目 | 使用布隆过滤器 |
| 批量结果 | 可变 | 流式处理 |
| 线程栈 | 8MB/线程 | 减少线程数 |

### 7.2 使用__slots__

```python
class ECPoint:
    __slots__ = ['x', 'y', 'curve', 'is_infinity']
    
    def __init__(self, x: Optional[int], y: Optional[int], curve=Secp256k1):
        self.x = x
        self.y = y
        self.curve = curve
        self.is_infinity = (x is None or y is None)

```python

**效果**: 减少约50%内存占用

### 7.3 布隆过滤器

**替代哈希集合**:

```python
import pybloom_live

class BloomDeduplicationFilter:
    def __init__(self, capacity: int = 1_000_000, error_rate: float = 0.001):
        self.bloom = pybloom_live.BloomFilter(capacity=capacity, error_rate=error_rate)
        self._lock = threading.Lock()
    
    def check_and_add(self, private_key: bytes) -> bool:
        with self._lock:
            if private_key in self.bloom:
                return False
            self.bloom.add(private_key)
            return True

```python

**内存对比**:
| 方法 | 百万条目内存占用 |
|------|-----------------|
| 哈希集合 | ~100MB |
| 布隆过滤器(0.1%误差) | ~1.5MB |

## 8. I/O优化

### 8.1 CSV导出优化

**批量写入**:

```python
def export_csv_optimized(self, filename: str, results: List[dict]):
    """优化CSV导出"""
    with open(filename, 'w', newline='', buffering=8192) as f:
        writer = csv.writer(f)
        writer.writerow(['序号', '比特币地址', '私钥 (WIF)'])
        
        # 批量写入
        batch = []
        for r in results:
            batch.append([r['index'], r['address'], r['private_key_wif']])
            if len(batch) >= 1000:
                writer.writerows(batch)
                batch.clear()
        
        if batch:
            writer.writerows(batch)

```markdown

### 8.2 断点保存优化

**增量保存**:

```python
def save_checkpoint_incremental(self, filename: str, data: dict):
    """增量保存断点"""
    # 只保存增量数据
    incremental_data = {
        'new_matches': data['matches'][self._last_saved_count:],
        'total_checked': data['total_checked']
    }
    
    with open(filename, 'a') as f:
        json.dump(incremental_data, f)
        f.write('\n')

```yaml

## 9. GPU加速

### 9.1 可行性分析

**适用场景**:

- 大规模碰撞检测

- 批量地址生成

**技术方案**:

- CUDA (NVIDIA GPU)

- OpenCL (跨平台)

- Metal (Apple Silicon)

### 9.2 实测性能（v3.2.0）

| 平台 | 实测速度 | 优化模式 |
|------|--------|---------|
| Intel Arc A770 | **3.07M keys/s** | GPU PRNG + 异步双缓冲 |
| Intel Arc A770 (基准) | 44K keys/s | 无GPU优化 |
| 提升倍数 | **70x** | batch_size=1,048,576 |

### 9.3 历史预期性能参考

| 平台 | 预期加速比 |
|------|-----------|
| NVIDIA RTX 3080 | 100-1000x |
| Apple M1/M2 | 50-100x |
| AMD RX 6800 | 100-500x |

### 9.4 动态性能基准值计算（新增）

**原理**:

- 在GPU初始化时运行简短的性能测试，获取实际GPU性能数据

- 使用实际性能的80%作为基准值，用于性能警告阈值计算

- 避免使用固定的500K keys/s基准，适应不同GPU的实际性能

**实现**:

```python
def _calculate_dynamic_benchmark(self):
    """
    计算动态性能基准值
    
    通过运行简短的性能测试，获取实际GPU性能数据，
    并设置动态基准值，用于性能警告阈值计算。
    """
    import time
    
    # 运行简短的性能测试
    test_batch_size = 100000
    seed = os.urandom(32)
    
    try:
        start_time = time.time()
        # 运行测试批次
        self._gpu_kernel.run_batch(seed, test_batch_size)
        execution_time = time.time() - start_time
        
        # 计算实际性能
        actual_speed = test_batch_size / execution_time
        # 使用实际性能的80%作为基准
        self._dynamic_speed_benchmark = actual_speed * 0.8
        
        logger.info(f"动态性能基准计算完成: {self._dynamic_speed_benchmark:.0f} keys/s")
    except Exception as e:
        logger.warning(f"动态性能基准计算失败，使用默认值: {e}")
        # 保持默认值
        pass

```

**优势**:

- 适应不同GPU的实际性能

- 避免固定基准值导致的误报或漏报

- 提供更准确的性能监控和警告

### 9.5 实现挑战

- 椭圆曲线运算难以并行化

- 内存传输开销

- 代码复杂度增加

## 10. 性能监控

### 10.1 性能指标收集

```python
import time
import statistics

class PerformanceMonitor:
    def __init__(self):
        self.timings = []
    
    def measure(self, func, *args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        self.timings.append(elapsed)
        return result
    
    def report(self):
        if not self.timings:
            return "无数据"
        
        return {
            'mean': statistics.mean(self.timings),
            'median': statistics.median(self.timings),
            'min': min(self.timings),
            'max': max(self.timings),
            'stdev': statistics.stdev(self.timings) if len(self.timings) > 1 else 0
        }

```markdown

### 10.2 实时监控

```python
def monitor_performance(engine: KeyCollisionEngine):
    """实时监控碰撞引擎性能"""
    import psutil
    
    process = psutil.Process()
    
    while engine.is_running():
        stats = engine.get_stats()
        memory_info = process.memory_info()
        
        print(f"速度: {stats.rate_per_second:.2f}/s, "
              f"内存: {memory_info.rss / 1024 / 1024:.2f}MB, "
              f"CPU: {process.cpu_percent()}%")
        
        time.sleep(1)

```markdown

## 11. 优化建议汇总

### 11.1 短期优化（已实现）

| 优化项 | 效果 | 实现难度 |
|--------|------|----------|
| 批量处理 | +20% | 低 |
| 线程池并行 | +400% (8核) | 低 |
| 进度控制 | UI流畅度提升 | 低 |
| 去重过滤 | -5%重复计算 | 中 |

### 11.2 中期优化

| 优化项 | 预期效果 | 实现难度 |
|--------|----------|----------|
| __slots__ | -50%内存 | 低 |
| 布隆过滤器 | -98%去重内存 | 中 |
| 预计算表 | +50%速度 | 中 |
| I/O缓冲 | +30%导出速度 | 低 |

### 11.3 长期优化

| 优化项 | 预期效果 | 实现难度 |
|--------|----------|----------|
| Cython扩展 | +10-100x | 高 |
| GPU加速 | +100-1000x | 高 |
| SIMD优化 | +2-4x | 高 |

## 12. 性能测试脚本

```python
#!/usr/bin/env python3
"""性能测试脚本"""

import time
import statistics
from src.core.address_generator import P2PKHAddressGenerator

def benchmark_address_generation(count: int = 1000):
    """测试地址生成性能"""
    generator = P2PKHAddressGenerator()
    
    timings = []
    for _ in range(count):
        start = time.perf_counter()
        generator.generate_address()
        elapsed = time.perf_counter() - start
        timings.append(elapsed)
    
    print(f"地址生成性能测试 ({count}次):")
    print(f"  平均: {statistics.mean(timings)*1000:.3f}ms")
    print(f"  中位数: {statistics.median(timings)*1000:.3f}ms")
    print(f"  最小: {min(timings)*1000:.3f}ms")
    print(f"  最大: {max(timings)*1000:.3f}ms")
    print(f"  吞吐量: {1/statistics.mean(timings):.2f}/s")

def benchmark_public_key_generation(count: int = 1000):
    """测试公钥生成性能"""
    from src.core.secp256k1 import EllipticCurve
    import secrets
    
    ec = EllipticCurve()
    private_keys = [secrets.token_bytes(32) for _ in range(count)]
    
    start = time.perf_counter()
    for pk in private_keys:
        ec.generate_public_key(pk)
    elapsed = time.perf_counter() - start
    
    print(f"\n公钥生成性能测试 ({count}次):")
    print(f"  总时间: {elapsed*1000:.3f}ms")
    print(f"  平均: {elapsed/count*1000:.3f}ms")
    print(f"  吞吐量: {count/elapsed:.2f}/s")

if __name__ == "__main__":
    benchmark_public_key_generation(100)
    benchmark_address_generation(100)

```markdown

## 13. 目标地址管理优化

### 13.1 地址解析缓存

**原理**: 使用LRU缓存加速重复地址解析

**代码实现**:

```python
from src.collision.targets.resolver import TargetResolver

# 启用缓存
resolver = TargetResolver(enable_cache=True, cache_max_size=10000)

# 第一次解析(缓存未命中)
address1 = resolver.resolve('5KJvsngHeMpm884wtkJNzQGaCErckhHJBGFsvd3VyK5qMZXj3hS')

# 第二次解析(缓存命中,性能提升10x)
address2 = resolver.resolve('5KJvsngHeMpm884wtkJNzQGaCErckhHJBGFsvd3VyK5qMZXj3hS')

# 查看缓存统计
stats = resolver.get_cache_stats()
print(f"缓存命中率: {stats['hit_rate']:.2%}")

```python

**性能提升**:

- 缓存命中: ~50,000次/秒

- 缓存未命中: ~4,500次/秒

- 提升幅度: **10x**

## 13.2 批量处理优化

**原理**: 批量地址验证,利用多核并行

**代码实现**:

```python
from src.collision.targets.validator import AddressBatchValidator

# 创建验证器(4线程并行)
validator = AddressBatchValidator(max_workers=4)

# 批量验证
addresses = ['1A1z...', '1B2x...', 'invalid']
results = validator.validate_batch(addresses)

# 获取有效地址
valid_addresses = validator.filter_valid(addresses)

```python

**性能提升**:

- 单线程验证: ~1,000地址/秒

- 4线程并行: ~3,500地址/秒

- 提升幅度: **3.5x**

## 13.3 大规模地址集匹配

**原理**: 布隆过滤器优化大规模地址匹配,节省98%内存

**代码实现**:

```python
from src.collision.targets.matcher import AddressMatcher

# 小规模地址集(<10万) - 使用Hash集合
matcher = AddressMatcher(strategy='hash_set', targets=targets)

# 大规模地址集(>=10万) - 使用布隆过滤器
matcher = AddressMatcher(
    strategy='bloom_filter',
    targets=large_targets,
    bloom_capacity=100000,
    bloom_error_rate=0.001
)

# 检查匹配
is_match = matcher.is_match('1TestAddress...')

```python

**内存对比**:
| 方法 | 10万地址内存占用 | 误判率 |
|------|-----------------|--------|
| Hash集合 | ~5MB | 0% |
| 布隆过滤器 | ~100KB | 0.1% |

**适用场景**:

- Hash集合: 目标地址 < 10万

- 布隆过滤器: 目标地址 >= 10万

## 13.4 文件加载优化

**原理**: 批量解析+缓存加速文件加载

**代码实现**:

```python
from src.collision.targets.resolver import TargetResolver

resolver = TargetResolver(enable_cache=True)

# 批量加载文件(自动使用批量解析)
targets = resolver.load_from_file('valid_addresses.txt')

# 查看解析统计
stats = resolver.get_cache_stats()
print(f"解析了 {len(targets)} 个地址, 缓存命中率: {stats['hit_rate']:.2%}")

```

**性能提升**:

- 加载10万地址(旧版): ~2秒

- 加载10万地址(新版): ~0.5秒

- 提升幅度: **4x**

## 14. 总结

BTC项目在纯Python实现的基础上，通过批量处理、多线程并行、去重过滤等策略实现了较好的性能。主要瓶颈在于椭圆曲线运算的纯Python实现。

对于性能要求更高的场景，建议：

1. 使用多线程充分利用多核CPU

2. 考虑使用Cython或C扩展优化热点代码

3. 对于大规模碰撞检测，考虑GPU加速方案

4. 监控内存使用，必要时使用布隆过滤器优化

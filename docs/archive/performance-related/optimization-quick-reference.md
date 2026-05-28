# BTC碰撞引擎性能优化快速参考

## [QUICK] 快速开始

### 1. 安装优化依赖

```bash
# 必装依赖(推荐,获得最佳性能)
pip install gmpy2>=2.1.5 pycryptodome>=3.19.0

# 可选工具(性能分析)
pip install memory-profiler>=0.61 pytest-benchmark>=4.0
```

### 2. 启用优化(自动)

所有优化模块**自动检测**依赖并启用,无需手动配置:

```python
from src.core import (
    get_precomputed_table,
    get_bigint_optimizer,
    get_simd_hash_optimizer
)

# 自动使用最优后端
bigint_opt = get_bigint_optimizer()
print(f"大整数后端: {bigint_opt.get_backend_name()}")
# 输出: "gmpy2 (Comba乘法)" 或 "Pure Python"

simd_opt = get_simd_hash_optimizer()
print(f"哈希后端: {simd_opt.get_backend_name()}")
# 输出: "pycryptodome (SIMD/AES-NI)" 或 "hashlib"
```

---

## [PACKAGE] 核心优化模块

### 预计算点表 (+50%标量乘法)

```python
from src.core import get_precomputed_table

# 获取预计算表(window_size=4~8,越大越快但占用越多内存)
table = get_precomputed_table(window_size=8)  # 推荐: w=8

# 使用预计算表加速标量乘法
from src.core import EllipticCurve, Secp256k1, ECPoint

ec = EllipticCurve()
k = 0x1234567890abcdef...  # 私钥
result = table.scalar_multiply_with_table(k, ec)
```

**性能**: 256次迭代 → 32次迭代,提升50-70%

---

### SIMD哈希加速 (+200% SHA256)

```python
from src.core import get_simd_hash_optimizer

optimizer = get_simd_hash_optimizer()

# 批量SHA256
data_list = [b'data1', b'data2', b'data3', ...]
hashes = optimizer.batch_sha256(data_list)

# 批量Hash160(SHA256 + RIPEMD160)
public_keys = [pubkey1, pubkey2, ...]
hash160s = optimizer.batch_hash160(public_keys)
```

**性能**: hashlib 0.85s → pycryptodome 0.28s (10000次SHA256)

---

### 内存池 (-60%对象分配延迟)

```python
from src.core import get_pool_manager

# 初始化全局池(只需一次)
pool_mgr = get_pool_manager()
pool_mgr.initialize()

# 获取ECPoint池
ec_pool = pool_mgr.get_ecpoint_pool()

# 使用池获取对象
point = ec_pool.acquire(x=Secp256k1.Gx, y=Secp256k1.Gy)
# 使用...
ec_pool.release(point)  # 自动清零并归还

# 查看统计
stats = ec_pool.get_stats()
print(f"复用率: {stats['reuse_rate']:.2f}")
```

---

### 工作窃取线程池 (+30%多线程效率)

```python
from src.core import get_thread_pool

# 获取全局线程池(自动使用CPU核心数-1)
pool = get_thread_pool()

# 提交任务
def compute_hash(data):
    import hashlib
    return hashlib.sha256(data).digest()

futures = []
for data in data_list:
    future = pool.submit(compute_hash, data)
    futures.append(future)

# 获取结果
results = [f.result() for f in futures]
```

---

### GPU内存池 (-60%GPU内存分配)

```python
from src.gpu.memory_pool import get_gpu_memory_pool
import pyopencl as cl

# 创建OpenCL上下文
context = cl.create_some_context()

# 获取GPU内存池
pool = get_gpu_memory_pool(context, max_buffers=100)

# 分配缓冲区(优先复用)
buf = pool.allocate(1024)  # 1024字节

# 使用缓冲区...
# cl.enqueue_copy(queue, buf, data)

# 归还缓冲区
pool.release(buf, size=1024)

# 查看统计
stats = pool.get_stats()
print(f"GPU缓冲区复用率: {stats['reuse_rate']:.2f}")
```

---

## [CHART] 性能基准测试

### 运行基准测试

```python
import time
from src.core import get_precomputed_table, get_simd_hash_optimizer

# 测试1: 预计算表性能
table = get_precomputed_table(window_size=8)
k = 12345678901234567890

start = time.perf_counter()
for _ in range(1000):
    result = table.scalar_multiply_with_table(k)
elapsed = time.perf_counter() - start

print(f"预计算表: {1000/elapsed:.2f} ops/sec")

# 测试2: SIMD哈希性能
optimizer = get_simd_hash_optimizer()
data_list = [f'data{i}'.encode() for i in range(10000)]

start = time.perf_counter()
hashes = optimizer.batch_sha256(data_list)
elapsed = time.perf_counter() - start

print(f"SIMD SHA256: {len(data_list)/elapsed:.0f} hashes/sec")
print(f"后端: {optimizer.get_backend_name()}")
```

---

## [WRENCH] 配置调优

### 推荐配置

```json
{
  "performance": {
    "precomputed_window_size": 8,
    "memory_pool_initial_size": 1000,
    "memory_pool_max_size": 10000,
    "thread_pool_size": "auto",
    "gpu_memory_pool_max_buffers": 100
  }
}
```

### 窗口大小选择

| window_size | 预计算点数 | 内存占用 | 性能提升 | 推荐场景 |
|-------------|-----------|---------|---------|---------|
| 4 | 16 | 2.5KB | +30% | 内存受限 |
| 6 | 64 | 10KB | +50% | 平衡 |
| 8 | 256 | 40KB | +70% | **推荐** |

---

## [WARN] 注意事项

### 1. 依赖回退

所有优化提供**自动回退**机制:

```python
# 如果gmpy2未安装,自动使用纯Python
bigint_opt = get_bigint_optimizer()
if not bigint_opt.is_optimized():
    print("警告: gmpy2未安装,性能较低")
    print("安装: pip install gmpy2")
```

### 2. 线程安全

所有池管理器**线程安全**,可多线程使用:

```python
import threading

def worker():
    pool = get_pool_manager().get_ecpoint_pool()
    point = pool.acquire()
    # 使用...
    pool.release(point)

threads = [threading.Thread(target=worker) for _ in range(8)]
for t in threads:
    t.start()
```

### 3. 内存管理

池对象会自动清理,但建议**显式释放**:

```python
# 推荐用法
point = pool.acquire()
try:
    # 使用point
    pass
finally:
    pool.release(point)  # 确保归还
```

---

## [PERF] 性能监控

### 实时监控池统计

```python
import time
from src.core import get_pool_manager

pool_mgr = get_pool_manager()

while True:
    stats = pool_mgr.get_ecpoint_pool().get_stats()
    print(f"ECPoint池: 大小={stats['current_size']}, "
          f"复用率={stats['reuse_rate']:.2f}, "
          f"创建数={stats['created_count']}")
    time.sleep(5)
```

---

## [SOS] 故障排查

### 问题1: gmpy2安装失败(Windows)

```bash
# 方案1: 使用预编译wheel
pip install gmpy2‑2.1.5‑cp311‑cp311‑win_amd64.whl

# 方案2: 使用conda
conda install gmpy2

# 方案3: 跳过(使用纯Python回退)
# 性能降低~35%,但功能正常
```

### 问题2: pycryptodome冲突

```bash
# 如果已安装pycrypto,先卸载
pip uninstall pycrypto
pip install pycryptodome
```

### 问题3: 内存池占用过高

```python
# 调整池大小
from src.core.memory_pool import GlobalPoolManager

pool_mgr = GlobalPoolManager()
pool_mgr.ecpoint_pool = ECPointPool(
    initial_size=500,   # 降低初始大小
    max_size=5000       # 降低最大大小
)
```

---

## [BOOKS] 相关文档

- **完整实施报告**: `docs/optimization-implementation-summary.md`
- **进度报告**: `docs/optimization-progress-report.md`
- **优化计划**: `.trae/specs/performance_optimization/integrated_optimization_plan.md`
- **架构文档**: `docs/architecture.md`

---

**版本**: v2.2.0-performance  
**更新日期**: 2026-04-21

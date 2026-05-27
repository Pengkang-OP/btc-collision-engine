# BTC项目API接口文档

**版本**: v5.0.0

> **面向**: 开发者

## 目录

- [1. 概述](#1-概述)

- [2. 椭圆曲线模块 (secp256k1.py)](#2-椭圆曲线模块-secp256k1py)

  - [2.1 Secp256k1类](#21-secp256k1类)

- [2.2 ECPoint类](#22-ecpoint类)

  - [构造函数](#构造函数)

    - [copy()](#copy)

- [2.3 EllipticCurve类](#23-ellipticcurve类)

  - [构造函数](#构造函数)

  - [mod_inverse()](#mod_inverse)

- [point_add()](#point_add)

- [scalar_multiply()](#scalar_multiply)

- [scalar_multiply_const_time()](#scalar_multiply_const_time)

- [generate_public_key()](#generate_public_key)

- [3. 哈希工具模块 (hash_utils.py)](#3-哈希工具模块-hash_utilspy)

  - [3.1 HashUtils类](#31-hashutils类)

    - [sha256()](#sha256)

    - [ripemd160()](#ripemd160)

    - [hash160()](#hash160)

    - [double_sha256()](#double_sha256)

- [4. Base58编码模块 (base58.py)](#4-base58编码模块-base58py)

  - [4.1 Base58类](#41-base58类)

    - [encode()](#encode)

    - [decode()](#decode)

    - [check_encode()](#check_encode)

- [check_decode()](#check_decode)

- [5. WIF私钥格式模块 (wif.py)](#5-wif私钥格式模块-wifpy)

  - [5.1 WIF类](#51-wif类)

    - [encode()](#encode)

- [decode()](#decode)

- [6. 地址生成器模块 (address_generator.py)](#6-地址生成器模块-address_generatorpy)

  - [6.1 P2PKHAddressGenerator类](#61-p2pkhaddressgenerator类)

    - [构造函数](#构造函数)

    - [generate_private_key()](#generate_private_key)

    - [private_key_to_public_key()](#private_key_to_public_key)

    - [public_key_to_address()](#public_key_to_address)

    - [generate_address()](#generate_address)

- [6.2 CryptoManager类 (新增)](#62-cryptomanager类-新增)

  - [架构](#架构)

  - [generate_public_key()](#generate_public_key)

    - [设计特点](#设计特点)

    - [构造函数](#构造函数-1)

    - [check_and_add()](#check_and_add-1)

    - [get_stats()](#get_stats-1)

  - [8.3 CheckpointManager类 (补充)](#83-checkpointmanager类-补充)

    - [安全设计](#安全设计)

    - [构造函数](#构造函数-2)

    - [save()](#save-1)

    - [load()](#load-1)

  - [8.4 DataLogger类 (新增)](#84-datalogger类-新增)

    - [构造函数](#构造函数-3)

    - [log_performance_data()](#log_performance_data-1)

  - [8.5 TargetResolver类 (补充)](#85-targetresolver类-补充)

    - [构造函数](#构造函数-4)

    - [resolve()](#resolve-1)

    - [load_from_file()](#load_from_file-1)

  - [8.6 AddressBatchValidator类 (新增)](#86-addressbatchvalidator类-新增)

    - [构造函数](#构造函数-5)

    - [validate_batch()](#validate_batch-1)

    - [filter_valid()](#filter_valid-1)

  - [8.7 AddressMatcher类 (新增)](#87-addressmatcher类-新增)

    - [构造函数](#构造函数-6)

    - [is_match()](#is_match-1)

- [9. 格式感知目标管理器 (format_aware_manager.py) - 新增](#9-格式感知目标管理器-format_aware_managerpy---新增)

  - [9.1 FormatAwareTargetManager类](#91-formatawaretargetmanager类)

    - [构造函数](#构造函数-7)

    - [add_target()](#add_target)

    - [add_targets()](#add_targets)

    - [load_from_file()](#load_from_file-2)

    - [get_targets_by_format()](#get_targets_by_format-1)

    - [get_all_targets()](#get_all_targets)

    - [get_format_stats()](#get_format_stats)

    - [has_targets()](#has_targets)

    - [get_target_count()](#get_target_count)

    - [check_match()](#check_match)

    - [check_match_all()](#check_match_all)

    - [remove_target()](#remove_target)

    - [clear()](#clear-1)

    - [get_supported_formats()](#get_supported_formats)

    - [get_max_batch_size()](#get_max_batch_size)

- [10. GPU引擎模块 (gpu_engine.py)](#10-gpu引擎模块-gpu_enginepy)

  - [10.1 GPUDevice类](#101-gpudevice类)

    - [detect_devices() 静态方法](#detect_devices-静态方法)

    - [is_available() 静态方法](#is_available-静态方法)

    - [initialize() 方法](#initialize-方法)

    - [get_device_info() 方法](#get_device_info-方法)

  - [10.2 GPUKernel类](#102-gpukernel类)

- [11. GPU碰撞引擎 (gpu_collision_engine.py)](#11-gpu碰撞引擎-gpu_collision_enginepy)

  - [11.1 GPUCollisionEngine类](#111-gpucollisionengine类)

    - [构造函数](#构造函数-8)

    - [random_search() 方法](#random_search-方法)

    - [range_scan() 方法](#range_scan-方法)

    - [handle_gpu_batch_error() 静态方法](#handle_gpu_batch_error-静态方法)

  - [11.2 GPU vs CPU性能对比](#112-gpu-vs-cpu性能对比)

- [12. GPU监控模块 (gpu_monitor.py)](#12-gpu监控模块-gpu_monitorpy)

  - [12.1 GPUMonitor类](#121-gpumonitor类)

    - [构造函数](#构造函数-9)

    - [get_gpu_info() 方法](#get_gpu_info-方法-1)

    - [get_gpu_metrics() 方法](#get_gpu_metrics-方法)

    - [track_memory_usage() 方法](#track_memory_usage-方法)

- [13. 监控系统API (monitoring_system.py)](#13-监控系统api-monitoring_systempy)

  - [13.1 MonitoringData类](#131-monitoringdata类)

    - [to_dict() 方法](#to_dict-方法)

  - [13.2 DataCollector类](#132-datacollector类)

    - [构造函数](#构造函数-10)

    - [collect_performance_data() 方法](#collect_performance_data-方法-1)

    - [collect_system_data() 方法](#collect_system_data-方法-1)

    - [collect_engine_data() 方法](#collect_engine_data-方法-1)

    - [collect_all_data() 方法](#collect_all_data-方法-1)

  - [13.3 DataStorage类](#133-datastorage类)

    - [构造函数](#构造函数-11)

    - [主要方法](#主要方法)

    - [current_data.json格式](#current_datajson格式)

    - [history_data.json格式](#history_datajson格式)

    - [error_log.json格式](#error_logjson格式)

    - [performance.log格式](#performancelog格式)

- [15. 统计模块API (collision_stats.py)](#15-统计模块api-collision_statspy)

  - [15.1 CollisionStats类](#151-collisionstats类)

    - [构造函数](#构造函数-15)

    - [update() 方法](#update-方法)

    - [add_match() 方法](#add_match-方法)

    - [snapshot() 方法](#snapshot-方法)

    - [format_elapsed() 方法](#format_elapsed-方法)

    - [format_speed() 方法](#format_speed-方法)

    - [get_speed() 方法](#get_speed-方法-1)

    - [record_gpu_error() 方法](#record_gpu_error-方法-1)

    - [record_worker_error() 方法](#record_worker_error-方法-1)

    - [record_wif_encode_error() 方法](#record_wif_encode_error-方法-1)

    - [get_error_rates() 方法](#get_error_rates-方法-1)

    - [is_healthy() 方法](#is_healthy-方法-1)

    - [error_summary() 方法](#error_summary-方法-1)

- [16. 使用示例汇总](#16-使用示例汇总)

  - [16.1 P2PKHSimulator类](#161-p2pkhsimulator类)

    - [构造函数](#构造函数-16)

    - [derive_address()](#derive_address-1)

    - [derive_address_detailed()](#derive_address_detailed-1)

    - [run_test_vector()](#run_test_vector-1)

    - [parse_private_key_input()](#parse_private_key_input-1)

    - [batch_generate()](#batch_generate-1)

    - [run_interactive()](#run_interactive-1)

- [17. GUI模块 (p2pkh_gui.py)](#17-gui模块-p2pkh_guipy)

  - [17.1 P2PKHGUI类](#171-p2pkhgui类)

    - [构造函数](#构造函数-17)

- [18. 异常类 (exceptions.py)](#18-异常类-exceptionspy)

  - [18.1 KeyGenerationError](#181-keygenerationerror)

- [19. 安全密钥管理器 (secure_key_manager.py) - 新增](#19-安全密钥管理器-secure_key_managerpy---新增)

  - [19.1 SecureKeyManager类](#191-securekeymanager类)

    - [安全特性](#安全特性-1)

    - [构造函数](#构造函数-18)

    - [generate_key()](#generate_key-1)

    - [get_key()](#get_key-1)

    - [clear()](#clear-2)

    - [get_clear_stats() 静态方法](#get_clear_stats-静态方法-1)

    - [上下文管理器](#上下文管理器)

## 1. 概述

本文档详细说明BTC项目中所有公共类和方法的API接口，包括参数说明、返回值、异常处理和使用示例。

## 2. 椭圆曲线模块 (secp256k1.py)

### 2.1 Secp256k1类

**文件位置**: `src/core/secp256k1.py`

**描述**: 定义比特币使用的secp256k1椭圆曲线的所有数学参数。

**类属性**:

| 属性 | 类型 | 值 | 说明 |
|------|------|-----|------|
| `P` | int | 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F | 素数域模数 |
| `N` | int | 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141 | 曲线阶 |
| `Gx` | int | 0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798 | 基点x坐标 |
| `Gy` | int | 0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8 | 基点y坐标 |
| `A` | int | 0 | 曲线参数a |
| `B` | int | 7 | 曲线参数b |

**使用示例**:

```python

from src.core.secp256k1 import Secp256k1

# 访问曲线参数

print(f"素数域模数: {Secp256k1.P:x}")
print(f"曲线阶: {Secp256k1.N:x}")

```

---

## 2.2 ECPoint类

**文件位置**: `src/core/secp256k1.py`

**描述**: 表示椭圆曲线上的一个点，支持普通点和无穷远点（单位元）。

### 构造函数

```python

ECPoint(x: Optional[int], y: Optional[int], curve=Secp256k1)

```

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `x` | Optional[int] | x坐标，None表示无穷远点 |
| `y` | Optional[int] | y坐标，None表示无穷远点 |
| `curve` | class | 椭圆曲线参数类，默认Secp256k1 |

**属性**:
| 属性 | 类型 | 说明 |
|------|------|------|
| `x` | Optional[int] | x坐标 |
| `y` | Optional[int] | y坐标 |
| `curve` | class | 曲线参数类 |
| `is_infinity` | bool | 是否为无穷远点 |

**方法**:

#### copy()

```python

copy() -> 'ECPoint'

```

创建点的副本。

**返回**: ECPoint - 当前点的深拷贝

**示例**:

```python

from src.core.secp256k1 import ECPoint, Secp256k1

# 创建基点G

G = ECPoint(Secp256k1.Gx, Secp256k1.Gy)

# 创建副本

G_copy = G.copy()

```

---

## 2.3 EllipticCurve类

**文件位置**: `src/core/secp256k1.py`

**描述**: 实现椭圆曲线上的核心运算，包括模逆元、点加法、标量乘法和公钥生成。

### 构造函数

```python

EllipticCurve(curve=Secp256k1)

```

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `curve` | class | 椭圆曲线参数类，默认Secp256k1 |

#### mod_inverse()

```python

mod_inverse(a: int, m: int) -> int

```

计算模逆元（扩展欧几里得算法）。

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `a` | int | 被求逆元的整数 |
| `m` | int | 模数 |

**返回**: int - a在模m下的逆元

**异常**:
| 异常 | 说明 |
|------|------|
| `ValueError` | 当逆元不存在时（a和m不互质） |

**示例**:

```python

from src.core.secp256k1 import EllipticCurve

ec = EllipticCurve()

# 计算3在模7下的逆元（结果为5，因为3*5=15≡1 mod 7）

result = ec.mod_inverse(3, 7)
print(result)  # 输出: 5

```

## point_add()

```python

point_add(p1: ECPoint, p2: ECPoint) -> ECPoint

```

椭圆曲线点加法。

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `p1` | ECPoint | 第一个点 |
| `p2` | ECPoint | 第二个点 |

**返回**: ECPoint - 两点的和点

**示例**:

```python

from src.core.secp256k1 import EllipticCurve, ECPoint, Secp256k1

ec = EllipticCurve()

# 创建两点

G = ECPoint(Secp256k1.Gx, Secp256k1.Gy)
result = ec.point_add(G, G)  # G + G = 2G

```

## scalar_multiply()

```python

scalar_multiply(k: int, point: ECPoint) -> ECPoint

```

椭圆曲线标量乘法（双倍-加法算法）。

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `k` | int | 标量（正整数） |
| `point` | ECPoint | 椭圆曲线点 |

**返回**: ECPoint - k倍的点

**注意**: 此实现未使用恒定时间算法，不适用于对抗侧信道攻击的场景。

**示例**:

```python

from src.core.secp256k1 import EllipticCurve, ECPoint, Secp256k1

ec = EllipticCurve()
G = ECPoint(Secp256k1.Gx, Secp256k1.Gy)

# 计算2G

result = ec.scalar_multiply(2, G)

```

## scalar_multiply_const_time()

```python

scalar_multiply_const_time(k: int, point: ECPoint) -> ECPoint

```

恒定时间的椭圆曲线标量乘法（Montgomery Ladder算法）。

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `k` | int | 标量（正整数） |
| `point` | ECPoint | 椭圆曲线点 |

**返回**: ECPoint - k倍的点

**注意**: 使用恒定时间算法，可有效防御侧信道攻击。

**示例**:

```python

from src.core.secp256k1 import EllipticCurve, ECPoint, Secp256k1

ec = EllipticCurve()
G = ECPoint(Secp256k1.Gx, Secp256k1.Gy)

# 恒定时间计算公钥

private_key = 12345
public_point = ec.scalar_multiply_const_time(private_key, G)

```

## generate_public_key()

```python

generate_public_key(private_key, compressed: bool = True) -> bytes

```

从私钥生成公钥。

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `private_key` | bytes/int | 私钥，可以是32字节bytes或整数 |
| `compressed` | bool | 是否使用压缩格式，默认True |

**返回**: bytes - 公钥字节串

- 压缩格式: 33字节 (0x02/0x03 + 32字节x坐标)

- 非压缩格式: 65字节 (0x04 + 32字节x坐标 + 32字节y坐标)

**异常**:
| 异常 | 说明 |
|------|------|
| `ValueError` | 当生成的公钥为无穷远点时 |

**示例**:

```python

from src.core.secp256k1 import EllipticCurve

ec = EllipticCurve()

# 从私钥生成公钥

private_key = b'\x00' * 31 + b'\x01'
compressed_pk = ec.generate_public_key(private_key, compressed=True)
uncompressed_pk = ec.generate_public_key(private_key, compressed=False)

print(f"压缩公钥: {compressed_pk.hex()}")
print(f"非压缩公钥: {uncompressed_pk.hex()}")
**注意**: `generate_public_key()` 方法默认使用恒定时间算法（Montgomery Ladder），
可有效防御侧信道攻击。无需单独调用恒定时间版本。

**示例**:

```

from src.core.secp256k1 import EllipticCurve

ec = EllipticCurve()

# 从私钥生成公钥（默认使用恒定时间算法）

private_key = b'\x00' * 31 + b'\x01'
compressed_pk = ec.generate_public_key(private_key, compressed=True)
uncompressed_pk = ec.generate_public_key(private_key, compressed=False)

print(f"压缩公钥: {compressed_pk.hex()}")
print(f"非压缩公钥: {uncompressed_pk.hex()}")

```python
---

## 3. 哈希工具模块 (hash_utils.py)

### 3.1 HashUtils类

**文件位置**: `src/core/hash_utils.py`

**描述**: 提供比特币中使用的各种哈希函数，所有方法均为静态方法。

#### sha256()

```

sha256(data: bytes) -> bytes

```python

计算SHA-256哈希。

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `data` | bytes | 待哈希的字节串 |

**返回**: bytes - 32字节SHA-256哈希值

**示例**:

```

from src.core.hash_utils import HashUtils

data = b"Hello, Bitcoin!"
hash_value = HashUtils.sha256(data)
print(f"SHA-256: {hash_value.hex()}")

```markdown

#### ripemd160()

```

ripemd160(data: bytes) -> bytes

```python

计算RIPEMD-160哈希。

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `data` | bytes | 待哈希的字节串 |

**返回**: bytes - 20字节RIPEMD-160哈希值

**示例**:

```

from src.core.hash_utils import HashUtils

data = b"Hello, Bitcoin!"
hash_value = HashUtils.ripemd160(data)
print(f"RIPEMD-160: {hash_value.hex()}")

```markdown

#### hash160()

```

hash160(data: bytes) -> bytes

```python

计算Hash160 = RIPEMD-160(SHA-256(data))。

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `data` | bytes | 待哈希的字节串 |

**返回**: bytes - 20字节Hash160值

**示例**:

```

from src.core.hash_utils import HashUtils

public_key = bytes.fromhex('0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798')
hash160 = HashUtils.hash160(public_key)
print(f"Hash160: {hash160.hex()}")

```markdown

#### double_sha256()

```

double_sha256(data: bytes) -> bytes

```python

计算双SHA-256哈希。

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `data` | bytes | 待哈希的字节串 |

**返回**: bytes - 32字节双SHA-256哈希值

**示例**:

```

from src.core.hash_utils import HashUtils

data = b"Hello, Bitcoin!"
checksum = HashUtils.double_sha256(data)[:4]
print(f"校验和: {checksum.hex()}")

```python
---

## 4. Base58编码模块 (base58.py)

### 4.1 Base58类

**文件位置**: `src/core/base58.py`

**描述**: 实现Base58和Base58Check编码，用于比特币地址和私钥的表示。

**类属性**:

| 属性 | 类型 | 值 | 说明 |
|------|------|-----|------|
| `ALPHABET` | str | '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz' | Base58字符集 |
| `BASE` | int | 58 | 基数 |

#### encode()

```

encode(data: bytes) -> str

```python

将字节串编码为Base58字符串。

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `data` | bytes | 输入字节串 |

**返回**: str - Base58编码的字符串

**示例**:

```

from src.core.base58 import Base58

data = bytes.fromhex('00010966776006953d5567439e5e39f86a0d273bee')
encoded = Base58.encode(data)
print(f"Base58: {encoded}")

```markdown

#### decode()

```

decode(s: str) -> bytes

```python

将Base58字符串解码为字节串。

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `s` | str | Base58编码的字符串 |

**返回**: bytes - 解码后的字节串

**示例**:

```

from src.core.base58 import Base58

encoded = "16UwLL9Risc3QfPqBUvKofHmBQ7wMtjvM"
decoded = Base58.decode(encoded)
print(f"Decoded: {decoded.hex()}")

```markdown

#### check_encode()

```

check_encode(version: int, payload: bytes) -> str

```python

Base58Check编码。

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `version` | int | 版本字节（1字节整数） |
| `payload` | bytes | 载荷数据 |

**返回**: str - Base58Check编码的字符串

**示例**:

```

from src.core.base58 import Base58
from src.core.hash_utils import HashUtils

# 编码比特币地址

hash160 = bytes.fromhex('91b24bf9f5288532960ac687abb035127b1d28a5')
address = Base58.check_encode(0x00, hash160)
print(f"比特币地址: {address}")

```markdown

## check_decode()

```

check_decode(s: str) -> tuple

```python

Base58Check解码。

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `s` | str | Base58Check编码的字符串 |

**返回**: tuple - (version, payload) 元组

**异常**:
| 异常 | 说明 |
|------|------|
| `ValueError` | 当校验和验证失败时 |

**示例**:

```

from src.core.base58 import Base58

address = "16UwLL9Risc3QfPqBUvKofHmBQ7wMtjvM"
try:
    version, payload = Base58.check_decode(address)
    print(f"版本: 0x{version:02x}")
    print(f"Payload: {payload.hex()}")
except ValueError as e:
    print(f"解码失败: {e}")

```python
---

## 5. WIF私钥格式模块 (wif.py)

### 5.1 WIF类

**文件位置**: `src/core/wif.py`

**描述**: 实现比特币私钥的WIF（Wallet Import Format）编码和解码。

#### encode()

```

encode(private_key: bytes, compressed: bool = True) -> str

```python

将私钥编码为WIF格式。

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `private_key` | bytes | 32字节私钥 |
| `compressed` | bool | 是否使用压缩格式，默认True |

**返回**: str - WIF编码的字符串

- 压缩格式: 以 'K' 或 'L' 开头 (52字符)

- 非压缩格式: 以 '5' 开头 (51字符)

**异常**:
| 异常 | 说明 |
|------|------|
| `ValueError` | 当私钥长度无效时 |

**示例**:

```

from src.core.wif import WIF

private_key = bytes.fromhex('0000000000000000000000000000000000000000000000000000000000000001')

# 压缩格式

wif_compressed = WIF.encode(private_key, compressed=True)
print(f"WIF压缩: {wif_compressed}")

# 非压缩格式

wif_uncompressed = WIF.encode(private_key, compressed=False)
print(f"WIF非压缩: {wif_uncompressed}")

```markdown

## decode()

```

decode(wif: str) -> tuple

```python

解码WIF格式私钥。

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `wif` | str | WIF编码的字符串 |

**返回**: tuple - (private_key, is_compressed) 元组

- private_key: 32字节私钥

- is_compressed: 是否为压缩格式

**异常**:
| 异常 | 说明 |
|------|------|
| `ValueError` | 当WIF格式无效时 |

**示例**:

```

from src.core.wif import WIF

wif = "KwDiBf89QgGbjEhKnhXJuH7LrciVrZi3qYjgd9M7rFU73sVHnoWn"
private_key, is_compressed = WIF.decode(wif)
print(f"私钥: {private_key.hex()}")
print(f"是否压缩: {is_compressed}")

```python
---

## 6. 地址生成器模块 (address_generator.py)

### 6.1 P2PKHAddressGenerator类

**文件位置**: `src/core/address_generator.py`

**描述**: 协调整个地址生成流程，从私钥生成到最终比特币地址。

#### 构造函数

```

P2PKHAddressGenerator()

```python

创建椭圆曲线运算器实例。

#### generate_private_key()

```

generate_private_key(max_retries: int = 100) -> bytes

```python

生成随机私钥。

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `max_retries` | int | 最大重试次数，默认100次 |

**返回**: bytes - 32字节私钥

**异常**:
| 异常 | 说明 |
|------|------|
| `KeyGenerationError` | 当无法在max_retries次内生成有效私钥时 |

**示例**:

```

from src.core.address_generator import P2PKHAddressGenerator

generator = P2PKHAddressGenerator()
private_key = generator.generate_private_key()
print(f"私钥: {private_key.hex()}")

```markdown

#### private_key_to_public_key()

```

private_key_to_public_key(private_key: bytes, compressed: bool = True) -> bytes

```python

从私钥生成公钥。

**实现逻辑**: 优先使用`crypto_manager`（coincurve后端），回退到纯Python实现。

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `private_key` | bytes | 32字节私钥 |
| `compressed` | bool | 是否使用压缩格式，默认True |

**返回**: bytes - 公钥字节串

**示例**:

```

from src.core.address_generator import P2PKHAddressGenerator

generator = P2PKHAddressGenerator()
private_key = generator.generate_private_key()
public_key = generator.private_key_to_public_key(private_key)
print(f"公钥: {public_key.hex()}")

```markdown

#### public_key_to_address()

```

public_key_to_address(public_key: bytes) -> str

```python

从公钥生成比特币地址。

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `public_key` | bytes | 公钥字节串（压缩或非压缩） |

**返回**: str - 以'1'开头的比特币地址

**示例**:

```

from src.core.address_generator import P2PKHAddressGenerator

generator = P2PKHAddressGenerator()
private_key = generator.generate_private_key()
public_key = generator.private_key_to_public_key(private_key)
address = generator.public_key_to_address(public_key)
print(f"地址: {address}")

```markdown

#### generate_address()

```

generate_address(private_key: bytes = None) -> Tuple[str, bytes, bytes]

```python

生成完整的比特币地址。

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `private_key` | bytes | 可选的32字节私钥，None则随机生成 |

**返回**: Tuple[str, bytes, bytes] - (address, compressed_public_key, uncompressed_public_key) 元组

**异常**:
| 异常 | 说明 |
|------|------|
| `ValueError` | 当私钥长度不为32字节时 |

**示例**:

```

from src.core.address_generator import P2PKHAddressGenerator

generator = P2PKHAddressGenerator()

# 随机生成地址

address, compressed_pk, uncompressed_pk = generator.generate_address()
print(f"地址: {address}")
print(f"压缩公钥: {compressed_pk.hex()}")
print(f"非压缩公钥: {uncompressed_pk.hex()}")

# 使用指定私钥

private_key = bytes.fromhex('0000000000000000000000000000000000000000000000000000000000000001')
address, _, _ = generator.generate_address(private_key)
print(f"地址: {address}")

```python
---

## 6.2 CryptoManager类 (新增)

**文件位置**: `src/core/crypto_backend.py`

**描述**: 加密后端管理器，自动选择最佳后端（coincurve或纯Python）。

### 架构

```

CryptoBackend (抽象基类)
├── PurePythonBackend: 纯Python实现
└── CoincurveBackend: coincurve库加速（推荐）

CryptoManager (管理器)
└── 自动选择最佳后端

```markdown

#### generate_public_key()

```

generate_public_key(private_key: bytes, compressed: bool = True) -> bytes

```python

统一的公钥生成接口。

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `private_key` | bytes | 32字节私钥 |
| `compressed` | bool | 是否使用压缩格式 |

**返回**: bytes - 公钥字节串

**性能**:

- Coincurve后端：~3000-5000地址/秒（单线程）

- PurePython后端：~1000地址/秒（单线程）

**示例**:

```

from src.core.crypto_backend import crypto_manager

private_key = bytes.fromhex('0000000000000000000000000000000000000000000000000000000000000001')
public_key = crypto_manager.generate_public_key(private_key, compressed=True)
print(f"公钥: {public_key.hex()}")

```python
---

## 7. 多格式地址生成器 (multi_format_generator.py) - 新增

### 7.1 AddressFormat枚举

**文件位置**: `src/core/multi_format_generator.py`

**描述**: 比特币地址格式枚举，定义支持的所有地址类型。

**枚举值**:
| 值 | 说明 | 前缀示例 |
|----|------|---------|
| `P2PKH` | Pay-to-Public-Key-Hash | `1...` |
| `P2SH` | Pay-to-Script-Hash | `3...` |
| `BECH32` | SegWit v0 (P2WPKH) | `bc1q...` |
| `TAPROOT` | SegWit v1 (P2TR) | `bc1p...` |

---

### 7.2 MultiFormatAddressGenerator类

**文件位置**: `src/core/multi_format_generator.py`

**描述**: 多格式比特币地址生成器，支持从单个私钥生成所有主流比特币地址格式，自动检测地址格式，提供智能匹配功能。

#### 构造函数

```

MultiFormatAddressGenerator(auto_detect: bool = True, prefer_compressed: bool = True)

```

**参数**:
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `auto_detect` | bool | True | 是否自动检测支持的格式 |
| `prefer_compressed` | bool | True | 是否优先使用压缩公钥 |

**示例**:

```

from src.core.multi_format_generator import MultiFormatAddressGenerator, AddressFormat

# 创建生成器

generator = MultiFormatAddressGenerator()

```

## generate_public_key()

```

generate_public_key(private_key: bytes, compressed: bool = True) -> bytes

```

从私钥生成公钥。

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `private_key` | bytes | 32字节私钥 |
| `compressed` | bool | 是否使用压缩格式 |

**返回**: bytes - 公钥字节串

### generate_p2pkh_address()

```

generate_p2pkh_address(private_key: bytes) -> str

```

生成P2PKH地址（Pay-to-Public-Key-Hash）。

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `private_key` | bytes | 32字节私钥 |

**返回**: str - P2PKH地址字符串（以`1`开头）

**示例**:

```

generator = MultiFormatAddressGenerator()
private_key = bytes.fromhex('0000000000000000000000000000000000000000000000000000000000000001')
address = generator.generate_p2pkh_address(private_key)
print(f"P2PKH地址: {address}")  # 1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH

```

#### generate_p2sh_address()

```

generate_p2sh_address(private_key: bytes) -> str

```

生成P2SH地址（Pay-to-Script-Hash）。

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `private_key` | bytes | 32字节私钥 |

**返回**: str - P2SH地址字符串（以`3`开头）

**示例**:

```

address = generator.generate_p2sh_address(private_key)
print(f"P2SH地址: {address}")  # 3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy

```

#### generate_bech32_address()

```

generate_bech32_address(private_key: bytes, hrp: str = "bc") -> str

```

生成Bech32地址（SegWit v0 - P2WPKH）。

**参数**:
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `private_key` | bytes | - | 32字节私钥 |
| `hrp` | str | "bc" | Human-Readable Part（主网"bc"，测试网"tb"） |

**返回**: str - Bech32地址字符串（以`bc1q`开头）

**示例**:

```

address = generator.generate_bech32_address(private_key)
print(f"Bech32地址: {address}")  # bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4

```

#### generate_taproot_address()

```

generate_taproot_address(private_key: bytes, hrp: str = "bc") -> str

```

生成Taproot地址（SegWit v1 - P2TR）。

**参数**:
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `private_key` | bytes | - | 32字节私钥 |
| `hrp` | str | "bc" | Human-Readable Part |

**返回**: str - Taproot地址字符串（以`bc1p`开头）

**注意**: Taproot使用xonly公钥（仅x坐标，32字节）

#### generate_all_formats()

```

generate_all_formats(private_key: bytes, hrp: str = "bc") -> Dict[AddressFormat, str]

```

生成所有格式的地址。

**参数**:
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `private_key` | bytes | - | 32字节私钥 |
| `hrp` | str | "bc" | Human-Readable Part |

**返回**: Dict[AddressFormat, str] - 格式到地址的映射字典

**示例**:

```

generator = MultiFormatAddressGenerator()
private_key = bytes.fromhex('0000000000000000000000000000000000000000000000000000000000000001')
addresses = generator.generate_all_formats(private_key)

print(f"P2PKH: {addresses[AddressFormat.P2PKH]}")
print(f"P2SH: {addresses[AddressFormat.P2SH]}")
print(f"Bech32: {addresses[AddressFormat.BECH32]}")
print(f"Taproot: {addresses[AddressFormat.TAPROOT]}")

```

#### detect_address_format()

```

detect_address_format(address: str) -> AddressFormat

```

自动检测比特币地址格式。

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `address` | str | 比特币地址字符串（大小写不敏感） |

**返回**: AddressFormat - 检测到的地址格式

**异常**:
| 异常 | 说明 |
|------|------|
| `ValueError` | 地址格式无法识别 |

**示例**:

```

generator = MultiFormatAddressGenerator()

# 检测各种格式

print(generator.detect_address_format("1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"))  # P2PKH
print(generator.detect_address_format("3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy"))  # P2SH
print(generator.detect_address_format("bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"))  # BECH32
print(generator.detect_address_format("BC1QW508D6Q EJXTDG4Y5R3ZARVARY0C5XW7KV8F3T4"))  # 支持大写

```

## match_all_formats()

```

match_all_formats(private_key: bytes, targets: Set[str], hrp: str = "bc") -> List[Tuple[str, str]]

```

用所有格式的地址匹配目标集合。

**参数**:
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `private_key` | bytes | - | 32字节私钥 |
| `targets` | Set[str] | - | 目标地址集合（小写存储） |
| `hrp` | str | "bc" | Human-Readable Part |

**返回**: List[Tuple[str, str]] - 匹配列表，每个元素是(地址, 格式字符串)

**示例**:

```

generator = MultiFormatAddressGenerator()
targets = {
    "1bgzg9tcn4rm9kbzdn7kprqz87sz26samh",
    "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"
}

private_key = bytes.fromhex('0000000000000000000000000000000000000000000000000000000000000001')
matches = generator.match_all_formats(private_key, targets)

for address, fmt in matches:
    print(f"匹配成功! {address} ({fmt})")

```
---

## 8. 碰撞检测引擎模块 (key_collision_engine.py)

### 8.1 KeyCollisionEngine类

**文件位置**: `src/collision/key_collision_engine.py`

**描述**: 比特币私钥碰撞引擎，支持随机碰撞检测、断点续传、去重过滤等功能。

#### 构造函数

```

KeyCollisionEngine(
    targets: Set[str],
    on_progress: Optional[Callable] = None,
    on_match: Optional[Callable] = None,
    on_complete: Optional[Callable] = None,
    checkpoint_enabled: bool = False,
    dedup_enabled: bool = False,
    dedup_max_size: int = 1_000_000,
    checkpoint_interval: int = 30,
    max_workers: Optional[int] = None,
    event_bus: Optional[EventBus] = None,
    data_logging_enabled: bool = True,
    data_logging_interval: int = 5,
    verbose_logging: bool = False,
    use_enhanced_monitoring: bool = True,
    use_performance_optimization: bool = True,
    precomputed_window_size: int = 8,
    use_simd_hash: bool = True,
    use_memory_pool: bool = True,
    crypto_backend_type: str = None
)

```python

**参数**:
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `targets` | Set[str] | 必填 | 目标地址集合 (set, O(1)查找) |
| `on_progress` | Callable | None | 进度回调 fn(stats: CollisionStats) |
| `on_match` | Callable | None | 匹配回调 fn(private_key: bytes, address: str, wif: str) |
| `on_complete` | Callable | None | 完成回调 fn(stats: CollisionStats) |
| `checkpoint_enabled` | bool | False | 是否启用断点续传 |
| `dedup_enabled` | bool | False | 是否启用去重过滤 |
| `dedup_max_size` | int | 1,000,000 | 去重过滤器最大容量 |
| `checkpoint_interval` | int | 30 | 断点自动保存间隔(秒) |
| `max_workers` | Optional[int] | None | 线程池最大工作线程数，None表示使用默认值 |
| `event_bus` | EventBus | None | 事件总线实例（v4.2.2新增，None则自动创建） |
| `data_logging_enabled` | bool | True | 是否启用数据日志记录 |
| `data_logging_interval` | int | 5 | 数据日志记录间隔(秒) |
| `verbose_logging` | bool | False | 是否启用详细日志（生产环境建议False） |
| `use_enhanced_monitoring` | bool | True | 是否使用增强监控系统（包含异常检测和告警） |
| `use_performance_optimization` | bool | True | 是否启用性能优化（v4.2.2新增） |
| `precomputed_window_size` | int | 8 | 预计算表窗口大小(4-8) |
| `use_simd_hash` | bool | True | 是否使用SIMD哈希优化 |
| `use_memory_pool` | bool | True | 是否使用内存池 |
| `crypto_backend_type` | str | None | 加密后端类型: 'coincurve', 'openssl', 'ecdsa', 'pure_python' |

**内部配置**:

```

self._batch_size = 1000  # 每批处理的私钥数量
self._progress_interval_sec = 0.5  # 进度回调最小间隔（秒）

```python

**运行模式**:

- `random_search()`: 随机搜索模式

- `range_scan(start, end)`: 范围扫描模式

- `brute_force(start, max_keys)`: 暴力穷举模式

**示例**:

```

from src.collision.key_collision_engine import KeyCollisionEngine

# 目标地址

targets = {"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"}

# 创建引擎

engine = KeyCollisionEngine(
    targets=targets,
    on_progress=lambda stats: print(f"已检查: {stats.total_checked}"),
    on_match=lambda pk, addr, wif: print(f"匹配! {addr} -> {wif}"),
    checkpoint_enabled=True,
    dedup_enabled=True
)

```markdown

## random_search()

```

random_search()

```python

随机碰撞模式 - 使用线程池并行生成私钥并比对。

**说明**: 启动随机碰撞检测，直到调用stop()或找到匹配。

**示例**:

```

from src.collision.key_collision_engine import KeyCollisionEngine
import threading

targets = {"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"}
engine = KeyCollisionEngine(targets=targets)

# 在后台线程中运行

thread = threading.Thread(target=engine.random_search)
thread.start()

# 运行一段时间后停止

import time
time.sleep(10)
engine.stop()
thread.join()

```markdown

## stop()

```

stop()

```python

停止碰撞检测。

**说明**: 设置停止标志，等待当前批次完成后停止。

### is_running()

```

is_running() -> bool

```python

检查引擎是否正在运行。

**返回**: bool - 是否正在运行

#### get_stats()

```

get_stats() -> CollisionStats

```python

获取当前统计信息。

**返回**: CollisionStats - 碰撞统计对象

---

### 7.2 DeduplicationFilter类 (补充)

**文件位置**: `src/collision/deduplication_filter.py` (122行)

**描述**: 私钥去重过滤器，防止重复检测相同私钥。

#### 设计特点

- **双缓冲设计**: `_current` + `_pending`集合，避免频繁清空

- **8字节指纹**: SHA256截断作为指纹，误判率极低

- **FIFO队列**: `deque(maxlen=max_size//2)`跟踪插入顺序

- **线程安全**: 所有计数器更新在锁内完成

- **适用场景**: 仅对`random_search`模式有意义

#### 构造函数

```

DeduplicationFilter(max_size: int = 1_000_000, enabled: bool = True)

```python

**参数**:
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `max_size` | int | 1,000,000 | 最大容量 |
| `enabled` | bool | True | 是否启用 |

#### check_and_add()

```

check_and_add(private_key: bytes) -> bool

```python

检查是否重复。不重复返回True，重复返回False。

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `private_key` | bytes | 私钥字节串 |

**返回**: bool - True表示不重复，False表示重复

#### get_stats()

```

get_stats() -> Dict[str, Any]

```python

返回去重统计。

**返回字段**:
| 字段 | 类型 | 说明 |
|------|------|------|
| `tracked_current` | int | 当前集合大小 |
| `tracked_pending` | int | 待淘汰集合大小 |
| `tracked_total` | int | 总跟踪数 |
| `duplicates_found` | int | 发现的重复数 |
| `checks_total` | int | 总检查数 |
| `duplicate_rate` | float | 重复率 |
| `memory_usage_estimate` | int | 内存估计（字节） |

---

### 7.3 CheckpointManager类 (补充)

**文件位置**: `src/collision/checkpoint_manager.py` (187行)

**描述**: 断点管理器，保存和恢复碰撞进度。

#### 安全设计

- **不保存私钥**: 仅保存地址和私钥哈希

- **原子写入**: 临时文件 + `os.replace()`

- **版本控制**: version=1

- **脏标志**: `_dirty`标记未保存更改

#### 构造函数

```

CheckpointManager(filepath: str = None, auto_save_interval: int = 30)

```python

**参数**:
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `filepath` | str | collision_checkpoint.json | 断点文件路径 |
| `auto_save_interval` | int | 30 | 自动保存间隔（秒） |

#### save()

```

save(mode: str, targets: Set[str], current_position: int,
     total_checked: int, matches: List[Dict],
     range_start: Optional[int] = None,
     range_end: Optional[int] = None,
     force: bool = False) -> None

```python

保存断点到JSON文件（线程安全）。

**安全说明**: 匹配的私钥信息不会被保存，仅保存地址和时间戳用于统计。

#### load()

```

load() -> Optional[Dict]

```python

从文件加载断点，文件不存在或格式错误返回None。

---

### 7.4 DataLogger类 (新增)

**文件位置**: `src/monitoring/data_logger.py`

**描述**: 数据日志记录器，定期记录性能指标到JSON文件。

#### 构造函数

```

DataLogger(log_dir: str = "monitoring_data", log_interval: int = 5)

```python

**参数**:
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `log_dir` | str | monitoring_data | 日志目录 |
| `log_interval` | int | 5 | 记录间隔（秒） |

#### log_performance_data()

```

log_performance_data(stats: CollisionStats) -> None

```python

记录性能数据。

**记录内容**:

- 速度（地址/秒）

- 已检查数量

- 匹配数量

- CPU使用率

- 内存使用量

- 时间戳

**日志文件**:

- `current_data.json`: 当前数据

- `history_data.json`: 历史数据

- `error_log.json`: 错误日志

- `report_YYYY-MM-DD.json`: 每日报告

---

### 7.5 TargetResolver类 (补充)

**文件位置**: `src/collision/targets/resolver.py` (419行)

**描述**: 目标地址解析器，支持LRU缓存加速重复地址解析。

#### 构造函数

```

TargetResolver(enable_cache: bool = True, cache_max_size: int = 10000)

```python

**参数**:
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `enable_cache` | bool | True | 是否启用LRU缓存 |
| `cache_max_size` | int | 10000 | 缓存最大容量 |

#### resolve()

```

resolve(key: str) -> str

```python

解析地址（支持WIF、Hex等格式）。

**性能**:

- 缓存命中：~50,000次/秒

- 缓存未命中：~4,500次/秒

- 提升幅度：**10x**

#### load_from_file()

```

load_from_file(filepath: str) -> Set[str]

```python

批量加载文件中的地址。

**性能**:

- 加载10万地址（旧版）：~2秒

- 加载10万地址（新版）：~0.5秒

- 提升幅度：**4x**

---

### 7.6 AddressBatchValidator类 (新增)

**文件位置**: `src/collision/targets/validator.py` (277行)

**描述**: 批量地址验证器，利用多核并行验证。

#### 构造函数

```

AddressBatchValidator(max_workers: int = 4)

```python

**参数**:
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `max_workers` | int | 4 | 并行工作线程数 |

#### validate_batch()

```

validate_batch(addresses: List[str]) -> List[Dict[str, Any]]

```python

批量验证地址列表。

**性能**:

- 单线程验证：~1,000地址/秒

- 4线程并行：~3,500地址/秒

- 提升幅度：**3.5x**

#### filter_valid()

```

filter_valid(addresses: List[str]) -> List[str]

```python

过滤出有效地址。

---

### 7.7 AddressMatcher类 (新增)

**文件位置**: `src/collision/targets/matcher.py` (294行)

**描述**: 地址匹配器，支持Hash集合和布隆过滤器两种策略。

#### 构造函数

```

AddressMatcher(strategy: str = 'hash_set', targets: Set[str] = None,
               bloom_capacity: int = 100000, bloom_error_rate: float = 0.001)

```python

**参数**:
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `strategy` | str | 'hash_set' | 匹配策略（'hash_set'或'bloom_filter'） |
| `targets` | Set[str] | None | 目标地址集合 |
| `bloom_capacity` | int | 100000 | 布隆过滤器容量 |
| `bloom_error_rate` | float | 0.001 | 布隆过滤器误判率 |

#### is_match()

```

is_match(address: str) -> bool

```python

检查地址是否匹配。

**内存对比**:
| 方法 | 10万地址内存占用 | 误判率 |
|------|-----------------|--------|
| Hash集合 | ~5MB | 0% |
| 布隆过滤器 | ~100KB | 0.1% |

**适用场景**:

- Hash集合：目标地址 < 10万

- 布隆过滤器：目标地址 >= 10万

---

## 9. 格式感知目标管理器 (format_aware_manager.py) - 新增

### 9.1 FormatAwareTargetManager类

**文件位置**: `src/collision/targets/format_aware_manager.py`

**描述**: 格式感知的目标地址管理器，自动检测目标地址格式，按格式分组管理，提供格式相关的智能匹配功能。

**特性**:

- 自动检测地址格式（P2PKH/P2SH/Bech32/Taproot）

- 大小写不敏感存储

- 按格式分组，高效查询

- 线程安全（使用RLock保护）

- 支持从文件批量加载

- 提供格式统计信息

#### 构造函数

```

FormatAwareTargetManager()

```

创建格式感知目标管理器实例。

**示例**:

```

from src.collision.targets.format_aware_manager import FormatAwareTargetManager
from src.core.multi_format_generator import AddressFormat

manager = FormatAwareTargetManager()

```

#### add_target()

```

add_target(address: str) -> bool

```

添加单个目标地址，自动检测格式。

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `address` | str | 比特币地址字符串（大小写不敏感） |

**返回**: bool - True表示成功添加新地址，False表示已存在

**示例**:

```

manager = FormatAwareTargetManager()

# 添加各种格式的地址

manager.add_target("1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH")  # P2PKH
manager.add_target("3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy")  # P2SH
manager.add_target("bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4")  # Bech32
manager.add_target("BC1QW508D6Q EJXTDG4Y5R3ZARVARY0C5XW7KV8F3T4")  # 支持大写

```

## add_targets()

```

add_targets(addresses: List[str]) -> int

```

批量添加目标地址。

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `addresses` | List[str] | 地址列表 |

**返回**: int - 成功添加的地址数量

**示例**:

```

manager = FormatAwareTargetManager()
addresses = [
    "1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH",
    "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy",
    "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"
]
count = manager.add_targets(addresses)
print(f"成功添加 {count} 个地址")

```

### load_from_file()

```

load_from_file(filepath: str) -> int

```

从文件加载目标地址。

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `filepath` | str | 文件路径 |

**返回**: int - 成功加载的地址数量

**文件格式**:

- 每行一个地址

- 以`#`开头的行被视为注释跳过

- 空行自动跳过

- 自动去除首尾空白

- 支持UTF-8编码

**示例**:

```

manager = FormatAwareTargetManager()
count = manager.load_from_file("target_addresses.txt")
print(f"从文件加载了 {count} 个地址")

```

#### get_targets_by_format()

```

get_targets_by_format() -> Dict[AddressFormat, Set[str]]

```

获取按格式分组的目标地址。

**返回**: Dict[AddressFormat, Set[str]] - 格式到地址集合的映射

**示例**:

```

manager = FormatAwareTargetManager()

# 添加一些地址...

targets = manager.get_targets_by_format()
for fmt, addrs in targets.items():
    print(f"{fmt.value}: {len(addrs)} 个地址")

```

## get_all_targets()

```

get_all_targets() -> Set[str]

```

获取所有目标地址。

**返回**: Set[str] - 所有地址的集合（小写格式）

### get_format_stats()

```

get_format_stats() -> Dict[str, int]

```

获取格式统计信息。

**返回**: Dict[str, int] - 格式名称到数量的映射

**示例**:

```

manager = FormatAwareTargetManager()

# 添加一些地址...

stats = manager.get_format_stats()
print("格式统计:")
for fmt, count in stats.items():
    print(f"  {fmt}: {count}")

```

## check_match()

```

check_match(private_key: bytes) -> tuple[bool, Optional[str], Optional[str]]

```

检查私钥是否匹配任何目标。内部自动生成对应格式的地址进行匹配。

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `private_key` | bytes | 32字节私钥 |

**返回**: (is_match, matched_address, matched_format) 元组

**示例**:

```

manager = FormatAwareTargetManager()

# 添加地址...

private_key = bytes.fromhex('0000000000000000000000000000000000000000000000000000000000000001')
is_match, matched_addr, matched_fmt = manager.check_match(private_key)

if is_match:
    print(f"找到匹配！格式: {matched_fmt}, 地址: {matched_addr}")

```

## check_match_all()

```

check_match_all(private_key: bytes) -> tuple[bool, list[tuple[str, str]]]

```

检查私钥是否匹配所有目标格式的地址，返回所有匹配。

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `private_key` | bytes | 32字节私钥 |

**返回**: (is_match, list[tuple[address, format]]) 元组

**示例**:

```

manager = FormatAwareTargetManager()

# 添加地址...

private_key = bytes.fromhex('0000000000000000000000000000000000000000000000000000000000000001')
is_match, all_matches = manager.check_match_all(private_key)

if is_match:
    print(f"找到 {len(all_matches)} 个匹配:")
    for addr, fmt in all_matches:
        print(f"  - {fmt}: {addr}")

```

## remove_target()

```

remove_target(address: str) -> bool

```

移除目标地址。

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `address` | str | 要移除的地址 |

**返回**: bool - True表示成功移除

### clear()

```

clear() -> None

```

清空所有目标地址。

**完整示例**:

```

from src.collision.targets.format_aware_manager import FormatAwareTargetManager

# 创建管理器

manager = FormatAwareTargetManager()

# 从文件加载目标地址

manager.load_from_file("targets.txt")

# 打印格式统计

stats = manager.get_format_stats()
print("目标地址格式统计:")
for fmt, count in stats.items():
    print(f"  {fmt}: {count}")

# 检查匹配（只需传入私钥，内部自动生成对应格式的地址）

private_key = bytes.fromhex('0000000000000000000000000000000000000000000000000000000000000001')
is_match, all_matches = manager.check_match_all(private_key)

if is_match:
    print(f"\n找到 {len(all_matches)} 个匹配!")
    for addr, fmt in all_matches:
        print(f"  - {fmt}: {addr}")

```
---

## 10. GPU引擎模块 (gpu_engine.py)

### 10.1 GPUDevice类

**文件位置**: `gpu_engine.py` (第1080行起)

**描述**: OpenCL GPU设备管理类,负责GPU设备检测、初始化和能力验证。

#### detect_devices() 静态方法

```

@staticmethod
detect_devices() -> List[Dict]

```python

检测所有可用的OpenCL GPU设备。

**返回**: List[Dict] - 设备信息列表,每个设备包含:

- `platform`: 平台名称

- `name`: 设备名称

- `vendor`: 设备厂商

- `device`: OpenCL设备对象

- `global_mem_size`: 显存大小(字节)

**过滤规则**:

- 自动过滤CPU设备

- 自动过滤核显(Intel HD Graphics, UHD Graphics, Iris)

- 仅保留独立GPU设备

**示例**:

```

from gpu_engine import GPUDevice

devices = GPUDevice.detect_devices()
for i, dev in enumerate(devices):
    print(f"GPU {i}: {dev['name']} ({dev['vendor']})")
    print(f"  显存: {dev['global_mem_size'] / (1024**3):.2f} GB")

```markdown

#### is_available() 静态方法

```

@staticmethod
is_available() -> bool

```python

检查pyopencl是否可用。

**返回**: bool - pyopencl可用返回True

#### initialize() 方法

```

initialize(device_index: int = 1) -> None

```python

初始化GPU设备。

**参数**:
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `device_index` | int | 1 | 设备索引,-1表示自动选择最佳设备 |

**设备选择逻辑**:

- `device_index = -1`: 自动选择最佳设备

- `device_index >= 0`: 使用指定设备(超出范围时自动回退)

- 其他负数: 视为无效,回退到自动选择

**最佳设备选择优先级**:

1. NVIDIA GPU (GeForce, RTX)

2. AMD GPU (Radeon)

3. Intel Arc GPU

4. 其他Intel GPU

**设备能力验证**:

- 最低计算单元: 2个

- 最低显存: 512MB

- 不满足时会发出警告但继续执行

**示例**:

```

from gpu_engine import GPUDevice

gpu = GPUDevice()

# 自动选择最佳GPU

gpu.initialize(device_index=-1)

# 获取设备信息

info = gpu.get_device_info()
print(f"设备: {info['name']}")
print(f"厂商: {info['vendor']}")
print(f"显存: {info['global_mem_size'] / (1024**3):.2f} GB")
print(f"计算单元: {info['max_compute_units']}")

```markdown

## get_device_info() 方法

```

get_device_info() -> Dict

```python

获取当前GPU设备信息。

**返回字段**:
| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | str | 设备名称 |
| `type` | str | 设备类型(通常是"GPU") |
| `vendor` | str | 设备厂商 |
| `platform` | str | OpenCL平台名称 |
| `global_mem_size` | int | 显存大小(字节) |
| `max_compute_units` | int | 计算单元数量 |

---

### 8.2 GPUKernel类

**文件位置**: `gpu_engine.py` (第1311行起)

**描述**: OpenCL内核管理类,负责GPU内核编译、参数设置和计算执行。

**核心功能**:

- uint256大数运算(加减乘除模逆)

- secp256k1椭圆曲线点乘(标量乘法)

- SHA-256 + RIPEMD-160哈希计算

- 批量私钥到Hash160转换

- 目标地址匹配检查

**OpenCL内核架构**:

```

uint256_t (256位整数)
├── d[8]: 8个uint32,小端序存储
└── 支持所有基本运算

secp256k1实现
├── 点加法: point_add()
├── 点倍乘: point_double()
├── 标量乘法: scalar_multiply()
└── 使用Jacobian坐标优化性能

哈希计算
├── SHA-256: sha256_hash()
├── RIPEMD-160: ripemd160_hash()
└── Hash160: hash160() = RIPEMD160(SHA256(x))

```python

**性能特点**:

- 并行处理: 每个工作项处理一个私钥

- 显存优化: 使用常量内存存储曲线参数

- 坐标优化: Jacobian投影坐标减少模逆运算

**使用示例**:

```

from gpu_engine import GPUDevice, GPUKernel
import pyopencl as cl

# 初始化GPU

gpu = GPUDevice()
gpu.initialize(device_index=-1)

# 创建内核

kernel = GPUKernel(gpu.context, gpu.queue)

# 批量计算私钥到Hash160

private_keys = [...]  # 私钥数组
hash160_results = kernel.compute_hash160_batch(private_keys)

# 检查目标匹配

targets = ["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"]
matches = kernel.check_matches(hash160_results, targets)

```python
---

## 11. GPU碰撞引擎 (gpu_collision_engine.py)

### 11.1 GPUCollisionEngine类

**文件位置**: `src/collision/gpu_collision_engine.py` (第535行起)

**描述**: 基于GPU加速的比特币私钥碰撞引擎,利用OpenCL并行计算能力实现高性能私钥碰撞检测。

#### 构造函数

```

GPUCollisionEngine(
    targets: Set[str],
    on_progress: Optional[Callable] = None,
    on_match: Optional[Callable] = None,
    on_complete: Optional[Callable] = None,
    checkpoint_enabled: bool = False,
    dedup_enabled: bool = False,
    dedup_max_size: int = 1_000_000,
    checkpoint_interval: int = 30,
    device_index: int = -1,
    batch_size: int = 65536,
    max_workers: Optional[int] = None
)

```python

**参数**:
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `targets` | Set[str] | 必填 | 目标地址集合 |
| `on_progress` | Callable | None | 进度回调 |
| `on_match` | Callable | None | 匹配回调 |
| `on_complete` | Callable | None | 完成回调 |
| `checkpoint_enabled` | bool | False | 是否启用断点续传 |
| `dedup_enabled` | bool | False | 是否启用去重 |
| `dedup_max_size` | int | 1,000,000 | 去重过滤器容量 |
| `checkpoint_interval` | int | 30 | 断点保存间隔(秒) |
| `device_index` | int | -1 | GPU设备索引(-1自动选择) |
| `batch_size` | int | 65536 | GPU批次大小 |
| `max_workers` | Optional[int] | None | CPU工作线程数 |

**与CPU引擎的参数对比**:

- 新增`device_index`: 选择GPU设备

- 新增`batch_size`: GPU批次大小(默认65536,远大于CPU的1000)

- 移除`data_logging_enabled`: GPU引擎暂不支持数据日志

#### random_search() 方法

```

random_search() -> None

```python

GPU随机搜索模式 - 使用GPU并行生成私钥并比对。

**工作流程**:

1. 初始化GPU设备和内核

2. 生成随机私钥批次(CPU端)

3. 传输私钥到GPU显存

4. GPU并行计算: 私钥 → 公钥 → Hash160

5. 传输Hash160结果回CPU

6. CPU端检查目标匹配

7. 发现匹配时触发回调

**性能优势**:

- 并行度: 65536个工作项同时计算

- 吞吐量: 比CPU引擎高10-100倍(取决于GPU)

- 显存带宽: 充分利用GPU高带宽特性

**示例**:

```

from src.collision.gpu.engine import GPUCollisionEngine

targets = {"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"}

engine = GPUCollisionEngine(
    targets=targets,
    on_progress=lambda stats: print(f"已检查: {stats.total_checked}"),
    on_match=lambda pk, addr, wif: print(f"匹配! {addr}"),
    device_index=-1,  # 自动选择最佳GPU
    batch_size=65536
)

engine.random_search()

```markdown

#### range_scan() 方法

```

range_scan(start: int, end: int) -> None

```python

GPU范围扫描模式 - 在指定私钥范围内进行扫描。

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `start` | int | 起始私钥(整数) |
| `end` | int | 结束私钥(整数) |

**特点**:

- 支持断点续传

- 自动分块处理大范围

- ETA计算准确

#### handle_gpu_batch_error() 静态方法

```

@staticmethod
handle_gpu_batch_error(mode: str, e: Exception, stats=None) -> bool

```python

统一处理GPU计算批次异常。

**错误分类**:
| 错误类型 | 是否可恢复 | 说明 |
|----------|-----------|------|
| RuntimeError | 是 | OpenCL运行时错误 |
| ValueError | 是 | 数据验证错误 |
| TypeError | 是 | WIF编码错误 |
| OverflowError | 是 | 数据溢出错误 |
| 其他 | 是 | 未知错误(记录堆栈) |

**资源不足检测**:
匹配关键词: `out of resources`, `memory`, `out of memory`, `allocation failed`, `insufficient`, `resource exhausted`

**返回**: bool - 总是返回True(继续执行)

---

### 9.2 GPU vs CPU性能对比

| 指标 | CPU引擎 | GPU引擎 | 提升倍数 |
|------|---------|---------|---------|
| 批次大小 | 1,000 | 65,536 | 65x |
| 单线程速度 | ~1,000/s | N/A | N/A |
| GPU并行速度 | N/A | ~100,000-1,000,000/s | 100-1000x |
| 显存占用 | 低 | 中-高 | N/A |
| 适用场景 | 无GPU环境 | 有独立GPU | N/A |

**GPU引擎适用场景**:

- 拥有独立GPU(NVIDIA/AMD/Intel Arc)

- 需要高性能碰撞检测

- 目标地址数量较大(>1000)

**CPU引擎适用场景**:

- 无GPU或仅核显

- 小批量测试

- 开发调试

---

## 10. GPU监控模块 (gpu_monitor.py)

### 10.1 GPUMonitor类

**文件位置**: `src/monitoring/gpu_monitor.py`

**描述**: GPU性能监控器,提供GPU使用率、显存使用等监控指标。

#### 构造函数

```

GPUMonitor()

```python

**特性**:

- 自动检测PyOpenCL可用性

- 5秒缓存机制避免频繁查询

- 线程安全

#### get_gpu_info() 方法

```

get_gpu_info() -> Dict[str, Any]

```python

获取GPU基本信息。

**返回字段**:
| 字段 | 类型 | 说明 |
|------|------|------|
| `available` | bool | GPU是否可用 |
| `gpu_count` | int | GPU数量 |
| `gpus` | List[Dict] | GPU详细信息列表 |

**GPU详细信息**:
| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | str | GPU名称 |
| `vendor` | str | 厂商 |
| `max_compute_units` | int | 计算单元数 |
| `global_memory_mb` | float | 显存大小(MB) |
| `max_clock_frequency` | int | 最大频率(MHz) |

**示例**:

```

from src.monitoring.gpu_monitor import GPUMonitor

monitor = GPUMonitor()
info = monitor.get_gpu_info()

if info['available']:
    print(f"检测到 {info['gpu_count']} 个GPU")
    for gpu in info['gpus']:
        print(f"  {gpu['name']}: {gpu['global_memory_mb']:.0f}MB")

```markdown

#### get_gpu_metrics() 方法

```

get_gpu_metrics() -> Dict[str, Any]

```python

获取GPU性能指标(使用5秒缓存)。

**返回字段**:
| 字段 | 类型 | 说明 |
|------|------|------|
| `available` | bool | GPU是否可用 |
| `gpu_count` | int | GPU数量 |
| `total_memory_mb` | float | 总显存(MB) |
| `memory_used_mb` | float | 已用显存(MB) |
| `memory_usage_percent` | float | 显存使用率(%) |
| `timestamp` | float | 时间戳 |

**注意**: PyOpenCL不直接提供GPU使用率,需要特定平台API。

#### track_memory_usage() 方法

```

track_memory_usage(allocated_bytes: int) -> None

```python

跟踪GPU显存使用。

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `allocated_bytes` | int | 已分配的字节数 |

**示例**:

```

from src.monitoring.gpu_monitor import get_gpu_monitor

monitor = get_gpu_monitor()

# 跟踪显存分配

allocated = 1024 * 1024 * 512  # 512MB
monitor.track_memory_usage(allocated)

metrics = monitor.get_gpu_metrics()
print(f"显存使用: {metrics['memory_used_mb']:.0f}MB ({metrics['memory_usage_percent']:.1f}%)")

```python
---

## 11. 监控系统API (monitoring_system.py)

### 11.1 MonitoringData类

**文件位置**: `src/monitoring/monitoring_system.py` (第26行)

**描述**: 监控数据结构,包含性能、系统、引擎和错误信息。

**数据结构**:

```

MonitoringData
├── timestamp: float              # 时间戳
├── performance: Dict             # 性能数据
│   ├── speed: float              # 每秒检测速率
│   ├── total_checked: int        # 已检测总数
│   ├── matches_found: int        # 匹配数
│   ├── cpu_usage: float          # CPU使用率(%)
│   ├── memory_usage: float       # 内存使用(MB)
│   └── thread_count: int         # 线程数
├── system: Dict                  # 系统数据
│   ├── os: str                   # 操作系统
│   ├── python_version: str       # Python版本
│   ├── pid: int                  # 进程ID
│   └── uptime: float             # 运行时间(秒)
├── engine: Dict                  # 引擎数据
│   ├── mode: str                 # 运行模式
│   ├── target_count: int         # 目标数量
│   ├── is_running: bool          # 是否运行
│   └── current_position: int     # 当前位置
└── errors: List[Dict]            # 错误记录

```markdown

#### to_dict() 方法

```

to_dict() -> Dict[str, Any]

```python

转换为字典格式。

---

### 11.2 DataCollector类

**文件位置**: `src/monitoring/monitoring_system.py` (第64行)

**描述**: 数据采集器,负责收集性能、系统和引擎数据。

#### 构造函数

```

DataCollector(engine=None)

```python

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `engine` | Optional | 碰撞引擎实例 |

#### collect_performance_data() 方法

```

collect_performance_data() -> Dict[str, Any]

```python

收集性能数据(CPU、内存、线程、速度)。

#### collect_system_data() 方法

```

collect_system_data() -> Dict[str, Any]

```python

收集系统数据(OS、Python版本、PID、运行时间)。

#### collect_engine_data() 方法

```

collect_engine_data() -> Dict[str, Any]

```python

收集引擎数据(模式、目标数、运行状态、位置)。

#### collect_all_data() 方法

```

collect_all_data() -> MonitoringData

```python

收集所有数据,返回MonitoringData对象。

---

### 11.3 DataStorage类

**文件位置**: `src/monitoring/monitoring_system.py` (第144行)

**描述**: 数据存储管理,负责监控数据的持久化。

#### 构造函数

```

DataStorage(storage_dir: str = "monitoring_data")

```python

**数据文件**:

- `current_data.json`: 当前监控数据

- `history_data.json`: 历史数据(最多1000条)

- `error_log.json`: 错误日志(最多500条)

#### 主要方法

| 方法 | 说明 |
|------|------|
| `save_current_data(data)` | 保存当前数据 |
| `save_history_data(data)` | 保存历史数据 |
| `save_error(error)` | 保存错误记录 |
| `get_current_data()` | 获取当前数据 |
| `get_history_data()` | 获取历史数据 |
| `get_error_logs()` | 获取错误日志 |

---

### 11.4 AnomalyDetector类

**文件位置**: `src/monitoring/monitoring_system.py` (第242行)

**描述**: 异常检测器,监控性能指标是否超出正常范围。

**阈值配置**:

```

thresholds = {
    "speed": {"min": 100, "max": 1000000},
    "cpu_usage": {"max": 90},
    "memory_usage": {"max": 1024}  # MB
}

```markdown

#### detect_anomalies() 方法

```

detect_anomalies(current_data: MonitoringData) -> List[Dict[str, Any]]

```python

检测异常,返回异常列表。

**异常类型**:

- `performance`: 性能异常(速度、CPU、内存)

- `engine`: 引擎异常(运行但速度为0)

#### analyze_trends() 方法

```

analyze_trends(history_data: List[Dict[str, Any]]) -> Dict[str, Any]

```python

分析趋势,返回速度、CPU、内存的趋势(increasing/decreasing/stable)。

---

### 11.5 AlertSystem类

**文件位置**: `src/monitoring/monitoring_system.py` (第365行)

**描述**: 告警系统,处理异常并生成告警。

#### generate_alert() 方法

```

generate_alert(anomaly: Dict[str, Any]) -> None

```python

生成告警,级别分为`warning`和`critical`。

#### process_anomalies() 方法

```

process_anomalies(anomalies: List[Dict[str, Any]]) -> None

```python

批量处理异常并生成告警。

---

### 11.6 ReportGenerator类

**文件位置**: `src/monitoring/monitoring_system.py` (第404行)

**描述**: 报告生成器,生成每日监控报告。

#### generate_daily_report() 方法

```

generate_daily_report() -> Dict[str, Any]

```python

生成每日报告,包含:

- 统计摘要(总检查数、匹配数、平均速度)

- 趋势分析

- 错误列表

- 优化建议

---

### 11.7 MonitoringSystem类

**文件位置**: `src/monitoring/monitoring_system.py` (第492行)

**描述**: 监控系统主类,集成所有监控组件。

#### 构造函数

```

MonitoringSystem(engine=None, collection_interval: int = 5)

```python

**参数**:
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `engine` | Optional | None | 碰撞引擎实例 |
| `collection_interval` | int | 5 | 数据采集间隔(秒) |

#### 主要方法

| 方法 | 说明 |
|------|------|
| `start()` | 启动监控系统 |
| `stop()` | 停止监控系统 |
| `is_running()` | 检查是否运行 |
| `get_current_status()` | 获取当前状态 |
| `generate_report()` | 生成报告 |

**监控循环**:

1. 收集数据(每5秒)

2. 保存数据(current + history)

3. 检测异常

4. 生成告警(如有异常)

5. 整点生成日报

**示例**:

```

from src.monitoring.monitoring_system import MonitoringSystem

# 创建监控系统

monitor = MonitoringSystem(engine=my_engine, collection_interval=5)

# 启动监控

monitor.start()

# 获取当前状态

status = monitor.get_current_status()
print(f"当前速度: {status['current_data']['performance']['speed']}")

# 生成报告

report = monitor.generate_report()

# 停止监控

monitor.stop()

```python
---

## 11.8 EnhancedMonitoringSystem类

**文件位置**: `src/monitoring/enhanced_monitoring.py`

**描述**: 增强版监控系统,集成DataLogger提供更全面的数据记录。

### 构造函数

```

EnhancedMonitoringSystem(engine=None, collection_interval: int = 5)

```python

**特性**:

- 继承MonitoringSystem所有功能

- 集成DataLogger数据日志

- 支持性能、系统、引擎数据的详细记录

- 自动保存和报告生成

---

## 12. 数据日志API (data_logger.py)

### 12.1 DataLogger类

**文件位置**: `src/monitoring/data_logger.py`

**描述**: 数据日志记录器,提供全面的性能数据、系统状态、引擎信息和错误记录功能。

#### 构造函数

```

DataLogger(storage_dir: str = "data_logs")

```python

**参数**:
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `storage_dir` | str | "data_logs" | 数据存储目录 |

**数据文件结构**:

```

data_logs/
├── current_data.json      # 当前数据(最新)
├── history_data.json      # 历史数据(最多1000条)
├── error_log.json         # 错误日志(最多500条)
├── performance.log        # 性能日志(CSV格式)
└── report_*.json          # 生成的报告

```markdown

#### record_performance_data() 方法

```

record_performance_data(
    speed: float,
    total_checked: int,
    matches_found: int,
    cpu_usage: float = 0.0,
    memory_usage: float = 0.0,
    thread_count: int = 0
) -> None

```python

记录性能数据。

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `speed` | float | 每秒检测速率 |
| `total_checked` | int | 已检测总数 |
| `matches_found` | int | 匹配数 |
| `cpu_usage` | float | CPU使用率(%) |
| `memory_usage` | float | 内存使用(MB) |
| `thread_count` | int | 线程数 |

**记录内容**:

- 时间戳和日期时间

- 性能指标

- 平均速度(最近100个样本)

- 写入performance.log(CSV格式)

#### record_system_data() 方法

```

record_system_data(
    os_name: str = "",
    python_version: str = "",
    pid: int = 0,
    uptime: float = 0.0
) -> None

```python

记录系统数据。

#### record_engine_data() 方法

```

record_engine_data(
    mode: str = "",
    target_count: int = 0,
    is_running: bool = False,
    current_position: int = 0,
    additional_info: Dict[str, Any] = None
) -> None

```python

记录引擎状态数据。

#### record_error() 方法

```

record_error(
    error_type: str,
    message: str,
    exception: Exception = None,
    context: Dict[str, Any] = None
) -> None

```python

记录错误信息。

**错误记录字段**:

- timestamp, datetime

- type: 错误类型

- message: 错误消息

- exception_type, exception_message

- context: 上下文信息

#### save_current_data() 方法

```

save_current_data() -> None

```python

保存当前数据到current_data.json。

#### save_history_data() 方法

```

save_history_data() -> None

```python

保存历史数据到history_data.json。

#### get_current_data() 方法

```

get_current_data() -> Dict[str, Any]

```python

获取当前数据。

#### get_statistics() 方法

```

get_statistics() -> Dict[str, Any]

```python

获取统计信息。

**返回字段**:
| 字段 | 类型 | 说明 |
|------|------|------|
| `total_checks` | int | 总检查数 |
| `matches_found` | int | 匹配数 |
| `avg_speed` | float | 平均速度 |
| `max_speed` | float | 最大速度 |
| `min_speed` | float | 最小速度 |
| `uptime` | float | 运行时间(秒) |
| `speed_std_dev` | float | 速度标准差 |

#### generate_report() 方法

```

generate_report(report_type: str = "daily") -> Dict[str, Any]

```python

生成报告。

**报告类型**:

- `daily`: 每日报告

- `weekly`: 每周报告

- `monthly`: 每月报告

**报告内容**:

- 统计摘要(总检查数、匹配数、速度统计)

- 趋势分析(速度、CPU、内存)

- 优化建议

**示例**:

```

from src.monitoring.data_logger import DataLogger

logger = DataLogger(storage_dir="data_logs")

# 记录性能数据

logger.record_performance_data(
    speed=50000.0,
    total_checked=1000000,
    matches_found=0,
    cpu_usage=75.5,
    memory_usage=512.0,
    thread_count=8
)

# 记录引擎数据

logger.record_engine_data(
    mode="random_search",
    target_count=100,
    is_running=True
)

# 获取统计

stats = logger.get_statistics()
print(f"平均速度: {stats['avg_speed']:.2f}/s")

# 生成报告

report = logger.generate_report("daily")

# 保存数据

logger.save_current_data()
logger.save_history_data()

```markdown

## cleanup_old_data() 方法

```

cleanup_old_data(max_age_days: int = 30) -> None

```python

清理旧数据。

**参数**:
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `max_age_days` | int | 30 | 数据最大保存天数 |

---

### 12.2 数据文件格式

#### current_data.json格式

```

{
  "saved_at": "2026-04-20T10:30:00",
  "uptime": 3600.5,
  "performance": {
    "timestamp": 1713598200.0,
    "datetime": "2026-04-20T10:30:00",
    "speed": 50000.0,
    "total_checked": 1000000,
    "matches_found": 0,
    "cpu_usage": 75.5,
    "memory_usage": 512.0,
    "thread_count": 8,
    "avg_speed": 48500.0
  },
  "system": {
    "timestamp": 1713598200.0,
    "os": "nt",
    "python_version": "3.10.0",
    "pid": 12345,
    "uptime": 3600.5
  },
  "engine": {
    "timestamp": 1713598200.0,
    "mode": "random_search",
    "target_count": 100,
    "is_running": true,
    "current_position": 0
  }
}

```markdown

#### history_data.json格式

```

[
  {
    "timestamp": 1713598200.0,
    "datetime": "2026-04-20T10:30:00",
    "speed": 50000.0,
    "total_checked": 1000000,
    "matches_found": 0,
    "cpu_usage": 75.5,
    "memory_usage": 512.0,
    "thread_count": 8,
    "avg_speed": 48500.0
  },
  ...
]

```markdown

#### error_log.json格式

```

[
  {
    "timestamp": 1713598200.0,
    "datetime": "2026-04-20T10:30:00",
    "type": "gpu_error",
    "message": "GPU计算失败",
    "exception_type": "RuntimeError",
    "exception_message": "Out of resources",
    "context": {
      "batch_size": 65536
    }
  },
  ...
]

```markdown

#### performance.log格式

```

# 性能日志 - 比特币密钥碰撞检测

# 创建时间: 2026-04-20T10:00:00

# 格式: timestamp,speed,total_checked,matches,cpu_usage,memory_usage,threads

1713598200.0,50000.0,1000000,0,75.5,512.0,8
1713598205.0,51000.0,1255000,0,76.0,515.0,8
...

```python
---

## 13. 统计模块API (collision_stats.py)

### 13.1 CollisionStats类

**文件位置**: `src/collision/collision_stats.py`

**描述**: 碰撞统计数据管理,线程安全的统计对象。

**安全说明**:

- 匹配的私钥信息不会存储在统计对象中

- 仅保存地址和时间戳用于统计展示

- 私钥通过on_match回调直接传递给调用者

#### 构造函数

```

CollisionStats()

```python

**属性**:
| 属性 | 类型 | 说明 |
|------|------|------|
| `total_checked` | int | 已检测总数 |
| `speed` | float | 每秒检测速率 |
| `elapsed` | float | 已运行时间(秒) |
| `start_time` | float | 开始时间戳 |
| `matches` | List[Dict] | 匹配结果列表(仅地址,无私钥) |
| `total_range` | int | 总范围(range模式) |
| `eta_seconds` | float | 预计剩余秒数(-1表示无法估算) |
| `gpu_errors` | int | GPU错误计数 |
| `worker_errors` | int | 工作线程错误计数 |
| `wif_encode_errors` | int | WIF编码错误计数 |
| `resource_errors` | int | 资源不足错误计数 |

**match记录格式**:

```

{
    "address": str,           # 匹配的地址
    "timestamp": float,       # 匹配时间
    "match_index": int,       # 匹配序号
    "private_key_hash": str   # 私钥SHA256哈希(前16字符)
}

```markdown

#### update() 方法

```

update(checked_count: int, total_range: int = 0) -> None

```python

更新统计数据。

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `checked_count` | int | 已检查数量 |
| `total_range` | int | 总范围(仅range模式传入) |

**ETA计算逻辑**:

```

if total_range > 0 and speed > 0:
    remaining = total_range - total_checked
    eta_seconds = remaining / speed
else:
    eta_seconds = -1.0  # 无法估算

```markdown

#### add_match() 方法

```

add_match(private_key: bytes, address: str) -> None

```python

记录匹配结果(不存储私钥)。

**安全处理**:

1. 计算私钥SHA256哈希(前16字符)

2. 仅保存地址、时间戳、匹配序号、私钥哈希

3. 不保存实际私钥

#### snapshot() 方法

```

snapshot() -> 'CollisionStats'

```python

返回线程安全的统计快照。

**特性**:

- 深拷贝matches列表

- 复制所有统计属性

- 包含异常统计指标

- 用于回调和UI显示

#### format_elapsed() 方法

```

format_elapsed() -> str

```yaml

格式化运行时间为HH:MM:SS格式。

#### format_speed() 方法

```

format_speed() -> str

```python

格式化速度(带单位): `/s`, `K/s`, `M/s`。

#### get_speed() 方法

```

get_speed() -> float

```python

获取当前碰撞速度(线程安全)。

#### record_gpu_error() 方法

```

record_gpu_error(is_resource_error: bool = False) -> None

```python

记录GPU错误。

#### record_worker_error() 方法

```

record_worker_error() -> None

```python

记录工作线程错误。

#### record_wif_encode_error() 方法

```

record_wif_encode_error() -> None

```python

记录WIF编码错误。

#### get_error_rates() 方法

```

get_error_rates() -> Dict[str, float]

```python

获取各类错误率。

**返回**:

```

{
    "total_error_rate": float,       # (GPU错误+Worker错误)/总检查数
    "gpu_error_rate": float,         # GPU错误/总检查数
    "worker_error_rate": float,      # Worker错误/总检查数
    "wif_encode_error_rate": float,  # WIF错误/总检查数
    "resource_error_rate": float     # 资源错误/总检查数
}

```markdown

#### is_healthy() 方法

```

is_healthy(error_rate_threshold: float = 0.01) -> bool

```python

检查系统健康状态。

**参数**:
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `error_rate_threshold` | float | 0.01 | 错误率阈值(默认1%) |

**返回**: bool - 所有错误率都低于阈值返回True

#### error_summary() 方法

```

error_summary() -> str

```python

生成错误统计摘要。

**输出示例**:

```

错误统计: GPU=5, Worker=2, WIF=1, Resource=3, 总计=7

```python

**计算说明**:

- 总计 = GPU错误 + Worker错误(独立错误事件数)

- Resource错误是GPU错误的子集,不重复计数

- WIF编码错误可能交叉于GPU/Worker,单独列出

**使用示例**:

```

from src.collision.collision_stats import CollisionStats

stats = CollisionStats()
stats.start_time = time.time()

# 更新统计

stats.update(checked_count=1000000, total_range=10000000)

# 添加匹配

stats.add_match(private_key=b'...', address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa")

# 记录错误

stats.record_gpu_error(is_resource_error=True)
stats.record_worker_error()

# 获取信息

print(f"速度: {stats.format_speed()}")
print(f"时间: {stats.format_elapsed()}")
print(f"ETA: {stats.eta_seconds:.0f}秒")
print(stats.error_summary())

# 检查健康状态

if stats.is_healthy(error_rate_threshold=0.01):
    print("系统健康")
else:
    print("错误率过高")

# 获取快照(用于回调)

snapshot = stats.snapshot()

```python
---

## 14. 使用示例汇总

### 14.1 P2PKHSimulator类

**文件位置**: `p2pkh_simulator.py`

**描述**: P2PKH地址生成模拟器主类，提供交互式命令行界面。

#### 构造函数

```

P2PKHSimulator()

```python

初始化模拟器，创建地址生成器和彩色输出器实例。

#### derive_address()

```

derive_address(private_key: bytes) -> tuple

```python

执行完整的地址推导流程。

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `private_key` | bytes | 32字节私钥 |

**返回**: tuple - (address, compressed_pk, uncompressed_pk) 元组

#### derive_address_detailed()

```

derive_address_detailed(private_key: bytes) -> tuple

```python

详细推导地址（带彩色输出）。

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `private_key` | bytes | 32字节私钥 |

**返回**: tuple - (address, compressed_pk, uncompressed_pk) 元组

#### run_test_vector()

```

run_test_vector() -> bool

```python

运行测试向量验证。

**返回**: bool - 测试通过返回True，否则返回False

#### parse_private_key_input()

```

parse_private_key_input(user_input: str) -> bytes

```python

解析用户输入的私钥。

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `user_input` | str | 用户输入字符串 |

**返回**: bytes - 32字节私钥

**异常**:
| 异常 | 说明 |
|------|------|
| `ValueError` | 当输入格式无效时 |

**支持的格式**:

- Hex: 64位十六进制字符串

- WIF: WIF格式的私钥字符串

- Decimal: 十进制整数

#### batch_generate()

```

batch_generate(count: int, export_csv: bool = False)

```python

批量生成地址。

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `count` | int | 生成数量 |
| `export_csv` | bool | 是否导出为CSV格式 |

#### run_interactive()

```

run_interactive()

```python

运行交互式菜单。

**说明**: 主程序循环，显示菜单并处理用户选择。

---

## 15. GUI模块 (p2pkh_gui.py)

### 15.1 P2PKHGUI类

**文件位置**: `p2pkh_gui.py`

**描述**: P2PKH地址生成器GUI主类，提供完整的比特币地址生成图形界面。

#### 构造函数

```

P2PKHGUI(root: tk.Tk)

```python

初始化GUI。

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `root` | tk.Tk | Tkinter根窗口 |

**示例**:

```

import tkinter as tk
from p2pkh_gui import P2PKHGUI

root = tk.Tk()
app = P2PKHGUI(root)
root.mainloop()

```python
---

## 16. 异常类 (exceptions.py)

### 16.1 KeyGenerationError

**文件位置**: `src/utils/exceptions.py`

**描述**: 私钥生成错误异常。

**属性**:
| 属性 | 类型 | 说明 |
|------|------|------|
| `message` | str | 错误消息 |
| `error_code` | int | 错误代码 |
| `context` | dict | 错误上下文 |

---

## 17. 使用示例汇总

### 17.1 生成比特币地址

```

from src.core.address_generator import P2PKHAddressGenerator

# 创建生成器

generator = P2PKHAddressGenerator()

# 生成随机地址

address, compressed_pk, uncompressed_pk = generator.generate_address()

print(f"比特币地址: {address}")
print(f"压缩公钥: {compressed_pk.hex()}")

```markdown

## 17.2 从WIF导入私钥

```

from src.core.wif import WIF
from src.core.address_generator import P2PKHAddressGenerator

# 解码WIF

wif = "KwDiBf89QgGbjEhKnhXJuH7LrciVrZi3qYjgd9M7rFU73sVHnoWn"
private_key, is_compressed = WIF.decode(wif)

# 生成地址

generator = P2PKHAddressGenerator()
address, _, _ = generator.generate_address(private_key)

print(f"地址: {address}")

```markdown

## 17.3 验证比特币地址

```

from src.core.base58 import Base58

address = "16UwLL9Risc3QfPqBUvKofHmBQ7wMtjvM"

try:
    version, payload = Base58.check_decode(address)
    print(f"地址有效")
    print(f"版本字节: 0x{version:02x}")
    print(f"Hash160: {payload.hex()}")
except ValueError as e:
    print(f"地址无效: {e}")

```markdown

### 17.4 运行碰撞检测

```

from src.collision.key_collision_engine import KeyCollisionEngine
import threading

# 目标地址

targets = {
    "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
    "12cbQLTFMXRnSzktFkuoG3eHoMeFtpTu3S"
}

# 回调函数

def on_match(private_key, address, wif):
    print(f"*** 匹配成功! ***")
    print(f"地址: {address}")
    print(f"WIF: {wif}")

def on_progress(stats):
    print(f"已检查: {stats.total_checked}, 速度: {stats.rate_per_second:.2f}/s")

# 创建引擎

engine = KeyCollisionEngine(
    targets=targets,
    on_match=on_match,
    on_progress=on_progress,
    checkpoint_enabled=True,
    dedup_enabled=True,
    max_workers=4
)

# 运行碰撞检测

try:
    engine.random_search()
except KeyboardInterrupt:
    engine.stop()

```python
---

## 18. 安全密钥管理器 (secure_key_manager.py) - 新增

### 18.1 SecureKeyManager类

**文件位置**: `src/core/secure_key_manager.py`

**描述**: 生产级私钥安全管理器，提供私钥的安全存储、使用和自动清零功能。

#### 安全特性

- **内存锁定**：使用mlock()防止私钥被交换到磁盘（Linux/macOS）

- **安全清零**：使用密码学库的安全清零函数，防止编译器优化

- **自动管理**：上下文管理器确保私钥使用后自动清零

- **多后端支持**：cryptography > PyNaCl > ctypes回退

- **清零统计**：类级别监控清零成功率

#### 构造函数

```

SecureKeyManager(lock_memory: bool = True)

```python

**参数**:
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `lock_memory` | bool | True | 是否锁定内存防止交换 |

**注意**:

- Windows不支持mlock()，会自动跳过

- 锁定内存需要足够的权限

#### generate_key()

```

generate_key() -> None

```python

生成加密安全的随机私钥。

**实现**:

- 使用`secrets.token_bytes(32)`生成32字节私钥

- 存储在bytearray中（可变，支持安全清零）

#### get_key()

```

get_key() -> bytearray

```python

获取当前私钥。

**返回**: bytearray - 32字节私钥

**异常**:
| 异常 | 说明 |
|------|------|
| `SecureMemoryError` | 当私钥未生成或已清零时 |

#### clear()

```

clear() -> None

```python

安全清零私钥。

**清零策略**:

1. 使用后端安全清零函数（cryptography/PyNaCl/ctypes）

2. 多次覆盖（3次：0x00, 0xFF, 0x00）

3. 设置标志位防止重复使用

**统计**:

- 更新类级别统计计数器

- 记录清零成功/失败次数

#### get_clear_stats() 静态方法

```

@staticmethod
get_clear_stats() -> Dict[str, int]

```python

获取清零统计信息。

**返回**:

```

{
    "total_clears": int,       # 总清零次数
    "successful_clears": int,  # 成功清零次数
    "failed_clears": int,      # 失败清零次数
    "success_rate": float      # 成功率（%）
}

```markdown

#### 上下文管理器

```

with SecureKeyManager() as key_mgr:
    key_mgr.generate_key()
    private_key = key_mgr.get_key()

    # 使用私钥...

    address = generate_address(private_key)

# 退出上下文时自动安全清零

```python

**使用示例**:

```

from src.core.secure_key_manager import SecureKeyManager

# 方式1: 上下文管理器（推荐）

with SecureKeyManager() as key_mgr:
    key_mgr.generate_key()
    private_key = key_mgr.get_key()

    # 使用私钥生成地址

    address = generator.public_key_to_address(
        generator.private_key_to_public_key(private_key)
    )
    print(f"地址: {address}")

# 私钥已自动清零

# 方式2: 手动管理

key_mgr = SecureKeyManager()
try:
    key_mgr.generate_key()
    private_key = key_mgr.get_key()

    # 使用私钥...

finally:
    key_mgr.clear()  # 确保清零

# 查看清零统计

stats = SecureKeyManager.get_clear_stats()
print(f"清零成功率: {stats['success_rate']:.2f}%")

```python

**后端优先级**:

| 后端 | 清零方法 | 内存锁定 | 推荐度 |
|------|---------|---------|--------|
| cryptography | cryptography.hazmat.primitives.zeroize | 支持 | ⭐⭐⭐⭐⭐ |
| PyNaCl | nacl.secret | 支持 | ⭐⭐⭐⭐ |
| ctypes | ctypes.memset | 支持 | ⭐⭐⭐ |

---

## 19. 碰撞引擎完整方法 - 补充

### 19.1 KeyCollisionEngine完整方法

**文件位置**: `src/collision/key_collision_engine.py`

#### range_scan() 方法

```

range_scan(start: int, end: int) -> None

```python

范围扫描模式 - 在指定私钥范围内顺序扫描。

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `start` | int | 起始私钥（整数） |
| `end` | int | 结束私钥（整数） |

**特点**:

- 顺序扫描，适合已知私钥范围

- 支持断点续传

- ETA计算准确（总范围已知）

- 实时计数器减少锁竞争

**使用示例**:

```

from src.collision.key_collision_engine import KeyCollisionEngine

targets = {"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"}
engine = KeyCollisionEngine(
    targets=targets,
    checkpoint_enabled=True,
    dedup_enabled=False  # 范围扫描不需要去重
)

# 扫描私钥范围 1 到 1000000

engine.range_scan(start=1, end=1000000)

```markdown

## brute_force() 方法

```

brute_force(start: int = 1, max_keys: Optional[int] = None) -> None

```python

暴力穷举模式 - 从指定位置开始顺序穷举。

**参数**:
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `start` | int | 1 | 起始私钥（整数） |
| `max_keys` | Optional[int] | None | 最大检查数量，None表示无限穷举 |

**特点**:

- 无限穷举，直到手动停止

- 原子位置计数器（多线程安全）

- 支持断点续传

**使用示例**:

```

from src.collision.key_collision_engine import KeyCollisionEngine
import threading

targets = {"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"}
engine = KeyCollisionEngine(targets=targets)

# 从私钥1开始穷举

thread = threading.Thread(target=engine.brute_force, args=(1,))
thread.start()

# 运行一段时间后停止

import time
time.sleep(60)
engine.stop()
thread.join()

```

## resume_from_checkpoint() 方法

```

resume_from_checkpoint() -> bool

```

从断点恢复碰撞检测。

**返回**: bool - 成功恢复返回True，无断点文件返回False

**恢复内容**:

- 统计计数器（total_checked, matches）

- 目标地址集合

- 运行模式（random/range/brute）

- range模式的当前位置

**使用示例**:

```

from src.collision.key_collision_engine import KeyCollisionEngine

targets = {"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"}
engine = KeyCollisionEngine(
    targets=targets,
    checkpoint_enabled=True
)

# 尝试从断点恢复

if engine.resume_from_checkpoint():
    print("从断点恢复成功")
    engine.random_search()  # 继续之前的模式
else:
    print("无断点文件，从头开始")
    engine.random_search()

```
---

## 22. 版本历史

| 版本 | 日期 | 说明 |
|------|------|------|
| v4.2.2 | 2026-05-15 | mod_inverse Binary GCD 2^256溢出修复，生产验收测试全通过 |
| v4.2.1 | 2026-04-20 | 补充SecureKeyManager API、碰撞引擎完整方法 |
| v4.2.1 | 2026-04 | 初始版本，完整API文档 |
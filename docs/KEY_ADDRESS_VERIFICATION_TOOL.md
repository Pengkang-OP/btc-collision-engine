# 比特币密钥派生及地址生成验证工具

**版本**: v4.5.1


## 概述

本工具 (`tools/btc_key_address_verifier.py`) 用于验证比特币密钥派生及地址生成流程的正确性。

### 功能特性

1. **私钥到公钥的数学验证**
   - secp256k1 椭圆曲线标量乘法验证
   - 公钥点在曲线上的验证
   - 压缩/非压缩公钥格式生成

2. **公钥到地址格式转换验证**
   - P2PKH (Legacy) - 以 '1' 开头
   - P2SH (Nested SegWit) - 以 '3' 开头
   - Bech32 (Native SegWit v0) - 以 'bc1' 开头
   - Bech32m (Taproot) - 以 'bc1p' 开头

3. **地址匹配验证**
   - 生成地址与目标地址逐一对比
   - 明确标识匹配/不匹配状态
   - 标出不匹配的具体环节

## 使用方法

### 命令行使用

```bash
# 设置 Python 路径
$env:PYTHONPATH = ".;$env:PYTHONPATH"

# 运行测试向量验证
python tools/btc_key_address_verifier.py --test-vector

# 验证自定义私钥
python tools/btc_key_address_verifier.py --private-key "0000000000000000000000000000000000000000000000000000000000000001"

# 验证私钥并对比目标地址
python tools/btc_key_address_verifier.py -k "0000000000000000000000000000000000000000000000000000000000000001" -t "1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH" "3LRW7jeCvQCRdPF8S3yUCfRAx4eqXFmdcr" "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"

# 生成随机私钥并验证
python tools/btc_key_address_verifier.py --random

# JSON 格式输出
python tools/btc_key_address_verifier.py --random --json

# 静默模式
python tools/btc_key_address_verifier.py --private-key "..." --quiet
```

### Python API 使用

```python
import sys
sys.path.insert(0, '.')

from tools.btc_key_address_verifier import BTCKeyAddressVerifier, AddressFormat

# 初始化验证器
verifier = BTCKeyAddressVerifier(verbose=True)

# 方式1: 使用已知私钥验证
private_key = "0000000000000000000000000000000000000000000000000000000000000001"
targets = {
    "p2pkh": "1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH",
    "p2sh": "3LRW7jeCvQCRdPF8S3yUCfRAx4eqXFmdcr",
    "bech32": "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4",
}
report = verifier.verify_private_key(private_key, targets)

# 访问结果
print(f"压缩公钥: {report.public_key_compressed}")
print(f"P2PKH地址: {report.address_results[AddressFormat.P2PKH].generated_address}")
print(f"匹配状态: {report.address_results[AddressFormat.P2PKH].is_match}")

# 方式2: 批量验证
results = verifier.batch_verify_addresses(private_key, targets)
for fmt, result in results["verification_results"].items():
    print(f"{fmt}: {result['generated']} - {'OK' if result['match'] else 'FAIL'}")

# 方式3: 随机私钥验证
report = verifier.generate_random_verification()
```

## 输出格式

### 控制台输出

```python
======================================================================
比特币密钥派生及地址生成验证
======================================================================

[阶段1] 私钥 → 公钥 验证
----------------------------------------
执行标量乘法: Q = 1 * G

[阶段2] 公钥 → 各格式地址 验证
----------------------------------------
生成 P2PKH (Legacy) 地址...
生成 P2SH (Nested SegWit) 地址...
生成 Bech32 (Native SegWit) 地址...
生成 Bech32m (Taproot) 地址...

[阶段3] 验证结果汇总
----------------------------------------
P2PKH: 1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH [OK] MATCH
P2SH: 3LRW7jeCvQCRdPF8S3yUCfRAx4eqXFmdcr [OK] MATCH
Bech32: bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4 [OK] MATCH
Bech32m: bc1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vqzk5jjw (format valid)
```

### JSON 输出

```json
{
  "private_key": {
    "hex": "0000000000000000000000000000000000000000000000000000000000000001",
    "int": "1"
  },
  "public_key": {
    "compressed": "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798",
    "uncompressed": "0479be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8",
    "x": "79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798",
    "y": "483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8",
    "on_curve": true
  },
  "addresses": {
    "P2PKH": {
      "format": "P2PKH",
      "generated": "1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH",
      "target": "1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH",
      "match": "[OK]",
      "status": "MATCH"
    }
  },
  "overall_match": true
}
```

## 验证流程

### 1. 私钥到公钥

```text
私钥 (32 bytes)
    │
    ▼ [椭圆曲线标量乘法 Q = k * G]
公钥 (33/65 bytes)
    │
    ▼ [验证点在 secp256k1 曲线上]
验证结果
```

### 2. P2PKH 地址

```text
公钥
    │
    ▼ [SHA256]
SHA256 Hash
    │
    ▼ [RIPEMD160]
Hash160 (20 bytes)
    │
    ▼ [添加版本字节 0x00]
版本 || Hash160
    │
    ▼ [Base58Check 编码]
P2PKH 地址 (以 '1' 开头)
```

### 3. P2SH 地址

```text
压缩公钥
    │
    ▼ [HASH160]
Pub Key Hash
    │
    ▼ [创建 RedeemScript]
OP_DUP OP_HASH160 <20 bytes> OP_EQUALVERIFY OP_CHECKSIG
    │
    ▼ [HASH160]
Script Hash
    │
    ▼ [添加版本字节 0x05]
版本 || Script Hash
    │
    ▼ [Base58Check 编码]
P2SH 地址 (以 '3' 开头)
```

### 4. Bech32 地址

```text
压缩公钥
    │
    ▼ [HASH160]
Pub Key Hash (20 bytes)
    │
    ▼ [创建 Witness Program]
0x00 || 0x14 || Pub Key Hash
    │
    ▼ [Bech32 编码]
Bech32 地址 (以 'bc1' 开头)
```

### 5. Bech32m (Taproot) 地址

```text
压缩公钥 (移除前缀，仅保留 x 坐标)
    │
    ▼ [x-only 公钥]
X Only Public Key (32 bytes)
    │
    ▼ [创建 Witness Program]
0x01 || 0x20 || X Only Public Key
    │
    ▼ [Bech32m 编码]
Bech32m 地址 (以 'bc1p' 开头)
```

## 测试向量

工具内置了 Bitcoin wiki 标准测试向量：

| 私钥 (十六进制) | 压缩公钥 | P2PKH 地址 |
|----------------|---------|------------|
| 0000000000000000000000000000000000000000000000000000000000000001 | 0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798 | 1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH |

## 错误处理

### 地址不匹配

当生成地址与目标地址不匹配时，工具会：
1. 显示 `[FAIL] MISMATCH`
2. 标出不一致环节
3. 显示生成的地址和目标地址

```text
P2PKH: 1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH [FAIL] MISMATCH
```

### 格式验证失败

当地址格式不正确时，工具会：
1. 显示格式错误详情
2. 列出验证步骤中的错误

## 示例脚本

参考 `examples/demo_btc_key_verification.py` 获取完整使用示例：

```bash
python examples/demo_btc_key_verification.py
```

## 依赖项

- Python 3.8+
- src.core.secp256k1 (secp256k1 椭圆曲线实现)
- src.core.hash_utils (Hash160 实现)
- src.core.base58 (Base58 编解码)
- bech32 (可选，用于 Bech32/Bech32m 编解码)

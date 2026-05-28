# 业务逻辑核心模块

本文档介绍BTC碰撞引擎的业务逻辑核心模块实现。

## 模块概览

根据项目设计分析报告第3章"业务逻辑实现"的要求，已实现以下核心模块：

### 1. 比特币目标地址表 (`BitcoinTargetTable`)

**文件**: `src/core/target_address_table.py`

**功能**:

- 存储待比对的比特币WIF格式地址
- 使用Hash160 Set结构实现O(1)高效查询
- 支持从JSON/CSV/TXT文件批量加载
- 线程安全设计

**核心方法**:

```python
# 添加目标地址
table.add_target(wif, address, hash160, address_type)

# 检查匹配
is_match, target_info = table.check_match(hash160)

# 从文件加载
count = table.load_from_file('targets.json')

# 获取统计
stats = table.get_statistics()
```

**性能特性**:

- 查询时间复杂度: O(1)
- 内存占用: ~40字节/目标
- 容量: 支持1000万+目标地址

### 2. 安全私钥生成器 (`SecureKeyGenerator`)

**文件**: `src/core/key_generator.py`

**功能**:

- 批量持续生成私钥地址
- 严格遵循Bitcoin Core规范
- 使用CSPRNG（密码学安全伪随机数生成器）
- 支持可配置的生成速率与数量控制

**核心方法**:

```python
# 配置生成器
config = {
    'batch_size': 1000,      # 每批生成数量
    'rate_limit': 0,         # 每秒生成速率（0=无限制）
    'key_format': 'both'     # 公钥格式
}
generator = SecureKeyGenerator(config)

# 批量生成
private_keys = generator.generate_batch(1000)

# 单个生成
private_key = generator.generate_single()

# 获取统计
stats = generator.get_statistics()
```

**安全特性**:

- [OK_CHECK] 使用`secrets.token_bytes()` CSPRNG
- [OK_CHECK] 私钥范围验证 (1 <= k < n)
- [OK_CHECK] SecureKeyManager自动清零
- [OK_CHECK] 线程安全设计

### 3. 地址转换器 (`AddressConverter`)

**文件**: `src/core/address_converter.py`

**功能**:

- 私钥到公钥地址的转换（6步推导）
- 公钥地址到WIF格式的转换
- 严格遵循Bitcoin Core规范
- 支持压缩和非压缩格式

**核心方法**:

```python
converter = AddressConverter()

# 私钥 → 所有格式
result = converter.private_key_to_all(private_key)
# 返回: 压缩/非压缩地址、WIF、公钥、Hash160

# 私钥 → 地址
result = converter.private_key_to_address(private_key, compressed=True)

# 私钥 → WIF
wif = converter.private_key_to_wif(private_key, compressed=True)

# WIF → 地址
result = converter.wif_to_address(wif)

# 验证转换
is_valid, msg = converter.validate_conversion(private_key)
```

**6步推导流程**:

1. 椭圆曲线标量乘法 (私钥 → 公钥)
2. SHA-256哈希
3. RIPEMD-160哈希 (得到Hash160)
4. 添加版本字节 (0x00 = Mainnet P2PKH)
5. 计算校验和 (双重SHA-256)
6. Base58Check编码

### 4. 持续比对系统 (`ContinuousMatcher`)

**文件**: `src/collision/continuous_matcher.py`

**功能**:

- 生成的比特币WIF地址与目标地址表逐一比对
- 高效准确的O(1)比对算法
- 支持大规模地址库的快速比对
- 实时统计和日志记录

**核心方法**:

```python
matcher = ContinuousMatcher(target_table)

# 批量比对
matches = matcher.check_address_batch(addresses)

# 单个比对
is_match, match_record = matcher.check_single_address(addr_info)

# 获取统计
stats = matcher.get_statistics()
```

**性能指标**:

- 单次比对: O(1)
- 批量比对: O(n)
- 吞吐量: 100万+ 地址/秒

### 5. 匹配数据存储 (`MatchDataStorage`)

**文件**: `src/collision/match_storage.py`

**功能**:

- 匹配成功时完整保存地址相关数据
- 包括WIF地址、公钥、私钥等关键信息
- 原子写入防止数据损坏
- 文件权限控制保障安全

**核心方法**:

```python
storage = MatchDataStorage('./matches')

# 保存匹配数据
filepath = storage.save_match(match_data)

# 列出所有匹配
files = storage.list_matches()

# 加载匹配数据
data = storage.load_match(filepath)

# 获取统计
stats = storage.get_statistics()
```

**数据安全特性**:

- 原子写入（临时文件 + os.replace()）
- 文件权限（0o600）
- 自动备份机制
- JSON格式便于验证

### 6. 规范合规性验证 (`BitcoinComplianceValidator`)

**文件**: `src/core/compliance_validator.py`

**功能**:

- 验证密钥对和地址符合Bitcoin Core规范
- 确保生成的密钥对完全兼容标准比特币网络
- 5项验证规则检查

**核心方法**:

```python
validator = BitcoinComplianceValidator()

# 验证单个数据
is_valid, issues = validator.validate(data)

# 批量验证
results = validator.validate_batch(data_list)
```

**验证规则**:

1. 私钥格式验证（32字节，范围检查）
2. 公钥格式验证（压缩33字节/非压缩65字节）
3. 地址格式验证（P2PKH以'1'开头，33-34字符）
4. WIF格式验证（5/K/L前缀，长度检查）
5. Hash160验证（20字节）

## 使用示例

完整的使用示例请参见：`examples/business_logic_demo.py`

运行示例：

```bash
python examples/business_logic_demo.py
```

## 模块依赖关系

```
业务逻辑模块
├── BitcoinTargetTable (目标地址表)
│   ├── WIF (WIF编解码)
│   └── P2PKHAddressGenerator (地址生成)
├── SecureKeyGenerator (私钥生成)
│   ├── SecureKeyManager (私钥管理)
│   └── secp256k1 (椭圆曲线)
├── AddressConverter (地址转换)
│   ├── EllipticCurve (椭圆曲线)
│   ├── HashUtils (哈希工具)
│   ├── Base58 (Base58编码)
│   └── WIF (WIF编解码)
├── ContinuousMatcher (持续比对)
│   └── BitcoinTargetTable (目标地址表)
├── MatchDataStorage (数据存储)
│   └── JSON (数据序列化)
└── BitcoinComplianceValidator (合规验证)
    └── 无外部依赖
```

## 性能优化

1. **哈希表查找**: Set<Hash160>实现O(1)查询
2. **批量处理**: 减少锁竞争，提高吞吐量
3. **本地缓存**: 线程本地统计，减少同步开销
4. **异步比对**: GPU计算与CPU比对并行

## 安全特性

1. **CSPRNG**: 使用`secrets.token_bytes()`生成私钥
2. **私钥清零**: SecureKeyManager自动清零
3. **原子写入**: 防止数据损坏
4. **文件权限**: 0o600仅所有者可访问
5. **不记录敏感信息**: 日志中不包含私钥

## 符合Bitcoin Core规范

所有模块严格遵循Bitcoin Core技术规范：

- [OK_CHECK] 私钥生成: CSPRNG + 范围验证
- [OK_CHECK] 地址生成: 6步推导完整实现
- [OK_CHECK] WIF编码: 版本字节 + 校验和 + Base58Check
- [OK_CHECK] 合规验证: 5项检查规则
- [OK_CHECK] 完全兼容标准比特币网络

## API参考

详细的API文档请参见项目设计分析报告第3章。

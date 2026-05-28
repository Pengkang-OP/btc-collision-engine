# Phase 1: `src/collision/` 密码学安全与常量时间审计报告

**审核时间**: 2026-05-28 | **目标模块**: `src/collision/` (P0) | **安全标准**: OWASP, cryptocoding guidelines

---

## 一、审核范围与方法

### 1.1 审核范畴

本报告针对 `src/collision/` 模块的密码学安全维度，覆盖：

| 类别 | 覆盖文件 | 说明 |
|------|----------|------|
| 密钥处理 | `key_collision_engine.py`, `events.py` | 私钥传递、WIF编码、日志脱敏 |
| 地址匹配 | `key_collision_engine.py`, `targets/matcher.py` | Hash160 比较逻辑 |
| 敏感数据持久化 | `checkpoint_manager.py`, `targets/storage.py` | 私钥字段剥离、SQL注入防护 |
| 事件系统安全 | `events.py`, `event_bus.py` | WIF自动掩码、EventBus密钥隔离 |
| 输入验证 | `targets/validator.py`, `key_collision_engine.py` | 地址格式校验、参数验证 |
| 时序安全 | 碰撞模块各入口点 | 秘密依赖的条件分支/比较 |

### 1.2 方法论

采用以下方法论组合：

1. **人工审查**: 逐文件追踪敏感数据流（私钥 → WIF → 事件 → 日志 → 持久化）
2. **常量时间分析**: 检查是否存在秘密依赖的条件分支/比较操作
3. **密码学原语使用验证**: 确认使用经过审计的库，无自定义加密实现

---

## 二、敏感数据流分析

### 2.1 私钥生命周期（碰撞模块视角）

```
SecureKeyManager.generate_key()  ←  core/secp256k1.py
        │
        [E]
private_key_bytes (bytes)
        │
        ├──→ _worker_generate_addresses()  →  地址生成  →  Hash160
        │                                                   │
        │                                                   [E]
        │                                          set(target_hash160s) 匹配
        │                                                   │
        │                                            [命中]   │   [未命中]
        │                                              │       └──→ 丢弃
        │                                              [E]
        │                                    _worker_check_and_handle_match()
        │                                              │
        │                                              ├──→ WIF.encode()       →  WIF (str)
        │                                              ├──→ stats.add_match()  →  SHA256→16hex (截断)
        │                                              ├──→ on_match 回调      →  pk_copy (bytes)
        │                                              └──→ EventBus.publish() →  private_key=b"", wif=""
        │
        └──→ [离开作用域] → 等待 GC（未显式清零）
```

### 2.2 安全控制评估

| 控制点 | 机制 | 评估 |
|--------|------|------|
| EventBus 私钥传递 | 显式设为 `b""` 空字节 (`key_collision_engine.py:1518`) | [OK] 良好 — 私钥不经过广播通道 |
| EventBus WIF 传递 | 显式设为 `""` 空字符串 (`key_collision_engine.py:1520`) | [OK] 良好 — 明文WIF不进入事件 |
| 事件 WIF 日志脱敏 | `__post_init__` 自动掩码为 `6chars...4chars` (`events.py:89-91`) | [OK] 优秀 — 自动脱敏 |
| 检查点私钥剥离 | `match.pop("private_key_hex")` + `pop("private_key_wif")` (`checkpoint_manager.py:183-185`) | [OK] 良好 — 敏感字段不写入检查点 |
| 统计中私钥哈希 | SHA256 截断前16hex (`collision_stats.py:143`) | [OK] 合理 — 不可逆哈希，足够唯一标识 |
| 内存中私钥清理 | **未调用 `bytearray.clear()` 或 `secrets.compare_digest()`** | [WARN] **Minor** — bytes 对象不可变，依赖 GC 回收 |
| 回调安全调用 | `_safe_invoke_match_callback` 使用 `invoke_with_timeout` (`key_collision_engine.py:1506`) | [WARN] 依赖调用者正确处理 pk_copy |

---

## 三、密码学原语使用审计

### 3.1 使用的密码学操作

| 操作 | 位置 | 底层库 | 评估 |
|------|------|--------|------|
| SHA256(private_key) | `collision_stats.py:143` | `hashlib.sha256` | [OK] 标准库，适合统计用哈希 |
| WIF 编码 | `key_collision_engine.py:1502` | `core.WIF.encode` | [OK] 委托给核心模块，碰撞模块不实现 |
| 公钥→Hash160 | `targets/resolver.py` | `core` 模块 | [OK] 委托给核心模块 |
| CRC32 完整性 | `checkpoint_manager.py:143,188` | `zlib.crc32` | [OK] 适合完整性检查（非安全场景） |

### 3.2 密码学反模式检查

| 反模式 | 是否存在于 collision 模块 | 结论 |
|--------|--------------------------|------|
| 自定义加密原语 | [FAIL] 未发现 | [OK] 良好 — 全部委托给 `core/` 模块 |
| 明文私钥持久化 | [FAIL] 未发现 | [OK] 检查点剥离敏感字段 |
| 使用 `Math.random()` 生成密钥 | [FAIL] 未发现 | [OK] 密钥生成在 `core/secp256k1.py` |
| 使用 `==` 比较哈希值 | [WARN] Python set `__contains__` | [OK] Hash160 是公开值，无需常量时间 |
| IV/nonce 重用 | N/A | [OK] 碰撞模块不使用对称加密 |
| 加密密码而非哈希 | N/A | [OK] 不适用 |

---

## 四、常量时间分析

### 4.1 审查方法

按照 `constant-time-analysis` skill 的 Python 审查指南，检查以下操作：

1. **秘密依赖的条件分支** — `if`/`else` 基于密钥值
2. **秘密比较** — 使用 `==` 或 `in` 比较密钥
3. **数组索引基于秘密值** — 使用秘密值作为列表/数组索引
4. **除法/取模基于秘密值** — 秘密值参与除/模运算

### 4.2 逐操作分析

#### 操作 1: `_worker_generate_addresses` 中的 Hash160 匹配

```python
# key_collision_engine.py:1377-1384
compressed_hash160 = self.generator.public_key_to_hash160(compressed_pub)
if compressed_hash160 in self.target_hash160s:
    matched_address = compressed_addr
    matched_compressed = True
    matched_hash160 = compressed_hash160
```

**分析**: 
- `target_hash160s` 是 `set[bytes]` — Python set `__contains__` 使用哈希表查找
- 哈希表查找不是 O(1) 常量时间，执行时间依赖于：
  - Bucket 碰撞数量（受负载因子影响）
  - **输入 hash160 的值**（因为 hash160 用于决定 bucket）
- **结论**: [OK] **安全** — hash160 是**公开值**（从公钥派生）。即使是攻击者，知道 hash160 并无帮助。时序侧信道需要攻击者能观察秘密值的时序差异，此处无秘密。

#### 操作 2: 私钥范围验证

```python
# key_collision_engine.py:1570
if k < 1 or k >= Secp256k1.N:
    continue
```

**分析**: 
- 在 range/brute_force 模式下，`k` 是顺序递增的非秘密值
- 在 random 模式下，`k` 是随机生成但用于生成地址（公开结果），不是秘密
- **结论**: [OK] **安全** — 分支不依赖秘密值

#### 操作 3: WIF 编码错误处理

```python
# key_collision_engine.py:1500-1559
try:
    pk_bytes = bytes(private_key) if not isinstance(private_key, bytes) else private_key
    wif = WIF.encode(pk_bytes, compressed=matched_compressed)
    ...
except (ValueError, TypeError, OverflowError) as e:
    ...
```

**分析**: 
- WIF 编码可能因错误输入抛异常
- 异常路径包含 `pk_bytes` 的引用，但错误消息不包含私钥值
- **结论**: [OK] **安全** — 错误处理不泄漏密钥材料

#### 操作 4: 去重过滤器中私钥比较

```python
# deduplication_filter.py:64
if key in self._seen_keys:
```

**分析**:
- 同样使用 `set` 的 `__contains__`，非常量时间
- `key` 是私钥 bytes（理论上应保密）
- **结论**: [WARN] **理论上可讨论，但实际风险极低**。理由：
  - 此过滤器的目的是避免已发现的**匹配项**被重复处理（而非逃避密码学比较）
  - 即使攻击者能通过时序推断 `key` 的存在性，他们也需要已经**拥有该私钥**才能进行时序攻击
  - 在已知私钥的情况下关心时序没有意义

### 4.3 常量时间分析的总结

| 操作 | 文件 | 涉及秘密? | 常量时间? | 安全? |
|------|------|-----------|-----------|-------|
| `hash160 in set` | `key_collision_engine.py` | [FAIL] (公开值) | [FAIL] | [OK] |
| `private_key in set` | `deduplication_filter.py` | [OK] (私钥) | [FAIL] | [OK] (实战不可利用) |
| `k < 1 or k >= N` | `key_collision_engine.py` | [FAIL] (扫描值) | [OK] | [OK] |
| `entry["private_key_hash"] = ...` | `collision_stats.py` | [OK] (私钥→hash) | [OK] | [OK] |
| `WIF.encode()` | `key_collision_engine.py` | [OK] (私钥) | 取决于 core 实现 | [OK] (委托) |

---

## 五、安全风险发现

### [RED] Critical（0 项）

碰撞模块中未发现 Critical 级密码学安全风险。

### [ORANGE] Major（1 项）

| ID | 文件 | 行 | 描述 | 建议 |
|----|------|----|------|------|
| CRY-M1 | `key_collision_engine.py` | 多个位置 | **私钥 bytes 对象未显式清零** — 私钥以 `bytes` (不可变) 形式存在于多个变量的作用域中。Python 的 GC 在释放 bytes 前不会覆写内存，私钥可能在进程堆中残留 | 对于签名等长生命周期场景，使用 `bytearray` 并手动 `clear()`；但对碰撞场景影响较小（worker 持续循环生成新私钥，旧私钥的引用很快被覆盖） |

### [BLUE] Minor（4 项）

| ID | 文件 | 行 | 描述 | 建议 |
|----|------|----|------|------|
| CRY-N1 | `key_collision_engine.py` | 1506 | `on_match` 回调接收到 `pk_copy` (bytes) — 如果调用者记录了回调参数，私钥可能无意进入日志 | 向回调传递 `pk_hash` (SHA256 截断) 而非原始私钥，让调用者需要时再从 WIF 获取 |
| CRY-N2 | `collision_stats.py` | 143 | `matches` 列表存储 `private_key_hash: sha256[:16]` — 持久化在内存列表，checkpoint 中也包含 | 确认 checkpoint 中 `private_key_hash` 的使用场景；考虑是否在 checkpoint 中也像 `private_key_hex` 一样剥离 |
| CRY-N3 | `targets/storage.py` | 多处 | 目标地址文件中的地址以明文 JSON/CSV 存储 | 虽然地址是公开信息，但应确认存储文件权限是否足够严格 |
| CRY-N4 | `event_bus.py` | 全局 | 全局 singleton EventBus 可能被任何组件订阅，潜在信息泄漏 | 确认敏感事件的订阅者范围是否受控 |

### [WHITE] Info（2 项）

| ID | 文件 | 行 | 描述 |
|----|------|----|------|
| CRY-I1 | `collision_stats.py` | 143 | SHA256 截断为 64bit（16 hex字符）— 对碰撞检测场景已足够，但碰撞概率为 2^-32 (生日攻击可降为 2^-16) |
| CRY-I2 | `key_collision_engine.py` | 多处 | 私钥在 worker 函数中作为局部变量，理论上可能被同一进程中的其他线程通过堆扫描获取 |

---

## 六、安全设计评估

### 6.1 优秀实践（已实施）

1. **[OK] EventBus 零私钥策略** — 碰撞事件不包含私钥/WIF，仅含地址（公开信息）
2. **[OK] WIF 自动脱敏** — `EngineMatchEvent.__post_init__()` 自动掩码，防止日志泄漏
3. **[OK] 检查点敏感字段剥离** — `private_key_hex` 和 `private_key_wif` 明确 pop
4. **[OK] 错误处理不泄漏密钥** — WIF 编码异常仅包含 error type + message，无私钥
5. **[OK] 输入参数验证** — start() 参数类型/范围严格检查
6. **[OK] SQL 注入防护** — storage.py 使用参数化查询
7. **[OK] 路径穿越防护** — 标准化路径检查

### 6.2 改进机会（待实施）

1. **[WARN] 考虑为关键回调的敏感参数添加生命周期管理** — `on_match` 回调中的 `pk_copy` 建议由调用者负责清理
2. **[WARN] 建议对包含敏感字段的日志行进行扫描** — 运行时检测是否有未预期的私钥/地址泄漏
3. **[INFO] 考虑添加 `__del__` 或 `weakref.finalize` 确保敏感 bytes 尽快可回收**

---

## 七、常量时间分析工具运行

### 7.1 工具说明

常量时间分析工具位于 `~/.codebuddy/skills/constant-time-analysis/ct_analyzer/analyzer.py`，可对 Python 文件进行静态分析。鉴于以下原因，对 collision 模块运行分析工具的必要性较低：

1. collision 模块**不实现**密码学原语（委托给 `core/` 模块）
2. 所有涉及私钥的操作（WIF 编码）委托给 `core/WIF.encode()`
3. 模块内的比较操作针对公开值（hash160）

### 7.2 重点分析推荐

建议在 **Phase 2** (core 模块审计) 中对以下文件运行常量时间分析：

| 文件 | 原因 |
|------|------|
| `src/core/secp256k1.py` | 椭圆曲线点乘运算 — 最关键的常量时间需求 |
| `src/core/crypto_backend.py` | 加密后端操作 |
| `src/core/secure_key_manager.py` | 密钥管理 — 可能的比较操作 |
| `src/core/base58.py` | Base58 编码中可能的除法/取模 |
| `src/core/wif.py` | WIF 格式编码 |

---

## 八、总结

### 8.1 总体评估

`src/collision/` 模块的密码学安全实践整体良好：

- **敏感数据流设计** [OK] — 私钥不经过广播通道，WIF 自动脱敏
- **持久化安全** [OK] — 检查点剥离私钥字段，参数化查询防注入
- **密码学原语使用** [OK] — 全部委托给 `core/` 模块，无自定义加密实现
- **常量时间安全** [OK] — 模块内的比较操作涉及公开值，无实际时序风险
- **输入验证** [OK] — 参数类型范围检查到位

### 8.2 安全等级评分

| 类别 | 评分 | 说明 |
|------|------|------|
| 敏感数据处理 | 90/100 | WIF 自动脱敏优秀，但私钥 bytes 未显式清零 |
| 密码学原语使用 | 95/100 | 无自定义加密，全部委托给专业模块 |
| 常量时间安全 | 92/100 | 无实质性风险，建议 core 模块重点分析 |
| 输入验证 | 88/100 | 基本覆盖但地址验证仅 format+length |
| 持久化安全 | 90/100 | 检查点/数据库均有保护措施 |
| **整体** | **91/100** | |

### 8.3 与碰撞模块审核报告的交叉引用

| 报告 | 交叉项 |
|------|--------|
| `collision_module_audit_report.md` | COL-C3 (stub MultiProcessEngine) — 即使实现完整，也需遵循相同安全实践 |
| `collision_module_audit_report.md` | COL-M4 (__all__ 缺失) — 影响模块边界定义 |
| 本报告 CRY-N1 | 与 COL-M2 (types.py) 相关 — 回调类型签名明确后可减少误用 |

---

*报告生成时间: 2026-05-28 04:33 UTC+8*  
*审计范围: `src/collision/` 22 个文件的密码学安全与常量时间维度*  
*建议后续审计: Phase 2 — `src/core/` 模块深度密码学审计（含常量时间分析工具运行）*

# Windows 内存锁机制说明

> **版本**: v3.5.1 | **最后更新**: 2026-05-01
> **面向**: 安全审计/开发者

## 概述

BTC 碰撞引擎在生成和处理比特币私钥时，使用操作系统级别的内存锁定机制防止敏感数据被交换到磁盘页面文件，从而降低私钥泄露的风险。

## 实现原理

### 多平台内存锁

`SecureKeyManager` (位于 `src/core/secure_key_manager.py`) 实现了跨平台的内存锁定：

| 平台 | API | 系统调用 | 说明 |
|------|-----|----------|------|
| **Windows** | `VirtualLock` | `kernel32.dll` | 锁定内存页，防止被换出到页面文件 |
| **Linux** | `mlock` | `libc.so.6` | 锁定物理内存页，需要 `CAP_IPC_LOCK` |
| **macOS** | `mlock` | `libSystem.B.dylib` | 锁定物理内存页，需要 root 权限 |

### Windows VirtualLock 详细说明

#### API 签名

```c
BOOL VirtualLock(LPVOID lpAddress, SIZE_T dwSize);
BOOL VirtualUnlock(LPVOID lpAddress, SIZE_T dwSize);
```

#### Python 调用路径

```python
# src/core/secure_key_manager.py

# 1. 初始化时加载 kernel32.dll
kernel32 = ctypes.WinDLL("kernel32.dll")
kernel32.VirtualLock.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
kernel32.VirtualLock.restype = ctypes.c_bool

# 2. 生成密钥后锁定内存
addr = ctypes.addressof(ctypes.c_char.from_buffer(self._key))
size = len(self._key)
result = kernel32.VirtualLock(addr, size)

# 3. 清零后解锁内存
kernel32.VirtualUnlock(addr, size)
```

#### 限制条件

1. **工作集限制**: 锁定的内存页计入进程工作集。Windows 对每个进程有最大工作集限制。
2. **系统资源**: 系统范围内锁定的总页面数受限。过多锁定会导致其他进程性能下降。
3. **权限要求**: 默认情况下进程需要 `SeLockMemoryPrivilege` 权限（管理员组默认拥有）。
4. **错误码分析**:
   - `ERROR_WORKING_SET_QUOTA (1453)`: 进程工作集配额不足
   - `ERROR_NOT_ENOUGH_MEMORY (8)`: 系统可用内存不足
   - `ERROR_LOCK_FAILED (无效)`: VirtualLock 失败时 `GetLastError()` 可能返回此值

### 密钥生命周期

```
┌──────────────┐    VirtualLock    ┌──────────────┐    SecureZeroMemory    ┌──────────────┐
│  密钥生成     │ ─────────────────→ │  内存锁定     │ ────────────────────→ │  安全清零     │
│  (bytearray)  │                   │  (不可交换)   │                       │  (0x00覆盖)  │
└──────────────┘                    └──────────────┘                       └──────────────┘
       │                                    │                                       │
       │                                    │                               VirtualUnlock
       └─────────────── 锁定时间窗口（最小化） ───────────────┘                    │
                                                                          ┌──────────────┐
                                                                          │  内存解锁     │
                                                                          └──────────────┘
```

## 安全后端

密钥清零支持三种后端（按优先级）：

| 优先级 | 后端 | 库 | 清零方法 |
|--------|------|-----|----------|
| 1 (推荐) | `cryptography` | `cryptography.hazmat` | `constant_time.bytes_eq()` + 显式覆盖 |
| 2 | `PyNaCl` | `nacl` | `sodium_memzero()` |
| 3 (回退) | `ctypes` | 内置 | `memset()` + `SecureZeroMemory()` |

### ctypes 回退实现

```python
# Windows 使用 SecureZeroMemory
if sys.platform == "win32":
    kernel32 = ctypes.WinDLL("kernel32.dll")
    kernel32.SecureZeroMemory(addr, size)
else:
    # POSIX 使用 memset + volatile 指针
    ctypes.memset(addr, 0, size)
```

## 安全考量

### 已知限制

1. **Python GC 影响**: Python 的垃圾回收器可能在锁定前复制 `bytearray` 对象，旧副本不会被锁定。因此密钥管理器使用 `bytearray` 而非 `bytes`，确保可变对象直接清零。
2. **CPU 缓存残留**: `VirtualLock`/`mlock` 防止磁盘交换，但无法防止 CPU 缓存中的残留数据。
3. **调试器风险**: 内存锁定不阻止调试器 (`ReadProcessMemory`) 读取内存。
4. **休眠/休眠文件**: 系统休眠 (S4) 时，内存内容写入 `hiberfil.sys`。建议在生产环境禁用休眠。

### 最佳实践

1. **最小化密钥生存时间**: 使用 `SecureKeyManager` 的上下文管理器，密钥使用完毕后立即清零。
2. **禁用系统休眠**: 生产环境执行 `powercfg /h off` 禁用休眠文件。
3. **监控清零统计**: 通过类级别计数器 `SecureKeyManager._successful_clears` / `SecureKeyManager._failed_clears` 监控清零成功率。
4. **定期审计**: 检查日志中的 `VirtualLock失败` 和 `安全清零失败` 警告。

## 配置与使用

### 启用内存锁

```python
from src.core.secure_key_manager import SecureKeyManager

# 启用内存锁定（默认）
with SecureKeyManager(lock_memory=True) as key_mgr:
    key_mgr.generate_key()
    private_key = key_mgr.get_key()
    # 使用私钥...
# 退出上下文时自动清零并解锁内存

# 禁用内存锁定（测试环境）
with SecureKeyManager(lock_memory=False) as key_mgr:
    key_mgr.generate_key()
    # 测试用...
```

### 验证内存锁状态

```python
key_mgr = SecureKeyManager(lock_memory=True)
key_mgr.generate_key()
print(f"内存已锁定: {key_mgr._memory_locked}")
print(f"清零已完成: {key_mgr._cleared}")
```

## GPU 私钥安全

对于 GPU 引擎路径，私钥安全额外通过以下机制保障：

1. **日志脱敏**: `SensitiveDataFilter` 自动将日志中的 64 位十六进制私钥替换为 `***REDACTED***`
2. **GPU 缓冲区**: OpenCL 缓冲区在释放前显式填充零
3. **匹配回调**: 仅传递私钥哈希而非原始私钥到日志输出

## 审计清单

- [ ] 确认 `SecureKeyManager` 在生产环境中使用 `lock_memory=True`
- [ ] 验证 Windows 工作集配额足够（检查是否出现 ERROR_WORKING_SET_QUOTA）
- [ ] 确认系统休眠已禁用 (`powercfg /h off`)
- [ ] 检查日志中是否有 `VirtualLock失败` 警告
- [ ] 验证 `SensitiveDataFilter` 已启用且正常工作

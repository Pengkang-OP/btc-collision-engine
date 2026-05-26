# Windows平台内存锁定说明

**文档版本**: v4.2.2
**日期**: 2026-04-24
**状态**: ✅ 已实施

---

## 1. 概述

### 1.1 什么是内存锁定？

内存锁定（Memory Locking）是一种安全机制，用于防止敏感数据被操作系统交换到磁盘（swap/pagefile）。对于比特币私钥碰撞引擎，这是保护私钥安全的重要措施。

### 1.2 为什么需要内存锁定？

- **安全性**: 私钥在内存中处理时，如果被交换到磁盘，可能被恢复

- **合规性**: 某些安全标准要求敏感数据不得写入持久化存储

- **性能**: 锁定的内存不会被页故障中断，提高性能

---

## 2. Windows实现

### 2.1 使用的API

```python
import ctypes
import ctypes.wintypes

# Windows API: VirtualLock
VirtualLock = ctypes.windll.kernel32.VirtualLock
VirtualLock.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
VirtualLock.restype = ctypes.wintypes.BOOL

# Windows API: VirtualUnlock
VirtualUnlock = ctypes.windll.kernel32.VirtualUnlock
VirtualUnlock.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
VirtualUnlock.restype = ctypes.wintypes.BOOL

```

### 2.2 使用方法

```python
def lock_memory(buffer: bytes) -> bool:
    """锁定内存，防止被交换到磁盘

    Args:
        buffer: 要锁定的字节缓冲区

    Returns:
        是否成功锁定
    """
    address = ctypes.addressof(ctypes.create_string_buffer(buffer))
    size = len(buffer)

    result = VirtualLock(address, size)
    if not result:
        error_code = ctypes.get_last_error()
        logger.warning(f"内存锁定失败: 错误码 {error_code}")
        return False

    logger.debug(f"内存锁定成功: {size} 字节")
    return True

def unlock_memory(buffer: bytes) -> bool:
    """解锁内存

    Args:
        buffer: 要解锁的字节缓冲区

    Returns:
        是否成功解锁
    """
    address = ctypes.addressof(ctypes.create_string_buffer(buffer))
    size = len(buffer)

    result = VirtualUnlock(address, size)
    if not result:
        error_code = ctypes.get_last_error()
        logger.warning(f"内存解锁失败: 错误码 {error_code}")
        return False

    return True

```

---

## 3. 限制和要求

### 3.1 权限要求

**管理员权限**:

- Windows默认限制可锁定的内存大小

- 需要管理员权限或使用`SeLockMemoryPrivilege`特权

**获取特权**:

```
1. 打开"本地安全策略" (secpol.msc)
2. 导航到: 本地策略 -> 用户权限分配
3. 找到"锁定内存中的页"
4. 添加需要的用户或服务账户

```

### 3.2 大小限制

**默认限制**:

- Windows 10/11: 约工作集大小的20%

- Windows Server: 可配置，默认较高

**检查限制**:

```python
import ctypes

# 获取工作集大小
GetCurrentProcessWorkingSetSize = ctypes.windll.kernel32.GetCurrentProcessWorkingSetSize
min_ws = ctypes.c_size_t()
max_ws = ctypes.c_size_t()

GetCurrentProcessWorkingSetSize(ctypes.byref(min_ws), ctypes.byref(max_ws))
print(f"工作集大小: {min_ws.value} - {max_ws.value} 字节")

```

### 3.3 已知问题

**问题1: 锁定失败**

```
错误: 内存锁定失败: 错误码 1314 (ERROR_PRIVILEGE_NOT_HELD)
原因: 缺少SeLockMemoryPrivilege特权
解决: 以管理员身份运行或添加特权

```

**问题2: 锁定过多内存**

```
错误: 内存锁定失败: 错误码 8 (ERROR_NOT_ENOUGH_MEMORY)
原因: 尝试锁定超过限制的内存
解决: 减少锁定内存大小或增加工作集限制

```

---

## 4. 跨平台对比

| 特性 | Windows | Linux | macOS |
|------|---------|-------|-------|
| API | VirtualLock | mlock/mlockall | mlock |
| 权限 | SeLockMemoryPrivilege | CAP_IPC_LOCK | root |
| 限制 | 工作集20% | ulimit -l | 无硬限制 |
| 最小粒度 | 页大小(4KB) | 页大小(4KB) | 页大小(4KB) |

### 4.1 Linux实现

```python
import ctypes

# Linux: mlock
libc = ctypes.CDLL("libc.so.6")
libc.mlock.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
libc.mlock.restype = ctypes.c_int

def lock_memory_linux(buffer: bytes) -> bool:
    """Linux内存锁定"""
    address = ctypes.addressof(ctypes.create_string_buffer(buffer))
    size = len(buffer)

    result = libc.mlock(address, size)
    if result != 0:
        logger.error(f"mlock失败: errno {result}")
        return False

    return True

```

### 4.2 macOS实现

```python
# macOS使用与Linux相同的mlock API
# 但可能需要禁用SIP或签名应用

```

---

## 5. 最佳实践

### 5.1 最小化锁定

**原则**: 只锁定真正敏感的数据

```python
# ✅ 正确: 只锁定私钥
private_key = generate_private_key()
lock_memory(private_key)

# ❌ 错误: 锁定整个缓冲区
large_buffer = bytearray(1024 * 1024 * 100)  # 100MB
lock_memory(large_buffer)  # 可能失败

```

### 5.2 及时解锁

**原则**: 使用完毕后立即解锁

```python
private_key = generate_private_key()
try:
    lock_memory(private_key)
    # 使用私钥...
    result = use_private_key(private_key)
finally:
    unlock_memory(private_key)  # 确保解锁
    clear_memory(private_key)   # 清除敏感数据

```

### 5.3 错误处理

**原则**: 锁定失败不应阻止程序运行

```python
def safe_lock_memory(buffer: bytes) -> bool:
    """安全地锁定内存，失败时警告但不抛出异常"""
    try:
        if sys.platform == 'win32':
            return lock_memory_windows(buffer)
        elif sys.platform == 'linux':
            return lock_memory_linux(buffer)
        else:
            logger.warning(f"平台 {sys.platform} 不支持内存锁定")
            return False
    except Exception as e:
        logger.warning(
            f"内存锁定失败(非致命): {e}\n"
            f"  建议: 以管理员身份运行或配置权限"
        )
        return False

```

---

## 6. 在BTC碰撞引擎中的使用

### 6.1 SecureKeyManager

```python
from src.core.secure_key_manager import SecureKeyManager

key_manager = SecureKeyManager()

# 自动锁定内存
key_manager.store("key1", private_key_bytes)

# 使用时自动解锁，使用后自动锁定
with key_manager.use("key1") as key:
    result = compute_something(key)

# 手动清除
key_manager.clear("key1")

```

### 6.2 配置选项

```json
{
  "security": {
    "lock_memory": true,
    "memory_lock_size_mb": 64,
    "auto_clear_on_exit": true
  }
}

```

---

## 7. 调试和监控

### 7.1 检查锁定状态

**Windows**:

```powershell
# 查看进程的工作集
Get-Process -Id <PID> | Select-Object WorkingSet, PeakWorkingSet

# 查看特权
whoami /priv | findstr SeLockMemoryPrivilege

```

**Linux**:

```bash
# 查看锁定内存限制
ulimit -l

# 查看进程锁定内存
cat /proc/<PID>/smaps | grep Locked

```

### 7.2 日志示例

```
2026-04-24 14:00:00 [DEBUG] src.core.secure_key_manager: 内存锁定成功: 32 字节
2026-04-24 14:00:00 [INFO] src.core.secure_key_manager: SecureKeyManager初始化完成
2026-04-24 14:00:05 [DEBUG] src.core.secure_key_manager: 内存解锁成功: 32 字节

```

---

## 8. 安全注意事项

### 8.1 不要完全依赖内存锁定

**风险**:

- 内存可能被core dump捕获

- 调试器可以读取内存

- DMA攻击可以访问内存

**缓解措施**:

1. 禁用core dump

2. 使用安全启动

3. 启用BitLocker/FileVault

4. 定期清除敏感数据

### 8.2 内存清除

```python
def secure_clear(buffer: bytearray):
    """安全清除内存，防止编译器优化"""
    for i in range(len(buffer)):
        buffer[i] = 0
    # 可选: 多次覆盖
    for i in range(len(buffer)):
        buffer[i] = 0xFF
    for i in range(len(buffer)):
        buffer[i] = 0

```

---

## 9. 故障排除

### 9.1 常见问题

**Q1: 内存锁定失败怎么办？**

```
A: 按以下步骤排查:
   1. 检查是否以管理员身份运行
   2. 检查SeLockMemoryPrivilege特权
   3. 检查尝试锁定的内存大小
   4. 查看Windows事件日志

```

**Q2: 如何增加可锁定内存大小？**

```
A: 两种方法:
   方法1: 修改组策略
   - gpedit.msc -> 计算机配置 -> Windows设置 -> 安全设置
   - 本地策略 -> 用户权限分配 -> 锁定内存中的页

   方法2: 修改注册表
   - HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management
   - 修改DisablePagingExecutive = 1

```

**Q3: 内存锁定会影响性能吗？**

```
A: 影响很小:
   - 正面: 减少页故障，提高性能
   - 负面: 减少可用物理内存
   - 建议: 只锁定必要的敏感数据

```

---

## 10. 参考资料

- [VirtualLock文档](https://docs.microsoft.com/en-us/windows/win32/api/memoryapi/nf-memoryapi-virtuallock)

- [内存管理最佳实践](https://docs.microsoft.com/en-us/windows/win32/memory/memory-management-functions)

- [Windows安全基线](https://docs.microsoft.com/en-us/windows/security/)

---

**维护者**: AI审计系统
**下次审查**: 2026-07-24

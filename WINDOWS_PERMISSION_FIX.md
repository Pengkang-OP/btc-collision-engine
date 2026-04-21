# Windows 权限错误修复报告

## 问题描述

在运行 BTC 碰撞引擎时，数据日志系统遇到 Windows 权限错误：

```
2026-04-21 01:31:25,916 - DataLogger - ERROR - 保存历史数据失败: [WinError 5] 拒绝访问。: 'F:\\Qoder\\btc-collision-engine\\data_logs\\.history_data__na9vivu.tmp' -> 'F:\\Qoder\\btc-collision-engine\\data_logs\\history_data.json'
```

## 根本原因

在 Windows 系统上，`os.replace()` 函数在以下情况下会抛出 `PermissionError`：

1. **目标文件被其他进程占用**（如防病毒软件、文件监控工具、编辑器）
2. **Windows 文件锁定机制**比 Linux 更严格，不允许直接替换正在使用的文件
3. **原子操作限制**：Windows 上的 `os.replace()` 不是完全原子的，可能会遇到访问冲突

## 解决方案

### 修改的文件

- `src/monitoring/data_logger.py`

### 具体改进

#### 1. `save_current_data()` 方法增强

**改进内容：**
- 添加重试机制（最多 3 次重试）
- 在 Windows 上使用"先删除再重命名"策略代替 `os.replace()`
- 每次重试之间等待 0.5 秒，给文件锁释放的时间
- 详细的错误日志，显示重试次数

**关键代码：**
```python
# Windows上先删除目标文件，再重命名（避免PermissionError）
if os.name == 'nt':
    try:
        os.remove(self.current_data_file)
    except PermissionError:
        # 如果文件被占用，等待后重试
        if attempt < max_retries - 1:
            time.sleep(retry_delay)
            continue
        raise
os.rename(temp_file, self.current_data_file)
```

#### 2. `save_history_data()` 方法增强

**改进内容：**
- 与 `save_current_data()` 相同的重试机制
- Windows 特定的文件替换策略
- 重试失败后自动将数据返回缓冲区，防止数据丢失
- 使用 `appendleft` 逆序插入，保持数据顺序

**关键代码：**
```python
max_retries = 3
retry_delay = 0.5  # 秒

for attempt in range(max_retries):
    try:
        # ... 写入临时文件 ...
        
        # Windows上先删除目标文件，再重命名
        if os.name == 'nt':
            try:
                os.remove(self.history_data_file)
            except PermissionError:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                raise
        os.rename(temp_file, self.history_data_file)
        return  # 成功，退出重试循环
        
    except Exception as e:
        self.logger.error(f"保存历史数据失败 (尝试 {attempt + 1}/{max_retries}): {e}")
        # ... 清理和重试逻辑 ...
```

## 测试验证

### 1. 原有测试通过

```bash
python -m pytest tests/test_data_logger.py -v
# 12 passed in 2.37s
```

### 2. 新增 Windows 权限重试测试

创建了 `tests/test_windows_permission_retry.py`，包含 3 个测试用例：

- `test_save_history_data_with_permission_error`: 测试历史数据保存的权限错误重试
- `test_save_current_data_with_permission_error`: 测试当前数据保存的权限错误重试
- `test_retry_exhausted_returns_data_to_buffer`: 测试重试耗尽后数据返回缓冲区

```bash
python -m pytest tests/test_windows_permission_retry.py -v
# 3 passed in 2.34s
```

## 优势

1. **更高的可靠性**：即使遇到临时权限问题，也能通过重试成功保存数据
2. **数据安全性**：重试失败后自动将数据返回缓冲区，不会丢失数据
3. **跨平台兼容**：在 Linux/macOS 上保持原有行为，仅在 Windows 上使用特殊处理
4. **详细日志**：记录每次重试的详细信息，便于调试
5. **向后兼容**：不影响现有功能和 API

## 建议

### 短期建议

1. **监控日志**：观察修复后是否还有权限错误发生
2. **检查占用进程**：如果频繁出现权限错误，检查是否有其他程序在监控 `data_logs` 目录

### 长期建议

1. **考虑使用文件锁**：对于高并发场景，可以考虑使用 `fcntl` (Linux) 或 `msvcrt` (Windows) 实现文件锁
2. **批量写入优化**：减少文件写入频率，降低冲突概率
3. **异步写入**：使用后台线程专门处理文件写入，避免阻塞主流程

## 总结

本次修复通过添加重试机制和 Windows 特定的文件操作策略，成功解决了 Windows 上的权限错误问题。修复方案保持了数据完整性和向后兼容性，并通过全面的测试验证了其正确性。

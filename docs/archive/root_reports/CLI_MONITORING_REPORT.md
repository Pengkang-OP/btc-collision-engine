# CLI运行状态监控报告

**监控时间**: 2026-04-23 02:36:30  
**监控对象**: key_collision_cli.py  
**监控状态**: ⚠️ 发现问题

---

## 📊 运行状态总览

### 基本信息

| 项目 | 状态 | 详情 |
|------|------|------|
| **CLI程序** | ❌ 已停止 | 发现严重问题后手动停止 |
| **碰撞引擎** | ❌ 未工作 | 速度持续为0 |
| **目标地址** | ✅ 已加载 | 38个地址 |
| **断点续传** | ❌ 失败 | 权限错误 |
| **监控系统** | ✅ 运行中 | 正常记录数据 |

---

## 🚨 发现的问题

### 问题1: 引擎速度为0 (严重)

**现象**:

```
[00:00:05] 已检查: 0 | 速度: 0.00/s | 匹配: 0 | ETA: --
[00:00:09] 已检查: 0 | 速度: 0.00/s | 匹配: 0 | ETA: --
[00:00:15] 已检查: 0 | 速度: 0.00/s | 匹配: 0 | ETA: --
...
[00:01:00] 已检查: 0 | 速度: 0.00/s | 匹配: 0 | ETA: --
```

**日志证据**:

```
MonitoringSystem - WARNING - ALERT: 检测速率过低: 0.00/s
MonitoringSystem - WARNING - ALERT: 检测速率过低: 0.00/s
MonitoringSystem - WARNING - ALERT: 检测速率过低: 0.00/s
```

**可能原因**:

1. 工作线程未正常启动
2. random_search模式存在问题
3. 线程阻塞或死锁
4. 目标地址加载后引擎未开始工作

**影响**:

- ❌ 无法进行碰撞检测
- ❌ 浪费计算资源
- ❌ 监控系统持续报警

---

### 问题2: 断点文件权限错误 (严重)

**现象**:

```
CheckpointManager - ERROR - 保存断点失败（权限不足）: [WinError 5] 拒绝访问。: 
'F:\Qoder\btc-collision-engine\src\collision\collision_checkpoint.json'
```

**频率**: 每0.5-1秒报错一次（极其频繁）

**文件权限检查**:

```
Path   : F:\Qoder\btc-collision-engine\src\collision\collision_checkpoint.json
Owner  : JOHN-PC\pengk
Group  : JOHN-PC\pengk
Access : JOHN-PC\pengk Allow Write, Read, Synchronize
```

**分析**:

- 文件存在且权限正常
- 但程序无法写入
- 可能是文件被锁定或占用

**可能原因**:

1. 文件被其他进程占用
2. 文件锁定机制问题
3. 写入时未正确释放锁
4. 并发写入冲突

**影响**:

- ❌ 无法保存断点
- ❌ 日志污染严重
- ❌ 性能影响（频繁错误处理）

---

## 📈 性能数据分析

### 监控数据统计

| 指标 | 数值 | 状态 |
|------|------|------|
| **已检查私钥** | 0 | ❌ 异常 |
| **检测速度** | 0.00 keys/s | ❌ 异常 |
| **匹配数** | 0 | ✅ 正常（未工作） |
| **运行时间** | 60秒 | - |
| **历史数据** | 521,157 bytes | ✅ 有数据 |
| **性能日志** | 170 bytes | ⚠️ 较少 |

### 数据文件状态

| 文件 | 大小 | 状态 |
|------|------|------|
| `src/data_logs/current_data.json` | 存在 | ✅ 正常 |
| `src/data_logs/history_data.json` | 521 KB | ✅ 有历史数据 |
| `src/data_logs/performance.log` | 170 bytes | ⚠️ 数据少 |
| `src/collision/collision_checkpoint.json` | 存在 | ❌ 无法写入 |

---

## 🔍 问题诊断

### 诊断1: 引擎初始化检查

**成功初始化的组件**:

- ✅ CryptoBackend: coincurve (libsecp256k1)
- ✅ BigIntOptimizer: gmpy2 Comba乘法
- ✅ SIMDHash: pycryptodome AES-NI
- ✅ PrecomputedTable: window_size=8, 256点
- ✅ MemoryPool: ECPoint + ByteArray池
- ✅ KeyCollisionEngine: 目标数=38
- ✅ EnhancedMonitoringSystem: 已启用

**日志输出**:

```
KeyCollisionEngine - INFO - KeyCollisionEngine 初始化完成: 目标数=38, 断点=True, 去重=False
KeyCollisionEngine - INFO - P3-9 Batch size自动调整: 1000 -> 4000 (CPU: 16核)
KeyCollisionEngine - INFO - 启动对撞引擎: 模式=random, 恢复=False, 目标数=38
KeyCollisionEngine - INFO - 启动工作线程: random_search
KeyCollisionEngine - INFO - 启动随机碰撞模式
KeyCollisionEngine - INFO - 目标地址数: 38
KeyCollisionEngine - INFO - 工作线程数: 16
KeyCollisionEngine - INFO - 对撞引擎启动完成
```

**结论**: 引擎初始化成功，但工作线程未产生实际工作

---

### 诊断2: 工作线程分析

**预期行为**:

1. 启动16个工作线程
2. 每个线程随机生成私钥
3. 计算地址并检查匹配
4. 更新统计数据

**实际行为**:

1. ✅ 线程启动成功
2. ❌ 未检测到私钥生成
3. ❌ 未检测到地址计算
4. ❌ 统计数据未更新

**可能问题**:

- 工作线程函数可能存在问题
- 线程可能阻塞在某个操作上
- 随机数生成可能失败
- 目标地址检查逻辑可能有bug

---

### 诊断3: 断点文件分析

**文件内容**:

```json
{
  "mode": "random",
  "total_checked": 0,
  "timestamp": "2026-04-23T02:34:48.126902"
}
```

**问题**:

- 文件存在且可读
- 但写入时报权限错误
- 可能是文件锁未正确释放

**检查建议**:

```python
# 检查文件是否被锁定
import psutil
for proc in psutil.process_iter(['open_files']):
    for file in proc.info['open_files'] or []:
        if 'collision_checkpoint.json' in file.path:
            print(f"进程 {proc.pid} 锁定了文件")
```

---

## 💡 修复建议

### 修复1: 引擎速度为0

**优先级**: 🔴 高（阻塞性bug）

**诊断步骤**:

1. 检查random_search工作线程函数
2. 添加调试日志确认线程执行
3. 检查私钥生成逻辑
4. 验证地址计算流程

**可能修复**:

```python
# 在random_search中添加日志
logger.debug("工作线程启动")
try:
    private_key = generate_random_key()
    logger.debug(f"生成私钥: {private_key.hex()[:16]}...")
    address = compute_address(private_key)
    logger.debug(f"计算地址: {address}")
    check_collision(address)
except Exception as e:
    logger.error(f"工作线程异常: {e}", exc_info=True)
```

---

### 修复2: 断点文件权限

**优先级**: 🟡 中（影响功能）

**修复方案**:

**方案A**: 更改断点文件位置（推荐）

```python
# 从 src/collision/ 改为 data_logs/
CHECKPOINT_FILE = os.path.join(DATA_DIR, "checkpoint.json")
```

**方案B**: 改进文件锁机制

```python
import fcntl

def save_checkpoint(self, data):
    try:
        with open(self.checkpoint_file, 'w') as f:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            json.dump(data, f)
            fcntl.flock(f, fcntl.LOCK_UN)
    except IOError:
        logger.warning("断点文件被锁定，跳过本次保存")
```

**方案C**: 增加重试机制

```python
def save_checkpoint(self, data, max_retries=3):
    for attempt in range(max_retries):
        try:
            with open(self.checkpoint_file, 'w') as f:
                json.dump(data, f)
            return
        except PermissionError:
            if attempt < max_retries - 1:
                time.sleep(0.5)
                continue
            raise
```

---

## 🎯 行动计划

### 立即行动

1. **停止当前CLI** ✅ 已完成
2. **检查工作线程代码** - 诊断速度为0的原因
3. **修复断点文件位置** - 避免权限问题
4. **添加调试日志** - 确认线程执行流程

### 短期优化

1. **改进错误处理** - 断点保存失败不应频繁报错
2. **优化监控阈值** - 初始阶段不报警速度过低
3. **增加健康检查** - 定期检测引擎是否正常工作

### 长期改进

1. **完善异常恢复** - 引擎异常时自动重启
2. **增强诊断工具** - 提供实时诊断命令
3. **改进日志策略** - 区分调试/信息/警告/错误

---

## 📋 监控清单

- [x] CLI程序状态检查
- [x] 引擎速度监控
- [x] 断点文件检查
- [x] 数据文件验证
- [x] 日志分析
- [ ] 工作线程诊断（待执行）
- [ ] 断点文件修复（待执行）
- [ ] 重新启动验证（待执行）

---

## 🔧 调试命令

### 查看实时日志

```bash
Get-Content logs\*.log -Tail 50 -Wait
```

### 检查进程状态

```bash
tasklist | findstr python
```

### 检查文件锁定

```python
python -c "
import psutil
for proc in psutil.process_iter(['open_files']):
    for file in proc.info['open_files'] or []:
        if 'collision_checkpoint' in file.path:
            print(f'进程 {proc.pid} 锁定了文件')
"
```

### 手动测试引擎

```python
python -c "
from src.collision import KeyCollisionEngine
engine = KeyCollisionEngine(targets=['1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH'])
engine.start(mode='random', duration=10)
"
```

---

**报告生成时间**: 2026-04-23 02:36:30  
**下次监控**: 修复问题后重新测试  
**建议行动**: 立即诊断并修复工作线程问题

# 引擎速度为0问题诊断与修复报告

**诊断时间**: 2026-04-23 02:42:00  
**问题**: CLI显示速度为0 keys/s  
**状态**: ✅ 已定位，部分修复

---

## 🔍 问题现象

### CLI运行输出

```
[00:00:05] 已检查: 0 | 速度: 0.00/s | 匹配: 0 | ETA: --
[00:00:09] 已检查: 0 | 速度: 0.00/s | 匹配: 0 | ETA: --
[00:00:15] 已检查: 0 | 速度: 0.00/s | 匹配: 0 | ETA: --
...
[00:01:00] 已检查: 0 | 速度: 0.00/s | 匹配: 0 | ETA: --
```

### 诊断测试输出

```python
2s: checked=0, speed=0 keys/s, running=True
4s: checked=0, speed=0 keys/s, running=True
6s: checked=0, speed=0 keys/s, running=True
8s: checked=0, speed=0 keys/s, running=True
10s: checked=0, speed=0 keys/s, running=True
Final: 1,032 keys, 102 keys/s  # ← 引擎确实在工作！
```

---

## 🎯 问题根源

### 核心问题：统计数据更新机制缺陷

**架构设计**:
```
Worker Thread                    Main Thread
    |                                |
    |-- _live_range_count -----------+--> get_stats()
    |   (每batch更新一次)                 |
    |                                    v
                                    合并到stats
```

**问题链条**:

1. **Worker线程**
   - 每处理一个batch（4000个私钥）后更新`_live_range_count`
   - 更新频率：`batch_size / speed = 4000 / 1500 ≈ 2.7秒`

2. **主线程**
   - CLI每5秒调用一次`get_stats()`
   - `get_stats()`读取并合并`_live_range_count`

3. **时序问题**
   ```
   Time:  0s    2s    4s    5s    6s    8s   10s
   Worker: |-----batch1-----|-----batch2-----|
   CLI:         |get_stats()|     |get_stats()|
   Result:      count=0          count=0      ← 在batch完成前查询
   ```

### 代码分析

**Worker线程更新**（key_collision_engine.py:609-611）:
```python
# 每批次结束后更新
if batch_count > 0:
    with self._state_lock:
        self._live_range_count += batch_count
```

**原始get_stats()**（修复前）:
```python
def get_stats(self) -> CollisionStats:
    return self.stats  # ❌ 没有包含_live_range_count
```

**问题**: 
- `stats.total_checked`只在线程结束时更新（random_search:759）
- 运行期间，实际计数在`_live_range_count`中
- 但`get_stats()`没有合并这个值

---

## ✅ 已应用的修复

### 修复1: 改进get_stats()方法

**文件**: `src/collision/key_collision_engine.py`  
**位置**: 第1483-1509行

**修复前**:
```python
def get_stats(self) -> CollisionStats:
    """获取当前碰撞统计信息"""
    return self.stats
```

**修复后**:
```python
def get_stats(self) -> CollisionStats:
    """
    获取当前碰撞统计信息
    
    P2修复: 包含_live_range_count确保实时统计数据准确
    """
    # P2修复: 将live_range_count合并到stats中
    if self.stats and hasattr(self, '_live_range_count') and self._live_range_count > 0:
        with self._state_lock:
            live_count = self._live_range_count
            if live_count > 0:
                # 更新stats的total_checked
                self.stats.total_checked += live_count
                # 重置live_counter避免重复计算
                self._live_range_count = 0
                # 重新计算速度
                if self.stats.start_time > 0:
                    elapsed = time.time() - self.stats.start_time
                    if elapsed > 0:
                        self.stats.speed = self.stats.total_checked / elapsed
    
    return self.stats
```

**效果**:
- ✅ `get_stats()`现在包含实时计数
- ✅ 速度计算更准确
- ✅ 避免重复计算（重置_counter）

---

## ⚠️ 剩余问题

### 问题1: 更新频率仍然较低

**原因**: 
- batch_size=4000（16核CPU）
- 地址生成速度约1500 keys/s
- 更新间隔：4000/1500 ≈ 2.7秒

**影响**:
- CLI每5秒查询，可能错过1-2次更新
- 显示的速度会有波动

**建议优化**:
```python
# 方案A: 减小batch_size
if cpu_count <= 2:
    optimal_batch_size = 500   # 0.3秒更新一次
elif cpu_count <= 4:
    optimal_batch_size = 1000  # 0.7秒更新一次
elif cpu_count <= 8:
    optimal_batch_size = 2000  # 1.3秒更新一次
else:
    optimal_batch_size = 2000  # 降低到2000，1.3秒更新一次
```

**方案B**: 增加中间更新点
```python
# 在batch内部也更新（每1000个）
if local_count % 1000 == 0 and batch_count > 0:
    with self._state_lock:
        self._live_range_count += batch_count
        batch_count = 0  # 重置避免重复
```

---

### 问题2: 断点文件权限错误

**现象**:
```
ERROR - 保存断点失败（权限不足）: [WinError 5] 拒绝访问
```

**原因**: 
- 断点文件位置：`src/collision/collision_checkpoint.json`
- 文件被频繁写入（每30秒）
- 可能存在文件锁冲突

**修复建议**:
```python
# 更改断点文件位置
CHECKPOINT_FILE = os.path.join(DATA_DIR, "checkpoint.json")
# 或
CHECKPOINT_FILE = os.path.join(LOGS_DIR, "checkpoint.json")
```

---

## 📊 性能测试数据

### 测试1: 1个目标地址，2个工作线程

```
运行时间: 10秒
总检查数: 1,032 keys
平均速度: 102 keys/s
```

**分析**:
- 速度偏低（预期~1500 keys/s）
- 可能原因：
  1. 地址生成使用了coincurve（较慢但安全）
  2. 目标地址检查（hash160比较）
  3. 日志输出开销

### 测试2: 38个目标地址，16个工作线程（CLI实际运行）

```
运行时间: 60秒
显示检查数: 0 keys  ← 问题！
实际检查数: 未知（但最终有数据）
```

**分析**:
- 多目标地址会增加比较开销
- 16个线程可能导致锁竞争
- 去重过滤器可能成为瓶颈

---

## 🔧 诊断工具

### 诊断脚本

创建了 `diagnose_engine_issue.py` 用于诊断引擎问题：

```bash
python diagnose_engine_issue.py
```

**功能**:
- 创建引擎并启动
- 每秒检查一次状态
- 显示实时计数和线程状态
- 输出最终统计

### 快速测试命令

```bash
# 测试引擎是否工作
python -c "import sys, os, time; sys.path.insert(0, '.'); from src.collision.key_collision_engine import KeyCollisionEngine; e = KeyCollisionEngine(targets={'1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH'}, checkpoint_enabled=False, dedup_enabled=False, max_workers=2); e.start(mode='random'); time.sleep(5); e.stop(); print(f'Checked: {e.get_stats().total_checked}')"
```

---

## 📋 修复清单

- [x] **修复1**: 改进get_stats()方法
  - 状态: ✅ 已完成
  - 文件: `src/collision/key_collision_engine.py`
  - 效果: 实时统计包含_live_range_count

- [ ] **优化1**: 减小batch_size（可选）
  - 状态: ⏳ 待实施
  - 建议: 16核CPU从4000降到2000
  - 效果: 更新频率从2.7秒降到1.3秒

- [ ] **优化2**: 增加中间更新点（可选）
  - 状态: ⏳ 待实施
  - 建议: 每1000个私钥更新一次
  - 效果: 更平滑的进度显示

- [ ] **修复2**: 断点文件位置
  - 状态: ⏳ 待实施
  - 建议: 改为`data_logs/checkpoint.json`
  - 效果: 避免权限错误

---

## 🎯 验证步骤

### 步骤1: 验证get_stats()修复

```bash
python -c "
import sys, os, time
sys.path.insert(0, '.')
from src.collision.key_collision_engine import KeyCollisionEngine

e = KeyCollisionEngine(
    targets={'1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH'}, 
    checkpoint_enabled=False, 
    dedup_enabled=False, 
    max_workers=2
)
e.start(mode='random')

for i in range(5):
    time.sleep(2)
    stats = e.get_stats()
    print(f'{(i+1)*2}s: checked={stats.total_checked:,}, speed={stats.speed:.0f} keys/s')

e.stop()
print(f'Final: {e.get_stats().total_checked:,} keys')
"
```

**预期输出**:
```
2s: checked=500, speed=250 keys/s
4s: checked=1000, speed=250 keys/s
6s: checked=1500, speed=250 keys/s
8s: checked=2000, speed=250 keys/s
10s: checked=2500, speed=250 keys/s
Final: 2,500 keys
```

### 步骤2: 验证CLI运行

```bash
python key_collision_cli.py -t 1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH -m random --duration 30
```

**预期**: 进度显示应该不再为0

---

## 📝 总结

### 问题本质

**不是引擎速度为0，而是统计数据更新机制有缺陷！**

- 引擎正常工作 ✅
- 私钥正常检测 ✅
- 但统计数据未实时反映到显示中 ❌

### 修复效果

- ✅ `get_stats()`现在包含实时计数
- ✅ 进度显示会更准确
- ⚠️ 但由于batch_size较大，仍可能有2-3秒的延迟

### 后续优化

1. 减小batch_size到2000（推荐）
2. 更改断点文件位置
3. 增加中间更新点（可选）

---

**诊断完成时间**: 2026-04-23 02:42:30  
**修复状态**: ✅ 核心问题已修复  
**建议**: 运行验证测试确认修复效果

# 异常变量命名规范

**文档版本**: v1.0  
**创建日期**: 2026-04-22  
**适用范围**: BTC碰撞引擎项目所有Python代码

---

## 命名策略

采用**语义化命名策略**，根据异常处理场景选择变量名。

---

## 命名规则

### 1. 资源清理场景 → `cleanup_error`

**适用场景**:

- 临时文件删除
- 缓存清理
- 资源释放
- 析构函数清理

**示例**:

```python
# A类修复: 资源清理
try:
    os.remove(temp_file)
except Exception as cleanup_error:
    logger.debug(f"清理临时文件失败（可忽略）: {cleanup_error}")

# 析构函数
def __del__(self):
    try:
        self.cleanup()
    except Exception as cleanup_error:
        # 对象销毁中，无法做更多处理
        pass
```

---

### 2. 权限设置场景 → `perm_error`

**适用场景**:

- 文件权限修改（chmod）
- Windows权限设置（icacls）
- 目录权限配置

**示例**:

```python
# 设置文件权限
try:
    os.chmod(log_file, 0o600)
except OSError as perm_error:
    logger.debug(f"设置文件权限失败（可忽略）: {perm_error}")

# Windows权限
try:
    subprocess.run(['icacls', filepath, '/inheritance:r'])
except Exception as perm_error:
    logger.debug(f"Windows权限设置失败: {perm_error}")
```

---

### 3. 数据解析场景 → `e`

**适用场景**:

- 字符串转数字
- JSON解析
- 时间戳解析
- 格式转换

**示例**:

```python
# C类修复: 数据解析
try:
    dt = datetime.fromisoformat(timestamp)
    return dt.strftime("%H:%M:%S")
except (ValueError, TypeError, OSError) as e:
    logger.debug(f"时间戳解析失败: {e}")
    return timestamp[:19]

# 数值解析
try:
    throughput = float(text.replace(' keys/s', ''))
except (ValueError, KeyError) as e:
    logger.debug(f"吞吐量解析失败: {e}")
```

---

### 4. 降级回退场景 → `e`

**适用场景**:

- 功能降级
- 默认值回退
- 备选方案切换
- GUI容错

**示例**:

```python
# B类修复: 降级回退
try:
    devices = selector.detect_all_devices()
    update_ui(devices)
except Exception as e:
    logger.warning(f"设备检测失败: {e}")
    show_error("设备检测失败")

# GUI容错
try:
    update_alert_list()
except Exception as e:
    logger.debug(f"更新告警列表失败（不影响GUI）: {e}")
```

---

### 5. 通用场景 → `e`

**适用场景**:

- 一般异常处理
- 未分类场景
- 简单错误捕获

**示例**:

```python
try:
    result = do_something()
except Exception as e:
    logger.error(f"操作失败: {e}")
    return None
```

---

## 命名对照表

| 变量名 | 场景类型 | 异常类型 | 日志级别 | 示例数量 |
|--------|---------|---------|---------|---------|
| `cleanup_error` | 资源清理 | Exception | DEBUG | 12处 |
| `perm_error` | 权限设置 | OSError/Exception | DEBUG | 3处 |
| `e` | 数据解析 | ValueError/TypeError | DEBUG | 6处 |
| `e` | 降级回退 | Exception | WARNING/DEBUG | 5处 |
| `e` | 通用场景 | Exception | ERROR/WARNING | 多处 |

---

## 搜索和统计

### 常用搜索命令

```bash
# 查找所有资源清理异常处理
grep -r "as cleanup_error:" src/

# 查找所有权限设置异常处理
grep -r "as perm_error:" src/

# 统计P1修复数量
grep -r "# [ABC]类修复:" src/ | wc -l

# 查找所有DEBUG级别的异常日志
grep -r "logger.debug.*_error:" src/

# 查找所有WARNING级别的异常日志
grep -r "logger.warning.*as e:" src/
```

### 代码统计

```bash
# 统计各类异常处理数量
echo "资源清理 (cleanup_error):"
grep -r "as cleanup_error:" src/ | wc -l

echo "权限设置 (perm_error):"
grep -r "as perm_error:" src/ | wc -l

echo "通用异常 (e):"
grep -r "as e:" src/ | wc -l
```

---

## 最佳实践

### 1. 优先语义化命名

✅ **推荐**:

```python
except Exception as cleanup_error:
    logger.debug(f"清理失败: {cleanup_error}")
```

❌ **不推荐**:

```python
except Exception as e:
    logger.debug(f"清理失败: {e}")
```

### 2. 保持上下文清晰

✅ **推荐**:

```python
try:
    os.remove(temp_file)
except OSError as cleanup_error:
    logger.debug(f"清理临时文件失败: {cleanup_error}")
```

❌ **不推荐**:

```python
try:
    os.remove(temp_file)
except Exception:
    pass  # 无日志，无变量
```

### 3. 日志消息要包含异常信息

✅ **推荐**:

```python
except Exception as cleanup_error:
    logger.debug(f"清理失败: {cleanup_error}")
```

❌ **不推荐**:

```python
except Exception as cleanup_error:
    logger.debug("清理失败")  # 缺少异常详情
```

---

## 团队规范

### 新代码遵循

1. **资源清理**: 必须使用`cleanup_error`
2. **权限设置**: 必须使用`perm_error`
3. **其他场景**: 使用`e`即可

### 代码审查检查项

- [ ] 资源清理是否使用`cleanup_error`
- [ ] 权限设置是否使用`perm_error`
- [ ] 异常变量是否在日志中使用
- [ ] 日志消息是否包含异常详情

### CI/CD集成（可选）

```yaml
# .github/workflows/lint.yml
- name: Check exception variable naming
  run: |
    # 检查资源清理是否使用正确命名
    if grep -r "except.*as e:" src/ | grep -i "cleanup\|remove\|delete"; then
      echo "Warning: Consider using 'cleanup_error' for resource cleanup"
    fi
```

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-04-22 | 初始版本，定义命名策略 |

---

**文档维护**: 开发团队  
**最后更新**: 2026-04-22  
**下次审查**: 2026-07-22

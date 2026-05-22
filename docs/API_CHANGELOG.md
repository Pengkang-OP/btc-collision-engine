# API 变更日志

> **版本**: v4.5.1 | **最后更新**: 2026-05-22

本文档记录了项目公共 API 的变更历史，帮助用户了解 API 变更并及时迁移。

## 变更日志

### v4.5.1 (2026-05-21)

**新增 API**:
- `src/cli/_path_setup.py`: `ensure_project_root()` - 项目路径初始化工具
- `src/utils/sensitive_patterns.py`: 敏感数据正则模式共享模块
- `src/collision/__init__.py`: 新增 `container` 参数到 `create_collision_engine()`

**已弃用 API** (计划在 v5.0.0 移除):
- `key_collision.py` 中的回退实现（TargetResolver 等）
- `src/core/secp256k1.scalar_multiply()` - 使用 `scalar_multiply_const_time()` 替代
- `src/collision/target_resolver.py` - 使用 `src/collision/targets/resolver.py` 替代
- `src/collision/gpu_config_manager.py` - 配置已集成到主配置系统

**移除的 API**:
- `ThreadSafeLogger` - 使用推荐的日志配置 API 替代
- `src/collision/gpu_collision_engine.py` (Shim 层) - 直接使用 `src.collision.gpu.engine`

### v4.5.0 (2026-05-21)

**重构 API**:
- `RandomSearchMode` 迁移至 `src/gpu/search_modes/random_search.py`
- `GPUCollisionEngine.random_search()` 架构重构

### v4.4.0 (2026-05-18)

**变更 API**:
- `secure_key_context()` 返回类型从 `bytearray` 改为 `memoryview`
- `SecureKeyManager.get_key()` 返回 `memoryview`（只读）
- 新增 `get_key_copy()` 获取可写副本

**新增 API**:
- `SensitiveDataFilter` - 错误消息敏感数据过滤
- `SecureMemoryError` - 安全内存错误异常

### v4.3.0 (2026-05-18)

**新增 API**:
- `MultiFormatAddressGenerator` - 多格式地址生成器
- `FormatAwareTargetManager` - 格式感知目标管理器
- `check_match()` / `check_match_all()` - 格式匹配方法

### v3.5.0 (2026-04-30)

**新增 API**:
- `ConfigWatcher` - 配置热重载
- `NotificationChannel` 抽象基类 + 通道实现
- `GPUDeviceScorer` - GPU 设备评分统一

### v3.4.0 (2026-04-30)

**重构 API**:
- 向导模块解耦为核心策略组件
- GPU 引擎引入协议层架构

### v3.3.0 (2026-04-26)

**新增 API**:
- `AsyncExecutor` - GPU 异步执行器
- 双队列架构（计算队列 + 传输队列）

### 弃用策略

1. 弃用 API 会在当前大版本添加 `DeprecationWarning`
2. 弃用 API 会在下个大版本移除
3. 迁移指南会在 API 变更日志中提供

## 当前弃用项

| API | 弃用版本 | 计划移除版本 | 替代方案 |
|-----|---------|------------|---------|
| `key_collision.py` 回退实现 | v4.5.0 | v5.0.0 | `src/collision/targets/resolver.py` |
| `scalar_multiply()` | v4.5.0 | v5.0.0 | `scalar_multiply_const_time()` |
| `target_resolver.py` | v4.3.0 | v5.0.0 | `src.collision.targets.resolver` |
| `gpu_config_manager.py` | v4.5.0 | v5.0.0 | 主配置系统 |

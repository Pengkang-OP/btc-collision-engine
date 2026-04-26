
# 预分配功能启用建议

## 修改位置
文件: src/collision/gpu_collision_engine.py
行号: L1782之后

## 实施代码

```python
# 在内存池初始化后添加
if self._gpu_memory_pool:
    self._gpu_memory_pool.preallocate_buffers(
        sizes=[
            self.batch_size * 32,  # 私钥缓冲区
            self.batch_size * 4,   # 匹配缓冲区
        ],
        count_per_size=2
    )
    logger.info("✅ GPU内存池预分配完成")
```

## 预期收益
- 首次分配延迟: -50%
- 初始化性能: +20%

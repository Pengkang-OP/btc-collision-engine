# OpenCL 内核文件

## 文件说明

### btc_collision.cl
- **描述**: 主碰撞检测内核文件
- **包含内容**:
  - uint256/uint512数据类型定义
  - secp256k1常量（G点、素数P、曲线阶N）
  - uint256基础运算（加减乘除、比较、转换）
  - 模运算（模加、模减、模乘、模幂、模逆）
  - 椭圆曲线运算（点倍乘、点加法、标量乘法）
  - SHA-256哈希算法
  - RIPEMD-160哈希算法
  - Hash160组合函数
  - 三个内核函数：
    - `batch_check`: 批量碰撞检测
    - `verify_arithmetic`: 算术验证（计算2*G）
    - `debug_hash`: 哈希调试

## 技术特性

### Intel Arc 优化
- 使用`uint32`替代`uchar`传输私钥数据（避免global char* hang bug）
- 使用`ulong`算术避免signed long bug
- 保守编译选项确保稳定性

### 性能优化
- 批量处理：单次内核执行处理65536个私钥
- 持久化缓冲区：避免频繁内存分配
- 异步执行：保持GPU持续高负载

### 数学运算
- uint256使用8个uint32小端序存储
- 模P归约利用P = 2^256 - 2^32 - 977的特殊形式
- 模逆使用费马小定理：a^(-1) = a^(P-2) mod P

## 使用方式

内核源码已嵌入在 `src/gpu/kernel.py` 的 `OPENCL_KERNEL_SOURCE` 变量中，
运行时自动编译，无需手动加载.cl文件。

此目录的.cl文件仅供参考和调试使用。

## 编译选项

根据GPU厂商不同，编译选项会自动调整：
- **NVIDIA**: `-cl-fast-relaxed-math`
- **AMD**: `-cl-std=CL2.0`
- **Intel**: 保守选项（无优化标志）

## 验证

运行以下命令验证内核正确性：
```bash
python -c "from src.gpu.kernel import OPENCL_KERNEL_SOURCE; print(f'内核源码长度: {len(OPENCL_KERNEL_SOURCE)} 字符')"
```

## 相关文档

- [GPU模块迁移报告](../../docs/gpu-module-migration-report.md)
- [内核迁移完整性审查](../../docs/kernel-migration-completeness-review.md)
- [工作流图](../../docs/workflow_diagrams.md)
- [GPU操作流程图](../../docs/gpu-operation-flowchart.md)

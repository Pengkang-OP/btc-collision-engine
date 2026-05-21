#!/usr/bin/env python3
"""调试工具: 从kernel.py提取OpenCL内核源码到 scripts/kernels/ 目录

内核源码的唯一真实来源是 src/gpu/kernel.py 中的 OPENCL_KERNEL_SOURCE。
此脚本仅用于调试目的，将内嵌源码导出为 .cl 文件方便查看。
"""

import os
import sys

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

# 现在可以导入src模块
from src.gpu.kernel import OPENCL_KERNEL_SOURCE  # noqa: E402


def create_kernel_files():
    """创建OpenCL内核文件"""

    kernel_dir = os.path.join(os.path.dirname(__file__), "kernels")
    os.makedirs(kernel_dir, exist_ok=True)

    # 1. 创建主碰撞检测内核文件
    main_kernel_path = os.path.join(kernel_dir, "btc_collision.cl")
    with open(main_kernel_path, "w", encoding="utf-8") as f:
        f.write("""// ============================================================================
// 比特币 secp256k1 GPU 碰撞检测内核
// ============================================================================
//
// 文件: btc_collision.cl
// 描述: BTC碰撞引擎的核心OpenCL内核，实现批量私钥到地址的碰撞检测
// 版本: v4.2.2
//
// 核心功能:
// - 批量私钥处理（支持uint32优化，避免Intel Arc hang bug）
// - secp256k1椭圆曲线标量乘法
// - SHA-256 + RIPEMD-160 (Hash160) 哈希计算
// - 压缩公钥序列化
// - 目标地址匹配检测
//
// 内核函数:
// - batch_check: 主碰撞检测内核
// - verify_arithmetic: 算术验证内核（计算2*G）
// - debug_hash: 哈希调试内核
//
// 技术规格:
// - uint256使用8个uint32小端序存储
// - 私钥输入使用uint32数组（非uchar）以提升4倍性能
// - 支持最大65536个工作项并行
//
// 详细文档:
// - [内核迁移完整性审查报告](../../docs/kernel-migration-completeness-review.md)
// - [GPU模块迁移报告](../../docs/gpu-module-migration-report.md)
// - [工作流图](../../docs/workflow_diagrams.md)
// ============================================================================

""")
        f.write(OPENCL_KERNEL_SOURCE)

    print(f"✓ 已创建: {main_kernel_path}")
    print(f"  大小: {os.path.getsize(main_kernel_path)} 字节")
    with open(main_kernel_path, encoding="utf-8") as f:
        line_count = sum(1 for _ in f)
    print(f"  行数: {line_count} 行")

    # 2. 创建README说明文件
    readme_path = os.path.join(kernel_dir, "README.md")
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write("""# OpenCL 内核文件

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
python -c "from src.gpu.kernel import OPENCL_KERNEL_SOURCE; print(f'内核源码长度: {len(OPENCL_KERNEL_SOURCE)} 字符')"  # noqa: E501
```

## 相关文档

- [GPU模块迁移报告](../../docs/gpu-module-migration-report.md)
- [内核迁移完整性审查](../../docs/kernel-migration-completeness-review.md)
- [工作流图](../../docs/workflow_diagrams.md)
- [GPU操作流程图](../../docs/gpu-operation-flowchart.md)
""")

    print(f"✓ 已创建: {readme_path}")

    # 3. 验证内核源码
    print("\n验证内核源码...")
    print(f"  总字符数: {len(OPENCL_KERNEL_SOURCE)}")
    print(f"  包含内核函数: {OPENCL_KERNEL_SOURCE.count('__kernel')} 个")
    print(f"  包含批处理内核: {'batch_check' in OPENCL_KERNEL_SOURCE}")
    print(f"  包含验证内核: {'verify_arithmetic' in OPENCL_KERNEL_SOURCE}")
    print(f"  包含调试内核: {'debug_hash' in OPENCL_KERNEL_SOURCE}")

    # 4. 统计信息
    print("\n内核统计信息:")
    lines = OPENCL_KERNEL_SOURCE.split("\n")
    print(f"  总行数: {len(lines)}")
    print(f"  注释行数: {sum(1 for line in lines if line.strip().startswith('//'))}")
    print(f"  空行数: {sum(1 for line in lines if not line.strip())}")

    print("\n✅ OpenCL内核文件创建完成！")


if __name__ == "__main__":
    create_kernel_files()

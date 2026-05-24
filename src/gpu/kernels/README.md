# OpenCL 内核文件

## 文件说明

> **⚠️ 重要**: OpenCL 内核源码的真实来源是 `src/gpu/_kernel_source.py` 中的 `OPENCL_KERNEL_SOURCE` 字符串。
> `src/gpu/kernel.py` 在运行时从 `_kernel_source.py` 导入并提供回退/外部加载逻辑。
> 此目录存放独立的内核调试和验证用脚本以及外部化 `.cl` 文件。

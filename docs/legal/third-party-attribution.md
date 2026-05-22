# 第三方代码归属

> **版本**: v4.5.1 | **最后更新**: 2026-05-22

本文件记录了项目中使用到的第三方代码、库和资源的归属信息。

## 开源库

本项目依赖于以下开源库（按字母顺序排列）：

### 运行时依赖

| 库 | 许可证 | 版权 | 用途 |
|---|--------|------|------|
| `bech32` | MIT | © 2023 bech32 作者 | Bech32 地址编码/解码 |
| `bitarray` | Python-2.0 | © 2023 bitarray 作者 | 位操作优化 |
| `cachetools` | MIT | © 2023 cachetools 作者 | 缓存工具 |
| `cffi` | MIT | © 2023 cffi 作者 | C 外部函数接口 |
| `chardet` | LGPL-2.1 | © 2023 chardet 作者 | 字符编码检测 |
| `coincurve` | MIT | © 2023 coincurve 作者 | secp256k1 椭圆曲线库绑定 |
| `cryptography` | Apache-2.0 / BSD-3-Clause | © 2023 cryptography 作者 | 加密库 (OpenSSL 绑定) |
| `ecdsa` | MIT | © 2023 ecdsa 作者 | ECDSA 签名实现 |
| `gmpy2` | LGPL-3.0 | © 2023 gmpy2 作者 | 大整数运算优化 |
| `jsonschema` | MIT | © 2023 jsonschema 作者 | JSON Schema 验证 |
| `numpy` | BSD-3-Clause | © 2023 NumPy 作者 | 数值计算 |
| `psutil` | BSD-3-Clause | © 2023 psutil 作者 | 系统资源监控 |
| `pybloom-live` | LGPL-3.0 | © 2023 pybloom-live 作者 | Bloom 过滤器 |
| `pycryptodome` | BSD-3-Clause | © 2023 PyCryptodome 作者 | 加密算法实现 |
| `PyNaCl` | Apache-2.0 | © 2023 PyNaCl 作者 | libsodium 绑定 |
| `pyopencl` | MIT | © 2023 PyOpenCL 作者 | OpenCL GPU 计算 |
| `pywin32` | PSF | © 2023 pywin32 作者 | Windows API 绑定 |
| `requests` | Apache-2.0 | © 2023 requests 作者 | HTTP 客户端 |
| `rich` | MIT | © 2023 rich 作者 | 终端格式化输出 |
| `setproctitle` | BSD-3-Clause | © 2023 setproctitle 作者 | 进程名设置 |
| `nvidia-ml-py` | BSD-3-Clause | © 2023 NVIDIA 公司 | GPU 监控 |

### 开发依赖

| 库 | 许可证 | 版权 | 用途 |
|---|--------|------|------|
| `pytest` | MIT | © 2023 pytest 作者 | 测试框架 |
| `pytest-cov` | BSD-3-Clause | © 2023 pytest-cov 作者 | 测试覆盖率 |
| `pytest-benchmark` | BSD-2-Clause | © 2023 pytest-benchmark 作者 | 性能基准测试 |
| `mypy` | MIT | © 2023 mypy 作者 | 类型检查 |
| `bandit` | Apache-2.0 | © 2023 bandit 作者 | 安全扫描 |
| `black` | MIT | © 2023 black 作者 | 代码格式化 |
| `ruff` | MIT | © 2023 ruff 作者 | 代码规范检查 |
| `sphinx` | BSD-3-Clause | © 2023 Sphinx 作者 | 文档生成 |

## 第三方代码片段

本项目不包含直接复制粘贴的第三方代码片段。所有代码均为原创实现。

## 项目许可证

本项目本身使用 **MIT 许可证**，详见 [LICENSE](../../LICENSE)。

## 许可证义务

### 需保留版权声明的许可证

使用以下许可证的库需要在分发时保留原始版权声明：

- MIT 许可证所有库
- BSD-3-Clause 许可证所有库
- Apache-2.0 许可证所有库
- Python-2.0 许可证 (`bitarray`)

### 需提供修改声明的许可证

- LGPL-3.0 (`gmpy2`, `pybloom-live`): 动态链接使用，无需修改
- LGPL-2.1 (`chardet`): 动态链接使用，无需修改

## 相关文档

- [许可证兼容性](license-compatibility.md)
- [加密出口管制声明](export-control.md)

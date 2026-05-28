# 许可证兼容性报告

> **版本**: v4.5.1 | **最后更新**: 2026-05-22

## 项目许可证

本项目使用 **MIT 许可证** — 一种宽松许可证，允许商用、修改、分发和私人使用。

## 依赖许可证兼容性矩阵

| 依赖 | 版本范围 | 许可证 | 兼容性说明 |
|------|---------|--------|-----------|
| `coincurve` | >=18.0.0 | MIT | [OK] 完全兼容 |
| `gmpy2` | >=2.1.0,<5.0.0 | LGPL-3.0 | [OK] 动态链接兼容 |
| `pycryptodome` | >=3.19.0,<5.0.0 | BSD-3-Clause | [OK] 完全兼容 |
| `cryptography` | >=43.0.0,<46.0.0 | Apache-2.0 OR BSD-3-Clause | [OK] 完全兼容 |
| `PyNaCl` | >=1.5.0,<2.0.0 | Apache-2.0 | [OK] 完全兼容 |
| `cffi` | >=1.15.0 | MIT | [OK] 完全兼容 |
| `ecdsa` | >=0.18.0 | MIT | [OK] 完全兼容 |
| `numpy` | >=1.24.0 | BSD-3-Clause | [OK] 完全兼容 |
| `pyopencl` | >=2022.1 | MIT | [OK] 完全兼容 |
| `psutil` | >=5.9.0 | BSD-3-Clause | [OK] 完全兼容 |
| `requests` | >=2.28.0,<3.0.0 | Apache-2.0 | [OK] 完全兼容 |
| `bech32` | >=1.2.0 | MIT | [OK] 完全兼容 |
| `bitarray` | >=2.6.0 | Python-2.0 | [OK] 完全兼容 |
| `pybloom-live` | >=2.2.0 | LGPL-3.0 | [OK] 动态链接兼容 |
| `cachetools` | >=5.3.0 | MIT | [OK] 完全兼容 |
| `chardet` | >=5.0.0,<6.0.0 | LGPL-2.1 | [OK] 动态链接兼容 |
| `setproctitle` | >=1.3.0 | BSD-3-Clause | [OK] 完全兼容 |
| `jsonschema` | >=4.0.0 | MIT | [OK] 完全兼容 |
| `rich` | >=13.0 | MIT | [OK] 完全兼容 |
| `pywin32` | >=306 (Windows) | PSF | [OK] 完全兼容 |
| `nvidia-ml-py` | >=12.0.0 | BSD-3-Clause | [OK] 完全兼容 |

## 风险评估

### LGPL 依赖说明

项目依赖于以下 LGPL 许可证的库，均通过动态链接使用，符合 LGPL 要求：

1. **gmpy2** (LGPL-3.0): GMP/MPFR/MPC 的 Python 绑定，动态链接

2. **pybloom-live** (LGPL-3.0): Bloom 过滤器实现，动态链接

3. **chardet** (LGPL-2.1): 字符编码检测，动态链接

### 无 GPL 依赖

项目没有任何 GPL 许可证依赖，避免了"传染性"许可证风险。

## 许可证合规建议

1. 在分发二进制文件时，包含 MIT 许可证副本

2. 在文档中保留第三方版权声明

3. 定期审查依赖许可证变更

## 相关文档

- [加密出口管制声明](export-control.md)

- [第三方代码归属](third-party-attribution.md)

- [LICENSE](../../LICENSE)

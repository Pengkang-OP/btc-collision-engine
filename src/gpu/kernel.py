import os as _os
import pathlib

from ._kernel_source import OPENCL_KERNEL_SOURCE as _EMBEDDED_KERNEL_SOURCE

"""OpenCL kernel source code

Contains OpenCL kernel code for Bitcoin secp256k1 GPU computation.

## Core Features

- **Big integer ops**: uint256 add, sub, multiply, mod
- **Elliptic curve**: point double, point add, scalar multiply (secp256k1)
- **Hash algorithms**: SHA-256, RIPEMD-160, Hash160
- **Main kernels**: batch_check, verify_arithmetic, debug_hash

## P1-2 Fixes

- Implements GPUKernelProtocol interface
- Supports dependency injection and test mocking

## Known Fixes

- Intel Arc A770 compatibility: global char* hang bug, signed long bug

## Usage Example

```python
from src.gpu.kernel import OPENCL_KERNEL_SOURCE
import pyopencl as cl

program = cl.Program(context, OPENCL_KERNEL_SOURCE).build()
batch_check_kernel = program.batch_check
```

## Detailed Documentation

For complete technical specs, API docs and usage guide, see:
- [Kernel migration completeness review](../kernel-migration-completeness-review.md)
- [GPU module migration report](../gpu-module-migration-report.md)

## Technical Specs

- **Total lines**: ~1,635
- **Kernel functions**: 4 (__kernel: batch_check, batch_check_local_mem, debug_hash, verify_arithmetic)
- **Helper functions**: 30+ (uint256 ops, SHA-256, RIPEMD-160, EC point ops)
- **Constant definitions**: 30+ (including macros, curve params, hash constants)
"""


# P1-2 fix: implement interface

# ============================================================================
# Kernel version management
# ============================================================================
# Format: MAJOR.MINOR.PATCH
# - MAJOR: incompatible API/algorithm changes (e.g., coordinate system switch)
# - MINOR: new features backward-compatible (e.g., new kernel function)
# - PATCH: bug fixes, optimizations (e.g., macro refactoring)
KERNEL_VERSION = "4.2.2"
KERNEL_VERSION_TUPLE = (4, 2, 2)

# Maps versions to changelog entries for auditing
KERNEL_VERSION_HISTORY: list[dict[str, str]] = [
    {
        "version": "4.2.2",
        "date": "2026-05",
        "changes": (
            "P1 fix: mod_inverse Binary GCD 2^256 overflow compensation "
            "(lost carry broke Bezout invariant)"
        ),
    },
    {
        "version": "4.2.1",
        "date": "2026-05",
        "changes": (
            "Audit fixes: mod_inverse input validation, "
            "PRECOMP_TABLE constants, SCALAR_WINDOW constants"
        ),
    },
    {
        "version": "4.2.0",
        "date": "2026-05",
        "changes": (
            "Binary GCD mod_inverse; precomp table O(1) load; "
            "SHA-256 single-block fast path; RIPEMD-160 loop; "
            "Intel Arc compile strategy; batch_size 2M"
        ),
    },
    {
        "version": "4.1.0",
        "date": "2026-04",
        "changes": "HASH160_TARGET_SCAN macro; batch eviction optimizations; adaptive worker stats",
    },
    {
        "version": "4.0.0",
        "date": "2026-03",
        "changes": "PRNG seed mode; precomputed table from host; MSB-first windowed scalar",
    },
    {
        "version": "3.0.0",
        "date": "2025-12",
        "changes": "Jacobian coordinates; Intel Arc A770 compatibility fixes",
    },
    {
        "version": "2.0.0",
        "date": "2025-09",
        "changes": "batch_check_local_mem kernel; uint256_mod_p iterative reduction",
    },
    {
        "version": "1.0.0",
        "date": "2025-06",
        "changes": "Initial OpenCL kernel: secp256k1, SHA-256, RIPEMD-160, batch_check",
    },
]


def get_kernel_version() -> str:
    """获取当前内核版本号"""
    return KERNEL_VERSION


def get_kernel_version_tuple() -> tuple[int, int, int]:
    """获取当前内核版本号元组 (major, minor, patch)"""
    return KERNEL_VERSION_TUPLE


def validate_kernel_version(min_version: str) -> bool:
    """校验内核版本是否满足最低要求

    用于编译时检查：确保当前内核版本 >= 调用方要求的最低版本。

    Args:
        min_version: 最低版本要求，格式 "major.minor.patch"

    Returns:
        True 如果当前版本 >= 最低版本

    Raises:
        ValueError: 版本格式无效

    使用示例:
        >>> if not validate_kernel_version("4.0.0"):
        ...     raise RuntimeError("Kernel too old for precomputed table feature")

    """
    try:
        parts = min_version.split(".")
        if len(parts) != 3:
            raise ValueError(f"Invalid version format: {min_version}")
        min_tuple = (int(parts[0]), int(parts[1]), int(parts[2]))
    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid version format: {min_version}") from e

    return min_tuple <= KERNEL_VERSION_TUPLE


def get_version_changelog(version: str | None = None) -> list[dict[str, str]]:
    """获取内核版本变更日志

    Args:
        version: 指定版本号，为 None 时返回所有历史

    Returns:
        变更日志列表

    """
    if version is None:
        return KERNEL_VERSION_HISTORY.copy()
    return [e for e in KERNEL_VERSION_HISTORY if e["version"] == version]


def get_latest_compatible_version(
    current_version: str, available_versions: list[str],
) -> str | None:
    """查找最新兼容版本（用于回滚场景）

    给定当前版本和可用版本列表，返回可回退到的最高版本。

    Args:
        current_version: 当前版本号
        available_versions: 可用的历史版本列表

    Returns:
        最高兼容版本号，无可用版本时返回 None

    """
    try:
        cur = tuple(int(x) for x in current_version.split("."))
    except (ValueError, AttributeError):
        return None

    compatible = []
    for v in available_versions:
        try:
            parts = tuple(int(x) for x in v.split("."))
            if parts < cur:
                compatible.append((parts, v))
        except (ValueError, AttributeError):
            continue

    if not compatible:
        return None

    # 返回最高兼容版本
    compatible.sort(key=lambda x: x[0], reverse=True)
    return compatible[0][1]


# OpenCL kernel source extracted to _kernel_source.py (Task 8 refactor)
# P2修复: 内核代码外部化 — 运行时从独立 .cl 文件加载，回退到嵌入源码


def _load_kernel_source() -> str:
    """加载 OpenCL 内核源码

    优先从 src/gpu/kernels/batch_check.cl 加载，文件不存在时回退到嵌入源码。
    外部化 .cl 文件便于版本管理、语法高亮和独立测试。

    Returns:
        OpenCL 内核源码字符串

    """
    _kernel_dir = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "kernels")
    _kernel_file = _os.path.join(_kernel_dir, "batch_check.cl")
    try:
        if pathlib.Path(_kernel_file).exists():
            source = pathlib.Path(_kernel_file).read_text(encoding="utf-8")
            return source
    except OSError:
        pass
    # 回退到嵌入源码（使用 _EMBEDDED_KERNEL_SOURCE 避免自引用）
    return _EMBEDDED_KERNEL_SOURCE


# 运行时加载: 优先从外部 .cl 文件加载内核源码，回退到 _EMBEDDED_KERNEL_SOURCE
OPENCL_KERNEL_SOURCE = _load_kernel_source()

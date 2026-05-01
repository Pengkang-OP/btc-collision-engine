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

- **Total lines**: 1,045
- **Kernel source**: 34,758 chars / 1,035 lines
- **Kernel functions**: 3 (__kernel)
- **Helper functions**: 26
- **Constant definitions**: 20 (including macros)
"""

# flake8: noqa: W605

from typing import Optional, List, Dict, Tuple

# P1-2 fix: implement interface

# ============================================================================
# Kernel version management
# ============================================================================
# Format: MAJOR.MINOR.PATCH
# - MAJOR: incompatible API/algorithm changes (e.g., coordinate system switch)
# - MINOR: new features backward-compatible (e.g., new kernel function)
# - PATCH: bug fixes, optimizations (e.g., macro refactoring)
KERNEL_VERSION = "4.1.0"
KERNEL_VERSION_TUPLE = (4, 1, 0)

# Maps versions to changelog entries for auditing
KERNEL_VERSION_HISTORY: List[Dict[str, str]] = [
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


def get_kernel_version_tuple() -> Tuple[int, int, int]:
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

    return KERNEL_VERSION_TUPLE >= min_tuple


def get_version_changelog(version: Optional[str] = None) -> List[Dict[str, str]]:
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
    current_version: str, available_versions: List[str]
) -> Optional[str]:
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


# OpenCL kernel source code
OPENCL_KERNEL_SOURCE = """
// ============================================================================
// Bitcoin secp256k1 GPU computation kernel
// Kernel Version: 4.1.0 (MAJOR.MINOR.PATCH)
// Compile-time validation: #if KERNEL_VERSION_MAJOR < 4 ...
// ============================================================================

// Kernel version defines for compile-time feature gating
#define KERNEL_VERSION_MAJOR 4
#define KERNEL_VERSION_MINOR 1
#define KERNEL_VERSION_PATCH 0

// uint256 type: 8 x uint32, little-endian (d[0]=LSB, d[7]=MSB)
typedef struct {
    uint d[8];
} uint256_t;

// uint512 type: 16 x uint32, little-endian
typedef struct {
    uint d[16];
} uint512_t;

// ============================================================================
// secp256k1 constants (little-endian storage)
// ============================================================================

// Gx = 0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798
constant uint GX[8] = {0x16F81798, 0x59F2815B, 0x2DCE28D9, 0x029BFCDB, 0xCE870B07, 0x55A06295, 0xF9DCBBAC, 0x79BE667E};  # noqa: E501

// Gy = 0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8
constant uint GY[8] = {0xFB10D4B8, 0x9C47D08F, 0xA6855419, 0xFD17B448, 0x0E1108A8, 0x5DA4FBFC, 0x26A3C465, 0x483ADA77};  # noqa: E501

// P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
constant uint SECP256K1_P[8] = {0xFFFFFC2F, 0xFFFFFFFE, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF};  # noqa: E501

// N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141 (curve order)
constant uint SECP256K1_N[8] = {0xD0364141, 0xBFD25E8C, 0xAF48A03B, 0xBAAEDCE6, 0xFFFFFFFE, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF};  # noqa: E501

// Zero constant
constant uint ZERO[8] = {0, 0, 0, 0, 0, 0, 0, 0};

// ============================================================================
// uint256 basic operations
// ============================================================================

// Add with carry: result = a + b, returns carry
// Use ulong arithmetic to avoid carry detection errors
uint uint256_add(const uint256_t *a, const uint256_t *b, uint256_t *result) {
    ulong carry = 0;
    for (int i = 0; i < 8; i++) {
        ulong sum = (ulong)a->d[i] + (ulong)b->d[i] + carry;
        result->d[i] = (uint)sum;
        carry = sum >> 32;
    }
    return (uint)carry;
}

// Subtract with borrow: result = a - b, returns borrow
// Key: use ulong arithmetic to avoid signed long bug on Intel Arc
void uint256_sub(const uint256_t *a, const uint256_t *b, uint256_t *result, int *borrow) {
    *borrow = 0;
    for (int i = 0; i < 8; i++) {
        uint ai = a->d[i];
        uint bi = b->d[i];
        uint borrow_u = (uint)(*borrow);
        ulong need_borrow = ((ulong)ai < (ulong)bi + (ulong)borrow_u) ? 1UL : 0UL;
        result->d[i] = (uint)((ulong)ai - (ulong)bi - (ulong)borrow_u + (need_borrow << 32));
        *borrow = (int)need_borrow;
    }
}

// Compare a and b: returns -1 (a<b), 0 (a==b), 1 (a>b)
int uint256_cmp(const uint256_t *a, const uint256_t *b) {
    for (int i = 7; i >= 0; i--) {
        if (a->d[i] < b->d[i]) return -1;
        if (a->d[i] > b->d[i]) return 1;
    }
    return 0;
}

// Check if zero
int uint256_is_zero(const uint256_t *a) {
    for (int i = 0; i < 8; i++) {
        if (a->d[i] != 0) return 0;
    }
    return 1;
}

// Copy
void uint256_copy(const uint256_t *src, uint256_t *dst) {
    for (int i = 0; i < 8; i++) {
        dst->d[i] = src->d[i];
    }
}

// Set to zero
void uint256_set_zero(uint256_t *a) {
    for (int i = 0; i < 8; i++) {
        a->d[i] = 0;
    }
}

// GPU-side key generation: key = seed + global_id (256-bit addition)
// seed is passed as __constant uint[8] from host (big-endian uint32 array)
// Avoids large private_keys global buffer; host only sends 32-byte seed
void generate_private_key(__constant const uint *seed, ulong gid, uint256_t *k) {
    // Read seed (big-endian uint32 array -> little-endian uint256_t)
    uint256_t s;
    for (int i = 0; i < 8; i++) {
        s.d[7 - i] = seed[i];
    }
    // 256-bit addition: k = s + gid
    ulong carry = (ulong)s.d[0] + gid;
    k->d[0] = (uint)carry;
    carry >>= 32;
    for (int i = 1; i < 8; i++) {
        carry += (ulong)s.d[i];
        k->d[i] = (uint)carry;
        carry >>= 32;
    }
}

// Load from byte array (big-endian input -> little-endian uint256)
// Use __global address space qualifier for global memory access
// Fix: use uint* instead of uchar* to avoid Intel Arc A770 global char* hang bug
// Retained for potential future use; main kernels now use generate_private_key.
void uint256_from_bytes_global(__global const uint *bytes, uint256_t *result) {
    // bytes is now uint array, 8 uints = 32-byte private key
    for (int i = 0; i < 8; i++) {
        // Direct uint32 read, no byte assembly needed (4x perf gain)
        // Note: assumes x86_64 and GPU are both little-endian (true for all mainstream platforms)
        result->d[7 - i] = bytes[i];
    }
}

// Load from byte array (big-endian input -> little-endian uint256) - private memory version
void uint256_from_bytes(const uchar *bytes, uint256_t *result) {
    for (int i = 0; i < 8; i++) {
        result->d[7 - i] = ((uint)bytes[i * 4] << 24) |
                           ((uint)bytes[i * 4 + 1] << 16) |
                           ((uint)bytes[i * 4 + 2] << 8) |
                           ((uint)bytes[i * 4 + 3]);
    }
}

// Store to byte array (little-endian uint256 -> big-endian output)
void uint256_to_bytes(const uint256_t *a, uchar *bytes) {
    for (int i = 0; i < 8; i++) {
        bytes[i * 4] = (uchar)(a->d[7 - i] >> 24);
        bytes[i * 4 + 1] = (uchar)(a->d[7 - i] >> 16);
        bytes[i * 4 + 2] = (uchar)(a->d[7 - i] >> 8);
        bytes[i * 4 + 3] = (uchar)(a->d[7 - i]);
    }
}

// ============================================================================
// uint256 multiplication (512-bit result)
// ============================================================================

void uint256_mul(const uint256_t *a, const uint256_t *b, uint256_t *result_lo, uint256_t *result_hi) {  # noqa: E501
    uint512_t temp;

    // Initialize temp result to 0
    for (int i = 0; i < 16; i++) {
        temp.d[i] = 0;
    }

    // Multiply
    for (int i = 0; i < 8; i++) {
        uint carry = 0;
        for (int j = 0; j < 8; j++) {
            ulong prod = (ulong)a->d[i] * (ulong)b->d[j] + temp.d[i + j] + carry;
            temp.d[i + j] = (uint)prod;
            carry = (uint)(prod >> 32);
        }
        temp.d[i + 8] = carry;
    }

    // Copy results
    for (int i = 0; i < 8; i++) {
        result_lo->d[i] = temp.d[i];
        result_hi->d[i] = temp.d[i + 8];
    }
}

// ============================================================================
// Modular arithmetic mod secp256k1 prime P
// ============================================================================

// Reduce mod P: using special form 2^256 mod p = 2^32 + 977
// P = 2^256 - 2^32 - 977
// So 2^256 == 2^32 + 977 (mod P)
// For 512-bit x = x_low + x_high * 2^256:
// x mod P = (x_low + x_high * (2^32 + 977)) mod P
void uint256_mod_p(const uint256_t *a, uint256_t *result) {
    uint256_t r;
    uint256_copy(a, &r);

    // For 256-bit input, just ensure result < P
    // Since a is already 256-bit, at most one subtraction needed
    uint256_t p;
    for (int i = 0; i < 8; i++) p.d[i] = SECP256K1_P[i];

    // If r >= P, then r -= P
    if (uint256_cmp(&r, &p) >= 0) {
        int borrow;
        uint256_sub(&r, &p, &r, &borrow);
    }

    uint256_copy(&r, result);
}

// 512-bit mod P reduction: input is two 256-bit nums (lo, hi) representing lo + hi * 2^256
// Using special form P = 2^256 - 2^32 - 977
// hi * 2^256 + lo == hi * (2^32 + 977) + lo (mod P)
// Fix: properly handle hi->d[7] overflow and iterative reduction
void uint512_mod_p(const uint256_t *lo, const uint256_t *hi, uint256_t *result) {
    uint256_t p;
    for (int i = 0; i < 8; i++) p.d[i] = SECP256K1_P[i];

    // Current hi and lo
    uint256_t current_lo, current_hi;
    uint256_copy(lo, &current_lo);
    uint256_copy(hi, &current_hi);

    // Iterative reduction: hi * 2^256 == hi * (2^32 + 977) mod p
    // After each reduction the new 'hi' part gets smaller
    // At most 2-3 iterations needed
    for (int iter = 0; iter < 4 && !uint256_is_zero(&current_hi); iter++) {
        // Compute hi * 977
        uint256_t hi_977;
        uint256_set_zero(&hi_977);
        ulong carry_977 = 0;
        for (int i = 0; i < 8; i++) {
            ulong prod = (ulong)current_hi.d[i] * 977UL + carry_977;
            hi_977.d[i] = (uint)prod;
            carry_977 = prod >> 32;
        }

        // Compute hi << 32 (result = 256-bit part + overflow d[7])
        uint256_t hi_shifted;
        uint hi_overflow = current_hi.d[7];  // MSB shifted out
        hi_shifted.d[0] = 0;
        for (int i = 1; i < 8; i++) {
            hi_shifted.d[i] = current_hi.d[i - 1];
        }

        // hi_term = hi_shifted + hi_977
        uint256_t hi_term;
        ulong carry1 = (ulong)uint256_add(&hi_shifted, &hi_977, &hi_term);

        // new lo = current_lo + hi_term
        uint256_t new_lo;
        ulong carry2 = (ulong)uint256_add(&current_lo, &hi_term, &new_lo);

        // total overflow = carry_977 + hi_overflow + carry1 + carry2
        // These overflows represent (overflow) * 2^256, used as new hi
        ulong total_overflow = carry_977 + (ulong)hi_overflow + carry1 + carry2;

        uint256_copy(&new_lo, &current_lo);
        uint256_set_zero(&current_hi);
        current_hi.d[0] = (uint)total_overflow;
        current_hi.d[1] = (uint)(total_overflow >> 32);
    }

    // Final reduction: ensure result < P
    // May need to subtract P multiple times (at most 2-3)
    for (int i = 0; i < 3; i++) {
        if (uint256_cmp(&current_lo, &p) >= 0) {
            int borrow;
            uint256_sub(&current_lo, &p, &current_lo, &borrow);
        }
    }

    uint256_copy(&current_lo, result);
}

// Modular addition
void mod_add(const uint256_t *a, const uint256_t *b, uint256_t *result) {
    uint256_t sum;
    uint carry = uint256_add(a, b, &sum);

    // If overflow or sum >= P, subtract P
    uint256_t p;
    for (int i = 0; i < 8; i++) p.d[i] = SECP256K1_P[i];

    if (carry || uint256_cmp(&sum, &p) >= 0) {
        int borrow;
        uint256_sub(&sum, &p, result, &borrow);
    } else {
        uint256_copy(&sum, result);
    }
}

// Modular subtraction
void mod_sub(const uint256_t *a, const uint256_t *b, uint256_t *result) {
    uint256_t p;
    for (int i = 0; i < 8; i++) p.d[i] = SECP256K1_P[i];

    int borrow;
    uint256_sub(a, b, result, &borrow);

    if (borrow) {
        // Result is negative, add P
        uint256_add(result, &p, result);
    }
}

// Modular multiplication
void mod_mul(const uint256_t *a, const uint256_t *b, uint256_t *result) {
    uint256_t lo, hi;
    uint256_mul(a, b, &lo, &hi);

    // Use 512-bit mod reduction
    uint512_mod_p(&lo, &hi, result);
}

// Modular squaring
void mod_sqr(const uint256_t *a, uint256_t *result) {
    mod_mul(a, a, result);
}

// Modular inverse: a^(-1) mod P = a^(P-2) mod P (Fermat's little theorem)
// secp256k1 custom addition chain using special binary structure of P-2:
//   P-2 = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2D
//   bits 255..33: 223 ones
//   bit  32:      0
//   bits 31..10:  22 ones
//   bits 9..6:    0000
//   bit  5:       1
//   bit  4:       0
//   bits 3..2:    11
//   bit  1:       0
//   bit  0:       1
// Total: 255 sqr + 15 mul (vs generic mod_pow: 256 sqr + ~128 mul)
void mod_inverse(const uint256_t *a, uint256_t *result) {
    uint256_t x2, x3, x6, x9, x11, x22, x44, x88, x176, x220, x223, t1;
    int i;

    // x2 = a^(2^2-1) = a^3
    mod_sqr(a, &x2);           // a^2
    mod_mul(&x2, a, &x2);      // a^3

    // x3 = a^(2^3-1) = a^7
    mod_sqr(&x2, &x3);         // a^6
    mod_mul(&x3, a, &x3);      // a^7

    // x6 = a^(2^6-1)
    mod_sqr(&x3, &x6);
    mod_sqr(&x6, &x6);
    mod_sqr(&x6, &x6);
    mod_mul(&x6, &x3, &x6);

    // x9 = a^(2^9-1)
    mod_sqr(&x6, &x9);
    mod_sqr(&x9, &x9);
    mod_sqr(&x9, &x9);
    mod_mul(&x9, &x3, &x9);

    // x11 = a^(2^11-1)
    mod_sqr(&x9, &x11);
    mod_sqr(&x11, &x11);
    mod_mul(&x11, &x2, &x11);

    // x22 = a^(2^22-1)
    mod_sqr(&x11, &x22);
    for (i = 1; i < 11; i++) mod_sqr(&x22, &x22);
    mod_mul(&x22, &x11, &x22);

    // x44 = a^(2^44-1)
    mod_sqr(&x22, &x44);
    for (i = 1; i < 22; i++) mod_sqr(&x44, &x44);
    mod_mul(&x44, &x22, &x44);

    // x88 = a^(2^88-1)
    mod_sqr(&x44, &x88);
    for (i = 1; i < 44; i++) mod_sqr(&x88, &x88);
    mod_mul(&x88, &x44, &x88);

    // x176 = a^(2^176-1)
    mod_sqr(&x88, &x176);
    for (i = 1; i < 88; i++) mod_sqr(&x176, &x176);
    mod_mul(&x176, &x88, &x176);

    // x220 = a^(2^220-1)
    mod_sqr(&x176, &x220);
    for (i = 1; i < 44; i++) mod_sqr(&x220, &x220);
    mod_mul(&x220, &x44, &x220);

    // x223 = a^(2^223-1)
    mod_sqr(&x220, &x223);
    mod_sqr(&x223, &x223);
    mod_sqr(&x223, &x223);
    mod_mul(&x223, &x3, &x223);

    // Build remaining part of P-2 (bits 32..0)

    // bit32 = 0: sqr only
    mod_sqr(&x223, &t1);

    // bits 31..10: 22 ones: sqr 22 times then mul x22
    for (i = 0; i < 22; i++) mod_sqr(&t1, &t1);
    mod_mul(&t1, &x22, &t1);

    // bits 9..6: 0000: sqr 4 times
    mod_sqr(&t1, &t1);
    mod_sqr(&t1, &t1);
    mod_sqr(&t1, &t1);
    mod_sqr(&t1, &t1);

    // bit5 = 1
    mod_sqr(&t1, &t1);
    mod_mul(&t1, a, &t1);

    // bit4 = 0
    mod_sqr(&t1, &t1);

    // bits 3..2 = 11: sqr 2 times then mul x2 (= a^3)
    // Handle bit3=1: sqr+mul_a
    mod_sqr(&t1, &t1);
    mod_mul(&t1, a, &t1);
    // Handle bit2=1: sqr+mul_a
    mod_sqr(&t1, &t1);
    mod_mul(&t1, a, &t1);

    // bit1 = 0
    mod_sqr(&t1, &t1);

    // bit0 = 1
    mod_sqr(&t1, &t1);
    mod_mul(&t1, a, &t1);

    uint256_copy(&t1, result);
}

// ============================================================================
// Elliptic curve operations (secp256k1)
// ============================================================================

// ============================================================================
// Jacobian Coordinates point operations
// v3.0.0 opt: eliminate intermediate mod_inverse, greatly reduce computation
// Jacobian (X:Y:Z) maps to affine (X/Z^2, Y/Z^3)
// Point double: 11 mod_mul+5 mod_sqr (vs affine: 4 mod_mul+505 Modular multiplication/mod_inverse)
// Point add: 16 mod_mul+4 mod_sqr (vs affine: 5 mod_mul+505 Modular multiplication/mod_inverse)
// ============================================================================

// Jacobian point double: (Rx:Ry:Rz) = 2*(Px:Py:Pz)
// Standard Jacobian formula (secp256k1 a=0 optimized)
// Cost: 4 mod_sqr + 7 mod_mul (11 mod ops total, no mod_inverse)
// Note: input and output can be same variable (uses temp vars internally)
void jac_point_double(const uint256_t *px, const uint256_t *py, const uint256_t *pz,
                      uint256_t *rx, uint256_t *ry, uint256_t *rz) {
    // Point at infinity check: Z == 0
    if (uint256_is_zero(pz)) {
        uint256_set_zero(rx);
        uint256_set_zero(ry);
        uint256_set_zero(rz);
        return;
    }

    // Copy inputs to internal vars before computation (prevent input/output aliasing)
    uint256_t X, Y, Z;
    uint256_copy(px, &X);
    uint256_copy(py, &Y);
    uint256_copy(pz, &Z);

    uint256_t t1, t2, t3, t4, t5;
    uint256_t out_x, out_y, out_z;

    // Jacobian point double formula for secp256k1 a=0:
    // S = 4*X*Y^2
    // M = 3*X^2  (secp256k1 a=0, no a*Z^4 term needed)
    // X3 = M^2 - 2*S
    // Y3 = M*(S - X3) - 8*Y^4
    // Z3 = 2*Y*Z

    // t1 = Y^2
    mod_sqr(&Y, &t1);

    // t2 = X*Y^2 (X * t1)
    mod_mul(&X, &t1, &t2);

    // t3 = S = 4*X*Y^2 = 4*t2
    mod_add(&t2, &t2, &t3);  // t3 = 2*t2
    mod_add(&t3, &t3, &t3);  // t3 = 4*t2 = S

    // t4 = X^2
    mod_sqr(&X, &t4);

    // t5 = M = 3*X^2 = 3*t4
    mod_add(&t4, &t4, &t5);  // t5 = 2*t4
    mod_add(&t5, &t4, &t5);  // t5 = 3*t4 = M

    // out_x = M^2 - 2*S
    mod_sqr(&t5, &t4);        // t4 = M^2
    mod_add(&t3, &t3, &t2);   // t2 = 2*S
    mod_sub(&t4, &t2, &out_x);  // out_x = M^2 - 2*S = X3

    // out_z = 2*Y*Z
    mod_mul(&Y, &Z, &t4);     // t4 = Y*Z
    mod_add(&t4, &t4, &out_z); // out_z = 2*Y*Z = Z3

    // out_y = M*(S - X3) - 8*Y^4
    mod_sub(&t3, &out_x, &t4);  // t4 = S - X3
    mod_mul(&t5, &t4, &t3);     // t3 = M*(S - X3)
    mod_sqr(&t1, &t4);          // t4 = Y^4
    mod_add(&t4, &t4, &t2);     // t2 = 2*Y^4
    mod_add(&t2, &t2, &t2);     // t2 = 4*Y^4
    mod_add(&t2, &t2, &t2);     // t2 = 8*Y^4
    mod_sub(&t3, &t2, &out_y);  // out_y = M*(S-X3) - 8*Y^4 = Y3

    // Unified output assignment (safe even if input/output share address)
    uint256_copy(&out_x, rx);
    uint256_copy(&out_y, ry);
    uint256_copy(&out_z, rz);
}

// Jacobian mixed point addition: (Rx:Ry:Rz) = (P1x:P1y:P1z) + (P2x:P2y:1)
// P2 is affine (Z2=1), P1 is Jacobian
// Cost: 4 mod_sqr + 12 mod_mul (16 mod ops total, no mod_inverse)
// Note: input and output can be same variable (uses temp vars internally)
void jac_point_add_affine(const uint256_t *p1x, const uint256_t *p1y, const uint256_t *p1z,
                          const uint256_t *p2x, const uint256_t *p2y,
                          uint256_t *rx, uint256_t *ry, uint256_t *rz) {
    // Check if P1 is point at infinity: Z1 == 0
    if (uint256_is_zero(p1z)) {
        uint256_copy(p2x, rx);
        uint256_copy(p2y, ry);
        uint256_set_zero(rz);
        rz->d[0] = 1;  // Z=1 denotes affine point
        return;
    }

    // Copy inputs to internal vars (prevent aliasing)
    uint256_t X1, Y1, Z1;
    uint256_copy(p1x, &X1);
    uint256_copy(p1y, &Y1);
    uint256_copy(p1z, &Z1);

    uint256_t t1, t2, t3, t4, t5, t6;
    uint256_t out_x, out_y, out_z;

    // Mixed addition formula (P2 has Z2=1):
    // U2 = X2*Z1^2
    // S2 = Y2*Z1^3
    // H = U2 - X1
    // R = S2 - Y1
    // X3 = R^2 - H^3 - 2*X1*H^2
    // Y3 = R*(X1*H^2 - X3) - Y1*H^3
    // Z3 = H*Z1

    // t1 = Z1^2
    mod_sqr(&Z1, &t1);

    // t2 = U2 = X2 * Z1^2
    mod_mul(p2x, &t1, &t2);

    // t3 = Z1^3 = Z1 * Z1^2
    mod_mul(&Z1, &t1, &t3);

    // t4 = S2 = Y2 * Z1^3
    mod_mul(p2y, &t3, &t4);

    // t5 = H = U2 - X1
    mod_sub(&t2, &X1, &t5);

    // t6 = R = S2 - Y1
    mod_sub(&t4, &Y1, &t6);

    // Handle special case P1 == P2 (H==0, R==0 -> point double)
    if (uint256_is_zero(&t5) && uint256_is_zero(&t6)) {
        // P1 == P2, need point double
        // Convert P2 to Jacobian then double
        uint256_t one;
        uint256_set_zero(&one);
        one.d[0] = 1;
        jac_point_double(p2x, p2y, &one, rx, ry, rz);
        return;
    }

    // H == 0, R != 0 -> P1 == -P2, result is point at infinity
    if (uint256_is_zero(&t5)) {
        uint256_set_zero(rx);
        uint256_set_zero(ry);
        uint256_set_zero(rz);
        return;
    }

    // t1 = H^2
    mod_sqr(&t5, &t1);

    // t3 = H^3 = H * H^2
    mod_mul(&t5, &t1, &t3);

    // t2 = X1*H^2
    mod_mul(&X1, &t1, &t2);

    // out_x = R^2 - H^3 - 2*X1*H^2
    mod_sqr(&t6, &t4);          // t4 = R^2
    mod_sub(&t4, &t3, &t4);     // t4 = R^2 - H^3
    mod_add(&t2, &t2, &t1);     // t1 = 2*X1*H^2
    mod_sub(&t4, &t1, &out_x);  // out_x = R^2 - H^3 - 2*X1*H^2 = X3

    // out_y = R*(X1*H^2 - X3) - Y1*H^3
    mod_sub(&t2, &out_x, &t4);  // t4 = X1*H^2 - X3
    mod_mul(&t6, &t4, &t1);     // t1 = R*(X1*H^2 - X3)
    mod_mul(&Y1, &t3, &t4);     // t4 = Y1*H^3
    mod_sub(&t1, &t4, &out_y);  // out_y = R*(X1*H^2 - X3) - Y1*H^3 = Y3

    // out_z = H * Z1
    mod_mul(&t5, &Z1, &out_z);  // out_z = H*Z1 = Z3

    // Unified output assignment
    uint256_copy(&out_x, rx);
    uint256_copy(&out_y, ry);
    uint256_copy(&out_z, rz);
}

// Jacobian to affine: (X:Y:Z) -> (X/Z^2, Y/Z^3)
// Cost: 1 mod_inverse + 3 mod_mul
void jac_to_affine(const uint256_t *jx, const uint256_t *jy, const uint256_t *jz,
                   uint256_t *ax, uint256_t *ay) {
    uint256_t z_inv, z_inv2, z_inv3;

    // z_inv = Z^(-1)
    mod_inverse(jz, &z_inv);

    // z_inv2 = Z^(-2)
    mod_sqr(&z_inv, &z_inv2);

    // z_inv3 = Z^(-3) = Z^(-1) * Z^(-2)
    mod_mul(&z_inv, &z_inv2, &z_inv3);

    // ax = X * Z^(-2)
    mod_mul(jx, &z_inv2, ax);

    // ay = Y * Z^(-3)
    mod_mul(jy, &z_inv3, ay);
}

// Affine point double (for precomputed table generation)
void ec_point_double(const uint256_t *px, const uint256_t *py, uint256_t *rx, uint256_t *ry) {
    if (uint256_is_zero(py)) {
        uint256_set_zero(rx);
        uint256_set_zero(ry);
        return;
    }

    uint256_t lambda, temp1, temp2, temp3, two_y_inv;

    // lambda = (3*x^2) * (2*y)^(-1) mod p
    // secp256k1 has a = 0

    // temp1 = x^2
    mod_sqr(px, &temp1);

    // temp3 = 3*x^2 = x^2 + x^2 + x^2
    mod_add(&temp1, &temp1, &temp2);  // temp2 = 2*x^2
    mod_add(&temp2, &temp1, &temp3);  // temp3 = 3*x^2

    // temp2 = 2*y
    mod_add(py, py, &temp2);

    // two_y_inv = (2*y)^(-1)
    mod_inverse(&temp2, &two_y_inv);

    // lambda = 3*x^2 * (2*y)^(-1)
    mod_mul(&temp3, &two_y_inv, &lambda);

    // rx = lambda^2 - 2*x
    mod_sqr(&lambda, &temp1);  // temp1 = lambda^2
    mod_add(px, px, &temp2);   // temp2 = 2*x
    mod_sub(&temp1, &temp2, rx);  // rx = lambda^2 - 2*x

    // ry = lambda*(x - rx) - y
    mod_sub(px, rx, &temp2);   // temp2 = x - rx
    mod_mul(&lambda, &temp2, &temp1);  // temp1 = lambda*(x - rx)
    mod_sub(&temp1, py, ry);   // ry = lambda*(x - rx) - y
}

// Scalar multiply: R = k * G (Jacobian MSB-first windowed algorithm)
// v3.0.0 major optimizations:
//   1. Use Jacobian coords to eliminate intermediate mod_inverse (major speedup)
//   2. Fix algorithm: changed from LSB-first to correct MSB-first
// v4.0.0 optimizations:
//   3. Precomputed table passed from host, avoids redundant computation per thread
// Algorithm steps:
//   1. Read precomputed table[1G..31G] from __constant memory (affine coords)
//   2. Handle top 1 bit (bit255)
//   3. Loop 51 times: 5 Jacobian doubles then table lookup add (high to low)
//   4. Final conversion to affine (1 mod_inverse)
// precomp_table layout: [G1x(8 uint), G1y(8 uint), G2x(8 uint), G2y(8 uint), ..., G31x, G31y]
// Total: 31x2x8 = 496 uint32
void ec_scalar_multiply(const uint256_t *k,
                        __constant const uint *precomp_table,
                        uint256_t *rx, uint256_t *ry) {
    // Read precomputed table from __constant memory
    uint256_t precomp_x[31], precomp_y[31];
    for (int i = 0; i < 31; i++) {
        int offset = i * 16;  // Each point: 16 uints (x:8 + y:8)
        for (int j = 0; j < 8; j++) {
            precomp_x[i].d[j] = precomp_table[offset + j];
            precomp_y[i].d[j] = precomp_table[offset + 8 + j];
        }
    }

    // Jacobian result initialized to point at infinity
    uint256_t jac_x, jac_y, jac_z;
    uint256_t temp2x, temp2y;  // temp vars for double/add output
    uint256_set_zero(&jac_x);
    uint256_set_zero(&jac_y);
    uint256_set_zero(&jac_z);

    // MSB-first window algorithm (w=5)
    // 256-bit decomposed as: top 1 bit(bit255) + 51 groups of 5 bits(bits 254..0)
    // Order: bit255 first, then high to low in 5-bit groups

    // Step 1: Handle top bit (bit255)
    {
        // Get bit 255 of private key: bit 31 of k->d[7] (bit 255 = d[7]>>31)
        int top_bit = (int)((k->d[7] >> 31) & 1);
        if (top_bit) {
            uint256_copy(&precomp_x[0], &jac_x);
            uint256_copy(&precomp_y[0], &jac_y);
            // jac_z = 1 (affine point has Jacobian Z=1)
            uint256_set_zero(&jac_z);
            jac_z.d[0] = 1;
        }
        // top_bit==0: result remains point at infinity (jac_z=0)
    }

    // Step 2: Loop 51 groups, 5 bits each, high to low
    // grp=50: bits 254..250
    // grp=49: bits 249..245
    // ...
    // grp=0: bits 4..0
    for (int grp = 50; grp >= 0; grp--) {
        // Get 5-bit window value for group grp
        // bit range: grp*5+4 to grp*5
        // which uint32 contains grp*5: d[grp*5/32]
        int bit_start = grp * 5;  // lowest bit position
        int d_idx = bit_start / 32;
        int d_shift = bit_start % 32;

        // Extract 5 bits: may span two limbs
        int window;
        if (d_shift <= 27) {
            // All 5 bits in same limb
            window = (int)((k->d[d_idx] >> d_shift) & 0x1F);
        } else {
            // Spans two limbs
            uint lo = k->d[d_idx] >> d_shift;
            uint hi = (d_idx + 1 < 8) ? (k->d[d_idx + 1] << (32 - d_shift)) : 0;
            window = (int)((lo | hi) & 0x1F);
        }

        // 5 Jacobian point doubles (no mod_inverse!)
        for (int j = 0; j < 5; j++) {
            jac_point_double(&jac_x, &jac_y, &jac_z, &temp2x, &temp2y, &jac_z);
            uint256_copy(&temp2x, &jac_x);
            uint256_copy(&temp2y, &jac_y);
        }

        // Table lookup add (Jacobian+affine mixed, no mod_inverse!)
        if (window > 0) {
            int index = window - 1;
            jac_point_add_affine(&jac_x, &jac_y, &jac_z,
                                 &precomp_x[index], &precomp_y[index],
                                 &temp2x, &temp2y, &jac_z);
            uint256_copy(&temp2x, &jac_x);
            uint256_copy(&temp2y, &jac_y);
        }
    }

    // Final: Jacobian -> affine (1 mod_inverse)
    jac_to_affine(&jac_x, &jac_y, &jac_z, rx, ry);
}

// ============================================================================
// SHA-256 implementation
// ============================================================================

__constant uint SHA256_K[64] = {
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
};

#define SHA256_ROTR(x, n) (((x) >> (n)) | ((x) << (32 - (n))))
#define SHA256_CH(x, y, z) (((x) & (y)) ^ (~(x) & (z)))
#define SHA256_MAJ(x, y, z) (((x) & (y)) ^ ((x) & (z)) ^ ((y) & (z)))
#define SHA256_EP0(x) (SHA256_ROTR(x, 2) ^ SHA256_ROTR(x, 13) ^ SHA256_ROTR(x, 22))
#define SHA256_EP1(x) (SHA256_ROTR(x, 6) ^ SHA256_ROTR(x, 11) ^ SHA256_ROTR(x, 25))
#define SHA256_SIG0(x) (SHA256_ROTR(x, 7) ^ SHA256_ROTR(x, 18) ^ ((x) >> 3))
#define SHA256_SIG1(x) (SHA256_ROTR(x, 17) ^ SHA256_ROTR(x, 19) ^ ((x) >> 10))

void sha256_transform(uint *state, const uchar *data) {
    uint a, b, c, d, e, f, g, h;
    uint w[64];

    // Prepare message schedule
    for (int i = 0; i < 16; i++) {
        w[i] = ((uint)data[i * 4] << 24) | ((uint)data[i * 4 + 1] << 16) |
               ((uint)data[i * 4 + 2] << 8) | ((uint)data[i * 4 + 3]);
    }

    for (int i = 16; i < 64; i++) {
        w[i] = SHA256_SIG1(w[i - 2]) + w[i - 7] + SHA256_SIG0(w[i - 15]) + w[i - 16];
    }

    // Initialize working variables
    a = state[0];
    b = state[1];
    c = state[2];
    d = state[3];
    e = state[4];
    f = state[5];
    g = state[6];
    h = state[7];

    // 64 rounds of compression
    for (int i = 0; i < 64; i++) {
        uint t1 = h + SHA256_EP1(e) + SHA256_CH(e, f, g) + SHA256_K[i] + w[i];
        uint t2 = SHA256_EP0(a) + SHA256_MAJ(a, b, c);
        h = g;
        g = f;
        f = e;
        e = d + t1;
        d = c;
        c = b;
        b = a;
        a = t1 + t2;
    }

    // Update state
    state[0] += a;
    state[1] += b;
    state[2] += c;
    state[3] += d;
    state[4] += e;
    state[5] += f;
    state[6] += g;
    state[7] += h;
}

void sha256(const uchar *data, uint len, uchar *hash) {
    uint state[8] = {
        0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
        0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19
    };

    uchar buffer[64];
    uint buffer_len = 0;
    uint total_len = 0;

    // Process input data
    for (uint i = 0; i < len; i++) {
        buffer[buffer_len++] = data[i];
        total_len++;

        if (buffer_len == 64) {
            sha256_transform(state, buffer);
            buffer_len = 0;
        }
    }

    // Padding
    buffer[buffer_len++] = 0x80;

    if (buffer_len > 56) {
        while (buffer_len < 64) {
            buffer[buffer_len++] = 0;
        }
        sha256_transform(state, buffer);
        buffer_len = 0;
    }

    while (buffer_len < 56) {
        buffer[buffer_len++] = 0;
    }

    // Append length (bits)
    ulong bit_len = (ulong)total_len * 8;
    buffer[56] = (uchar)(bit_len >> 56);
    buffer[57] = (uchar)(bit_len >> 48);
    buffer[58] = (uchar)(bit_len >> 40);
    buffer[59] = (uchar)(bit_len >> 32);
    buffer[60] = (uchar)(bit_len >> 24);
    buffer[61] = (uchar)(bit_len >> 16);
    buffer[62] = (uchar)(bit_len >> 8);
    buffer[63] = (uchar)(bit_len);

    sha256_transform(state, buffer);

    // Output result (big-endian)
    for (int i = 0; i < 8; i++) {
        hash[i * 4] = (uchar)(state[i] >> 24);
        hash[i * 4 + 1] = (uchar)(state[i] >> 16);
        hash[i * 4 + 2] = (uchar)(state[i] >> 8);
        hash[i * 4 + 3] = (uchar)(state[i]);
    }
}

// ============================================================================
// RIPEMD-160 implementation (based on Bitcoin Core)
// ============================================================================

// RIPEMD-160 round constants (left: KL, right: KR), stored in __constant memory for performance
__constant uint RIPEMD160_KL[5] = {
    0x00000000,  // Left path round 1 (0-15)
    0x5a827999,  // Left path round 2 (16-31)
    0x6ed9eba1,  // Left path round 3 (32-47)
    0x8f1bbcdc,  // Left path round 4 (48-63)
    0xa953fd4e   // Left path round 5 (64-79)
};

__constant uint RIPEMD160_KR[5] = {
    0x50a28be6,  // Right path round 1 (0-15)
    0x5c4dd124,  // Right path round 2 (16-31)
    0x6d703ef3,  // Right path round 3 (32-47)
    0x7a6d76e9,  // Right path round 4 (48-63)
    0x00000000   // Right path round 5 (64-79)
};

#define RIPEMD160_ROTL(x, n) (((x) << (n)) | ((x) >> (32 - (n))))

// F functions
#define f0(x, y, z) ((x) ^ (y) ^ (z))
#define f1(x, y, z) (((x) & (y)) | (~(x) & (z)))
#define f2(x, y, z) (((x) | ~(y)) ^ (z))
#define f3(x, y, z) (((x) & (z)) | ((y) & ~(z)))
#define f4(x, y, z) ((x) ^ ((y) | ~(z)))

// Round function macro
#define ROL(a, b, c, d, e, f, k, r, s) \
    a = RIPEMD160_ROTL(a + f(b, c, d) + x[r] + k, s) + e; \
    c = RIPEMD160_ROTL(c, 10)

void ripemd160_transform(uint *state, const uchar *data) {
    uint x[16];
    for (int i = 0; i < 16; i++) {
        x[i] = ((uint)data[i * 4]) | ((uint)data[i * 4 + 1] << 8) |
               ((uint)data[i * 4 + 2] << 16) | ((uint)data[i * 4 + 3] << 24);
    }

    uint a1 = state[0], b1 = state[1], c1 = state[2], d1 = state[3], e1 = state[4];
    uint a2 = state[0], b2 = state[1], c2 = state[2], d2 = state[3], e2 = state[4];

    // Left path (using K values: 0, 1, 2, 3, 4)
    // Round 1 (0-15): F0, K0=0x00000000
    ROL(a1, b1, c1, d1, e1, f0, 0x00000000,  0, 11);
    ROL(e1, a1, b1, c1, d1, f0, 0x00000000,  1, 14);
    ROL(d1, e1, a1, b1, c1, f0, 0x00000000,  2, 15);
    ROL(c1, d1, e1, a1, b1, f0, 0x00000000,  3, 12);
    ROL(b1, c1, d1, e1, a1, f0, 0x00000000,  4,  5);
    ROL(a1, b1, c1, d1, e1, f0, 0x00000000,  5,  8);
    ROL(e1, a1, b1, c1, d1, f0, 0x00000000,  6,  7);
    ROL(d1, e1, a1, b1, c1, f0, 0x00000000,  7,  9);
    ROL(c1, d1, e1, a1, b1, f0, 0x00000000,  8, 11);
    ROL(b1, c1, d1, e1, a1, f0, 0x00000000,  9, 13);
    ROL(a1, b1, c1, d1, e1, f0, 0x00000000, 10, 14);
    ROL(e1, a1, b1, c1, d1, f0, 0x00000000, 11, 15);
    ROL(d1, e1, a1, b1, c1, f0, 0x00000000, 12,  6);
    ROL(c1, d1, e1, a1, b1, f0, 0x00000000, 13,  7);
    ROL(b1, c1, d1, e1, a1, f0, 0x00000000, 14,  9);
    ROL(a1, b1, c1, d1, e1, f0, 0x00000000, 15,  8);

    // Round 2 (16-31): F1, K1=0x5a827999
    ROL(e1, a1, b1, c1, d1, f1, 0x5a827999,  7,  7);
    ROL(d1, e1, a1, b1, c1, f1, 0x5a827999,  4,  6);
    ROL(c1, d1, e1, a1, b1, f1, 0x5a827999, 13,  8);
    ROL(b1, c1, d1, e1, a1, f1, 0x5a827999,  1, 13);
    ROL(a1, b1, c1, d1, e1, f1, 0x5a827999, 10, 11);
    ROL(e1, a1, b1, c1, d1, f1, 0x5a827999,  6,  9);
    ROL(d1, e1, a1, b1, c1, f1, 0x5a827999, 15,  7);
    ROL(c1, d1, e1, a1, b1, f1, 0x5a827999,  3, 15);
    ROL(b1, c1, d1, e1, a1, f1, 0x5a827999, 12,  7);
    ROL(a1, b1, c1, d1, e1, f1, 0x5a827999,  0, 12);
    ROL(e1, a1, b1, c1, d1, f1, 0x5a827999,  9, 15);
    ROL(d1, e1, a1, b1, c1, f1, 0x5a827999,  5,  9);
    ROL(c1, d1, e1, a1, b1, f1, 0x5a827999,  2, 11);
    ROL(b1, c1, d1, e1, a1, f1, 0x5a827999, 14,  7);
    ROL(a1, b1, c1, d1, e1, f1, 0x5a827999, 11, 13);
    ROL(e1, a1, b1, c1, d1, f1, 0x5a827999,  8, 12);

    // Round 3 (32-47): F2, K2=0x6ed9eba1
    ROL(d1, e1, a1, b1, c1, f2, 0x6ed9eba1,  3, 11);
    ROL(c1, d1, e1, a1, b1, f2, 0x6ed9eba1, 10, 13);
    ROL(b1, c1, d1, e1, a1, f2, 0x6ed9eba1, 14,  6);
    ROL(a1, b1, c1, d1, e1, f2, 0x6ed9eba1,  4,  7);
    ROL(e1, a1, b1, c1, d1, f2, 0x6ed9eba1,  9, 14);
    ROL(d1, e1, a1, b1, c1, f2, 0x6ed9eba1, 15,  9);
    ROL(c1, d1, e1, a1, b1, f2, 0x6ed9eba1,  8, 13);
    ROL(b1, c1, d1, e1, a1, f2, 0x6ed9eba1,  1, 15);
    ROL(a1, b1, c1, d1, e1, f2, 0x6ed9eba1,  2, 14);
    ROL(e1, a1, b1, c1, d1, f2, 0x6ed9eba1,  7,  8);
    ROL(d1, e1, a1, b1, c1, f2, 0x6ed9eba1,  0, 13);
    ROL(c1, d1, e1, a1, b1, f2, 0x6ed9eba1,  6,  6);
    ROL(b1, c1, d1, e1, a1, f2, 0x6ed9eba1, 13,  5);
    ROL(a1, b1, c1, d1, e1, f2, 0x6ed9eba1, 11, 12);
    ROL(e1, a1, b1, c1, d1, f2, 0x6ed9eba1,  5,  7);
    ROL(d1, e1, a1, b1, c1, f2, 0x6ed9eba1, 12,  5);

    // Round 4 (48-63): F3, K3=0x8f1bbcdc
    ROL(c1, d1, e1, a1, b1, f3, 0x8f1bbcdc,  1, 11);
    ROL(b1, c1, d1, e1, a1, f3, 0x8f1bbcdc,  9, 12);
    ROL(a1, b1, c1, d1, e1, f3, 0x8f1bbcdc, 11, 14);
    ROL(e1, a1, b1, c1, d1, f3, 0x8f1bbcdc, 10, 15);
    ROL(d1, e1, a1, b1, c1, f3, 0x8f1bbcdc,  0, 14);
    ROL(c1, d1, e1, a1, b1, f3, 0x8f1bbcdc,  8, 15);
    ROL(b1, c1, d1, e1, a1, f3, 0x8f1bbcdc, 12,  9);
    ROL(a1, b1, c1, d1, e1, f3, 0x8f1bbcdc,  4,  8);
    ROL(e1, a1, b1, c1, d1, f3, 0x8f1bbcdc, 13,  9);
    ROL(d1, e1, a1, b1, c1, f3, 0x8f1bbcdc,  3, 14);
    ROL(c1, d1, e1, a1, b1, f3, 0x8f1bbcdc,  7,  5);
    ROL(b1, c1, d1, e1, a1, f3, 0x8f1bbcdc, 15,  6);
    ROL(a1, b1, c1, d1, e1, f3, 0x8f1bbcdc, 14,  8);
    ROL(e1, a1, b1, c1, d1, f3, 0x8f1bbcdc,  5,  6);
    ROL(d1, e1, a1, b1, c1, f3, 0x8f1bbcdc,  6,  5);
    ROL(c1, d1, e1, a1, b1, f3, 0x8f1bbcdc,  2, 12);

    // Round 5 (64-79): F4, K4=0xa953fd4e
    ROL(b1, c1, d1, e1, a1, f4, 0xa953fd4e,  4,  9);
    ROL(a1, b1, c1, d1, e1, f4, 0xa953fd4e,  0, 15);
    ROL(e1, a1, b1, c1, d1, f4, 0xa953fd4e,  5,  5);
    ROL(d1, e1, a1, b1, c1, f4, 0xa953fd4e,  9, 11);
    ROL(c1, d1, e1, a1, b1, f4, 0xa953fd4e,  7,  6);
    ROL(b1, c1, d1, e1, a1, f4, 0xa953fd4e, 12,  8);
    ROL(a1, b1, c1, d1, e1, f4, 0xa953fd4e,  2, 13);
    ROL(e1, a1, b1, c1, d1, f4, 0xa953fd4e, 10, 12);
    ROL(d1, e1, a1, b1, c1, f4, 0xa953fd4e, 14,  5);
    ROL(c1, d1, e1, a1, b1, f4, 0xa953fd4e,  1, 12);
    ROL(b1, c1, d1, e1, a1, f4, 0xa953fd4e,  3, 13);
    ROL(a1, b1, c1, d1, e1, f4, 0xa953fd4e,  8, 14);
    ROL(e1, a1, b1, c1, d1, f4, 0xa953fd4e, 11, 11);
    ROL(d1, e1, a1, b1, c1, f4, 0xa953fd4e,  6,  8);
    ROL(c1, d1, e1, a1, b1, f4, 0xa953fd4e, 15,  5);
    ROL(b1, c1, d1, e1, a1, f4, 0xa953fd4e, 13,  6);

    // Right path (using K' values, note reversed order)
    // Right path round 1 (0-15): F4, K0'=0x50a28be6
    ROL(a2, b2, c2, d2, e2, f4, 0x50a28be6,  5,  8);
    ROL(e2, a2, b2, c2, d2, f4, 0x50a28be6, 14,  9);
    ROL(d2, e2, a2, b2, c2, f4, 0x50a28be6,  7,  9);
    ROL(c2, d2, e2, a2, b2, f4, 0x50a28be6,  0, 11);
    ROL(b2, c2, d2, e2, a2, f4, 0x50a28be6,  9, 13);
    ROL(a2, b2, c2, d2, e2, f4, 0x50a28be6,  2, 15);
    ROL(e2, a2, b2, c2, d2, f4, 0x50a28be6, 11, 15);
    ROL(d2, e2, a2, b2, c2, f4, 0x50a28be6,  4,  5);
    ROL(c2, d2, e2, a2, b2, f4, 0x50a28be6, 13,  7);
    ROL(b2, c2, d2, e2, a2, f4, 0x50a28be6,  6,  7);
    ROL(a2, b2, c2, d2, e2, f4, 0x50a28be6, 15,  8);
    ROL(e2, a2, b2, c2, d2, f4, 0x50a28be6,  8, 11);
    ROL(d2, e2, a2, b2, c2, f4, 0x50a28be6,  1, 14);
    ROL(c2, d2, e2, a2, b2, f4, 0x50a28be6, 10, 14);
    ROL(b2, c2, d2, e2, a2, f4, 0x50a28be6,  3, 12);
    ROL(a2, b2, c2, d2, e2, f4, 0x50a28be6, 12,  6);

    // Right path round 2 (16-31): F3, K1'=0x5c4dd124
    ROL(e2, a2, b2, c2, d2, f3, 0x5c4dd124,  6,  9);
    ROL(d2, e2, a2, b2, c2, f3, 0x5c4dd124, 11, 13);
    ROL(c2, d2, e2, a2, b2, f3, 0x5c4dd124,  3, 15);
    ROL(b2, c2, d2, e2, a2, f3, 0x5c4dd124,  7,  7);
    ROL(a2, b2, c2, d2, e2, f3, 0x5c4dd124,  0, 12);
    ROL(e2, a2, b2, c2, d2, f3, 0x5c4dd124, 13,  8);
    ROL(d2, e2, a2, b2, c2, f3, 0x5c4dd124,  5,  9);
    ROL(c2, d2, e2, a2, b2, f3, 0x5c4dd124, 10, 11);
    ROL(b2, c2, d2, e2, a2, f3, 0x5c4dd124, 14,  7);
    ROL(a2, b2, c2, d2, e2, f3, 0x5c4dd124, 15,  7);
    ROL(e2, a2, b2, c2, d2, f3, 0x5c4dd124,  8, 12);
    ROL(d2, e2, a2, b2, c2, f3, 0x5c4dd124, 12,  7);
    ROL(c2, d2, e2, a2, b2, f3, 0x5c4dd124,  4,  6);
    ROL(b2, c2, d2, e2, a2, f3, 0x5c4dd124,  9, 15);
    ROL(a2, b2, c2, d2, e2, f3, 0x5c4dd124,  1, 13);
    ROL(e2, a2, b2, c2, d2, f3, 0x5c4dd124,  2, 11);

    // Right path round 3 (32-47): F2, K2'=0x6d703ef3
    ROL(d2, e2, a2, b2, c2, f2, 0x6d703ef3, 15,  9);
    ROL(c2, d2, e2, a2, b2, f2, 0x6d703ef3,  5,  7);
    ROL(b2, c2, d2, e2, a2, f2, 0x6d703ef3,  1, 15);
    ROL(a2, b2, c2, d2, e2, f2, 0x6d703ef3,  3, 11);
    ROL(e2, a2, b2, c2, d2, f2, 0x6d703ef3,  7,  8);
    ROL(d2, e2, a2, b2, c2, f2, 0x6d703ef3, 14,  6);
    ROL(c2, d2, e2, a2, b2, f2, 0x6d703ef3,  6,  6);
    ROL(b2, c2, d2, e2, a2, f2, 0x6d703ef3,  9, 14);
    ROL(a2, b2, c2, d2, e2, f2, 0x6d703ef3, 11, 12);
    ROL(e2, a2, b2, c2, d2, f2, 0x6d703ef3,  8, 13);
    ROL(d2, e2, a2, b2, c2, f2, 0x6d703ef3, 12,  5);
    ROL(c2, d2, e2, a2, b2, f2, 0x6d703ef3,  2, 14);
    ROL(b2, c2, d2, e2, a2, f2, 0x6d703ef3, 10, 13);
    ROL(a2, b2, c2, d2, e2, f2, 0x6d703ef3,  0, 13);
    ROL(e2, a2, b2, c2, d2, f2, 0x6d703ef3,  4,  7);
    ROL(d2, e2, a2, b2, c2, f2, 0x6d703ef3, 13,  5);

    // Right path round 4 (48-63): F1, K3'=0x7a6d76e9
    ROL(c2, d2, e2, a2, b2, f1, 0x7a6d76e9,  8, 15);
    ROL(b2, c2, d2, e2, a2, f1, 0x7a6d76e9,  6,  5);
    ROL(a2, b2, c2, d2, e2, f1, 0x7a6d76e9,  4,  8);
    ROL(e2, a2, b2, c2, d2, f1, 0x7a6d76e9,  1, 11);
    ROL(d2, e2, a2, b2, c2, f1, 0x7a6d76e9,  3, 14);
    ROL(c2, d2, e2, a2, b2, f1, 0x7a6d76e9, 11, 14);
    ROL(b2, c2, d2, e2, a2, f1, 0x7a6d76e9, 15,  6);
    ROL(a2, b2, c2, d2, e2, f1, 0x7a6d76e9,  0, 14);
    ROL(e2, a2, b2, c2, d2, f1, 0x7a6d76e9,  5,  6);
    ROL(d2, e2, a2, b2, c2, f1, 0x7a6d76e9, 12,  9);
    ROL(c2, d2, e2, a2, b2, f1, 0x7a6d76e9,  2, 12);
    ROL(b2, c2, d2, e2, a2, f1, 0x7a6d76e9, 13,  9);
    ROL(a2, b2, c2, d2, e2, f1, 0x7a6d76e9,  9, 12);
    ROL(e2, a2, b2, c2, d2, f1, 0x7a6d76e9,  7,  5);
    ROL(d2, e2, a2, b2, c2, f1, 0x7a6d76e9, 10, 15);
    ROL(c2, d2, e2, a2, b2, f1, 0x7a6d76e9, 14,  8);

    // Right path round 5 (64-79): F0, K4'=0x00000000
    ROL(b2, c2, d2, e2, a2, f0, 0x00000000, 12,  8);
    ROL(a2, b2, c2, d2, e2, f0, 0x00000000, 15,  5);
    ROL(e2, a2, b2, c2, d2, f0, 0x00000000, 10, 12);
    ROL(d2, e2, a2, b2, c2, f0, 0x00000000,  4,  9);
    ROL(c2, d2, e2, a2, b2, f0, 0x00000000,  1, 12);
    ROL(b2, c2, d2, e2, a2, f0, 0x00000000,  5,  5);
    ROL(a2, b2, c2, d2, e2, f0, 0x00000000,  8, 14);
    ROL(e2, a2, b2, c2, d2, f0, 0x00000000,  7,  6);
    ROL(d2, e2, a2, b2, c2, f0, 0x00000000,  6,  8);
    ROL(c2, d2, e2, a2, b2, f0, 0x00000000,  2, 13);
    ROL(b2, c2, d2, e2, a2, f0, 0x00000000, 13,  6);
    ROL(a2, b2, c2, d2, e2, f0, 0x00000000, 14,  5);
    ROL(e2, a2, b2, c2, d2, f0, 0x00000000,  0, 15);
    ROL(d2, e2, a2, b2, c2, f0, 0x00000000,  3, 13);
    ROL(c2, d2, e2, a2, b2, f0, 0x00000000,  9, 11);
    ROL(b2, c2, d2, e2, a2, f0, 0x00000000, 11, 11);

    // Combine results
    uint t = state[1] + c1 + d2;
    state[1] = state[2] + d1 + e2;
    state[2] = state[3] + e1 + a2;
    state[3] = state[4] + a1 + b2;
    state[4] = state[0] + b1 + c2;
    state[0] = t;
}

void ripemd160(const uchar *data, uint len, uchar *hash) {
    uint state[5] = {0x67452301, 0xEFCDAB89, 0x98BADCFE, 0x10325476, 0xC3D2E1F0};

    uchar buffer[64];
    uint buffer_len = 0;
    uint total_len = 0;

    // Process input data
    for (uint i = 0; i < len; i++) {
        buffer[buffer_len++] = data[i];
        total_len++;

        if (buffer_len == 64) {
            ripemd160_transform(state, buffer);
            buffer_len = 0;
        }
    }

    // Padding
    buffer[buffer_len++] = 0x80;

    if (buffer_len > 56) {
        while (buffer_len < 64) {
            buffer[buffer_len++] = 0;
        }
        ripemd160_transform(state, buffer);
        buffer_len = 0;
    }

    while (buffer_len < 56) {
        buffer[buffer_len++] = 0;
    }

    // Append length (bits, little-endian)
    ulong bit_len = (ulong)total_len * 8;
    buffer[56] = (uchar)(bit_len);
    buffer[57] = (uchar)(bit_len >> 8);
    buffer[58] = (uchar)(bit_len >> 16);
    buffer[59] = (uchar)(bit_len >> 24);
    buffer[60] = (uchar)(bit_len >> 32);
    buffer[61] = (uchar)(bit_len >> 40);
    buffer[62] = (uchar)(bit_len >> 48);
    buffer[63] = (uchar)(bit_len >> 56);

    ripemd160_transform(state, buffer);

    // Output result (little-endian)
    for (int i = 0; i < 5; i++) {
        hash[i * 4] = (uchar)(state[i]);
        hash[i * 4 + 1] = (uchar)(state[i] >> 8);
        hash[i * 4 + 2] = (uchar)(state[i] >> 16);
        hash[i * 4 + 3] = (uchar)(state[i] >> 24);
    }
}

// ============================================================================
// Hash160: RIPEMD160(SHA256(data))
// ============================================================================

void hash160(const uchar *data, uint len, uchar *result) {
    uchar sha256_hash[32];
    sha256(data, len, sha256_hash);
    ripemd160(sha256_hash, 32, result);
}

// ============================================================================
// Main kernel: batch check private keys
// ============================================================================

// Macro: Hash160 target scan with progressive early-exit (uint32 vectorized, 5 uint compares)
// Eliminates code duplication between batch_check and batch_check_local_mem.
// Parameters:
//   src_base  - pointer to array of 20-byte Hash160 entries (local or global memory)
//   h0..h4    - pre-assembled hash160_result as 5 uint32 (little-endian)
//   n_targets - number of target entries
//   match     - int variable (will be set to target_index+1 on match, 0 otherwise)
#define HASH160_TARGET_SCAN(src_base, h0, h1, h2, h3, h4, n_targets, match) \
do { \
    for (uint _t = 0; _t < (n_targets) && (match) == 0; _t++) { \
        const uchar *_src = (src_base) + _t * 20u; \
        uint _t0 = (uint)_src[0]  | ((uint)_src[1]  << 8) | ((uint)_src[2]  << 16) | ((uint)_src[3]  << 24); \  # noqa: E501, W605
        if (_t0 != (h0)) continue; \
        uint _t1 = (uint)_src[4]  | ((uint)_src[5]  << 8) | ((uint)_src[6]  << 16) | ((uint)_src[7]  << 24); \  # noqa: E501, W605
        if (_t1 != (h1)) continue; \
        uint _t2 = (uint)_src[8]  | ((uint)_src[9]  << 8) | ((uint)_src[10] << 16) | ((uint)_src[11] << 24); \  # noqa: E501, W605
        if (_t2 != (h2)) continue; \
        uint _t3 = (uint)_src[12] | ((uint)_src[13] << 8) | ((uint)_src[14] << 16) | ((uint)_src[15] << 24); \  # noqa: E501, W605
        if (_t3 != (h3)) continue; \
        uint _t4 = (uint)_src[16] | ((uint)_src[17] << 8) | ((uint)_src[18] << 16) | ((uint)_src[19] << 24); \  # noqa: E501, W605
        if (_t4 != (h4)) continue; \
        match = (int)(_t + 1); \
    } \
} while(0)

__kernel void batch_check(
    __constant const uint *seed,            // 32-byte seed (8 uint32, big-endian); key = seed + gid
    const uint num_keys,
    __global const uchar *target_hash160s,  // Input: num_targets * 20 bytes
    const uint num_targets,
    __global int *match_flags,              // Output: num_keys flags (0=no match, target_index+1=match)  # noqa: E501
    const uint check_uncompressed,          // v4.0: 0=compressed only, 1=also check uncompressed format  # noqa: E501
    __constant const uint *precomp_table    // Precomputed table: 31x2x8 = 496 uint32 (G1..G31 affine)  # noqa: E501
) {
    // P1-2 fix: ulong gid prevents 32-bit overflow when batch_size >= 2^32
    ulong gid = get_global_id(0);
    if (gid >= num_keys) return;

    // Generate private key on GPU: k = seed + gid (256-bit addition)
    uint256_t k;
    generate_private_key(seed, gid, &k);

    // P1-3 fix: Validate private key range (1 <= k < N)
    // Previously only checked k==0, missing k >= N check.
    // k >= N would produce a point on the curve but with incorrect discrete log.
    uint256_t n_val;
    for (int i = 0; i < 8; i++) n_val.d[i] = SECP256K1_N[i];
    if (uint256_is_zero(&k) || uint256_cmp(&k, &n_val) >= 0) {
        match_flags[gid] = 0;
        return;
    }

    // Scalar multiply: Q = k * G
    uint256_t qx, qy;
    ec_scalar_multiply(&k, precomp_table, &qx, &qy);

    // Serialize compressed public key (0x02/0x03 + x)
    uchar pubkey[33];
    // Check y parity (look at lowest bit of lowest limb)
    if (qy.d[0] & 1) {
        pubkey[0] = 0x03;  // odd
    } else {
        pubkey[0] = 0x02;  // even
    }

    // Convert x coordinate to big-endian
    uint256_to_bytes(&qx, &pubkey[1]);

    // Hash160(pubkey) -> 20 bytes
    uchar hash160_result[20];
    hash160(pubkey, 33, hash160_result);

    // Compare against all target Hash160 (uint32 vectorized: 5 uint compares vs 20 uchar, with progressive early-exit)  # noqa: E501
    // Pre-assemble hash160_result as 5 uint32 (little-endian)
    uint h0 = (uint)hash160_result[0]  | ((uint)hash160_result[1]  << 8) | ((uint)hash160_result[2]  << 16) | ((uint)hash160_result[3]  << 24);  # noqa: E501
    uint h1 = (uint)hash160_result[4]  | ((uint)hash160_result[5]  << 8) | ((uint)hash160_result[6]  << 16) | ((uint)hash160_result[7]  << 24);  # noqa: E501
    uint h2 = (uint)hash160_result[8]  | ((uint)hash160_result[9]  << 8) | ((uint)hash160_result[10] << 16) | ((uint)hash160_result[11] << 24);  # noqa: E501
    uint h3 = (uint)hash160_result[12] | ((uint)hash160_result[13] << 8) | ((uint)hash160_result[14] << 16) | ((uint)hash160_result[15] << 24);  # noqa: E501
    uint h4 = (uint)hash160_result[16] | ((uint)hash160_result[17] << 8) | ((uint)hash160_result[18] << 16) | ((uint)hash160_result[19] << 24);  # noqa: E501

    int match = 0;
    HASH160_TARGET_SCAN(target_hash160s, h0, h1, h2, h3, h4, num_targets, match);

    // v4.0: If no match and uncompressed checking enabled, try uncompressed format
    if (match == 0 && check_uncompressed) {
        // Serialize uncompressed public key (0x04 + x + y)
        uchar pubkey_uncomp[65];
        pubkey_uncomp[0] = 0x04;
        uint256_to_bytes(&qx, &pubkey_uncomp[1]);
        uint256_to_bytes(&qy, &pubkey_uncomp[33]);

        // Hash160(uncompressed pubkey) -> 20 bytes
        hash160(pubkey_uncomp, 65, hash160_result);

        // Re-pack hash160_result as 5 uint32 (little-endian)
        h0 = (uint)hash160_result[0]  | ((uint)hash160_result[1]  << 8) | ((uint)hash160_result[2]  << 16) | ((uint)hash160_result[3]  << 24);  # noqa: E501
        h1 = (uint)hash160_result[4]  | ((uint)hash160_result[5]  << 8) | ((uint)hash160_result[6]  << 16) | ((uint)hash160_result[7]  << 24);  # noqa: E501
        h2 = (uint)hash160_result[8]  | ((uint)hash160_result[9]  << 8) | ((uint)hash160_result[10] << 16) | ((uint)hash160_result[11] << 24);  # noqa: E501
        h3 = (uint)hash160_result[12] | ((uint)hash160_result[13] << 8) | ((uint)hash160_result[14] << 16) | ((uint)hash160_result[15] << 24);  # noqa: E501
        h4 = (uint)hash160_result[16] | ((uint)hash160_result[17] << 8) | ((uint)hash160_result[18] << 16) | ((uint)hash160_result[19] << 24);  # noqa: E501

        // Compare uncompressed Hash160 against all targets
        HASH160_TARGET_SCAN(target_hash160s, h0, h1, h2, h3, h4, num_targets, match);
    }

    match_flags[gid] = match;
}

// ============================================================================
// Main kernel (local memory): batch check private keys - cache target Hash160 in workgroup shared memory  # noqa: E501
// ============================================================================

__kernel void batch_check_local_mem(
    __constant const uint *seed,            // 32-byte seed (8 uint32, big-endian); key = seed + gid
    const uint num_keys,
    __global const uchar *target_hash160s,  // Input: num_targets * 20 bytes
    const uint num_targets,
    __global int *match_flags,              // Output: num_keys flags
    const uint check_uncompressed,          // v4.0: 0=compressed only, 1=also check uncompressed format  # noqa: E501
    __local uchar *cached_targets,          // local memory cache: num_targets * 20 bytes
    __constant const uint *precomp_table    // Precomputed table: 31x2x8 = 496 uint32 (G1..G31 affine)  # noqa: E501
) {
    // P1-2 fix: ulong gid prevents 32-bit overflow when batch_size >= 2^32
    ulong gid = get_global_id(0);
    uint lid = get_local_id(0);
    uint lsize = get_local_size(0);
    uint total_bytes = num_targets * 20u;

    // Workgroup threads cooperatively load target Hash160 from global to local memory
    for (uint i = lid; i < total_bytes; i += lsize) {
        cached_targets[i] = target_hash160s[i];
    }
    // Wait for all threads to finish loading
    barrier(CLK_LOCAL_MEM_FENCE);

    if (gid >= num_keys) return;

    // Generate private key on GPU: k = seed + gid (256-bit addition)
    uint256_t k;
    generate_private_key(seed, gid, &k);

    // P1-3 fix: Validate private key range (1 <= k < N)
    uint256_t n_val;
    for (int i = 0; i < 8; i++) n_val.d[i] = SECP256K1_N[i];
    if (uint256_is_zero(&k) || uint256_cmp(&k, &n_val) >= 0) {
        match_flags[gid] = 0;
        return;
    }

    // Scalar multiply: Q = k * G
    uint256_t qx, qy;
    ec_scalar_multiply(&k, precomp_table, &qx, &qy);

    // Serialize compressed public key (0x02/0x03 + x)
    uchar pubkey[33];
    if (qy.d[0] & 1) {
        pubkey[0] = 0x03;  // odd
    } else {
        pubkey[0] = 0x02;  // even
    }

    // Convert x coordinate to big-endian
    uint256_to_bytes(&qx, &pubkey[1]);

    // Hash160(pubkey) -> 20 bytes
    uchar hash160_result[20];
    hash160(pubkey, 33, hash160_result);

    // Compare against all target Hash160 (local memory version, uint32 vectorized, 5 uint compares, progressive early-exit)  # noqa: E501
    // Pre-assemble hash160_result as 5 uint32 (little-endian)
    uint h0 = (uint)hash160_result[0]  | ((uint)hash160_result[1]  << 8) | ((uint)hash160_result[2]  << 16) | ((uint)hash160_result[3]  << 24);  # noqa: E501
    uint h1 = (uint)hash160_result[4]  | ((uint)hash160_result[5]  << 8) | ((uint)hash160_result[6]  << 16) | ((uint)hash160_result[7]  << 24);  # noqa: E501
    uint h2 = (uint)hash160_result[8]  | ((uint)hash160_result[9]  << 8) | ((uint)hash160_result[10] << 16) | ((uint)hash160_result[11] << 24);  # noqa: E501
    uint h3 = (uint)hash160_result[12] | ((uint)hash160_result[13] << 8) | ((uint)hash160_result[14] << 16) | ((uint)hash160_result[15] << 24);  # noqa: E501
    uint h4 = (uint)hash160_result[16] | ((uint)hash160_result[17] << 8) | ((uint)hash160_result[18] << 16) | ((uint)hash160_result[19] << 24);  # noqa: E501

    int match = 0;
    HASH160_TARGET_SCAN(cached_targets, h0, h1, h2, h3, h4, num_targets, match);

    // v4.0: If no match and uncompressed checking enabled, try uncompressed format
    if (match == 0 && check_uncompressed) {
        // Serialize uncompressed public key (0x04 + x + y)
        uchar pubkey_uncomp[65];
        pubkey_uncomp[0] = 0x04;
        uint256_to_bytes(&qx, &pubkey_uncomp[1]);
        uint256_to_bytes(&qy, &pubkey_uncomp[33]);

        // Hash160(uncompressed pubkey) -> 20 bytes
        hash160(pubkey_uncomp, 65, hash160_result);

        // Re-pack hash160_result as 5 uint32 (little-endian)
        h0 = (uint)hash160_result[0]  | ((uint)hash160_result[1]  << 8) | ((uint)hash160_result[2]  << 16) | ((uint)hash160_result[3]  << 24);  # noqa: E501
        h1 = (uint)hash160_result[4]  | ((uint)hash160_result[5]  << 8) | ((uint)hash160_result[6]  << 16) | ((uint)hash160_result[7]  << 24);  # noqa: E501
        h2 = (uint)hash160_result[8]  | ((uint)hash160_result[9]  << 8) | ((uint)hash160_result[10] << 16) | ((uint)hash160_result[11] << 24);  # noqa: E501
        h3 = (uint)hash160_result[12] | ((uint)hash160_result[13] << 8) | ((uint)hash160_result[14] << 16) | ((uint)hash160_result[15] << 24);  # noqa: E501
        h4 = (uint)hash160_result[16] | ((uint)hash160_result[17] << 8) | ((uint)hash160_result[18] << 16) | ((uint)hash160_result[19] << 24);  # noqa: E501

        // Compare uncompressed Hash160 against local cached targets
        HASH160_TARGET_SCAN(cached_targets, h0, h1, h2, h3, h4, num_targets, match);
    }

    match_flags[gid] = match;
}

// ============================================================================
// Debug kernel: debug hash computation flow
// ============================================================================

__kernel void debug_hash(
    __global uchar *pubkey_out,    // Output: 33-byte compressed public key
    __global uchar *sha256_out,    // Output: 32-byte SHA256
    __global uchar *hash160_out,   // Output: 20-byte Hash160
    const uint key_value,          // Input: private key value (1 or 2)
    __global uint *qx_out,         // Output: 8 uints Qx
    __global uint *qy_out,         // Output: 8 uints Qy
    __constant const uint *precomp_table  // Precomputed table: 31x2x8 = 496 uint32
) {
    // k = key_value
    uint256_t k;
    uint256_set_zero(&k);
    k.d[0] = key_value;

    uint256_t qx, qy;
    ec_scalar_multiply(&k, precomp_table, &qx, &qy);

    // Output Qx and Qy
    for (int i = 0; i < 8; i++) {
        qx_out[i] = qx.d[i];
        qy_out[i] = qy.d[i];
    }

    // Serialize compressed public key
    uchar pubkey[33];
    if (qy.d[0] & 1) {
        pubkey[0] = 0x03;
    } else {
        pubkey[0] = 0x02;
    }
    uint256_to_bytes(&qx, &pubkey[1]);

    // Output public key
    for (int i = 0; i < 33; i++) pubkey_out[i] = pubkey[i];

    // SHA-256
    uchar sha_hash[32];
    sha256(pubkey, 33, sha_hash);
    for (int i = 0; i < 32; i++) sha256_out[i] = sha_hash[i];

    // RIPEMD-160
    uchar ripe_hash[20];
    ripemd160(sha_hash, 32, ripe_hash);
    for (int i = 0; i < 20; i++) hash160_out[i] = ripe_hash[i];
}

// ============================================================================
// Verification kernel: compute 2*G for self-test
// ============================================================================

__kernel void verify_arithmetic(
    __global uint *result_x,  // Output: x coordinate of 2*G (8 uints)
    __global uint *result_y   // Output: y coordinate of 2*G (8 uints)
) {
    uint256_t gx, gy, rx, ry;

    // Load G
    for (int i = 0; i < 8; i++) {
        gx.d[i] = GX[i];
        gy.d[i] = GY[i];
    }

    // Compute 2*G
    ec_point_double(&gx, &gy, &rx, &ry);

    // Output result
    for (int i = 0; i < 8; i++) {
        result_x[i] = rx.d[i];
        result_y[i] = ry.d[i];
    }
}
"""

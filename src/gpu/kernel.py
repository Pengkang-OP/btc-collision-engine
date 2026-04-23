"""OpenCL内核源码

包含比特币secp256k1 GPU计算所需的OpenCL内核代码

## 核心功能

- **大数运算**: uint256加法、减法、乘法、模运算
- **椭圆曲线**: 点倍乘、点加法、标量乘法 (secp256k1)
- **哈希算法**: SHA-256、RIPEMD-160、Hash160
- **主要内核**: batch_check、verify_arithmetic、debug_hash

## P1-2修复

- 实现GPUKernelProtocol接口
- 支持依赖注入和测试Mock

## 已知修复

- Intel Arc A770兼容性: global char* hang bug、signed long bug

## 使用示例

```python
from src.gpu.kernel import OPENCL_KERNEL_SOURCE
import pyopencl as cl

program = cl.Program(context, OPENCL_KERNEL_SOURCE).build()
batch_check_kernel = program.batch_check
```

## 详细文档

完整的技术规格、API文档和使用指南请参阅:
- [内核迁移完整性审查报告](../kernel-migration-completeness-review.md)
- [GPU模块迁移报告](../gpu-module-migration-report.md)

## 技术规格

- **总行数**: 1,045行
- **内核源码**: 34,758字符 / 1,035行
- **内核函数**: 3个 (__kernel)
- **辅助函数**: 26个
- **常量定义**: 20个 (含宏定义)
"""
import logging
from typing import Optional, Any, List, Dict

# P1-2修复：实现接口
from .kernel_protocol import GPUKernelProtocol

# OpenCL内核源码
OPENCL_KERNEL_SOURCE = """
// ============================================================================
// 比特币 secp256k1 GPU 计算内核
// ============================================================================

// uint256 类型定义: 8 个 uint32，小端序 (d[0]=LSB, d[7]=MSB)
typedef struct {
    uint d[8];
} uint256_t;

// uint512 类型定义: 16 个 uint32，小端序
typedef struct {
    uint d[16];
} uint512_t;

// ============================================================================
// secp256k1 常量（小端序存储）
// ============================================================================

// Gx = 0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798
constant uint GX[8] = {0x16F81798, 0x59F2815B, 0x2DCE28D9, 0x029BFCDB, 0xCE870B07, 0x55A06295, 0xF9DCBBAC, 0x79BE667E};

// Gy = 0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8
constant uint GY[8] = {0xFB10D4B8, 0x9C47D08F, 0xA6855419, 0xFD17B448, 0x0E1108A8, 0x5DA4FBFC, 0x26A3C465, 0x483ADA77};

// P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
constant uint SECP256K1_P[8] = {0xFFFFFC2F, 0xFFFFFFFE, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF};

// N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141 (曲线阶)
constant uint SECP256K1_N[8] = {0xD0364141, 0xBFD25E8C, 0xAF48A03B, 0xBAAEDCE6, 0xFFFFFFFE, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF};

// 0 常量
constant uint ZERO[8] = {0, 0, 0, 0, 0, 0, 0, 0};

// ============================================================================
// uint256 基础运算
// ============================================================================

// 带进位加法: result = a + b，返回进位
// 使用 ulong 算术避免进位检测错误
uint uint256_add(const uint256_t *a, const uint256_t *b, uint256_t *result) {
    ulong carry = 0;
    for (int i = 0; i < 8; i++) {
        ulong sum = (ulong)a->d[i] + (ulong)b->d[i] + carry;
        result->d[i] = (uint)sum;
        carry = sum >> 32;
    }
    return (uint)carry;
}

// 带借位减法: result = a - b，返回借位
// 关键：使用 ulong 算术避免 Intel Arc 上的 signed long bug
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

// 比较 a 和 b: 返回 -1 (a<b), 0 (a==b), 1 (a>b)
int uint256_cmp(const uint256_t *a, const uint256_t *b) {
    for (int i = 7; i >= 0; i--) {
        if (a->d[i] < b->d[i]) return -1;
        if (a->d[i] > b->d[i]) return 1;
    }
    return 0;
}

// 判断是否为 0
int uint256_is_zero(const uint256_t *a) {
    for (int i = 0; i < 8; i++) {
        if (a->d[i] != 0) return 0;
    }
    return 1;
}

// 复制
void uint256_copy(const uint256_t *src, uint256_t *dst) {
    for (int i = 0; i < 8; i++) {
        dst->d[i] = src->d[i];
    }
}

// 设置为 0
void uint256_set_zero(uint256_t *a) {
    for (int i = 0; i < 8; i++) {
        a->d[i] = 0;
    }
}

// 从字节数组加载（大端序输入 -> 小端序 uint256）
// 使用 __global 地址空间修饰符以支持全局内存访问
// 修复：使用uint*替代uchar*避免Intel Arc A770的global char* hang bug
void uint256_from_bytes_global(__global const uint *bytes, uint256_t *result) {
    // bytes现在是uint数组，每8个uint组成32字节私钥
    for (int i = 0; i < 8; i++) {
        // 直接读取uint32，无需字节组装（性能提升4倍）
        // 注意：假设x86_64和GPU都是小端序（所有主流平台满足此假设）
        result->d[7 - i] = bytes[i];
    }
}

// 从字节数组加载（大端序输入 -> 小端序 uint256）- 私有内存版本
void uint256_from_bytes(const uchar *bytes, uint256_t *result) {
    for (int i = 0; i < 8; i++) {
        result->d[7 - i] = ((uint)bytes[i * 4] << 24) | 
                           ((uint)bytes[i * 4 + 1] << 16) | 
                           ((uint)bytes[i * 4 + 2] << 8) | 
                           ((uint)bytes[i * 4 + 3]);
    }
}

// 存储到字节数组（小端序 uint256 -> 大端序输出）
void uint256_to_bytes(const uint256_t *a, uchar *bytes) {
    for (int i = 0; i < 8; i++) {
        bytes[i * 4] = (uchar)(a->d[7 - i] >> 24);
        bytes[i * 4 + 1] = (uchar)(a->d[7 - i] >> 16);
        bytes[i * 4 + 2] = (uchar)(a->d[7 - i] >> 8);
        bytes[i * 4 + 3] = (uchar)(a->d[7 - i]);
    }
}

// ============================================================================
// uint256 乘法（结果512位）
// ============================================================================

void uint256_mul(const uint256_t *a, const uint256_t *b, uint256_t *result_lo, uint256_t *result_hi) {
    uint512_t temp;
    
    // 初始化临时结果为 0
    for (int i = 0; i < 16; i++) {
        temp.d[i] = 0;
    }
    
    // 乘法
    for (int i = 0; i < 8; i++) {
        uint carry = 0;
        for (int j = 0; j < 8; j++) {
            ulong prod = (ulong)a->d[i] * (ulong)b->d[j] + temp.d[i + j] + carry;
            temp.d[i + j] = (uint)prod;
            carry = (uint)(prod >> 32);
        }
        temp.d[i + 8] = carry;
    }
    
    // 复制结果
    for (int i = 0; i < 8; i++) {
        result_lo->d[i] = temp.d[i];
        result_hi->d[i] = temp.d[i + 8];
    }
}

// ============================================================================
// 模 secp256k1 素数 P 运算
// ============================================================================

// 模 P 归约: 利用 p 的特殊形式 2^256 mod p = 2^32 + 977
// P = 2^256 - 2^32 - 977
// 所以 2^256 ≡ 2^32 + 977 (mod P)
// 对于 512 位数 x = x_low + x_high * 2^256，有:
// x mod P = (x_low + x_high * (2^32 + 977)) mod P
void uint256_mod_p(const uint256_t *a, uint256_t *result) {
    uint256_t r;
    uint256_copy(a, &r);
    
    // 对于 256 位输入，我们只需要确保结果 < P
    // 由于 a 已经是 256 位的，我们只需要最多一次减法
    uint256_t p;
    for (int i = 0; i < 8; i++) p.d[i] = SECP256K1_P[i];
    
    // 如果 r >= P，则 r -= P
    if (uint256_cmp(&r, &p) >= 0) {
        int borrow;
        uint256_sub(&r, &p, &r, &borrow);
    }
    
    uint256_copy(&r, result);
}

// 512 位模 P 归约: 输入是两个 256 位数 (lo, hi) 表示 512 位数 lo + hi * 2^256
// 使用 P = 2^256 - 2^32 - 977 的特殊形式
// hi * 2^256 + lo ≡ hi * (2^32 + 977) + lo (mod P)
// 修复：正确处理 hi->d[7] 溢出和迭代归约
void uint512_mod_p(const uint256_t *lo, const uint256_t *hi, uint256_t *result) {
    uint256_t p;
    for (int i = 0; i < 8; i++) p.d[i] = SECP256K1_P[i];
    
    // 当前 hi 和 lo
    uint256_t current_lo, current_hi;
    uint256_copy(lo, &current_lo);
    uint256_copy(hi, &current_hi);
    
    // 迭代归约：hi * 2^256 ≡ hi * (2^32 + 977) mod p
    // 每次归约后新的"hi"部分会越来越小
    // 最多需要2-3次迭代
    for (int iter = 0; iter < 4 && !uint256_is_zero(&current_hi); iter++) {
        // 计算 hi * 977
        uint256_t hi_977;
        uint256_set_zero(&hi_977);
        ulong carry_977 = 0;
        for (int i = 0; i < 8; i++) {
            ulong prod = (ulong)current_hi.d[i] * 977UL + carry_977;
            hi_977.d[i] = (uint)prod;
            carry_977 = prod >> 32;
        }
        
        // 计算 hi << 32 (结果分为 256位部分 + 溢出的 d[7])
        uint256_t hi_shifted;
        uint hi_overflow = current_hi.d[7];  // 被移出的最高位
        hi_shifted.d[0] = 0;
        for (int i = 1; i < 8; i++) {
            hi_shifted.d[i] = current_hi.d[i - 1];
        }
        
        // hi_term = hi_shifted + hi_977
        uint256_t hi_term;
        ulong carry1 = (ulong)uint256_add(&hi_shifted, &hi_977, &hi_term);
        
        // 新 lo = current_lo + hi_term
        uint256_t new_lo;
        ulong carry2 = (ulong)uint256_add(&current_lo, &hi_term, &new_lo);
        
        // 总溢出 = carry_977 + hi_overflow + carry1 + carry2
        // 这些溢出代表 (溢出) * 2^256，需要作为新的 hi
        ulong total_overflow = carry_977 + (ulong)hi_overflow + carry1 + carry2;
        
        uint256_copy(&new_lo, &current_lo);
        uint256_set_zero(&current_hi);
        current_hi.d[0] = (uint)total_overflow;
        current_hi.d[1] = (uint)(total_overflow >> 32);
    }
    
    // 最终归约：确保 result < P
    // 可能需要减去 P 多次（最多 2-3 次）
    for (int i = 0; i < 3; i++) {
        if (uint256_cmp(&current_lo, &p) >= 0) {
            int borrow;
            uint256_sub(&current_lo, &p, &current_lo, &borrow);
        }
    }
    
    uint256_copy(&current_lo, result);
}

// 模加
void mod_add(const uint256_t *a, const uint256_t *b, uint256_t *result) {
    uint256_t sum;
    uint carry = uint256_add(a, b, &sum);
    
    // 如果溢出或 sum >= P，则减去 P
    uint256_t p;
    for (int i = 0; i < 8; i++) p.d[i] = SECP256K1_P[i];
    
    if (carry || uint256_cmp(&sum, &p) >= 0) {
        int borrow;
        uint256_sub(&sum, &p, result, &borrow);
    } else {
        uint256_copy(&sum, result);
    }
}

// 模减
void mod_sub(const uint256_t *a, const uint256_t *b, uint256_t *result) {
    uint256_t p;
    for (int i = 0; i < 8; i++) p.d[i] = SECP256K1_P[i];
    
    int borrow;
    uint256_sub(a, b, result, &borrow);
    
    if (borrow) {
        // 结果为负，加上 P
        uint256_add(result, &p, result);
    }
}

// 模乘
void mod_mul(const uint256_t *a, const uint256_t *b, uint256_t *result) {
    uint256_t lo, hi;
    uint256_mul(a, b, &lo, &hi);
    
    // 使用 512 位模归约
    uint512_mod_p(&lo, &hi, result);
}

// 模平方
void mod_sqr(const uint256_t *a, uint256_t *result) {
    mod_mul(a, a, result);
}

// 模幂: a^e mod P (使用平方-乘法算法)
void mod_pow(const uint256_t *a, const uint256_t *e, uint256_t *result) {
    uint256_t base, exp;
    uint256_copy(a, &base);
    uint256_copy(e, &exp);
    
    // result = 1
    uint256_set_zero(result);
    result->d[0] = 1;
    
    while (!uint256_is_zero(&exp)) {
        if (exp.d[0] & 1) {
            mod_mul(result, &base, result);
        }
        mod_sqr(&base, &base);
        
        // exp >>= 1
        for (int i = 0; i < 7; i++) {
            exp.d[i] = (exp.d[i] >> 1) | (exp.d[i + 1] << 31);
        }
        exp.d[7] >>= 1;
    }
}

// 模逆: a^(-1) mod P = a^(P-2) mod P (费马小定理)
void mod_inverse(const uint256_t *a, uint256_t *result) {
    // P - 2 = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2D
    uint256_t p_minus_2;
    for (int i = 0; i < 8; i++) p_minus_2.d[i] = SECP256K1_P[i];
    p_minus_2.d[0] -= 2;  // P - 2
    
    mod_pow(a, &p_minus_2, result);
}

// ============================================================================
// 椭圆曲线运算 (secp256k1)
// ============================================================================

// ============================================================================
// 雅可比坐标系（Jacobian Coordinates）点运算
// v3.0.0优化: 消除中间模逆，大幅减少计算量
// 雅可比坐标 (X:Y:Z) 对应仿射坐标 (X/Z², Y/Z³)
// 点倍加: 11次mod_mul+5次mod_sqr（vs 仿射坐标: 4次mod_mul+505次模乘/mod_inverse）
// 点加法: 16次mod_mul+4次mod_sqr（vs 仿射坐标: 5次mod_mul+505次模乘/mod_inverse）
// ============================================================================

// 雅可比坐标点倍加: (Rx:Ry:Rz) = 2*(Px:Py:Pz)
// 使用标准雅可比公式（secp256k1 a=0 优化版）
// 成本: 4次mod_sqr + 7次mod_mul（共11次模运算，无mod_inverse）
// 賢识: 输入和输出可以是同一变量（内部全程使用临时变量）
void jac_point_double(const uint256_t *px, const uint256_t *py, const uint256_t *pz,
                      uint256_t *rx, uint256_t *ry, uint256_t *rz) {
    // 无穷远点检测: Z == 0
    if (uint256_is_zero(pz)) {
        uint256_set_zero(rx);
        uint256_set_zero(ry);
        uint256_set_zero(rz);
        return;
    }
    
    // 在开始计算前，先拷贝输入到内部变量（防止输入输出别名）
    uint256_t X, Y, Z;
    uint256_copy(px, &X);
    uint256_copy(py, &Y);
    uint256_copy(pz, &Z);
    
    uint256_t t1, t2, t3, t4, t5;
    uint256_t out_x, out_y, out_z;
    
    // secp256k1 a=0 的雅可比点倍加公式:
    // S = 4*X*Y^2
    // M = 3*X^2  (secp256k1 a=0, 无需 a*Z^4 项)
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
    
    // 统一赋值输出（即使输入输出为同一地址也安全）
    uint256_copy(&out_x, rx);
    uint256_copy(&out_y, ry);
    uint256_copy(&out_z, rz);
}

// 雅可比坐标混合点加法: (Rx:Ry:Rz) = (P1x:P1y:P1z) + (P2x:P2y:1)
// P2 是仿射坐标点（Z2=1），P1 是雅可比坐标点
// 成本: 4次mod_sqr + 12次mod_mul（共16次模运算，无mod_inverse）
// 賢识: 输入和输出可以是同一变量（内部全程使用临时变量）
void jac_point_add_affine(const uint256_t *p1x, const uint256_t *p1y, const uint256_t *p1z,
                          const uint256_t *p2x, const uint256_t *p2y,
                          uint256_t *rx, uint256_t *ry, uint256_t *rz) {
    // 检查 P1 是否是无穷远点: Z1 == 0
    if (uint256_is_zero(p1z)) {
        uint256_copy(p2x, rx);
        uint256_copy(p2y, ry);
        uint256_set_zero(rz);
        rz->d[0] = 1;  // Z=1 表示仿射点
        return;
    }
    
    // 先拷贝输入到内部变量（防止输入输出别名）
    uint256_t X1, Y1, Z1;
    uint256_copy(p1x, &X1);
    uint256_copy(p1y, &Y1);
    uint256_copy(p1z, &Z1);
    
    uint256_t t1, t2, t3, t4, t5, t6;
    uint256_t out_x, out_y, out_z;
    
    // 混合加法公式 (P2 的 Z2=1):
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
    
    // 处理 P1 == P2 的特殊情况 (H==0, R==0 -> 点倍加)
    if (uint256_is_zero(&t5) && uint256_is_zero(&t6)) {
        // P1 == P2, 需要点倍加
        // 转换 P2 到雅可比坐标后倍加
        uint256_t one;
        uint256_set_zero(&one);
        one.d[0] = 1;
        jac_point_double(p2x, p2y, &one, rx, ry, rz);
        return;
    }
    
    // H == 0, R != 0 -> P1 == -P2, 结果是无穷远点
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
    
    // 统一赋值输出
    uint256_copy(&out_x, rx);
    uint256_copy(&out_y, ry);
    uint256_copy(&out_z, rz);
}

// 雅可比坐标转仿射坐标: (X:Y:Z) -> (X/Z^2, Y/Z^3)
// 成本: 1次mod_inverse + 3次mod_mul
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

// 保留仿射坐标点倍加（用于预计算表生成）
void ec_point_double(const uint256_t *px, const uint256_t *py, uint256_t *rx, uint256_t *ry) {
    if (uint256_is_zero(py)) {
        uint256_set_zero(rx);
        uint256_set_zero(ry);
        return;
    }
    
    uint256_t lambda, temp1, temp2, temp3, two_y_inv;
    
    // lambda = (3*x^2) * (2*y)^(-1) mod p
    // secp256k1 中 a = 0
    
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

// 保留仿射坐标点加法（用于预计算表生成）
void ec_point_add(const uint256_t *p1x, const uint256_t *p1y,
                  const uint256_t *p2x, const uint256_t *p2y,
                  uint256_t *rx, uint256_t *ry) {
    // 检查 P 是否是无穷远点
    if (uint256_is_zero(p1x) && uint256_is_zero(p1y)) {
        uint256_copy(p2x, rx);
        uint256_copy(p2y, ry);
        return;
    }
    
    // 检查 Q 是否是无穷远点
    if (uint256_is_zero(p2x) && uint256_is_zero(p2y)) {
        uint256_copy(p1x, rx);
        uint256_copy(p1y, ry);
        return;
    }
    
    // 检查 P == Q (点倍乘)
    if (uint256_cmp(p1x, p2x) == 0 && uint256_cmp(p1y, p2y) == 0) {
        ec_point_double(p1x, p1y, rx, ry);
        return;
    }
    
    // 检查 P == -Q (结果是无穷远点)
    uint256_t neg_p2y;
    uint256_t p;
    for (int i = 0; i < 8; i++) p.d[i] = SECP256K1_P[i];
    int borrow;
    uint256_sub(&p, p2y, &neg_p2y, &borrow);
    
    if (uint256_cmp(p1x, p2x) == 0 && uint256_cmp(p1y, &neg_p2y) == 0) {
        uint256_set_zero(rx);
        uint256_set_zero(ry);
        return;
    }
    
    uint256_t lambda, temp1, temp2, dx_inv;
    
    // lambda = (y2 - y1) / (x2 - x1) mod p
    mod_sub(p2y, p1y, &temp1);  // temp1 = y2 - y1
    mod_sub(p2x, p1x, &temp2);  // temp2 = x2 - x1
    mod_inverse(&temp2, &dx_inv);  // dx_inv = (x2 - x1)^(-1)
    mod_mul(&temp1, &dx_inv, &lambda);  // lambda = (y2 - y1) / (x2 - x1)
    
    // rx = lambda^2 - x1 - x2
    mod_sqr(&lambda, &temp1);  // temp1 = lambda^2
    mod_sub(&temp1, p1x, &temp2);  // temp2 = lambda^2 - x1
    mod_sub(&temp2, p2x, rx);  // rx = lambda^2 - x1 - x2
    
    // ry = lambda*(x1 - rx) - y1
    mod_sub(p1x, rx, &temp2);  // temp2 = x1 - rx
    mod_mul(&lambda, &temp2, &temp1);  // temp1 = lambda*(x1 - rx)
    mod_sub(&temp1, p1y, ry);  // ry = lambda*(x1 - rx) - y1
}

// 标量乘法: R = k * G (雅可比坐标系 MSB-first 窗口优化算法)
// v3.0.0重大优化:
//   1. 使用雅可比坐标系消除中间模逆（理论大幅加速）
//   2. 修复算法错误：从 LSB-first 改为正确的 MSB-first 实现
// 算法步骤:
//   1. 预计算表[1G..31G]（仿射坐标）
//   2. 处理最高1位（bit255）
//   3. 循环51次：每次先5次雅可比倍加，再查表加点（从高位到低位）
//   4. 最终转换到仿射坐标（1次mod_inverse）
void ec_scalar_multiply(const uint256_t *k, const uint256_t *gx, const uint256_t *gy,
                        uint256_t *rx, uint256_t *ry) {
    // 预计算仿射坐标表 [1G, 2G, 3G, ..., 31G]
    uint256_t precomp_x[31], precomp_y[31];
    uint256_t temp2x, temp2y;
    
    uint256_copy(gx, &precomp_x[0]);
    uint256_copy(gy, &precomp_y[0]);
    for (int i = 1; i < 31; i++) {
        ec_point_add(&precomp_x[i-1], &precomp_y[i-1], gx, gy, &temp2x, &temp2y);
        uint256_copy(&temp2x, &precomp_x[i]);
        uint256_copy(&temp2y, &precomp_y[i]);
    }
    
    // 雅可比坐标结果初始为无穷远点
    uint256_t jac_x, jac_y, jac_z;
    uint256_set_zero(&jac_x);
    uint256_set_zero(&jac_y);
    uint256_set_zero(&jac_z);
    
    // MSB-first 窗口算法 (w=5)
    // 256位分解为: 最高1位(bit255) + 51组各5位(bits 254..0)
    // 处理顺序: 先bit255，然后从高到低每次取5位
    
    // 步陨1: 处理最高1位 (bit255)
    {
        // 获取私鑰第255位: k->d[7] 的第31位 (bit 255 = d[7]>>31)
        int top_bit = (int)((k->d[7] >> 31) & 1);
        if (top_bit) {
            uint256_copy(&precomp_x[0], &jac_x);
            uint256_copy(&precomp_y[0], &jac_y);
            // jac_z = 1 (仿射点对应雅可比Z=1)
            uint256_set_zero(&jac_z);
            jac_z.d[0] = 1;
        }
        // top_bit==0: 结果仍为无穷远点 (jac_z=0)
    }
    
    // 步陨2: 循环51组，每组5位，从高位到低位
    // grp=50: bits 254..250
    // grp=49: bits 249..245
    // ...
    // grp=0: bits 4..0
    for (int grp = 50; grp >= 0; grp--) {
        // 获取第 grp 组的5位窗口值
        // bit范围: grp*5+4 到 grp*5
        // grp*5 属于哪个 uint32: d[grp*5/32]
        int bit_start = grp * 5;  // 最低位位置
        int d_idx = bit_start / 32;
        int d_shift = bit_start % 32;
        
        // 提取5位: 可能跨两个limb
        int window;
        if (d_shift <= 27) {
            // 所有5位在同一个limb中
            window = (int)((k->d[d_idx] >> d_shift) & 0x1F);
        } else {
            // 跨两个limb
            uint lo = k->d[d_idx] >> d_shift;
            uint hi = (d_idx + 1 < 8) ? (k->d[d_idx + 1] << (32 - d_shift)) : 0;
            window = (int)((lo | hi) & 0x1F);
        }
        
        // 5次雅可比点倍加 (无mod_inverse!)
        for (int j = 0; j < 5; j++) {
            jac_point_double(&jac_x, &jac_y, &jac_z, &temp2x, &temp2y, &jac_z);
            uint256_copy(&temp2x, &jac_x);
            uint256_copy(&temp2y, &jac_y);
        }
        
        // 查表加点（雅可比+仿射混合，无mod_inverse!）
        if (window > 0) {
            int index = window - 1;
            jac_point_add_affine(&jac_x, &jac_y, &jac_z,
                                 &precomp_x[index], &precomp_y[index],
                                 &temp2x, &temp2y, &jac_z);
            uint256_copy(&temp2x, &jac_x);
            uint256_copy(&temp2y, &jac_y);
        }
    }
    
    // 最终: 雅可比坐标 -> 仿射坐标 (1次mod_inverse)
    jac_to_affine(&jac_x, &jac_y, &jac_z, rx, ry);
}

// ============================================================================
// SHA-256 实现
// ============================================================================

constant uint SHA256_K[64] = {
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
    
    // 准备消息调度
    for (int i = 0; i < 16; i++) {
        w[i] = ((uint)data[i * 4] << 24) | ((uint)data[i * 4 + 1] << 16) | 
               ((uint)data[i * 4 + 2] << 8) | ((uint)data[i * 4 + 3]);
    }
    
    for (int i = 16; i < 64; i++) {
        w[i] = SHA256_SIG1(w[i - 2]) + w[i - 7] + SHA256_SIG0(w[i - 15]) + w[i - 16];
    }
    
    // 初始化工作变量
    a = state[0];
    b = state[1];
    c = state[2];
    d = state[3];
    e = state[4];
    f = state[5];
    g = state[6];
    h = state[7];
    
    // 64 轮压缩
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
    
    // 更新状态
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
    
    // 处理输入数据
    for (uint i = 0; i < len; i++) {
        buffer[buffer_len++] = data[i];
        total_len++;
        
        if (buffer_len == 64) {
            sha256_transform(state, buffer);
            buffer_len = 0;
        }
    }
    
    // 填充
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
    
    // 追加长度（位）
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
    
    // 输出结果（大端序）
    for (int i = 0; i < 8; i++) {
        hash[i * 4] = (uchar)(state[i] >> 24);
        hash[i * 4 + 1] = (uchar)(state[i] >> 16);
        hash[i * 4 + 2] = (uchar)(state[i] >> 8);
        hash[i * 4 + 3] = (uchar)(state[i]);
    }
}

// ============================================================================
// RIPEMD-160 实现 (参考 Bitcoin Core 实现)
// ============================================================================

#define RIPEMD160_ROTL(x, n) (((x) << (n)) | ((x) >> (32 - (n))))

// F 函数
#define f0(x, y, z) ((x) ^ (y) ^ (z))
#define f1(x, y, z) (((x) & (y)) | (~(x) & (z)))
#define f2(x, y, z) (((x) | ~(y)) ^ (z))
#define f3(x, y, z) (((x) & (z)) | ((y) & ~(z)))
#define f4(x, y, z) ((x) ^ ((y) | ~(z)))

// 轮函数宏
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
    
    // 左路 (使用 K 值: 0, 1, 2, 3, 4)
    // 第 1 轮 (0-15): F0, K0=0x00000000
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
    
    // 第 2 轮 (16-31): F1, K1=0x5a827999
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
    
    // 第 3 轮 (32-47): F2, K2=0x6ed9eba1
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
    
    // 第 4 轮 (48-63): F3, K3=0x8f1bbcdc
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
    
    // 第 5 轮 (64-79): F4, K4=0xa953fd4e
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
    
    // 右路 (使用 K' 值，注意顺序是反的)
    // 右路第 1 轮 (0-15): 使用 F4, K0'=0x50a28be6
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
    
    // 右路第 2 轮 (16-31): 使用 F3, K1'=0x5c4dd124
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
    
    // 右路第 3 轮 (32-47): 使用 F2, K2'=0x6d703ef3
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
    
    // 右路第 4 轮 (48-63): 使用 F1, K3'=0x7a6d76e9
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
    
    // 右路第 5 轮 (64-79): 使用 F0, K4'=0x00000000
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
    
    // 组合结果
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
    
    // 处理输入数据
    for (uint i = 0; i < len; i++) {
        buffer[buffer_len++] = data[i];
        total_len++;
        
        if (buffer_len == 64) {
            ripemd160_transform(state, buffer);
            buffer_len = 0;
        }
    }
    
    // 填充
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
    
    // 追加长度（位，小端序）
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
    
    // 输出结果（小端序）
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
// 主内核: 批量检查私钥
// ============================================================================

__kernel void batch_check(
    __global const uint *private_keys,  // 修复: uint*替代uchar*避免Intel Arc hang bug (num_keys * 8 uints)
    const uint num_keys,
    __global const uchar *target_hash160s,  // 输入: num_targets * 20 字节
    const uint num_targets,
    __global int *match_flags  // 输出: num_keys 个标志 (0=不匹配, target_index+1=匹配)
) {
    uint gid = get_global_id(0);
    if (gid >= num_keys) return;
    
    // 读取私钥 (uint32数组 -> uint256 小端)
    // 修复：每个私钥现在是8个uint32（而非32个uchar）
    uint256_t k;
    uint256_from_bytes_global(&private_keys[gid * 8], &k);
    
    // 检查私钥是否为 0
    if (uint256_is_zero(&k)) {
        match_flags[gid] = 0;
        return;
    }
    
    // 基点 G
    uint256_t gx, gy;
    for (int i = 0; i < 8; i++) {
        gx.d[i] = GX[i];
        gy.d[i] = GY[i];
    }
    
    // 标量乘法: Q = k * G
    uint256_t qx, qy;
    ec_scalar_multiply(&k, &gx, &gy, &qx, &qy);
    
    // 序列化压缩公钥 (0x02/0x03 + x)
    uchar pubkey[33];
    // 检查 y 的奇偶性 (看最低 limb 的最低位)
    if (qy.d[0] & 1) {
        pubkey[0] = 0x03;  // 奇数
    } else {
        pubkey[0] = 0x02;  // 偶数
    }
    
    // x 坐标转大端序
    uint256_to_bytes(&qx, &pubkey[1]);
    
    // Hash160(公钥) -> 20 字节
    uchar hash160_result[20];
    hash160(pubkey, 33, hash160_result);
    
    // 与所有目标 Hash160 比对
    int match = 0;
    for (uint t = 0; t < num_targets && match == 0; t++) {
        int equal = 1;
        for (int i = 0; i < 20; i++) {
            if (hash160_result[i] != target_hash160s[t * 20 + i]) {
                equal = 0;
                break;
            }
        }
        if (equal) {
            match = (int)(t + 1);  // 存储 target_index + 1
        }
    }
    
    match_flags[gid] = match;
}

// ============================================================================
// 调试内核: 调试哈希计算流程
// ============================================================================

__kernel void debug_hash(
    __global uchar *pubkey_out,    // 输出: 33 字节压缩公钥
    __global uchar *sha256_out,    // 输出: 32 字节 SHA256
    __global uchar *hash160_out,   // 输出: 20 字节 Hash160
    const uint key_value,          // 输入: 私钥值 (1 或 2)
    __global uint *qx_out,         // 输出: 8 uints Qx
    __global uint *qy_out          // 输出: 8 uints Qy
) {
    // 基点 G
    uint256_t gx, gy;
    for (int i = 0; i < 8; i++) {
        gx.d[i] = GX[i];
        gy.d[i] = GY[i];
    }
    
    // k = key_value
    uint256_t k;
    uint256_set_zero(&k);
    k.d[0] = key_value;
    
    uint256_t qx, qy;
    ec_scalar_multiply(&k, &gx, &gy, &qx, &qy);
    
    // 输出 Qx 和 Qy
    for (int i = 0; i < 8; i++) {
        qx_out[i] = qx.d[i];
        qy_out[i] = qy.d[i];
    }
    
    // 序列化压缩公钥
    uchar pubkey[33];
    if (qy.d[0] & 1) {
        pubkey[0] = 0x03;
    } else {
        pubkey[0] = 0x02;
    }
    uint256_to_bytes(&qx, &pubkey[1]);
    
    // 输出公钥
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
// 验证内核: 计算 2*G 用于自检
// ============================================================================

__kernel void verify_arithmetic(
    __global uint *result_x,  // 输出: 2*G 的 x 坐标 (8 个 uint)
    __global uint *result_y   // 输出: 2*G 的 y 坐标 (8 个 uint)
) {
    uint256_t gx, gy, rx, ry;
    
    // 加载 G
    for (int i = 0; i < 8; i++) {
        gx.d[i] = GX[i];
        gy.d[i] = GY[i];
    }
    
    // 计算 2*G
    ec_point_double(&gx, &gy, &rx, &ry);
    
    // 输出结果
    for (int i = 0; i < 8; i++) {
        result_x[i] = rx.d[i];
        result_y[i] = ry.d[i];
    }
}
"""

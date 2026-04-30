"""
Fix encoding issues in OpenCL kernel files.
Replace all non-ASCII characters (Chinese comments) with English equivalents.
"""
import re
import os

# Map of Chinese text -> English translation
# Applied to kernel.py OPENCL_KERNEL_SOURCE (the single source of truth for OpenCL kernels)
REPLACEMENTS = [
    # File header / section comments
    ("比特币 secp256k1 GPU 计算内核", "Bitcoin secp256k1 GPU computation kernel"),
    ("比特币secp256k1 GPU计算内核", "Bitcoin secp256k1 GPU computation kernel"),

    # Type definitions
    ("uint256 类型定义: 8 个 uint32，小端序 (d[0]=LSB, d[7]=MSB)", "uint256 type: 8 x uint32, little-endian (d[0]=LSB, d[7]=MSB)"),
    ("uint512 类型定义: 16 个 uint32，小端序", "uint512 type: 16 x uint32, little-endian"),

    # secp256k1 constants
    ("secp256k1 常量（小端序存储）", "secp256k1 constants (little-endian storage)"),
    ("N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141 (曲线阶)",
     "N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141 (curve order)"),
    ("0 常量", "Zero constant"),

    # uint256 basic operations
    ("uint256 基础运算", "uint256 basic operations"),
    ("带进位加法: result = a + b，返回进位", "Add with carry: result = a + b, returns carry"),
    ("使用 ulong 算术避免进位检测错误", "Use ulong arithmetic to avoid carry detection errors"),
    ("带借位减法: result = a - b，返回借位", "Subtract with borrow: result = a - b, returns borrow"),
    ("关键：使用 ulong 算术避免 Intel Arc 上的 signed long bug", "Key: use ulong arithmetic to avoid signed long bug on Intel Arc"),
    ("比较 a 和 b: 返回 -1 (a<b), 0 (a==b), 1 (a>b)", "Compare a and b: returns -1 (a<b), 0 (a==b), 1 (a>b)"),
    ("判断是否为 0", "Check if zero"),
    ("复制", "Copy"),
    ("设置为 0", "Set to zero"),

    # uint256_from_bytes_global
    ("从字节数组加载（大端序输入 -> 小端序 uint256）", "Load from byte array (big-endian input -> little-endian uint256)"),
    ("使用 __global 地址空间修饰符以支持全局内存访问", "Use __global address space qualifier for global memory access"),
    ("修复：使用uint*替代uchar*避免Intel Arc A770的global char* hang bug",
     "Fix: use uint* instead of uchar* to avoid Intel Arc A770 global char* hang bug"),
    ("bytes现在是uint数组，每8个uint组成32字节私钥", "bytes is now uint array, 8 uints = 32-byte private key"),
    ("直接读取uint32，无需字节组装（性能提升4倍）", "Direct uint32 read, no byte assembly needed (4x perf gain)"),
    ("注意：假设x86_64和GPU都是小端序（所有主流平台满足此假设）",
     "Note: assumes x86_64 and GPU are both little-endian (true for all mainstream platforms)"),
    ("从字节数组加载（大端序输入 -> 小端序 uint256）- 私有内存版本",
     "Load from byte array (big-endian input -> little-endian uint256) - private memory version"),
    ("存储到字节数组（小端序 uint256 -> 大端序输出）", "Store to byte array (little-endian uint256 -> big-endian output)"),

    # uint256 multiply
    ("uint256 乘法（结果512位）", "uint256 multiplication (512-bit result)"),
    ("初始化临时结果为 0", "Initialize temp result to 0"),
    ("乘法", "Multiply"),
    ("复制结果", "Copy result"),

    # Mod P operations
    ("模 secp256k1 素数 P 运算", "Modular arithmetic mod secp256k1 prime P"),
    ("模 P 归约: 利用 p 的特殊形式 2^256 mod p = 2^32 + 977",
     "Reduce mod P: using special form 2^256 mod p = 2^32 + 977"),
    ("P = 2^256 - 2^32 - 977", "P = 2^256 - 2^32 - 977"),
    ("所以 2^256 ≡ 2^32 + 977 (mod P)", "So 2^256 == 2^32 + 977 (mod P)"),
    ("对于 512 位数 x = x_low + x_high * 2^256，有:",
     "For 512-bit x = x_low + x_high * 2^256:"),
    ("x mod P = (x_low + x_high * (2^32 + 977)) mod P",
     "x mod P = (x_low + x_high * (2^32 + 977)) mod P"),
    ("对于 256 位输入，我们只需要确保结果 < P", "For 256-bit input, just ensure result < P"),
    ("由于 a 已经是 256 位的，我们只需要最多一次减法", "Since a is already 256-bit, at most one subtraction needed"),
    ("如果 r >= P，则 r -= P", "If r >= P, then r -= P"),
    ("512 位模 P 归约: 输入是两个 256 位数 (lo, hi) 表示 512 位数 lo + hi * 2^256",
     "512-bit mod P reduction: input is two 256-bit nums (lo, hi) representing lo + hi * 2^256"),
    ("使用 P = 2^256 - 2^32 - 977 的特殊形式", "Using special form P = 2^256 - 2^32 - 977"),
    ("hi * 2^256 + lo ≡ hi * (2^32 + 977) + lo (mod P)",
     "hi * 2^256 + lo == hi * (2^32 + 977) + lo (mod P)"),
    ("修复：正确处理 hi->d[7] 溢出和迭代归约", "Fix: properly handle hi->d[7] overflow and iterative reduction"),
    ("当前 hi 和 lo", "Current hi and lo"),
    ("迭代归约：hi * 2^256 ≡ hi * (2^32 + 977) mod p", "Iterative reduction: hi * 2^256 == hi * (2^32 + 977) mod p"),
    ("每次归约后新的\"hi\"部分会越来越小", "After each reduction the new 'hi' part gets smaller"),
    ("最多需要2-3次迭代", "At most 2-3 iterations needed"),
    ("计算 hi * 977", "Compute hi * 977"),
    ("计算 hi << 32 (结果分为 256位部分 + 溢出的 d[7])", "Compute hi << 32 (result = 256-bit part + overflow d[7])"),
    ("被移出的最高位", "MSB shifted out"),
    ("hi_term = hi_shifted + hi_977", "hi_term = hi_shifted + hi_977"),
    ("新 lo = current_lo + hi_term", "new lo = current_lo + hi_term"),
    ("总溢出 = carry_977 + hi_overflow + carry1 + carry2",
     "total overflow = carry_977 + hi_overflow + carry1 + carry2"),
    ("这些溢出代表 (溢出) * 2^256，需要作为新的 hi",
     "These overflows represent (overflow) * 2^256, used as new hi"),
    ("最终归约：确保 result < P", "Final reduction: ensure result < P"),
    ("可能需要减去 P 多次（最多 2-3 次）", "May need to subtract P multiple times (at most 2-3)"),

    # mod add/sub/mul
    ("模加", "Modular addition"),
    ("如果溢出或 sum >= P，则减去 P", "If overflow or sum >= P, subtract P"),
    ("模减", "Modular subtraction"),
    ("结果为负，加上 P", "Result is negative, add P"),
    ("模乘", "Modular multiplication"),
    ("使用 512 位模归约", "Use 512-bit mod reduction"),
    ("模平方", "Modular squaring"),

    # mod_inverse
    ("模逆: a^(-1) mod P = a^(P-2) mod P (费马小定理)",
     "Modular inverse: a^(-1) mod P = a^(P-2) mod P (Fermat's little theorem)"),
    ("secp256k1 定制加法链，利用 P-2 的特殊二进制结构:",
     "secp256k1 custom addition chain using special binary structure of P-2:"),
    ("bits 255..33: 223个1", "bits 255..33: 223 ones"),
    ("bit  32:      0", "bit  32:      0"),
    ("bits 31..10:  22个1", "bits 31..10:  22 ones"),
    ("bits 9..6:    0000", "bits 9..6:    0000"),
    ("bit  5:       1", "bit  5:       1"),
    ("bit  4:       0", "bit  4:       0"),
    ("bits 3..2:    11", "bits 3..2:    11"),
    ("bit  1:       0", "bit  1:       0"),
    ("bit  0:       1", "bit  0:       1"),
    ("总计: 255次 sqr + 15次 mul (vs 通用 mod_pow 的 256 sqr + ~128 mul)",
     "Total: 255 sqr + 15 mul (vs generic mod_pow: 256 sqr + ~128 mul)"),
    ("构建 P-2 的剩余部分 (bits 32..0)", "Build remaining part of P-2 (bits 32..0)"),
    ("bit32 = 0: 仅 sqr", "bit32 = 0: sqr only"),
    ("bits 31..10: 22个1: sqr 22次再 mul x22", "bits 31..10: 22 ones: sqr 22 times then mul x22"),
    ("bits 9..6: 0000: sqr 4次", "bits 9..6: 0000: sqr 4 times"),
    ("bit5 = 1", "bit5 = 1"),
    ("bit4 = 0", "bit4 = 0"),
    ("bits 3..2 = 11: sqr 2次再 mul x2 (= a^3, but we need a^(2^2-1) = a^3)",
     "bits 3..2 = 11: sqr 2 times then mul x2 (= a^3)"),
    ("先处理 bit3=1: sqr+mul_a", "Handle bit3=1: sqr+mul_a"),
    ("处理 bit2=1: sqr+mul_a", "Handle bit2=1: sqr+mul_a"),
    ("bit1 = 0", "bit1 = 0"),
    ("bit0 = 1", "bit0 = 1"),

    # EC operations section
    ("椭圆曲线运算 (secp256k1)", "Elliptic curve operations (secp256k1)"),
    ("雅可比坐标系（Jacobian Coordinates）点运算", "Jacobian Coordinates point operations"),
    ("v3.0.0优化: 消除中间模逆，大幅减少计算量", "v3.0.0 opt: eliminate intermediate mod_inverse, greatly reduce computation"),
    ("雅可比坐标 (X:Y:Z) 对应仿射坐标 (X/Z\u00b2, Y/Z\u00b3)", "Jacobian (X:Y:Z) maps to affine (X/Z^2, Y/Z^3)"),
    ("雅可比坐标 (X:Y:Z) 对应仿射坐标 (X/Z², Y/Z³)", "Jacobian (X:Y:Z) maps to affine (X/Z^2, Y/Z^3)"),
    ("点倍加: 11次mod_mul+5次mod_sqr（vs 仿射坐标: 4次mod_mul+505次模乘/mod_inverse）",
     "Point double: 11 mod_mul+5 mod_sqr (vs affine: 4 mod_mul+505 mod ops/mod_inverse)"),
    ("点加法: 16次mod_mul+4次mod_sqr（vs 仿射坐标: 5次mod_mul+505次模乘/mod_inverse）",
     "Point add: 16 mod_mul+4 mod_sqr (vs affine: 5 mod_mul+505 mod ops/mod_inverse)"),
    ("雅可比坐标点倍加: (Rx:Ry:Rz) = 2*(Px:Py:Pz)", "Jacobian point double: (Rx:Ry:Rz) = 2*(Px:Py:Pz)"),
    ("使用标准雅可比公式（secp256k1 a=0 优化版）", "Standard Jacobian formula (secp256k1 a=0 optimized)"),
    ("成本: 4次mod_sqr + 7次mod_mul（共11次模运算，无mod_inverse）",
     "Cost: 4 mod_sqr + 7 mod_mul (11 mod ops total, no mod_inverse)"),
    ("賢识: 输入和输出可以是同一变量（内部全程使用临时变量）",
     "Note: input and output can be same variable (uses temp vars internally)"),
    ("无穷远点检测: Z == 0", "Point at infinity check: Z == 0"),
    ("在开始计算前，先拷贝输入到内部变量（防止输入输出别名）",
     "Copy inputs to internal vars before computation (prevent input/output aliasing)"),
    ("secp256k1 a=0 的雅可比点倍加公式:", "Jacobian point double formula for secp256k1 a=0:"),
    ("统一赋值输出（即使输入输出为同一地址也安全）", "Unified output assignment (safe even if input/output share address)"),
    ("雅可比坐标混合点加法: (Rx:Ry:Rz) = (P1x:P1y:P1z) + (P2x:P2y:1)",
     "Jacobian mixed point addition: (Rx:Ry:Rz) = (P1x:P1y:P1z) + (P2x:P2y:1)"),
    ("P2 是仿射坐标点（Z2=1），P1 是雅可比坐标点", "P2 is affine (Z2=1), P1 is Jacobian"),
    ("成本: 4次mod_sqr + 12次mod_mul（共16次模运算，无mod_inverse）",
     "Cost: 4 mod_sqr + 12 mod_mul (16 mod ops total, no mod_inverse)"),
    ("检查 P1 是否是无穷远点: Z1 == 0", "Check if P1 is point at infinity: Z1 == 0"),
    ("Z=1 表示仿射点", "Z=1 denotes affine point"),
    ("先拷贝输入到内部变量（防止输入输出别名）", "Copy inputs to internal vars (prevent aliasing)"),
    ("混合加法公式 (P2 的 Z2=1):", "Mixed addition formula (P2 has Z2=1):"),
    ("处理 P1 == P2 的特殊情况 (H==0, R==0 -> 点倍加)", "Handle special case P1 == P2 (H==0, R==0 -> point double)"),
    ("P1 == P2, 需要点倍加", "P1 == P2, need point double"),
    ("转换 P2 到雅可比坐标后倍加", "Convert P2 to Jacobian then double"),
    ("H == 0, R != 0 -> P1 == -P2, 结果是无穷远点", "H == 0, R != 0 -> P1 == -P2, result is point at infinity"),
    ("统一赋值输出", "Unified output assignment"),
    ("雅可比坐标转仿射坐标: (X:Y:Z) -> (X/Z^2, Y/Z^3)", "Jacobian to affine: (X:Y:Z) -> (X/Z^2, Y/Z^3)"),
    ("成本: 1次mod_inverse + 3次mod_mul", "Cost: 1 mod_inverse + 3 mod_mul"),
    ("保留仿射坐标点倍加（用于预计算表生成）", "Affine point double (for precomputed table generation)"),
    ("lambda = (3*x^2) * (2*y)^(-1) mod p", "lambda = (3*x^2) * (2*y)^(-1) mod p"),
    ("secp256k1 中 a = 0", "secp256k1 has a = 0"),

    # ec_scalar_multiply
    ("标量乘法: R = k * G (雅可比坐标系 MSB-first 窗口优化算法)",
     "Scalar multiplication: R = k * G (Jacobian MSB-first windowed algorithm)"),
    ("v3.0.0重大优化:", "v3.0.0 major optimizations:"),
    ("1. 使用雅可比坐标系消除中间模逆（理论大幅加速）",
     "1. Use Jacobian coords to eliminate intermediate mod_inverse (major speedup)"),
    ("2. 修复算法错误：从 LSB-first 改为正确的 MSB-first 实现",
     "2. Fix algorithm: changed from LSB-first to correct MSB-first"),
    ("v4.0.0优化:", "v4.0.0 optimizations:"),
    ("3. 预计算表由 host 传入，避免每个工作线程重复计算",
     "3. Precomputed table passed from host, avoids redundant computation per thread"),
    ("算法步骤:", "Algorithm steps:"),
    ("1. 从 __constant 内存读取预计算表[1G..31G]（仿射坐标）",
     "1. Read precomputed table[1G..31G] from __constant memory (affine coords)"),
    ("2. 处理最高1位（bit255）", "2. Handle top 1 bit (bit255)"),
    ("3. 循环51次：每次先5次雅可比倡加，再查表加点（从高位到低位）",
     "3. Loop 51 times: 5 Jacobian doubles then table lookup add (high to low)"),
    ("4. 最终转换到仿射坐标（1次mod_inverse）", "4. Final conversion to affine (1 mod_inverse)"),
    ("precomp_table 布局: [G1x(8 uint), G1y(8 uint), G2x(8 uint), G2y(8 uint), ..., G31x, G31y]",
     "precomp_table layout: [G1x(8 uint), G1y(8 uint), G2x(8 uint), G2y(8 uint), ..., G31x, G31y]"),
    ("共 31\u00d72\u00d78 = 496 个 uint32", "Total: 31x2x8 = 496 uint32"),
    ("共 31×2×8 = 496 个 uint32", "Total: 31x2x8 = 496 uint32"),
    ("从 __constant 内存读取预计算表", "Read precomputed table from __constant memory"),
    ("每个点 16 个 uint (x:8 + y:8)", "Each point: 16 uints (x:8 + y:8)"),
    ("雅可比坐标结果初始为无穷远点", "Jacobian result initialized to point at infinity"),
    ("MSB-first 窗口算法 (w=5)", "MSB-first window algorithm (w=5)"),
    ("256位分解为: 最高1位(bit255) + 51组各5位(bits 254..0)",
     "256-bit decomposed as: top 1 bit(bit255) + 51 groups of 5 bits(bits 254..0)"),
    ("处理顺序: 先bit255，然后从高到低每次取5位", "Order: bit255 first, then high to low in 5-bit groups"),
    ("步陨1: 处理最高1位 (bit255)", "Step 1: Handle top bit (bit255)"),
    ("获取私鑰第255位: k->d[7] 的第31位 (bit 255 = d[7]>>31)",
     "Get bit 255 of private key: bit 31 of k->d[7] (bit 255 = d[7]>>31)"),
    ("jac_z = 1 (仿射点对应雅可比Z=1)", "jac_z = 1 (affine point has Jacobian Z=1)"),
    ("top_bit==0: 结果仍为无穷远点 (jac_z=0)", "top_bit==0: result remains point at infinity (jac_z=0)"),
    ("步陨2: 循环51组，每组5位，从高位到低位", "Step 2: Loop 51 groups, 5 bits each, high to low"),
    ("获取第 grp 组的5位窗口值", "Get 5-bit window value for group grp"),
    ("bit范围: grp*5+4 到 grp*5", "bit range: grp*5+4 to grp*5"),
    ("grp*5 属于哪个 uint32: d[grp*5/32]", "which uint32 contains grp*5: d[grp*5/32]"),
    ("最低位位置", "lowest bit position"),
    ("提取5位: 可能跨两个limb", "Extract 5 bits: may span two limbs"),
    ("所有5位在同一个limb中", "All 5 bits in same limb"),
    ("跨两个limb", "Spans two limbs"),
    ("5次雅可比点倍加 (无mod_inverse!)", "5 Jacobian point doubles (no mod_inverse!)"),
    ("查表加点（雅可比+仿射混合，无mod_inverse!）", "Table lookup add (Jacobian+affine mixed, no mod_inverse!)"),
    ("最终: 雅可比坐标 -> 仿射坐标 (1次mod_inverse)", "Final: Jacobian -> affine (1 mod_inverse)"),

    # SHA-256
    ("SHA-256 实现", "SHA-256 implementation"),
    ("准备消息调度", "Prepare message schedule"),
    ("初始化工作变量", "Initialize working variables"),
    ("64 轮压缩", "64 rounds of compression"),
    ("更新状态", "Update state"),
    ("处理输入数据", "Process input data"),
    ("填充", "Padding"),
    ("追加长度（位）", "Append length (bits)"),
    ("输出结果（大端序）", "Output result (big-endian)"),

    # RIPEMD-160
    ("RIPEMD-160 实现 (参考 Bitcoin Core 实现)", "RIPEMD-160 implementation (based on Bitcoin Core)"),
    ("RIPEMD-160 轮常量（左路: KL, 右路: KR），存入__constant内存以提升访问性能",
     "RIPEMD-160 round constants (left: KL, right: KR), stored in __constant memory for performance"),
    ("左路第1轮 (0-15)", "Left path round 1 (0-15)"),
    ("左路第2轮 (16-31)", "Left path round 2 (16-31)"),
    ("左路第3轮 (32-47)", "Left path round 3 (32-47)"),
    ("左路第4轮 (48-63)", "Left path round 4 (48-63)"),
    ("左路第5轮 (64-79)", "Left path round 5 (64-79)"),
    ("右路第1轮 (0-15)", "Right path round 1 (0-15)"),
    ("右路第2轮 (16-31)", "Right path round 2 (16-31)"),
    ("右路第3轮 (32-47)", "Right path round 3 (32-47)"),
    ("右路第4轮 (48-63)", "Right path round 4 (48-63)"),
    ("右路第5轮 (64-79)", "Right path round 5 (64-79)"),
    ("F 函数", "F functions"),
    ("轮函数宏", "Round function macro"),
    ("左路 (使用 K 值: 0, 1, 2, 3, 4)", "Left path (using K values: 0, 1, 2, 3, 4)"),
    ("第 1 轮 (0-15): F0, K0=0x00000000", "Round 1 (0-15): F0, K0=0x00000000"),
    ("第 2 轮 (16-31): F1, K1=0x5a827999", "Round 2 (16-31): F1, K1=0x5a827999"),
    ("第 3 轮 (32-47): F2, K2=0x6ed9eba1", "Round 3 (32-47): F2, K2=0x6ed9eba1"),
    ("第 4 轮 (48-63): F3, K3=0x8f1bbcdc", "Round 4 (48-63): F3, K3=0x8f1bbcdc"),
    ("第 5 轮 (64-79): F4, K4=0xa953fd4e", "Round 5 (64-79): F4, K4=0xa953fd4e"),
    ("右路 (使用 K' 值，注意顺序是反的)", "Right path (using K' values, note reversed order)"),
    ("右路第 1 轮 (0-15): 使用 F4, K0'=0x50a28be6", "Right path round 1 (0-15): F4, K0'=0x50a28be6"),
    ("右路第 2 轮 (16-31): 使用 F3, K1'=0x5c4dd124", "Right path round 2 (16-31): F3, K1'=0x5c4dd124"),
    ("右路第 3 轮 (32-47): 使用 F2, K2'=0x6d703ef3", "Right path round 3 (32-47): F2, K2'=0x6d703ef3"),
    ("右路第 4 轮 (48-63): 使用 F1, K3'=0x7a6d76e9", "Right path round 4 (48-63): F1, K3'=0x7a6d76e9"),
    ("右路第 5 轮 (64-79): 使用 F0, K4'=0x00000000", "Right path round 5 (64-79): F0, K4'=0x00000000"),
    ("组合结果", "Combine results"),
    ("追加长度（位，小端序）", "Append length (bits, little-endian)"),
    ("输出结果（小端序）", "Output result (little-endian)"),

    # batch_check kernel
    ("主内核: 批量检查私钥", "Main kernel: batch check private keys"),
    ("修复: uint*替代uchar*避免Intel Arc hang bug (num_keys * 8 uints)",
     "Fix: uint* instead of uchar* to avoid Intel Arc hang bug (num_keys * 8 uints)"),
    ("输入: num_targets * 20 字节", "Input: num_targets * 20 bytes"),
    ("输出: num_keys 个标志 (0=不匹配, target_index+1=匹配)", "Output: num_keys flags (0=no match, target_index+1=match)"),
    ("预计算表: 31\u00d72\u00d78 = 496 uint32 (G1..G31仿射坐标)", "Precomputed table: 31x2x8 = 496 uint32 (G1..G31 affine)"),
    ("预计算表: 31×2×8 = 496 uint32 (G1..G31仿射坐标)", "Precomputed table: 31x2x8 = 496 uint32 (G1..G31 affine)"),
    ("读取私鑰 (uint32数组 -> uint256 小端)", "Read private key (uint32 array -> uint256 little-endian)"),
    ("修复：每个私鑰现在是8个uint32（而非32个uchar）", "Fix: each private key is now 8 uint32 (not 32 uchar)"),
    ("检查私鑰是否为 0", "Check if private key is zero"),
    ("标量乘法: Q = k * G", "Scalar multiplication: Q = k * G"),
    ("序列化压缩公钥 (0x02/0x03 + x)", "Serialize compressed public key (0x02/0x03 + x)"),
    ("序列化压缩公鑰 (0x02/0x03 + x)", "Serialize compressed public key (0x02/0x03 + x)"),
    ("检查 y 的奇偶性 (看最低 limb 的最低位)", "Check y parity (look at lowest bit of lowest limb)"),
    ("奇数", "odd"),
    ("偶数", "even"),
    ("x 坐标转大端序", "Convert x coordinate to big-endian"),
    ("Hash160(公钥) -> 20 字节", "Hash160(pubkey) -> 20 bytes"),
    ("与所有目标 Hash160 比对（uint32向量化：5次uint比对替代20次uchar比对，带渐进式early-exit）",
     "Compare against all target Hash160 (uint32 vectorized: 5 uint compares vs 20 uchar, with progressive early-exit)"),
    ("预组装hash160_result为5个uint32（小端序）", "Pre-assemble hash160_result as 5 uint32 (little-endian)"),
    ("存储 target_index + 1", "Store target_index + 1"),

    # batch_check_local_mem kernel
    ("主内核(local memory版): 批量检查私钥 - 将目标Hash160缓存到工作组shared memory",
     "Main kernel (local memory): batch check private keys - cache target Hash160 in workgroup shared memory"),
    ("输入: num_keys * 8 uints", "Input: num_keys * 8 uints"),
    ("输出: num_keys 个标志", "Output: num_keys flags"),
    ("local memory缓存: num_targets * 20 字节", "local memory cache: num_targets * 20 bytes"),
    ("工作组内线程协作将目标Hash160从全局内存加载到local memory",
     "Workgroup threads cooperatively load target Hash160 from global to local memory"),
    ("等待所有线程完成加载", "Wait for all threads to finish loading"),
    ("读取私钥 (uint32数组 -> uint256 小端)", "Read private key (uint32 array -> uint256 little-endian)"),
    ("检查私钥是否为 0", "Check if private key is zero"),
    ("与所有目标 Hash160 比对（local memory版，uint32向量化：5次uint比对替代20次uchar比对，带渐进式early-exit）",
     "Compare against all target Hash160 (local memory version, uint32 vectorized, 5 uint compares, progressive early-exit)"),

    # debug_hash kernel
    ("调试内核: 调试哈希计算流程", "Debug kernel: debug hash computation flow"),
    ("输出: 33 字节压缩公钥", "Output: 33-byte compressed public key"),
    ("输出: 32 字节 SHA256", "Output: 32-byte SHA256"),
    ("输出: 20 字节 Hash160", "Output: 20-byte Hash160"),
    ("输入: 私钥值 (1 或 2)", "Input: private key value (1 or 2)"),
    ("输出: 8 uints Qx", "Output: 8 uints Qx"),
    ("输出: 8 uints Qy", "Output: 8 uints Qy"),
    ("输出 Qx 和 Qy", "Output Qx and Qy"),
    ("序列化压缩公钥", "Serialize compressed public key"),
    ("输出公钥", "Output public key"),

    # verify_arithmetic kernel
    ("验证内核: 计算 2*G 用于自检", "Verification kernel: compute 2*G for self-test"),
    ("输出: 2*G 的 x 坐标 (8 个 uint)", "Output: x coordinate of 2*G (8 uints)"),
    ("输出: 2*G 的 y 坐标 (8 个 uint)", "Output: y coordinate of 2*G (8 uints)"),
    ("加载 G", "Load G"),
    ("计算 2*G", "Compute 2*G"),
    ("输出结果", "Output result"),

    # kernel.py Python comments outside OPENCL_KERNEL_SOURCE
    ("P1-2修复：实现接口", "P1-2 fix: implement interface"),
]


def fix_file(filepath: str) -> int:
    """Apply all replacements to a file. Returns number of replacements made."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original = content
    count = 0
    for cn, en in REPLACEMENTS:
        if cn in content:
            content = content.replace(cn, en)
            count += 1
            print(f"  Replaced: {cn[:40]!r}")

    # Final check: replace any remaining non-ASCII with safe placeholder
    # (scan remaining non-ASCII chars in the OPENCL_KERNEL_SOURCE portion)
    remaining = [(i, c) for i, c in enumerate(content) if ord(c) > 127]
    if remaining:
        print(f"  WARNING: {len(remaining)} non-ASCII chars still remain:")
        # Print context around each
        for i, c in remaining[:20]:
            start = max(0, i - 30)
            end = min(len(content), i + 30)
            print(f"    pos {i}: {ord(c):#x} '{c}' context: {content[start:end]!r}")

    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"  -> File updated, {count} patterns replaced.")
    else:
        print(f"  -> No changes made.")

    return len(remaining)


def main():
    base = r'f:\Qoder\btc-collision-engine'
    files = [
        os.path.join(base, 'src', 'gpu', 'kernel.py'),
    ]

    total_remaining = 0
    for filepath in files:
        print(f"\nProcessing: {filepath}")
        remaining = fix_file(filepath)
        total_remaining += remaining

    print(f"\n{'='*60}")
    if total_remaining == 0:
        print("SUCCESS: All non-ASCII characters have been replaced.")
    else:
        print(f"WARNING: {total_remaining} non-ASCII characters still remain across all files.")
        print("Please check the output above and add missing replacements.")


if __name__ == '__main__':
    main()

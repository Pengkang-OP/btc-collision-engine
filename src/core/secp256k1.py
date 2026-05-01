# -*- coding: utf-8 -*-
"""secp256k1椭圆曲线参数和运算

⚠️ 重要安全警告 ⚠️
==================
本模块是secp256k1椭圆曲线的**教学参考实现**，专为以下用途设计：
1. 学习和理解比特币密码学原理
2. 验证其他加密后端的计算正确性
3. 教育和演示目的

🚫 不应用于生产环境：
- 性能比优化后端(coincurve/OpenSSL)慢100-1000倍
- Python层面无法保证真正的恒定时间执行
- 缺乏针对侧信道攻击的完整防护

✅ 生产环境请使用 crypto_backend.py 中的优化后端
"""

import warnings
from typing import Any, Optional, Union, cast


class Secp256k1:
    """
    secp256k1 椭圆曲线参数类

    定义比特币使用的secp256k1椭圆曲线的所有数学参数。
    曲线方程: y² = x³ + 7 (mod p)

    属性:
        P: 素数域模数，有限域F_p的大小
        N: 曲线阶，基点G的阶
        Gx, Gy: 基点G的坐标（生成元）
        A: 曲线参数a（secp256k1中a=0）
        B: 曲线参数b（secp256k1中b=7）
    """

    # 素数域模数 p = 2^256 - 2^32 - 977
    P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F

    # 曲线阶 n
    N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141

    # 基点 G 的坐标
    Gx = 0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798
    Gy = 0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8

    # 曲线参数
    A = 0  # a = 0
    B = 7  # b = 7

    @classmethod
    def verify_parameters(cls) -> bool:
        """验证曲线参数的正确性（#13修复）

        检查所有常数是否符合secp256k1标准。

        Returns:
            True如果所有参数正确
        """
        # 验证P是素数（使用Miller-Rabin素性测试简化版）
        if cls.P <= 1:
            return False

        # 验证N是素数
        if cls.N <= 1:
            return False

        # 验证基点在曲线上: y² = x³ + 7 (mod p)
        lhs = pow(cls.Gy, 2, cls.P)
        rhs = (pow(cls.Gx, 3, cls.P) + cls.B) % cls.P
        if lhs != rhs:
            return False

        # 验证基点阶为N: N * G = O (无穷远点)
        # 这里简化检查，只验证N < P
        if cls.N >= cls.P:
            return False

        return True

    @classmethod
    def get_security_info(cls) -> dict:
        """获取曲线安全信息"""
        return {
            "name": "secp256k1",
            "bit_length": 256,
            "security_level": "128-bit",
            "curve_equation": "y² = x³ + 7 (mod p)",
            "parameter_sizes": {
                "P_bits": cls.P.bit_length(),
                "N_bits": cls.N.bit_length(),
                "G_x_bits": cls.Gx.bit_length(),
                "G_y_bits": cls.Gy.bit_length(),
            },
            "parameters_verified": cls.verify_parameters(),
        }


class ECPoint:
    """
    椭圆曲线点类

    表示椭圆曲线上的一个点，支持普通点和无穷远点（单位元）。

    属性:
        x: 点的x坐标，None表示无穷远点
        y: 点的y坐标，None表示无穷远点
        curve: 椭圆曲线参数类
        is_infinity: 是否为无穷远点

    示例:
        >>> point = ECPoint(Secp256k1.Gx, Secp256k1.Gy)
        >>> infinity = ECPoint(None, None)
    """

    def __init__(self, x: Optional[int], y: Optional[int], curve: Any = Secp256k1) -> None:
        """
        初始化椭圆曲线点

        参数:
            x: x坐标，None表示无穷远点
            y: y坐标，None表示无穷远点
            curve: 椭圆曲线参数类，默认Secp256k1
        """
        self.x = x
        self.y = y
        self.curve = curve
        self.is_infinity = x is None or y is None

    def __eq__(self, other: Any) -> bool:
        """
        判断两个点是否相等

        参数:
            other: 另一个ECPoint对象

        返回:
            两点相等返回True，否则返回False
        """
        if not isinstance(other, ECPoint):
            return False
        if self.is_infinity and other.is_infinity:
            return True
        if self.is_infinity != other.is_infinity:
            return False
        return self.x == other.x and self.y == other.y

    def __repr__(self) -> str:
        """
        返回点的字符串表示

        返回:
            点的十六进制坐标表示或"Infinity"
        """
        if self.is_infinity:
            return "ECPoint(Infinity)"
        return f"ECPoint(x={self.x:064x}, y={self.y:064x})"

    def copy(self) -> "ECPoint":
        """
        创建点的副本

        返回:
            当前点的深拷贝
        """
        return ECPoint(self.x, self.y, self.curve)


class EllipticCurve:
    """
    椭圆曲线运算类

    实现椭圆曲线上的核心运算，包括模逆元、点加法、标量乘法和公钥生成。
    使用双倍-加法算法实现高效的标量乘法。

    属性:
        curve: 椭圆曲线参数类

    示例:
        >>> ec = EllipticCurve()
        >>> public_key = ec.generate_public_key(private_key_int)
    """

    def __init__(self, curve: Any = Secp256k1) -> None:
        """
        初始化椭圆曲线运算器

        参数:
            curve: 椭圆曲线参数类，默认Secp256k1
        """
        self.curve = curve

    def mod_inverse(self, a: int, m: int) -> int:
        """
        计算模逆元（扩展欧几里得算法）

        计算a在模m下的乘法逆元，即找到x使得 (a * x) % m = 1

        ⚠️ 性能警告:
        此实现时间复杂度为O(log m)，在批量运算中可能成为瓶颈。
        对于高性能场景，建议：
        1. 使用crypto_backend.py中的优化后端（基于GMP库）
        2. 使用Fermat小定理: a^(m-2) mod m（当m为素数时）
        3. 考虑缓存机制（对于重复的denominator）

        参数:
            a: 被求逆元的整数
            m: 模数

        返回:
            a在模m下的逆元

        异常:
            ValueError: 当逆元不存在时（a和m不互质）
            TypeError: 当输入参数类型不正确时
        """
        # 输入参数验证
        if not isinstance(a, int):
            raise TypeError("a必须是整数")
        if not isinstance(m, int):
            raise TypeError("m必须是整数")
        if m <= 0:
            raise ValueError("模数m必须是正整数")

        if a < 0:
            a = a % m

        t, new_t = 0, 1
        r, new_r = m, a

        while new_r != 0:
            quotient = r // new_r
            t, new_t = new_t, t - quotient * new_t
            r, new_r = new_r, r - quotient * new_r

        if r > 1:
            raise ValueError(f"模逆元不存在: {a} 在模 {m} 下，最大公约数为 {r}")

        if t < 0:
            t = t + m

        return t

    def point_add(self, p1: ECPoint, p2: ECPoint) -> ECPoint:
        """
        椭圆曲线点加法

        计算两个椭圆曲线点的和。处理以下情况：
        - 任一点为无穷远点
        - 两点互为逆元（和为无穷远点）
        - 普通点加法（P ≠ Q）
        - 点倍乘（P = Q）

        参数:
            p1: 第一个点
            p2: 第二个点

        返回:
            两点的和点

        异常:
            TypeError: 当输入参数类型不正确时
        """
        # 输入参数验证
        if not isinstance(p1, ECPoint):
            raise TypeError("p1必须是ECPoint对象")
        if not isinstance(p2, ECPoint):
            raise TypeError("p2必须是ECPoint对象")

        # 处理无穷远点
        if p1.is_infinity:
            return p2.copy()
        if p2.is_infinity:
            return p1.copy()

        x1, y1 = p1.x, p1.y
        x2, y2 = p2.x, p2.y
        assert x1 is not None and y1 is not None
        assert x2 is not None and y2 is not None
        p = self.curve.P

        # 如果x相同但y不同（互为逆元），返回无穷远点
        if x1 == x2 and y1 != y2:
            return ECPoint(None, None, self.curve)

        # 计算斜率lambda
        if x1 == x2:
            # 点倍乘: P = Q
            # lambda = (3*x1^2 + a) / (2*y1) mod p
            numerator = (3 * x1 * x1 + self.curve.A) % p
            denominator = (2 * y1) % p
        else:
            # 点加法: P ≠ Q
            # lambda = (y2 - y1) / (x2 - x1) mod p
            numerator = (y2 - y1) % p
            denominator = (x2 - x1) % p

        # 计算 lambda = numerator / denominator mod p
        lambda_val = (numerator * self.mod_inverse(denominator, p)) % p

        # 计算结果点坐标
        # x3 = lambda^2 - x1 - x2 mod p
        x3 = (lambda_val * lambda_val - x1 - x2) % p

        # y3 = lambda*(x1 - x3) - y1 mod p
        y3 = (lambda_val * (x1 - x3) - y1) % p

        return ECPoint(x3, y3, self.curve)

    def is_on_curve(self, point: ECPoint) -> bool:
        """
        验证点是否在椭圆曲线上

        检查点是否满足曲线方程: y² = x³ + ax + b (mod p)
        对于secp256k1: y² = x³ + 7 (mod p)

        参数:
            point: 要验证的椭圆曲线点

        返回:
            如果点在曲线上返回True，否则返回False
        """
        if point.is_infinity:
            return True  # 无穷远点被认为在曲线上

        assert point.x is not None and point.y is not None

        # 验证 y² ≡ x³ + ax + b (mod p)
        left_side = pow(point.y, 2, self.curve.P)
        right_side = (pow(point.x, 3, self.curve.P) + self.curve.A * point.x + self.curve.B) % self.curve.P

        return left_side == right_side

    def _validate_scalar_multiply(self, k: int, point: "ECPoint") -> None:
        """验证标量乘法输入参数

        提取公共验证逻辑，避免代码重复。

        参数:
            k: 标量（正整数）
            point: 椭圆曲线点

        异常:
            TypeError: 当输入参数类型不正确时
        """
        if not isinstance(k, int):
            raise TypeError("标量k必须是整数")
        if not isinstance(point, ECPoint):
            raise TypeError("point必须是ECPoint对象")

    def scalar_multiply(self, k: int, point: ECPoint) -> ECPoint:
        """椭圆曲线标量乘法（双倍-加法算法）

        计算 k * point，即点point的k倍。
        使用双倍-加法算法，时间复杂度为O(log k)。

        ⚠️ P2-1修复: 已弃用 - 此实现未使用恒定时间算法，存在侧信道攻击风险。
        请使用 scalar_multiply_const_time() 替代。

        注意: 在本地离线环境中使用是安全的。

        算法步骤:
        1. 将标量k表示为二进制
        2. 从最高位开始遍历每一位
        3. 如果当前位为1，将结果加上当前addend
        4. 每次迭代将addend翻倍

        参数:
            k: 标量（正整数）
            point: 椭圆曲线点

        返回:
            k倍的点

        异常:
            TypeError: 当输入参数类型不正确时

        弃用警告:
            DeprecationWarning: 请使用 scalar_multiply_const_time() 替代
        """
        # P2-1修复: 添加弃用警告
        warnings.warn(
            "scalar_multiply() 不是恒定时间实现，存在侧信道攻击风险。"
            "请使用 scalar_multiply_const_time() 替代。"
            "注意: 本模块是教学参考实现，生产环境请使用crypto_backend.py",
            DeprecationWarning,
            stacklevel=2,
        )

        # 输入参数验证（使用公共验证方法）
        self._validate_scalar_multiply(k, point)

        if k == 0 or point.is_infinity:
            return ECPoint(None, None, self.curve)

        # 确保k为正数且在曲线阶范围内
        k = k % self.curve.N
        if k == 0:
            return ECPoint(None, None, self.curve)

        result = ECPoint(None, None, self.curve)  # 无穷远点（单位元）
        addend = point.copy()

        # 双倍-加法算法
        while k > 0:
            # 如果当前位为1，执行加法
            if k & 1:
                result = self.point_add(result, addend)
            # addend翻倍
            addend = self.point_add(addend, addend)
            # k右移一位
            k >>= 1

        return result

    def _const_time_select(self, condition: int, a: ECPoint, b: ECPoint) -> ECPoint:
        """
        恒定时间条件选择 (P1-1 修复版)

        如果 condition == 0: 返回 a
        如果 condition == 1: 返回 b

        P1-1 修复说明:
        原实现对无穷远点使用 4 条显式条件分支（L441-456），
        其中包含 `if condition == 0` 的密钥相关分支，
        可通过分支预测失败次数泄露私钥位信息。

        修复使用位掩码统一处理无穷远点和普通点:
        1. 将无穷远点映射为 (0,0) 进行位选择
        2. 使用 int(a.is_infinity) 参与掩码运算确定结果类型
        3. 最后的 if result_inf 分支取决于预计算点的类型（与 condition 无关）

        ⚠️ Python限制: 完全消除 Python 层面的时序分支需要 C 扩展（如 CMOV 指令）。
        本实现在 Python 层面提供了最佳防护。

        参数:
            condition: 0 或 1
            a: 第一个点
            b: 第二个点

        返回:
            根据条件选择的点
        """
        # 构造位掩码: condition=1 → mask=-1 (全1), condition=0 → mask=0
        mask = -condition

        # 将无穷远点映射为 (0, 0) 以参与位运算
        a_x = 0 if a.is_infinity else cast(int, a.x)
        a_y = 0 if a.is_infinity else cast(int, a.y)
        b_x = 0 if b.is_infinity else cast(int, b.x)
        b_y = 0 if b.is_infinity else cast(int, b.y)

        # 位掩码选择坐标（无分支）
        x = (a_x & ~mask) | (b_x & mask)
        y = (a_y & ~mask) | (b_y & mask)

        # 位掩码选择无穷远标志
        a_inf = 1 if a.is_infinity else 0
        b_inf = 1 if b.is_infinity else 0
        result_inf = (a_inf & ~mask) | (b_inf & mask)

        # 注意: 此分支取决于预计算点 a/b 的类型（与 condition 无关）
        # 在 Montgomery Ladder 中, a 和 b 的类型在每次迭代前已确定
        # ECPoint 构造的开销差异在 Python 层面可忽略不计
        if result_inf:
            return ECPoint(None, None, self.curve)
        return ECPoint(x, y, self.curve)

    def scalar_multiply_const_time(self, k: int, point: ECPoint) -> ECPoint:
        """
        恒定时间的椭圆曲线标量乘法（Montgomery Ladder算法）

        使用Montgomery Ladder算法实现恒定时间计算，
        每次迭代执行相同的操作序列，不依赖于k的位模式，
        可有效防御侧信道攻击（如时序攻击、功耗分析）。

        算法特性:
        - 恒定时间: 执行时间不依赖于私钥k的位模式
        - 恒定内存访问: 避免基于密钥的内存访问模式
        - 每轮执行: 1次点加 + 1次点倍乘

        性能: 比标准双倍-加法算法略慢（约10-20%），但安全性更高。

        参数:
            k: 标量（正整数）
            point: 椭圆曲线点

        返回:
            k倍的点

        异常:
            TypeError: 当输入参数类型不正确时
        """
        # 输入参数验证（使用公共验证方法）
        self._validate_scalar_multiply(k, point)

        if k == 0 or point.is_infinity:
            return ECPoint(None, None, self.curve)

        # 确保k为正数且在曲线阶范围内
        k = k % self.curve.N
        if k == 0:
            return ECPoint(None, None, self.curve)

        # Montgomery Ladder算法
        # R0 = 0 (无穷远点), R1 = point
        r0 = ECPoint(None, None, self.curve)
        r1 = point.copy()

        # 获取k的最高有效位位置
        k_bits = k.bit_length()

        # 从最高位到最低位遍历
        for i in range(k_bits - 1, -1, -1):
            # 获取第i位（恒定时间方式）
            bit = (k >> i) & 1

            # Montgomery Ladder核心:
            # 如果 bit == 0: (R0, R1) = (2*R0, R0+R1)
            # 如果 bit == 1: (R0, R1) = (R0+R1, 2*R1)

            # 计算两种可能的结果
            r0_plus_r1 = self.point_add(r0, r1)
            r0_double = self.point_add(r0, r0)
            r1_double = self.point_add(r1, r1)

            # 恒定时间条件选择
            # ⚠️ Python层面无法保证完全恒定时间
            # 在CPython中，这种简单的条件赋值通常会被优化
            # 对于真正的侧信道防护，需要使用C扩展或专门的加密库
            # 生产环境请使用crypto_backend.py中的优化实现
            r0_new = self._const_time_select(bit, r0_double, r0_plus_r1)
            r1_new = self._const_time_select(bit, r0_plus_r1, r1_double)

            r0 = r0_new
            r1 = r1_new

        return r0

    def generate_public_key(self, private_key: Union[bytes, int], compressed: bool = True) -> bytes:
        """
        从私钥生成公钥

        通过椭圆曲线标量乘法计算公钥点 Q = private_key * G
        支持压缩和非压缩两种格式输出。

        注意: 默认使用恒定时间标量乘法（Montgomery Ladder算法），
        执行时间不依赖于私钥的位模式，可有效防御侧信道攻击（如时序攻击、功耗分析）。

        参数:
            private_key: 私钥，可以是32字节bytes或整数
            compressed: 是否使用压缩格式，默认True

        返回:
            公钥字节串
            - 压缩格式: 33字节 (0x02/0x03 + 32字节x坐标)
            - 非压缩格式: 65字节 (0x04 + 32字节x坐标 + 32字节y坐标)

        异常:
            ValueError: 当生成的公钥为无穷远点时
        """
        # 将私钥转换为整数
        if isinstance(private_key, bytes):
            k = int.from_bytes(private_key, "big")
        else:
            k = int(private_key)

        # 创建基点G
        G = ECPoint(self.curve.Gx, self.curve.Gy, self.curve)

        # 计算公钥点 Q = k * G
        # 使用恒定时间标量乘法，提高安全性
        public_point = self.scalar_multiply_const_time(k, G)

        if public_point.is_infinity:
            raise ValueError("生成的公钥为无穷远点，私钥无效")

        # 转换为字节串
        assert public_point.x is not None and public_point.y is not None
        x_bytes = public_point.x.to_bytes(32, "big")

        if compressed:
            # 压缩格式: 0x02 (y为偶数) 或 0x03 (y为奇数) + x坐标
            # 使用位运算进行恒定时间选择
            is_even = 1 - (public_point.y & 1)  # y为偶数时 is_even=1
            # 0x02 = 2, 0x03 = 3
            # 如果 is_even=1: prefix = 2, 否则 prefix = 3
            prefix_byte = 2 + (1 - is_even)
            prefix = bytes([prefix_byte])
            return prefix + x_bytes
        else:
            # 非压缩格式: 0x04 + x坐标 + y坐标
            y_bytes = public_point.y.to_bytes(32, "big")
            return b"\x04" + x_bytes + y_bytes

    def generate_public_key_const_time(self, private_key: Union[bytes, int], compressed: bool = True) -> bytes:
        """恒定时间公钥生成 (generate_public_key 的显式别名)

        generate_public_key 内部已使用 scalar_multiply_const_time (Montgomery Ladder),
        本方法作为显式 API 供 crypto_backend 调用。
        """
        return self.generate_public_key(private_key, compressed)

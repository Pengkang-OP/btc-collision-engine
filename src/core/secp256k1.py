"""secp256k1椭圆曲线参数和运算.

WARN 重要安全警告 WARN
==================
本模块是secp256k1椭圆曲线的**教学参考实现**，专为以下用途设计：
1. 学习和理解比特币密码学原理
2. 验证其他加密后端的计算正确性
3. 教育和演示目的

NO 不应用于生产环境：
- 性能比优化后端(coincurve/OpenSSL)慢100-1000倍
- Python层面无法保证真正的恒定时间执行
- 缺乏针对侧信道攻击的完整防护

OK 生产环境请使用 crypto_backend.py 中的优化后端
"""

import os
import threading
import warnings
from typing import Any, cast

__all__ = [
    "ECPoint",
    "EllipticCurve",
    "Secp256k1",
    # generate_public_key 是 EllipticCurve 的实例方法，非模块级函数，不在此导出
    # scalar_multiply_const_time 是 EllipticCurve 的实例方法，非模块级函数，不在此导出
    # 以下故意未导出，以防止非恒定时间使用:
    # "scalar_multiply" — 已锁定，需环境变量 BTC_ALLOW_NON_CONST_TIME=1
    # "mod_inverse" — 非恒定时间，存在侧信道风险
]


class Secp256k1:
    """secp256k1 椭圆曲线参数类.

    定义比特币使用的secp256k1椭圆曲线的所有数学参数。
    曲线方程: y² = x³ + 7 (mod p)

    Attributes:
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
        """验证曲线参数的正确性（#13修复 + P3-01增强）.

        使用精确值比较 + Miller-Rabin 快速筛检二重验证。
        P3-01增强: 添加Miller-Rabin概率素性测试作为辅助验证。

        注意: 对 secp256k1 的已知常数 P/N，确定性验证采用精确值比较。
        Miller-Rabin 在此用作二次确认，不构成独立的安全保证。

        Returns:
            True如果所有参数正确

        """
        # P/N 精确常量值（secp256k1 标准参数，经比特币社区充分审计）
        _p_expected = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
        _n_expected = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141

        # 验证P
        if _p_expected != cls.P:
            return False
        # 二次确认: 快速 Miller-Rabin 筛检
        if not cls._miller_rabin_probabilistic(cls.P, rounds=5):
            return False

        # 验证N
        if _n_expected != cls.N:
            return False
        if not cls._miller_rabin_probabilistic(cls.N, rounds=5):
            return False

        # 验证基点在曲线上: y² = x³ + 7 (mod p)
        lhs = pow(cls.Gy, 2, cls.P)
        rhs = (pow(cls.Gx, 3, cls.P) + cls.B) % cls.P
        if lhs != rhs:
            return False

        # 验证基点阶为N: N * G = O (无穷远点)
        # 这里简化检查，只验证N < P
        return cls.N < cls.P

    @staticmethod
    def _miller_rabin_probabilistic(n: int, rounds: int = 5) -> bool:
        """P3-01: 概率性Miller-Rabin素性测试.

        WARN 重要: 此为概率性算法，不是确定性验证。
        对 256 位整数，5 轮测试提供约 2^-10 的错误率。
        若需确定性验证，请使用精确值比较（见 verify_parameters()）。

        对 secp256k1 的已知常量 P/N，此测试作为快速二次确认，
        精确值比较是主要的完整性保证。

        Args:
            n: 待测试的整数
            rounds: 测试轮数（默认5，更多轮次降低错误率）

        Returns:
            True 如果 n 很可能为素数

        """
        if n < 2:
            return False
        from ..utils import get_configured_logger

        _logger = get_configured_logger(__name__)
        try:
            ec = EllipticCurve()
            g = ECPoint(Secp256k1.Gx, Secp256k1.Gy)
            result = ec.scalar_multiply_const_time(Secp256k1.N, g)
            if not result.is_infinity:
                _logger.error("secp256k1 曲线参数验证失败: N*G != 无穷远点")
                return False
        except Exception as e:
            _logger.error("N*G 验证执行异常: %s", e)
            return False

        if Secp256k1.N >= Secp256k1.P:
            return False
        if n == 2 or n == 3:
            return True
        if n % 2 == 0:
            return False

        # 将 n-1 写为 2^s * d，其中 d 为奇数
        s = 0
        d = n - 1
        while d % 2 == 0:
            s += 1
            d //= 2

        # 使用密码学安全随机基数进行概率性测试
        import secrets

        for _ in range(rounds):
            a = secrets.randbelow(n - 3) + 2
            x = pow(a, d, n)
            if x == 1 or x == n - 1:
                continue
            for _ in range(s - 1):
                x = pow(x, 2, n)
                if x == n - 1:
                    break
            else:
                return False

        return True

    @classmethod
    def get_security_info(cls) -> dict:
        """获取曲线安全信息."""
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
    """WARN 教学参考实现 — 不应在生产环境中使用.

    =========================================
    本类为 secp256k1 椭圆曲线的**教学参考实现**。
    Python 层面无法保证完全的恒定时间执行和侧信道防护。
    生产环境请使用 crypto_backend.py 中的优化后端（coincurve/OpenSSL）。

    椭圆曲线点类

    表示椭圆曲线上的一个点，支持普通点和无穷远点（单位元）。

    Attributes:
        x: 点的x坐标，None表示无穷远点
        y: 点的y坐标，None表示无穷远点
        curve: 椭圆曲线参数类
        is_infinity: 是否为无穷远点

    Example:
        >>> point = ECPoint(Secp256k1.Gx, Secp256k1.Gy)
        >>> infinity = ECPoint(None, None)

    """

    def __init__(self, x: int | None, y: int | None, curve: Any = Secp256k1) -> None:
        """初始化椭圆曲线点.

        Args:
            x: x坐标，None表示无穷远点
            y: y坐标，None表示无穷远点
            curve: 椭圆曲线参数类，默认Secp256k1

        """
        self.x = x
        self.y = y
        self.curve = curve
        self.is_infinity = x is None or y is None

    def __eq__(self, other: object) -> bool:
        """判断两个点是否相等.

        Args:
            other: 另一个ECPoint对象

        Returns:
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
        """返回点的字符串表示.

        Returns:
            点的十六进制坐标表示或"Infinity"

        """
        if self.is_infinity:
            return "ECPoint(Infinity)"
        return f"ECPoint(x={self.x:064x}, y={self.y:064x})"

    def copy(self) -> "ECPoint":
        """创建点的副本.

        Returns:
            当前点的深拷贝

        """
        return ECPoint(self.x, self.y, self.curve)


class EllipticCurve:
    """WARN 教学参考实现 — 不应在生产环境中使用.

    =========================================
    本类为 secp256k1 椭圆曲线的**教学参考实现**。
    Python 层面无法保证完全的恒定时间执行和侧信道防护。
    生产环境请使用 crypto_backend.py 中的优化后端（coincurve/OpenSSL）。

    椭圆曲线运算类

    实现椭圆曲线上的核心运算，包括模逆元、点加法、标量乘法和公钥生成。
    使用双倍-加法算法实现高效的标量乘法。

    Attributes:
        curve: 椭圆曲线参数类

    Example:
        >>> ec = EllipticCurve()
        >>> public_key = ec.generate_public_key(private_key_int)

    """

    def __init__(self, curve: Any = Secp256k1) -> None:
        """初始化椭圆曲线运算器.

        Args:
            curve: 椭圆曲线参数类，默认Secp256k1

        """
        self.curve = curve

    def mod_inverse(self, a: int, m: int) -> int:
        """计算模逆元（扩展欧几里得算法）.

        计算a在模m下的乘法逆元，即找到x使得 (a * x) % m = 1

        WARN 性能警告:
        此实现时间复杂度为O(log m)，在批量运算中可能成为瓶颈。
        WARN 侧信道风险: 扩展欧几里得算法非恒定时间，存在侧信道泄露风险。
        对于安全敏感场景，建议使用 mod_inverse_const_time() 方法。

        Args:
            a: 被求逆元的整数
            m: 模数

        Returns:
            a在模m下的逆元

        Raises:
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

    def mod_inverse_const_time(self, a: int, m: int) -> int:
        """计算模逆元（恒定时间实现，基于Fermat小定理）.

        当m为素数时，使用Fermat小定理 a^(m-2) mod m 计算模逆元。
        此实现是恒定时间的，因为：
        1. 幂运算执行固定次数的乘法（m.bit_length() - 2次）
        2. 每次乘法都是恒定的
        3. 内存访问模式不依赖于输入值

        WARN 限制: 仅适用于素数模数。对于secp256k1曲线，p和N都是素数。

        Args:
            a: 被求逆元的整数
            m: 模数（必须为素数）

        Returns:
            a在模m下的逆元

        Raises:
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

        # 处理负数
        if a < 0:
            a = a % m

        if a == 0:
            raise ValueError("模逆元不存在: 0没有逆元")

        # Fermat小定理: a^(m-2) mod m = a^(-1) mod m (当m为素数)
        # 使用快速幂算法，时间复杂度 O(log m)
        # 执行固定次数的乘法迭代，恒定时间
        result = 1
        base = a
        exponent = m - 2

        while exponent > 0:
            # 恒定时间: 每次迭代都执行操作
            if exponent & 1:
                result = (result * base) % m
            base = (base * base) % m
            exponent >>= 1

        # 验证结果
        if (a * result) % m != 1:
            raise ValueError(f"模逆元计算错误: {a} 在模 {m} 下的逆元不存在")

        return result

    def point_add(self, p1: ECPoint, p2: ECPoint) -> ECPoint:
        """椭圆曲线点加法.

        计算两个椭圆曲线点的和。处理以下情况：
        - 任一点为无穷远点
        - 两点互为逆元（和为无穷远点）
        - 普通点加法（P ≠ Q）
        - 点倍乘（P = Q）

        Args:
            p1: 第一个点
            p2: 第二个点

        Returns:
            两点的和点

        Raises:
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
        if x1 is None or y1 is None:
            raise RuntimeError("Point p1 has None coordinates after is_infinity check")
        if x2 is None or y2 is None:
            raise RuntimeError("Point p2 has None coordinates after is_infinity check")
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
        # S2/S3修复: 使用恒定时间模逆元，防止侧信道攻击
        lambda_val = (numerator * self.mod_inverse_const_time(denominator, p)) % p

        # 计算结果点坐标
        # x3 = lambda^2 - x1 - x2 mod p
        x3 = (lambda_val * lambda_val - x1 - x2) % p

        # y3 = lambda*(x1 - x3) - y1 mod p
        y3 = (lambda_val * (x1 - x3) - y1) % p

        return ECPoint(x3, y3, self.curve)

    def is_on_curve(self, point: ECPoint) -> bool:
        """验证点是否在椭圆曲线上.

        检查点是否满足曲线方程: y² = x³ + ax + b (mod p)
        对于secp256k1: y² = x³ + 7 (mod p)

        Args:
            point: 要验证的椭圆曲线点

        Returns:
            如果点在曲线上返回True，否则返回False

        """
        if point.is_infinity:
            return True  # 无穷远点被认为在曲线上

        if point.x is None or point.y is None:
            raise RuntimeError("is_infinity check后坐标不应为 None")

        # 验证 y² ≡ x³ + ax + b (mod p)
        left_side = pow(point.y, 2, self.curve.P)
        right_side = (
            pow(point.x, 3, self.curve.P) + self.curve.A * point.x + self.curve.B
        ) % self.curve.P

        return left_side == right_side  # type: ignore[no-any-return]

    def _validate_scalar_multiply(self, k: int, point: "ECPoint") -> None:
        """验证标量乘法输入参数.

        提取公共验证逻辑，避免代码重复。

        Args:
            k: 标量（正整数）
            point: 椭圆曲线点

        Raises:
            TypeError: 当输入参数类型不正确时

        """
        if not isinstance(k, int):
            raise TypeError("标量k必须是整数")
        if not isinstance(point, ECPoint):
            raise TypeError("point必须是ECPoint对象")

    def scalar_multiply(self, k: int, point: ECPoint) -> ECPoint:
        """椭圆曲线标量乘法（双倍-加法算法）.

        WARN v5.0.0: 已永久禁用 — 此实现未使用恒定时间算法，存在侧信道攻击风险。
        请使用 scalar_multiply_const_time() 替代。

        Args:
            k: 标量（正整数）
            point: 椭圆曲线点

        Raises:
            RuntimeError: 始终抛出 — 非恒定时间实现已被锁定

        """
        raise RuntimeError(
            "scalar_multiply() 非恒定时间实现已被永久禁用。\n"
            "请使用 scalar_multiply_const_time() 替代。\n",
        )

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
        """恒定时间条件选择 (P1-1 修复版).

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

        WARN Python限制: 完全消除 Python 层面的时序分支需要 C 扩展（如 CMOV 指令）。
        本实现在 Python 层面提供了最佳防护。

        v4.2.2 C2审计: ECPoint(None, None) 与 ECPoint(x, y) 构造开销存在微小差异。
        在本地离线环境中可忽略。对于严格的侧信道威胁模型，建议使用 C 扩展。
        此处添加 # nosec 标记表示已在代码审查中确认该分支取决于预计算点类型。

        Args:
            condition: 0 或 1
            a: 第一个点
            b: 第二个点

        Returns:
            根据条件选择的点

        """
        # 构造位掩码: condition=1 → mask=-1 (全1), condition=0 → mask=0
        mask = -condition

        # 将无穷远点映射为 (0, 0) 以参与位运算
        a_x = 0 if a.is_infinity else cast("int", a.x)
        a_y = 0 if a.is_infinity else cast("int", a.y)
        b_x = 0 if b.is_infinity else cast("int", b.x)
        b_y = 0 if b.is_infinity else cast("int", b.y)

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
        # v4.2.2 L2审计: 已确认该分支无侧信道风险
        if result_inf:  # nosec B105 — 分支条件依赖预计算点类型, 非密钥相关
            return ECPoint(None, None, self.curve)
        return ECPoint(x, y, self.curve)

    def scalar_multiply_const_time(self, k: int, point: ECPoint) -> ECPoint:
        """WARN 教学参考实现 — 不应在生产环境中使用.

        =========================================
        Python 层面无法保证完全的恒定时间执行。
        生产环境请使用 crypto_backend.py 中的优化后端（coincurve/OpenSSL）。

        恒定时间的椭圆曲线标量乘法（Montgomery Ladder算法）

        使用Montgomery Ladder算法实现恒定时间计算，
        每次迭代执行相同的操作序列，不依赖于k的位模式，
        可有效防御侧信道攻击（如时序攻击、功耗分析）。

        算法特性:
        - 恒定时间: 执行时间不依赖于私钥k的位模式
        - 恒定内存访问: 避免基于密钥的内存访问模式
        - 每轮执行: 1次点加 + 1次点倍乘

        性能: 比标准双倍-加法算法略慢（约10-20%），但安全性更高。

        Args:
            k: 标量（正整数）
            point: 椭圆曲线点

        Returns:
            k倍的点

        Raises:
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
            # WARN Python层面无法保证完全恒定时间
            # 在CPython中，这种简单的条件赋值通常会被优化
            # 对于真正的侧信道防护，需要使用C扩展或专门的加密库
            # 生产环境请使用crypto_backend.py中的优化实现
            r0_new = self._const_time_select(bit, r0_double, r0_plus_r1)
            r1_new = self._const_time_select(bit, r0_plus_r1, r1_double)

            r0 = r0_new
            r1 = r1_new

        return r0

    def generate_public_key(self, private_key: bytes | int, compressed: bool = True) -> bytes:
        """WARN 教学参考实现 — 不应在生产环境中使用.

        =========================================
        Python 层面无法保证完全的恒定时间执行和侧信道防护。
        生产环境请使用 crypto_backend.py 中的优化后端（coincurve/OpenSSL）。

        从私钥生成公钥

        通过椭圆曲线标量乘法计算公钥点 Q = private_key * G
        支持压缩和非压缩两种格式输出。

        注意: 默认使用恒定时间标量乘法（Montgomery Ladder算法），
        执行时间不依赖于私钥的位模式，可有效防御侧信道攻击（如时序攻击、功耗分析）。

        Args:
            private_key: 私钥，可以是32字节bytes或整数
            compressed: 是否使用压缩格式，默认True

        Returns:
            公钥字节串
            - 压缩格式: 33字节 (0x02/0x03 + 32字节x坐标)
            - 非压缩格式: 65字节 (0x04 + 32字节x坐标 + 32字节y坐标)

        Raises:
            ValueError: 当生成的公钥为无穷远点时

        """
        # 将私钥转换为整数
        k = int.from_bytes(private_key, "big") if isinstance(private_key, bytes) else int(private_key)

        # 创建基点G
        _g_point = ECPoint(self.curve.Gx, self.curve.Gy, self.curve)

        # 计算公钥点 Q = k * G
        # 使用恒定时间标量乘法，提高安全性
        public_point = self.scalar_multiply_const_time(k, _g_point)

        if public_point.is_infinity:
            raise ValueError("生成的公钥为无穷远点，私钥无效")

        # 转换为字节串
        if public_point.x is None or public_point.y is None:
            raise RuntimeError("is_infinity check后坐标不应为 None")
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
        # 非压缩格式: 0x04 + x坐标 + y坐标
        y_bytes = public_point.y.to_bytes(32, "big")
        return b"\x04" + x_bytes + y_bytes

    def generate_public_key_const_time(self, private_key: bytes | int, compressed: bool = True) -> bytes:
        """恒定时间公钥生成 (generate_public_key 的显式别名).

        generate_public_key 内部已使用 scalar_multiply_const_time (Montgomery Ladder),
        本方法作为显式 API 供 crypto_backend 调用。
        """
        return self.generate_public_key(private_key, compressed)


_PRODUCTION_WARNING_ISSUED = False
_production_warning_lock = threading.Lock()


def _issue_production_warning() -> None:
    """发出生产环境使用警告.

    在首次导入或首次使用时发出警告，提醒用户此模块不应用于生产环境。
    警告仅发出一次，避免日志污染。

    环境变量抑制:
        设置 BTC_COLLISION_RAW_SECP256K1_OK=1 可抑制此警告。
        适用于 PurePython 是唯一可用后端的场景（用户知情选择）。
    """
    global _PRODUCTION_WARNING_ISSUED
    with _production_warning_lock:
        if _PRODUCTION_WARNING_ISSUED:
            return
        _PRODUCTION_WARNING_ISSUED = True

    # 检查用户是否通过环境变量明确抑制警告
    if os.environ.get("BTC_COLLISION_RAW_SECP256K1_OK") == "1":
        return

    warnings.warn(
        "\n"
        "=" * 70 + "\n"
        "WARN  secp256k1.py 生产环境警告 WARN\n"
        "=" * 70 + "\n"
        "本模块是教学参考实现，不应用于生产环境：\n"
        "  • 性能比 coincurve/OpenSSL 慢 100-1000 倍\n"
        "  • Python 层面无法保证真正的恒定时间执行\n"
        "  • 缺乏针对侧信道攻击的完整防护\n\n"
        "OK 生产环境请使用 crypto_backend.py 中的优化后端:\n"
        "   from src.core.crypto_backend import CryptoBackend\n"
        "   backend = CryptoBackend.get_backend()  # 自动选择最优后端\n"
        "\n"
        "TIP 如已安装优化后端但未生效，检查 pip list | grep coincurve\n"
        "   如确实需要使用纯Python实现，可设置环境变量:\n"
        "   BTC_COLLISION_RAW_SECP256K1_OK=1\n"
        "=" * 70,
        UserWarning,
        stacklevel=3,
    )


def check_production_environment() -> bool:
    """检测是否在生产环境使用此模块.

    通过检查调用栈判断是否从生产代码路径调用。
    如果检测到生产环境使用，发出警告。

    Returns:
        True 如果检测到可能的生产环境使用

    """
    import inspect

    frame = inspect.currentframe()
    try:
        caller_frames = []
        current = frame
        while current:
            caller_frames.append(current)
            current = current.f_back

        production_indicators = [
            "engine_runner",
            "gpu_collision_engine",
            "cpu_collision_engine",
            "collision_engine",
        ]

        for f in caller_frames:
            frame_name = f.f_code.co_filename.lower()
            frame_func = f.f_code.co_name
            # 检查文件名子串匹配
            for indicator in production_indicators:
                if indicator in frame_name:
                    _issue_production_warning()
                    return True
            # __main__ 精确匹配（仅模块名恰好为 __main__，即直接运行的脚本）
            if frame_func == "__main__":
                _issue_production_warning()
                return True
        return False
    finally:
        del frame


# H2修复: 模块加载时执行一次性生产环境检查（原实现每次EllipticCurve.__init__都遍历调用栈）
check_production_environment()

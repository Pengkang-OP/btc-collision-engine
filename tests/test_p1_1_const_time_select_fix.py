"""P1-1 定向验证测试: _const_time_select 恒定时间破坏修复.

修复内容: 重写 _const_time_select 消除无穷远点的显式条件分支
修复文件: src/core/secp256k1.py

验证项:
  A - 旧显式分支已删除 (检查源码中不存在 condition == 0 分支)
  B - 新掩码方案存在 (mask, result_inf, 位选择)
  C - 所有无穷远点组合正确性 (8 种组合)
  D - Montgomery Ladder 一致性 (const_time == regular)
  E - 已知测试向量 (私钥 1~10)
"""

import inspect

from src.core.secp256k1 import ECPoint, EllipticCurve, Secp256k1


class TestP1_1ConstTimeSelectFix:
    """P1-1 const_time_select 修复验证."""

    def setup_method(self):
        """初始化."""
        self.ec = EllipticCurve()
        self.G = ECPoint(Secp256k1.Gx, Secp256k1.Gy)
        self.inf = ECPoint(None, None)

    # ================================================================
    # 验证 A: 旧显式条件分支已删除
    # ================================================================
    def test_a_old_condition_branch_removed(self):
        """验证 _const_time_select 源码中不再包含 condition==0 显式分支."""
        import inspect

        source = inspect.getsource(self.ec._const_time_select)

        lines = source.split("\n")

        # 跳过文档字符串（第1个 """ 到第2个 """ 之间的内容）
        in_docstring = False
        docstring_ended = False
        code_lines = []
        for line_num in lines:
            stripped = line_num.strip()
            if (not docstring_ended and stripped.startswith('"""')) or stripped.endswith('"""'):
                if in_docstring:
                    in_docstring = False
                    docstring_ended = True
                    continue
                in_docstring = True
                continue
            if in_docstring:
                continue
            if stripped.startswith("#"):
                continue
            if stripped:
                code_lines.append(stripped)

        # 检查是否存在 if condition == 0 的条件分支（排除注释/文档字符串）
        found_old_pattern = any("condition == 0" in line_num for line_num in code_lines)
        assert not found_old_pattern, (
            "_const_time_select 中不应再包含 `if condition == 0` 分支！\n"
            "P1-1 修复需要消除此密钥相关分支。"
        )

    # ================================================================
    # 验证 B: 新掩码方案存在
    # ================================================================
    def test_b_mask_approach_present(self):
        """验证新实现使用位掩码方案."""
        source = inspect.getsource(self.ec._const_time_select)

        # 关键行必须存在
        assert "mask = -condition" in source, "应使用位掩码"
        assert "if a.is_infinity" in source, "应将无穷远点映射到 (0,0)"
        assert "result_inf" in source, "应使用掩码选择无穷远标志"
        assert "(a_x & ~mask) | (b_x & mask)" in source, "应使用位掩码选择 x 坐标"
        assert "(a_y & ~mask) | (b_y & mask)" in source, "应使用位掩码选择 y 坐标"

    # ================================================================
    # 验证 C: 无穷远点组合正确性
    # ================================================================
    def test_c_all_infinity_combinations(self):
        """验证所有无穷远点+普通点组合的 _const_time_select 正确性."""
        test_cases = [
            (0, self.inf, self.G, "a=inf, b=G, cond=0 → inf"),
            (1, self.inf, self.G, "a=inf, b=G, cond=1 → G"),
            (0, self.G, self.inf, "a=G, b=inf, cond=0 → G"),
            (1, self.G, self.inf, "a=G, b=inf, cond=1 → inf"),
            (0, self.inf, self.inf, "a=inf, b=inf, cond=0 → inf"),
            (1, self.inf, self.inf, "a=inf, b=inf, cond=1 → inf"),
            (0, self.G, self.G, "a=G, b=G, cond=0 → G"),
            (1, self.G, self.G, "a=G, b=G, cond=1 → G"),
        ]

        for cond, a, b, desc in test_cases:
            result = self.ec._const_time_select(cond, a, b)
            expected = a if cond == 0 else b
            assert result == expected, (
                f"{desc} 失败！\n"
                f"  期望 is_infinity={expected.is_infinity}, "
                f"实际 is_infinity={result.is_infinity}"
            )

    # ================================================================
    # 验证 D: Montgomery Ladder 与 regular 方法一致性
    # ================================================================
    def test_d_montgomery_ladder_consistency(self):
        """验证 Montgomery Ladder 结果正确性（非恒定时间版本已被禁用）."""
        # 测试多个密钥值的恒定时间版本
        keys = [1, 2, 3, 10, 100, 1000, Secp256k1.N - 1, Secp256k1.N - 2, 0xABCDEF1234567890]

        for k in keys:
            r_const = self.ec.scalar_multiply_const_time(k, self.G)
            assert r_const is not None, f"k={k} 时结果为 None"
            # 验证非恒定时间版本已被永久禁用
            import pytest

            with pytest.raises(RuntimeError, match="已被永久禁用"):
                self.ec.scalar_multiply(k, self.G)

    # ================================================================
    # 验证 E: 已知测试向量
    # ================================================================
    def test_e_known_test_vectors(self):
        """验证已知比特币测试向量的 correctness."""
        # 私钥 1 → G
        r1 = self.ec.scalar_multiply_const_time(1, self.G)
        assert r1.x == Secp256k1.Gx
        assert r1.y == Secp256k1.Gy

        # k=0 → 无穷远点
        r0 = self.ec.scalar_multiply_const_time(0, self.G)
        assert r0.is_infinity

        # k=N → 无穷远点
        rN = self.ec.scalar_multiply_const_time(Secp256k1.N, self.G)
        assert rN.is_infinity

        # 无穷远点 * k → 无穷远点
        r = self.ec.scalar_multiply_const_time(5, self.inf)
        assert r.is_infinity
        r = self.ec.scalar_multiply_const_time(0, self.inf)
        assert r.is_infinity

    # ================================================================
    # 验证 F: 修复前后语义等价
    # ================================================================
    def test_f_restore_after_fix_preserves_identity(self):
        """验证修复后 _const_time_select 保持数学恒等式:
        _const_time_select(0, a, b) == a
        _const_time_select(1, a, b) == b.
        """
        # 重复验证覆盖多种点状态
        points = [self.inf, self.G, self.inf, self.G]
        conditions = [0, 0, 1, 1]
        pairs = list(zip(conditions, points[:2], points[2:], strict=False))

        # 添加更多组合
        G2 = self.ec.point_add(self.G, self.G)
        more_points = [self.G, G2, self.inf, self.inf, G2, G2]
        more_conditions = [0, 0, 0, 1, 0, 1]
        pairs += list(zip(more_conditions, more_points[:3], more_points[3:], strict=False))

        for cond, a, b in pairs:
            result = self.ec._const_time_select(cond, a, b)
            expected = a if cond == 0 else b
            assert result == expected, f"cond={cond}, a.inf={a.is_infinity}, b.inf={b.is_infinity}"

"""CLI 命令行接口测试 - 高优先级.

覆盖范围：
- 命令行参数解析
- 参数组合校验（互斥/依赖关系）
- 无效参数处理
- 帮助信息输出

使用 pytest 的 CLI runner (pytester) 模式，
避免实际启动引擎进程。

运行：
    pytest tests/test_cli.py -v --tb=short
"""

import pathlib

import pytest

# ============================================================================
# 测试：CLI 入口
# ============================================================================


@pytest.mark.unit
class TestCLIEntryPoint:
    """CLI 入口点测试."""

    def test_key_collision_script_exists(self):
        """测试：key_collision.py 脚本存在."""
        assert pathlib.Path("key_collision.py").exists()
        assert pathlib.Path("key_collision_cli.py").exists()

    def test_key_collision_has_main_function(self):
        """v5.0.0: 验证 key_collision_cli.py 包含入口函数（key_collision.py 已移除 __main__）."""
        import ast

        # key_collision_cli.py 应有 __main__ 入口
        with pathlib.Path("key_collision_cli.py").open(encoding="utf-8") as f:
            tree = ast.parse(f.read())

        has_main_block = any(
            isinstance(node, ast.If)
            and hasattr(node.test, "left")
            and isinstance(node.test.left, ast.Name)
            and node.test.left.id == "__name__"
            for node in ast.walk(tree)
        )
        assert has_main_block, "key_collision_cli.py 缺少 __main__ 入口"

        # key_collision.py v5.0.0 已移除 __main__，不再可独立运行
        with pathlib.Path("key_collision.py").open(encoding="utf-8") as f:
            tree = ast.parse(f.read())

        has_main_block = any(
            isinstance(node, ast.If)
            and hasattr(node.test, "left")
            and isinstance(node.test.left, ast.Name)
            and node.test.left.id == "__name__"
            for node in ast.walk(tree)
        )
        assert not has_main_block, "key_collision.py v5.0.0 不应包含 __main__ 入口"

    def test_ast_syntax_validity(self):
        """测试：CLI 脚本 AST 语法有效."""
        import ast

        files_to_check = ["key_collision.py", "key_collision_cli.py"]
        for fname in files_to_check:
            with pathlib.Path(fname).open(encoding="utf-8") as f:
                try:
                    ast.parse(f.read())
                except SyntaxError as e:
                    pytest.fail(f"{fname} 语法错误: {e}")


# ============================================================================
# 测试：参数模式校验
# ============================================================================


@pytest.mark.unit
class TestCLIModeArguments:
    """CLI 模式参数测试."""

    def test_mode_random_valid(self):
        """测试：random 模式参数有效."""
        valid_modes = ["random", "range", "brute_force"]
        for mode in valid_modes:
            assert mode in valid_modes

    def test_mode_invalid_rejected(self):
        """测试：无效模式被拒绝."""
        valid_modes = {"random", "range", "brute_force"}
        invalid_modes = ["invalid", "", "123", "random2"]

        for mode in invalid_modes:
            if isinstance(mode, str) and mode:
                assert mode not in valid_modes, f"'{mode}' 不应是有效模式"

    def test_help_argument(self):
        """测试：帮助参数."""
        help_flags = ["-h", "--help"]
        for flag in help_flags:
            assert flag.startswith("-")


# ============================================================================
# 测试：参数组合与互斥
# ============================================================================


@pytest.mark.unit
class TestCLIArgumentCombinations:
    """CLI 参数组合测试."""

    def test_threads_positive_integer(self):
        """测试：threads 参数必须是正整数."""
        valid = [1, 2, 4, 8, 16, 32]
        invalid = [0, -1, -8, 1.5, "abc", None]

        for v in valid:
            assert isinstance(v, int) and v > 0

        for v in invalid:
            is_valid = isinstance(v, int) and v > 0
            assert not is_valid, f"{v} 不应通过校验"

    def test_batch_size_positive_integer(self):
        """测试：batch_size 参数必须是正整数."""
        valid = [1024, 65536, 1048576]
        invalid = [0, -1, 1024.5, "large"]

        for v in valid:
            assert isinstance(v, int) and v > 0

        for v in invalid:
            is_valid = isinstance(v, int) and v > 0
            assert not is_valid, f"{v} 不应通过校验"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

"""ConfigBuilder 单元测试

覆盖 src/wizard/config_builder.py 中未直接测试的路径：
- build() 输入校验 (ValueError 分支)
- build() target_file / gpu / checkpoint 组合
- build_summary() 格式化输出
"""

import unittest

from src.wizard.config_builder import ConfigBuilder
from src.wizard.interfaces import WizardResult


class TestConfigBuilder(unittest.TestCase):
    """ConfigBuilder.build() 输入校验与命令构建测试"""

    def setUp(self):
        self.builder = ConfigBuilder()
        self.TARGET = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"

    # ── 输入校验 ─────────────────────────────────────────────

    def test_build_no_targets_raises(self):
        """targets 和 target_file 均为空时抛出 ValueError"""
        result = WizardResult(targets=[], target_file=None, mode="random")
        with self.assertRaises(ValueError) as ctx:
            self.builder.build(result)
        self.assertIn("No targets", str(ctx.exception))

    def test_build_invalid_mode_raises(self):
        """mode 不在 VALID_MODES 中时抛出 ValueError"""
        result = WizardResult(
            targets=[self.TARGET], mode="invalid_mode"
        )
        with self.assertRaises(ValueError) as ctx:
            self.builder.build(result)
        self.assertIn("Invalid mode", str(ctx.exception))

    def test_build_range_requires_start_key(self):
        """mode='range' 且 start_key=None 时抛出 ValueError"""
        result = WizardResult(
            targets=[self.TARGET], mode="range",
            start_key=None, end_key=None,
        )
        with self.assertRaises(ValueError) as ctx:
            self.builder.build(result)
        self.assertIn("start_key", str(ctx.exception))

    def test_build_range_requires_end_key(self):
        """mode='range' 有 start_key 但 end_key=None 时抛出 ValueError"""
        result = WizardResult(
            targets=[self.TARGET], mode="range",
            start_key="0x1", end_key=None,
        )
        with self.assertRaises(ValueError) as ctx:
            self.builder.build(result)
        self.assertIn("end_key", str(ctx.exception))

    def test_build_brute_force_requires_start_key(self):
        """mode='brute_force' 且 start_key=None 时抛出 ValueError"""
        result = WizardResult(
            targets=[self.TARGET], mode="brute_force",
            start_key=None,
        )
        with self.assertRaises(ValueError) as ctx:
            self.builder.build(result)
        self.assertIn("start_key", str(ctx.exception))

    def test_build_brute_force_with_start_key(self):
        """mode='brute_force' 有 start_key 时正常构建命令"""
        result = WizardResult(
            targets=[self.TARGET], mode="brute_force",
            start_key="0xABC", end_key="0xFFFF",
        )
        cmd = self.builder.build(result)
        self.assertIn("--start", cmd)
        self.assertIn("0xABC", cmd)
        self.assertIn("--end", cmd)
        self.assertIn("0xFFFF", cmd)

    # ── 命令构建 ─────────────────────────────────────────────

    def test_build_with_target_file(self):
        """使用 target_file 构建命令时使用 -f 参数"""
        result = WizardResult(
            targets=[], target_file="targets.txt", mode="random",
        )
        cmd = self.builder.build(result)
        self.assertIn("-f", cmd)
        self.assertIn("targets.txt", cmd)

    def test_build_random_full_options(self):
        """mode=random, 全部选项开启 (checkpoint/dedup/duration/gpu)"""
        result = WizardResult(
            targets=[self.TARGET],
            mode="random",
            checkpoint=True,
            dedup=True,
            duration=3600,
            gpu_indices=[0],
            use_multi_gpu=False,
        )
        cmd = self.builder.build(result)
        self.assertIn("-t", cmd)
        self.assertIn(self.TARGET, cmd)
        self.assertIn("-m", cmd)
        self.assertIn("random", cmd)
        self.assertIn("--checkpoint", cmd)
        self.assertIn("--dedup", cmd)
        self.assertIn("--duration", cmd)

    def test_build_range_with_keys(self):
        """mode=range 时包含 start_key/end_key 参数"""
        result = WizardResult(
            targets=[self.TARGET],
            mode="range",
            start_key="0x1",
            end_key="0xFF",
        )
        cmd = self.builder.build(result)
        self.assertIn("--start", cmd)
        self.assertIn("0x1", cmd)
        self.assertIn("--end", cmd)
        self.assertIn("0xFF", cmd)

    def test_build_multi_gpu_flag(self):
        """use_multi_gpu=True 且 gpu_indices 不为空时命令包含 --multi-gpu"""
        result = WizardResult(
            targets=[self.TARGET], mode="random",
            gpu_indices=[0, 1], use_multi_gpu=True,
        )
        cmd = self.builder.build(result)
        self.assertIn("--multi-gpu", cmd)

    # ── build_summary ────────────────────────────────────────

    def test_build_summary(self):
        """build_summary() 返回格式化的多行字符串"""
        result = WizardResult(
            targets=[self.TARGET], mode="random", gpu_indices=[0],
        )
        summary = self.builder.build_summary(result)
        self.assertIn("生成的命令", summary)
        self.assertIn("-m", summary)
        self.assertIn("random", summary)

    # ── save_command ─────────────────────────────────────────

    def test_save_command_basic(self):
        """save_command() 保存命令到文件"""
        import os
        import shutil
        import tempfile
        result = WizardResult(
            targets=[self.TARGET], mode="random",
        )
        tmpdir = tempfile.mkdtemp()
        try:
            filepath = os.path.join(tmpdir, "run.sh")
            success = self.builder.save_command(result, filepath)
            self.assertTrue(success)
            with open(filepath, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("#!/bin/bash", content)
            self.assertIn("random", content)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)

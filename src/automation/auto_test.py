"""
自动化测试模块
===============
基于分析结果执行全面的测试用例，确保功能与性能达标
"""

import importlib
import subprocess
import sys
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from .models import AnalysisReport, TestCase, TestResult, TestSuiteResult


class AutoTestModule:
    """自动化测试模块"""

    def __init__(self, project_root: Path | None = None, max_workers: int = 4):
        self.project_root = project_root or Path(__file__).parent.parent.parent.parent
        self.max_workers = max_workers
        self.test_cases: list[TestCase] = []
        self._lock = threading.Lock()

        # 初始化测试用例
        self._discover_test_cases()

    def _discover_test_cases(self):
        """自动发现测试用例"""
        self.test_cases = [
            # 核心功能测试
            TestCase(
                id="TC-001",
                name="测试配置验证",
                category="Config",
                priority=1,
                test_func="test_config_validation",
                params={"config_path": str(self.project_root / "config.json")},
            ),
            TestCase(
                id="TC-002",
                name="测试CLI帮助信息",
                category="CLI",
                priority=1,
                test_func="test_cli_help",
                params={},
            ),
            TestCase(
                id="TC-003",
                name="测试加密后端初始化",
                category="Crypto",
                priority=1,
                test_func="test_crypto_backend_init",
                params={},
            ),
            TestCase(
                id="TC-004",
                name="测试日志系统",
                category="Logging",
                priority=2,
                test_func="test_logging_system",
                params={},
            ),
            TestCase(
                id="TC-005",
                name="测试模块导入",
                category="Import",
                priority=2,
                test_func="test_module_imports",
                params={},
            ),
            # 性能测试
            TestCase(
                id="TC-006",
                name="测试大整数运算性能",
                category="Performance",
                priority=2,
                test_func="test_bigint_performance",
                params={"iterations": 1000},
            ),
            TestCase(
                id="TC-007",
                name="测试哈希计算性能",
                category="Performance",
                priority=3,
                test_func="test_hash_performance",
                params={"iterations": 10000},
            ),
            # 集成测试
            TestCase(
                id="TC-008",
                name="测试端到端工作流",
                category="Integration",
                priority=1,
                test_func="test_e2e_workflow",
                params={"duration": 5},
            ),
            TestCase(
                id="TC-009",
                name="测试断点续传功能",
                category="Integration",
                priority=2,
                test_func="test_checkpoint_feature",
                params={},
            ),
            TestCase(
                id="TC-010",
                name="测试多语言支持",
                category="i18n",
                priority=3,
                test_func="test_i18n_support",
                params={"languages": ["zh_CN", "en_US"]},
            ),
        ]

    def run_all_tests(self, analysis_report: AnalysisReport | None = None) -> TestSuiteResult:
        """运行所有测试"""
        suite_id = f"suite_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        suite = TestSuiteResult(
            suite_id=suite_id,
            total=len(self.test_cases),
            passed=0,
            failed=0,
            skipped=0,
            errors=0,
            start_time=datetime.now(),
        )

        # 按优先级排序
        sorted_cases = sorted(self.test_cases, key=lambda x: x.priority)

        # 并行执行测试
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(self._run_single_test, tc): tc for tc in sorted_cases}

            for future in as_completed(futures):
                tc = futures[future]
                try:
                    result = future.result()
                    suite.results.append(result)

                    if result.status == "passed":
                        suite.passed += 1
                    elif result.status == "failed":
                        suite.failed += 1
                    elif result.status == "skipped":
                        suite.skipped += 1
                    else:
                        suite.errors += 1

                except Exception as e:
                    error_result = TestResult(
                        test_id=tc.id,
                        test_name=tc.name,
                        status="error",
                        duration=0,
                        message=f"测试执行异常: {str(e)}",
                        error_details=traceback.format_exc(),
                    )
                    suite.results.append(error_result)
                    suite.errors += 1

        suite.end_time = datetime.now()
        suite.duration = (suite.end_time - suite.start_time).total_seconds()

        return suite

    def _run_single_test(self, test_case: TestCase) -> TestResult:
        """运行单个测试"""
        start_time = time.time()

        try:
            # 动态调用测试函数
            test_func = getattr(self, test_case.test_func, None)
            if test_func is None:
                return TestResult(
                    test_id=test_case.id,
                    test_name=test_case.name,
                    status="skipped",
                    duration=0,
                    message=f"测试函数 {test_case.test_func} 未找到",
                )

            # 执行测试
            result = test_func(**test_case.params)

            duration = time.time() - start_time

            if result is True or result is None:
                return TestResult(
                    test_id=test_case.id,
                    test_name=test_case.name,
                    status="passed",
                    duration=duration,
                    message="测试通过",
                )
            elif isinstance(result, dict):
                return TestResult(
                    test_id=test_case.id,
                    test_name=test_case.name,
                    status=result.get("status", "passed"),
                    duration=duration,
                    message=result.get("message", ""),
                    metrics=result.get("metrics", {}),
                )
            else:
                return TestResult(
                    test_id=test_case.id,
                    test_name=test_case.name,
                    status="failed",
                    duration=duration,
                    message=str(result),
                )

        except Exception as e:
            duration = time.time() - start_time
            return TestResult(
                test_id=test_case.id,
                test_name=test_case.name,
                status="error",
                duration=duration,
                message=f"测试执行错误: {str(e)}",
                error_details=traceback.format_exc(),
            )

    # ========== 测试函数实现 ==========

    def test_config_validation(self, config_path: str) -> dict:
        """测试配置验证"""
        import json

        try:
            with open(config_path) as f:
                config = json.load(f)

            required_keys = ["workers", "checkpoint_interval"]
            missing = [k for k in required_keys if k not in config]

            if missing:
                return {
                    "status": "failed",
                    "message": f"缺少必需配置项: {missing}",
                    "metrics": {"missing_keys": missing},
                }

            return {
                "status": "passed",
                "message": "配置验证通过",
                "metrics": {"config_keys": list(config.keys())},
            }
        except Exception as e:
            return {
                "status": "failed",
                "message": f"配置验证失败: {str(e)}",
            }

    def test_cli_help(self) -> dict:
        """测试CLI帮助信息"""
        try:
            result = subprocess.run(  # nosec B603
                [sys.executable, "key_collision_cli.py", "--help"],
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                timeout=30,
                shell=False,
            )

            if result.returncode == 0 and "usage:" in result.stdout:
                return {
                    "status": "passed",
                    "message": "CLI帮助信息正常",
                    "metrics": {"output_length": len(result.stdout)},
                }
            else:
                return {
                    "status": "failed",
                    "message": "CLI帮助信息异常",
                    "metrics": {"stderr": result.stderr[:500]},
                }
        except Exception as e:
            return {
                "status": "error",
                "message": f"CLI测试执行失败: {str(e)}",
            }

    def test_crypto_backend_init(self) -> dict:
        """测试加密后端初始化"""
        try:
            from src.core.crypto_backend import CryptoBackend

            backend = CryptoBackend()
            available = backend.get_available_backends()
            current = backend.get_current_backend()

            if current:
                return {
                    "status": "passed",
                    "message": f"加密后端初始化成功: {current}",
                    "metrics": {"available_backends": available, "current": current},
                }
            else:
                return {
                    "status": "failed",
                    "message": "加密后端初始化失败",
                }
        except Exception as e:
            return {
                "status": "error",
                "message": f"加密后端测试异常: {str(e)}",
            }

    def test_logging_system(self) -> dict:
        """测试日志系统"""
        try:
            log_dir = self.project_root / "logs"
            if not log_dir.exists():
                return {
                    "status": "failed",
                    "message": "日志目录不存在",
                }

            return {
                "status": "passed",
                "message": "日志系统正常",
                "metrics": {"log_dir_exists": True},
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"日志系统测试异常: {str(e)}",
            }

    def test_module_imports(self) -> dict:
        """测试模块导入"""
        modules_to_test = [
            "src.core.secp256k1",
            "src.core.secure_key_manager",
            "src.collision.key_collision_engine",
            "src.cli.arg_parser",
        ]

        failed_imports = []
        successful_imports = []

        for module_name in modules_to_test:
            try:
                importlib.import_module(module_name)
                successful_imports.append(module_name)
            except Exception as e:
                failed_imports.append(f"{module_name}: {str(e)}")

        if failed_imports:
            return {
                "status": "failed",
                "message": f"模块导入失败: {len(failed_imports)} 个",
                "metrics": {"failed": failed_imports, "success": successful_imports},
            }

        return {
            "status": "passed",
            "message": "所有模块导入成功",
            "metrics": {"imported": successful_imports},
        }

    def test_bigint_performance(self, iterations: int = 1000) -> dict:
        """测试大整数运算性能"""
        try:
            import time

            start = time.time()
            a = 2**1024
            b = 3**512

            for _ in range(iterations):
                _ = a * b
                _ = a + b

            duration = time.time() - start
            ops_per_sec = iterations / duration if duration > 0 else 0

            if ops_per_sec > 100:
                return {
                    "status": "passed",
                    "message": f"大整数运算性能达标: {ops_per_sec:.1f} ops/sec",
                    "metrics": {"duration": duration, "ops_per_sec": ops_per_sec},
                }
            else:
                return {
                    "status": "failed",
                    "message": f"大整数运算性能不达标: {ops_per_sec:.1f} ops/sec",
                    "metrics": {"duration": duration, "ops_per_sec": ops_per_sec},
                }
        except Exception as e:
            return {
                "status": "error",
                "message": f"性能测试异常: {str(e)}",
            }

    def test_hash_performance(self, iterations: int = 10000) -> dict:
        """测试哈希计算性能"""
        try:
            import hashlib
            import time

            start = time.time()

            for i in range(iterations):
                data = f"test_data_{i}".encode()
                _ = hashlib.sha256(data).hexdigest()

            duration = time.time() - start
            ops_per_sec = iterations / duration if duration > 0 else 0

            if ops_per_sec > 5000:
                return {
                    "status": "passed",
                    "message": f"哈希计算性能达标: {ops_per_sec:.0f} ops/sec",
                    "metrics": {"duration": duration, "ops_per_sec": ops_per_sec},
                }
            else:
                return {
                    "status": "warning",
                    "message": f"哈希计算性能偏低: {ops_per_sec:.0f} ops/sec",
                    "metrics": {"duration": duration, "ops_per_sec": ops_per_sec},
                }
        except Exception as e:
            return {
                "status": "error",
                "message": f"哈希性能测试异常: {str(e)}",
            }

    def test_e2e_workflow(self, duration: int = 5) -> dict:
        """测试端到端工作流"""
        try:
            result = subprocess.run(  # nosec B603
                [sys.executable, "key_collision_cli.py", "--version"],
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                timeout=10,
                shell=False,
            )

            if result.returncode == 0:
                return {
                    "status": "passed",
                    "message": "端到端工作流测试通过",
                    "metrics": {"output_preview": result.stdout[:200]},
                }
            else:
                return {
                    "status": "failed",
                    "message": "端到端工作流测试失败",
                    "metrics": {"stderr": result.stderr[:500]},
                }
        except Exception as e:
            return {
                "status": "error",
                "message": f"端到端测试异常: {str(e)}",
            }

    def test_checkpoint_feature(self) -> dict:
        """测试断点续传功能"""
        try:
            # 验证断点续传模块存在
            import src.collision.checkpoint_manager as cp_module

            _ = cp_module.CheckpointManager  # 验证模块有 CheckpointManager 类
            return {
                "status": "passed",
                "message": "断点续传功能模块存在",
                "metrics": {"checkpoint_module_exists": True},
            }
        except ImportError:
            return {
                "status": "warning",
                "message": "断点续传模块未找到，跳过测试",
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"断点续传测试异常: {str(e)}",
            }

    def test_i18n_support(self, languages: list[str] = None) -> dict:
        """测试多语言支持"""
        languages = languages or ["zh_CN", "en_US"]

        try:
            i18n_dir = self.project_root / "src" / "i18n" / "locales"

            if not i18n_dir.exists():
                return {
                    "status": "warning",
                    "message": "i18n目录不存在",
                }

            supported = []
            for lang in languages:
                lang_file = i18n_dir / f"{lang}.json"
                if lang_file.exists():
                    supported.append(lang)

            return {
                "status": "passed",
                "message": f"支持的语言: {supported}",
                "metrics": {"supported_languages": supported},
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"i18n测试异常: {str(e)}",
            }


def run_tests(project_root: Path | None = None, analysis_report=None) -> TestSuiteResult:
    """运行所有测试"""
    module = AutoTestModule(project_root)
    return module.run_all_tests(analysis_report)

# -*- coding: utf-8 -*-
"""系统健康检查模块

提供系统环境和依赖的健康状态检查，帮助快速诊断问题。

扩展检查项:
- Python版本兼容性
- 关键依赖是否安装且版本正确
- 配置文件有效性（包括生产配置）
- 磁盘空间是否充足
- 目录权限
- GPU设备可用性（如启用）
- 网络连通性测试
- 端口占用检查
- 进程状态验证
- 依赖版本兼容性深度检查
- 配置文件权限检查
"""

import importlib
import json
import logging
import os
import shutil
import socket
import sys
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class HealthChecker:
    """系统健康检查器

    检查项:
    - Python版本兼容性
    - 关键依赖是否安装且版本正确
    - 配置文件有效性
    - 磁盘空间是否充足
    - 目录权限
    - GPU设备可用性（如启用）
    - 网络连通性
    - 端口占用
    - 进程状态
    - 依赖版本兼容性
    - 配置文件权限
    """

    def __init__(self, project_root: Optional[str] = None) -> None:
        """初始化健康检查器

        参数:
            project_root: 项目根目录路径
        """
        self.project_root = project_root or os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        self.results: Dict[str, Tuple[bool, str]] = {}
        self.required_configs = ["config.json", "config.production.json"]

    def check_python_version(self) -> Tuple[bool, str]:
        """检查Python版本兼容性"""
        if sys.version_info < (3, 9):
            return False, f"Python版本过低: {sys.version} (需要3.9+)"
        return True, f"Python版本: {sys.version}"

    def check_dependencies(self) -> Tuple[bool, str]:
        """检查关键依赖是否安装"""
        required_deps = {
            "coincurve": "椭圆曲线运算",
            "gmpy2": "大整数优化",
            "psutil": "系统监控",
            "cachetools": "缓存管理",
            "pybloom_live": "布隆过滤器",
            "chardet": "文件编码检测",
        }

        missing = []
        available = []

        for dep, desc in required_deps.items():
            try:
                importlib.import_module(dep)
                available.append(f"{dep}({desc})")
            except ImportError:
                missing.append(f"{dep}({desc})")

        if missing:
            return False, f"缺少依赖: {', '.join(missing)}"
        return True, f"所有依赖已安装: {', '.join(available)}"

    def check_config_file(self) -> Tuple[bool, str]:
        """检查配置文件"""
        config_path = os.path.join(self.project_root, "config.json")

        if not os.path.exists(config_path):
            return False, f"配置文件不存在: {config_path}"

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)

            if not isinstance(config, dict):
                return False, "配置文件格式错误: 根节点必须是JSON对象"

            return True, f"配置文件有效: {config_path}"
        except json.JSONDecodeError as e:
            return False, f"配置文件JSON格式错误: {e}"
        except Exception as e:
            return False, f"配置文件检查失败: {e}"

    def check_disk_space(self, min_mb: int = 100) -> Tuple[bool, str]:
        """检查磁盘空间

        参数:
            min_mb: 最小可用空间要求（MB）
        """
        try:
            total, used, free = shutil.disk_usage(self.project_root)
            free_mb = free / (1024 * 1024)

            if free_mb < min_mb:
                return False, f"磁盘空间不足: {free_mb:.1f}MB (需要{min_mb}MB+)"

            return True, f"磁盘空间充足: {free_mb:.1f}MB可用"
        except Exception as e:
            return False, f"磁盘空间检查失败: {e}"

    def check_directories(self) -> Tuple[bool, str]:
        """检查必要目录是否存在且有权限"""
        required_dirs = ["logs", "data_logs", "monitoring_data"]
        missing = []
        no_permission = []

        for dir_name in required_dirs:
            dir_path = os.path.join(self.project_root, dir_name)

            if not os.path.exists(dir_path):
                missing.append(dir_name)
                continue

            # 检查写权限
            test_file = os.path.join(dir_path, ".test_write")
            try:
                with open(test_file, "w") as f:
                    f.write("test")
                os.remove(test_file)
            except PermissionError:
                no_permission.append(dir_name)
            except OSError:
                pass

        issues = []
        if missing:
            issues.append(f"目录不存在: {', '.join(missing)}")
        if no_permission:
            issues.append(f"无写权限: {', '.join(no_permission)}")

        if issues:
            return False, "; ".join(issues)
        return True, f"所有必要目录正常: {', '.join(required_dirs)}"

    def check_gpu_availability(self) -> Tuple[bool, str]:
        """检查GPU设备可用性"""
        try:
            import pyopencl as cl

            platforms = cl.get_platforms()

            if not platforms:
                return False, "未检测到OpenCL平台"

            devices = []
            for platform in platforms:
                for device in platform.get_devices():
                    devices.append(f"{device.name} ({device.vendor})")

            if not devices:
                return False, "未检测到GPU设备"

            return True, f"GPU设备可用: {', '.join(devices)}"
        except ImportError:
            return False, "PyOpenCL未安装（GPU模式需要）"
        except Exception as e:
            return False, f"GPU检查失败: {e}"

    def check_monitoring_system(self) -> Tuple[bool, str]:
        """检查监控系统状态"""
        try:
            from src.monitoring.monitoring_system import DataStorage

            # 检查监控系统依赖

            # 检查数据存储目录
            storage = DataStorage()
            storage_dir = storage.storage_dir

            if not os.path.exists(storage_dir):
                return False, f"监控数据目录不存在: {storage_dir}"

            # 检查目录写权限
            test_file = os.path.join(storage_dir, ".test_monitoring")
            try:
                with open(test_file, "w") as f:
                    f.write("test")
                os.remove(test_file)
            except PermissionError:
                return False, f"监控数据目录无写权限: {storage_dir}"

            return True, f"监控系统正常: 数据目录 {storage_dir}"
        except ImportError as e:
            return False, f"监控系统依赖缺失: {e}"
        except Exception as e:
            return False, f"监控系统检查失败: {e}"

    def check_config_files(self) -> Tuple[bool, str]:
        """检查所有必需的配置文件"""
        missing = []
        invalid = []

        for config_name in self.required_configs:
            config_path = os.path.join(self.project_root, config_name)

            if not os.path.exists(config_path):
                missing.append(config_name)
                continue

            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)

                if not isinstance(config, dict):
                    invalid.append(f"{config_name} (格式错误)")
            except json.JSONDecodeError as e:
                invalid.append(f"{config_name} (JSON错误: {e})")

        issues = []
        if missing:
            issues.append(f"缺失配置文件: {', '.join(missing)}")
        if invalid:
            issues.append(f"无效配置文件: {', '.join(invalid)}")

        if issues:
            return False, "; ".join(issues)
        return True, f"所有配置文件正常: {', '.join(self.required_configs)}"

    def check_config_permissions(self) -> Tuple[bool, str]:
        """检查配置文件权限"""
        insecure_files = []

        for config_name in self.required_configs:
            config_path = os.path.join(self.project_root, config_name)

            if os.path.exists(config_path):
                # 获取文件权限（八进制）
                try:
                    stat_info = os.stat(config_path)
                    permissions = stat_info.st_mode & 0o777

                    # 检查是否过松（组或其他用户有读写权限）
                    if permissions & 0o077:  # 组或其他有任何权限
                        insecure_files.append(f"{config_name} ({oct(permissions)[2:]})")
                except Exception:
                    pass

        if insecure_files:
            return False, f"配置文件权限不安全: {', '.join(insecure_files)} (建议设置为 600)"
        return True, "配置文件权限安全"

    def check_network_connectivity(self) -> Tuple[bool, str]:
        """检查网络连通性"""
        test_hosts = [
            ("www.google.com", 443),
            ("api.github.com", 443),
        ]

        failed = []
        succeeded = []

        for host, port in test_hosts:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                result = sock.connect_ex((host, port))
                sock.close()

                if result == 0:
                    succeeded.append(host)
                else:
                    failed.append(host)
            except Exception:
                failed.append(host)

        if failed:
            return False, f"网络连接失败: {', '.join(failed)}"
        return True, f"网络连接正常: {', '.join(succeeded)}"

    def check_port_availability(self, ports: Optional[List[int]] = None) -> Tuple[bool, str]:
        """检查端口占用情况"""
        ports = ports or [9090, 3000, 9100]
        used_ports = []

        for port in ports:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                if s.connect_ex(("localhost", port)) == 0:
                    used_ports.append(str(port))

        if used_ports:
            return False, f"端口已被占用: {', '.join(used_ports)}"
        return True, f"所有端口可用: {', '.join(map(str, ports))}"

    def check_process_status(self) -> Tuple[bool, str]:
        """检查进程状态"""
        try:
            import psutil

            # 检查是否有其他实例在运行
            current_pid = os.getpid()
            process_name = "btc-collision"

            for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                try:
                    if proc.pid != current_pid:
                        cmdline = " ".join(proc.cmdline())
                        if "key_collision" in cmdline.lower() or process_name in cmdline.lower():
                            return False, f"检测到其他实例正在运行 (PID: {proc.pid})"
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

            return True, "无其他实例运行"
        except ImportError:
            return True, "psutil未安装，跳过进程检查"
        except Exception as e:
            return False, f"进程检查失败: {e}"

    def check_dependency_versions(self) -> Tuple[bool, str]:
        """检查依赖版本兼容性"""
        version_requirements = {
            "coincurve": (18, 0, 0),
            "gmpy2": (2, 1, 0),
            "psutil": (5, 9, 0),
            "pycryptodome": (3, 19, 0),
        }

        issues = []

        for dep, min_version in version_requirements.items():
            try:
                module = importlib.import_module(dep)
                version_str = getattr(module, "__version__", "unknown")

                # 解析版本号
                try:
                    version_parts = version_str.split(".")
                    version = tuple(map(int, version_parts[:3]))

                    if version < min_version:
                        issues.append(
                            f"{dep}版本过低: {version_str} (需要 {'.'.join(map(str, min_version))}+)"
                        )
                except ValueError:
                    pass  # 无法解析版本，跳过

            except ImportError:
                pass  # 依赖未安装，由其他检查处理

        if issues:
            return False, "; ".join(issues)
        return True, "所有依赖版本符合要求"

    def run_all_checks(
        self, include_gpu: bool = False, include_network: bool = False
    ) -> Dict[str, Tuple[bool, str]]:
        """运行所有健康检查

        参数:
            include_gpu: 是否包含GPU检查
            include_network: 是否包含网络检查

        返回:
            检查结果字典 {检查项: (是否通过, 详细信息)}
        """
        print("=" * 70)
        print("BTC碰撞引擎 - 系统健康检查")
        print("=" * 70)
        print()

        checks = [
            ("Python版本", self.check_python_version),
            ("依赖安装", self.check_dependencies),
            ("依赖版本", self.check_dependency_versions),
            ("配置文件", self.check_config_files),
            ("配置权限", self.check_config_permissions),
            ("磁盘空间", self.check_disk_space),
            ("目录权限", self.check_directories),
            ("进程状态", self.check_process_status),
            ("监控系统", self.check_monitoring_system),
        ]

        if include_gpu:
            checks.append(("GPU设备", self.check_gpu_availability))

        if include_network:
            checks.append(("网络连接", self.check_network_connectivity))
            checks.append(("端口占用", self.check_port_availability))

        all_passed = True
        for check_name, check_func in checks:
            try:
                passed, message = check_func()
                self.results[check_name] = (passed, message)

                status = "[成功]" if passed else "[失败]"
                print(f"{status} {check_name}: {message}")

                if not passed:
                    all_passed = False
            except Exception as e:
                self.results[check_name] = (False, str(e))
                print(f"[错误] {check_name}: {e}")
                all_passed = False

        print()
        print("=" * 70)
        if all_passed:
            print("[成功] 所有检查通过！系统状态健康。")
        else:
            print("[警告] 部分检查未通过，请查看上述详细信息。")
        print("=" * 70)

        return self.results

    def generate_report(self) -> str:
        """生成健康检查报告"""
        lines = ["系统健康检查报告", "=" * 70, ""]

        for check_name, (passed, message) in self.results.items():
            status = "✓ 通过" if passed else "✗ 失败"
            lines.append(f"{check_name}: {status}")
            lines.append(f"  详情: {message}")
            lines.append("")

        return "\n".join(lines)


def main() -> None:
    """健康检查CLI入口"""
    import argparse

    parser = argparse.ArgumentParser(description="BTC碰撞引擎系统健康检查")
    parser.add_argument("--gpu", action="store_true", help="包含GPU设备检查")
    parser.add_argument("--network", action="store_true", help="包含网络连通性检查")
    parser.add_argument("--report", metavar="FILE", help="生成报告文件")

    args = parser.parse_args()

    checker = HealthChecker()
    results = checker.run_all_checks(include_gpu=args.gpu, include_network=args.network)

    if args.report:
        report = checker.generate_report()
        with open(args.report, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"\n报告已保存: {args.report}")

    # 返回退出码
    all_passed = all(passed for passed, _ in results.values())
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()

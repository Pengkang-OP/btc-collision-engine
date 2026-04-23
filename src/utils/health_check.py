# -*- coding: utf-8 -*-
"""系统健康检查模块

提供系统环境和依赖的健康状态检查，帮助快速诊断问题。
"""

import importlib
import json
import logging
import os
import shutil
import sys
from typing import Dict, List, Tuple

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
    """
    
    def __init__(self, project_root: str = None):
        """初始化健康检查器
        
        参数:
            project_root: 项目根目录路径
        """
        self.project_root = project_root or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.results: Dict[str, Tuple[bool, str]] = {}
    
    def check_python_version(self) -> Tuple[bool, str]:
        """检查Python版本兼容性"""
        if sys.version_info < (3, 9):
            return False, f"Python版本过低: {sys.version} (需要3.9+)"
        return True, f"Python版本: {sys.version}"
    
    def check_dependencies(self) -> Tuple[bool, str]:
        """检查关键依赖是否安装"""
        required_deps = {
            'coincurve': '椭圆曲线运算',
            'gmpy2': '大整数优化',
            'psutil': '系统监控',
            'cachetools': '缓存管理',
            'pybloom_live': '布隆过滤器',
            'chardet': '文件编码检测',
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
        config_path = os.path.join(self.project_root, 'config.json')
        
        if not os.path.exists(config_path):
            return False, f"配置文件不存在: {config_path}"
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
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
        required_dirs = ['logs', 'data_logs', 'monitoring_data']
        missing = []
        no_permission = []
        
        for dir_name in required_dirs:
            dir_path = os.path.join(self.project_root, dir_name)
            
            if not os.path.exists(dir_path):
                missing.append(dir_name)
                continue
            
            # 检查写权限
            test_file = os.path.join(dir_path, '.test_write')
            try:
                with open(test_file, 'w') as f:
                    f.write('test')
                os.remove(test_file)
            except PermissionError:
                no_permission.append(dir_name)
            except Exception:
                pass
        
        issues = []
        if missing:
            issues.append(f"目录不存在: {', '.join(missing)}")
        if no_permission:
            issues.append(f"无写权限: {', '.join(no_permission)}")
        
        if issues:
            return False, '; '.join(issues)
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
    
    def run_all_checks(self, include_gpu: bool = False) -> Dict[str, Tuple[bool, str]]:
        """运行所有健康检查
        
        参数:
            include_gpu: 是否包含GPU检查
            
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
            ("配置文件", self.check_config_file),
            ("磁盘空间", self.check_disk_space),
            ("目录权限", self.check_directories),
        ]
        
        if include_gpu:
            checks.append(("GPU设备", self.check_gpu_availability))
        
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


def main():
    """健康检查CLI入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="BTC碰撞引擎系统健康检查")
    parser.add_argument(
        "--gpu",
        action="store_true",
        help="包含GPU设备检查"
    )
    parser.add_argument(
        "--report",
        metavar="FILE",
        help="生成报告文件"
    )
    
    args = parser.parse_args()
    
    checker = HealthChecker()
    results = checker.run_all_checks(include_gpu=args.gpu)
    
    if args.report:
        report = checker.generate_report()
        with open(args.report, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"\n报告已保存: {args.report}")
    
    # 返回退出码
    all_passed = all(passed for passed, _ in results.values())
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()

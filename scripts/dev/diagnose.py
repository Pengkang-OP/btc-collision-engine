#!/usr/bin/env python3
"""BTC 碰撞引擎 - 自助诊断工具

用法:
    python scripts/dev/diagnose.py          # 完整诊断
    python scripts/dev/diagnose.py --quick  # 快速检查（跳过 GPU 测试）
    python scripts/dev/diagnose.py --json   # 输出 JSON 格式报告

检查项目:
    1. Python 版本
    2. 核心依赖库可用性
    3. 可选性能依赖库
    4. 配置文件有效性
    5. GPU / OpenCL 可用性
    6. 磁盘空间
    7. CLI 入口可导入性
"""

import argparse
import json
import os
import shutil
import sys
import time
from typing import Any

# ─────────────────────────────────────────────
# 颜色输出（Windows 终端兼容）
# ─────────────────────────────────────────────
try:
    import colorama

    colorama.init(autoreset=True)
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    CYAN = "\033[36m"
    BOLD = "\033[1m"
    RESET = "\033[0m"
except ImportError:
    GREEN = YELLOW = RED = CYAN = BOLD = RESET = ""

PASS = f"{GREEN}[PASS]{RESET}"
WARN = f"{YELLOW}[WARN]{RESET}"
FAIL = f"{RED}[FAIL]{RESET}"
INFO = f"{CYAN}[INFO]{RESET}"
SEP = "─" * 60


# ─────────────────────────────────────────────
# 项目根目录定义
# ─────────────────────────────────────────────
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ─────────────────────────────────────────────
# 检查函数
# ─────────────────────────────────────────────


def check_python_version() -> tuple[bool, str]:
    """检查 Python 版本 >= 3.7"""
    v = sys.version_info
    ver_str = f"{v.major}.{v.minor}.{v.micro}"
    if v >= (3, 7):
        return True, f"Python {ver_str}"
    return False, f"Python {ver_str}（要求 >= 3.7）"  # noqa: E501


def check_core_deps() -> list[dict[str, Any]]:
    """检查核心必选依赖"""
    deps = [
        ("hashlib", "内置", "哈希计算"),
        ("hmac", "内置", "HMAC"),
        ("struct", "内置", "二进制解析"),
        ("threading", "内置", "多线程"),
        ("json", "内置", "配置解析"),
        ("Crypto", "pycryptodome", "SHA256/RIPEMD160 加速"),
        ("bech32", "bech32", "Bech32 地址编码（可选）"),
        ("bitarray", "bitarray", "Bloom 过滤器"),
        ("requests", "requests", "HTTP 通信"),
        ("chardet", "chardet", "字符编码检测"),
        ("setproctitle", "setproctitle", "进程标题（可选）"),
    ]
    results = []
    for module, pkg, desc in deps:
        try:
            __import__(module)
            results.append({"module": module, "pkg": pkg, "desc": desc, "ok": True, "error": None})
        except ImportError as e:
            results.append({"module": module, "pkg": pkg, "desc": desc, "ok": False, "error": str(e)})
    return results


def check_perf_deps() -> list[dict[str, Any]]:
    """检查可选性能依赖"""
    deps = [
        ("coincurve", "coincurve", "libsecp256k1 绑定（3-5x 加速，强烈推荐）"),
        ("gmpy2", "gmpy2", "GMP 大整数加速（椭圆曲线计算）"),  # noqa: E501
        ("numpy", "numpy", "数值计算加速"),
        ("ecdsa", "ecdsa", "纯 Python ECDSA 后备"),
        ("pyopencl", "pyopencl", "OpenCL GPU 支持"),
    ]
    results = []
    for module, pkg, desc in deps:
        try:
            mod = __import__(module)
            ver = getattr(mod, "__version__", "未知版本")
            results.append(
                {
                    "module": module,
                    "pkg": pkg,
                    "desc": desc,
                    "ok": True,
                    "version": ver,
                    "error": None,
                }
            )
        except ImportError as e:
            results.append(
                {
                    "module": module,
                    "pkg": pkg,
                    "desc": desc,
                    "ok": False,
                    "version": None,
                    "error": str(e),
                }
            )
    return results


def check_config() -> tuple[bool, str, dict]:
    """检查 config.json 是否存在且有效"""
    config_path = os.path.join(_PROJECT_ROOT, "config.json")
    if not os.path.exists(config_path):
        return False, "config.json 不存在（请执行: copy config.example.json config.json）", {}
    try:
        with open(config_path, encoding="utf-8") as f:
            cfg = json.load(f)
        keys = list(cfg.keys())
        return True, f"config.json 有效，顶层键: {keys}", cfg
    except json.JSONDecodeError as e:
        return False, f"config.json JSON 格式错误: {e}", {}
    except Exception as e:
        return False, f"config.json 读取失败: {e}", {}


def check_gpu(quick: bool = False) -> list[dict[str, Any]]:
    """检查 GPU / OpenCL 设备"""
    if quick:
        return [{"note": "快速模式已跳过 GPU 检查"}]
    try:
        import pyopencl as cl
    except ImportError:
        return [{"error": "pyopencl 未安装，无法检测 GPU（运行: pip install pyopencl）"}]

    devices = []
    try:
        for pi, platform in enumerate(cl.get_platforms()):
            for di, device in enumerate(platform.get_devices()):
                mem_mb = device.global_mem_size // (1024 * 1024)
                devices.append(
                    {
                        "platform_index": pi,
                        "device_index": di,
                        "platform": platform.name,
                        "name": device.name,
                        "vendor": device.vendor,
                        "vram_mb": mem_mb,
                        "max_work_group": device.max_work_group_size,
                        "opencl_version": device.version,
                    }
                )
    except Exception as e:
        return [{"error": f"OpenCL 设备枚举失败: {e}"}]

    if not devices:
        return [{"error": "未检测到任何 OpenCL 设备"}]
    return devices


def check_disk() -> dict[str, Any]:
    """检查磁盘空间"""
    logs_dir = os.path.join(_PROJECT_ROOT, "logs")
    check_path = logs_dir if os.path.exists(logs_dir) else _PROJECT_ROOT
    try:
        usage = shutil.disk_usage(check_path)
        free_mb = usage.free / (1024 * 1024)
        total_mb = usage.total / (1024 * 1024)
        used_pct = (usage.used / usage.total) * 100
        return {
            "path": check_path,
            "free_mb": round(free_mb, 1),
            "total_mb": round(total_mb, 1),
            "used_pct": round(used_pct, 1),
            "ok": free_mb >= 200,
            "warning": free_mb < 200,
        }
    except Exception as e:
        return {"error": str(e), "ok": True}


def check_cli_import() -> tuple[bool, str]:
    """检查 CLI 入口能否正常导入"""
    try:
        from src.cli.main import main  # noqa: F401

        return True, "src.cli.main 导入成功"  # noqa: E501
    except ImportError as e:
        return False, f"src.cli.main 导入失败: {e}"
    except Exception as e:
        return False, f"src.cli.main 导入异常: {e}"


def check_crypto_backend() -> tuple[str, str]:
    """检测当前使用的加密后端"""
    try:
        from src.crypto.backend import get_backend_name

        name = get_backend_name()
        return name, "正常"
    except Exception:
        pass

    # 按优先级手动检测
    for mod, name in [
        ("coincurve", "coincurve (libsecp256k1)"),
        ("gmpy2", "gmpy2"),
        ("Crypto", "pycryptodome"),
        ("ecdsa", "ecdsa (纯Python)"),
    ]:
        try:
            __import__(mod)
            return name, "可用"
        except ImportError:
            continue
    return "纯Python后备", "无加速库"


# ─────────────────────────────────────────────
# 报告输出
# ─────────────────────────────────────────────


def print_report(results: dict[str, Any], as_json: bool = False):
    if as_json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return

    print(f"\n{BOLD}{SEP}{RESET}")
    print(f"{BOLD}  BTC 碰撞引擎 - 自助诊断报告{RESET}")
    print(f"  时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  项目路径: {_PROJECT_ROOT}")
    print(f"{BOLD}{SEP}{RESET}\n")

    # Python 版本
    ok, msg = results["python"]
    print(f"{PASS if ok else FAIL} Python 版本: {msg}")

    # CLI 导入
    ok, msg = results["cli_import"]
    print(f"{PASS if ok else FAIL} CLI 入口: {msg}")

    # 加密后端
    backend, status = results["crypto_backend"]
    print(f"{INFO} 加密后端: {backend}（{status}）")

    # 配置文件
    ok, msg, _ = results["config"]
    print(f"{PASS if ok else WARN} 配置文件: {msg}")

    # 磁盘空间
    disk = results["disk"]
    if "error" not in disk:
        tag = PASS if disk["ok"] else WARN
        disk_str = (
            f"{tag} 磁盘空间: {disk['free_mb']} MB 可用"
            f" / {disk['total_mb']} MB 总计（已用 {disk['used_pct']}%）"
        )
        print(disk_str)
    else:
        print(f"{WARN} 磁盘空间: 检查失败 - {disk['error']}")

    print()
    # 核心依赖
    print(f"{BOLD}核心依赖:{RESET}")
    for d in results["core_deps"]:
        tag = PASS if d["ok"] else FAIL
        status_str = "OK" if d["ok"] else f"缺失（pip install {d['pkg']}）"
        print(f"  {tag} {d['module']:<18} {d['desc']:<30}  {status_str}")

    print()
    # 性能依赖
    print(f"{BOLD}性能/可选依赖:{RESET}")
    for d in results["perf_deps"]:
        if d["ok"]:
            print(f"  {PASS} {d['module']:<14} v{d['version']:<12}  {d['desc']}")
        else:
            print(f"  {WARN} {d['module']:<14} {'未安装':<14}  {d['desc']}")
            print(f"         → pip install {d['pkg']}")

    print()
    # GPU
    print(f"{BOLD}GPU / OpenCL:{RESET}")
    for dev in results["gpu"]:
        if "error" in dev:
            print(f"  {WARN} {dev['error']}")
        elif "note" in dev:
            print(f"  {INFO} {dev['note']}")
        else:
            print(f"  {PASS} [{dev['platform_index']}:{dev['device_index']}] {dev['name']}")
            print(
                f"         厂商={dev['vendor']}  VRAM={dev['vram_mb']} MB  "
                f"MaxWG={dev['max_work_group']}  OpenCL={dev['opencl_version']}"
            )

    # 总结
    print(f"\n{BOLD}{SEP}{RESET}")
    fail_cnt = sum(1 for d in results["core_deps"] if not d["ok"])
    warn_cnt = sum(1 for d in results["perf_deps"] if not d["ok"])
    ok_py, _ = results["python"]
    ok_cli, _ = results["cli_import"]
    if not ok_py or not ok_cli or fail_cnt > 0:
        print(f"{RED}{BOLD}  诊断结果: 存在 {fail_cnt} 个严重问题，需要修复{RESET}")
    elif warn_cnt > 0:
        msg = f"  诊断结果: 基本可用，{warn_cnt} 个可选依赖未安装（不影响基础功能）"
        print(f"{YELLOW}{BOLD}{msg}{RESET}")
    else:
        print(f"{GREEN}{BOLD}  诊断结果: 一切正常，可以正常运行{RESET}")
    print(f"{BOLD}{SEP}{RESET}\n")


# ─────────────────────────────────────────────
# 主函数
# ─────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="BTC 碰撞引擎自助诊断工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--quick", action="store_true", help="快速模式（跳过 GPU 检测）")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式报告")
    args = parser.parse_args()

    results = {
        "python": check_python_version(),
        "cli_import": check_cli_import(),
        "crypto_backend": check_crypto_backend(),
        "config": check_config(),
        "core_deps": check_core_deps(),
        "perf_deps": check_perf_deps(),
        "gpu": check_gpu(quick=args.quick),
        "disk": check_disk(),
    }

    print_report(results, as_json=args.json)


if __name__ == "__main__":
    main()

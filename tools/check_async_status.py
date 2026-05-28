#!/usr/bin/env python3
"""快速检查GPU异步功能状态
读取最新的日志文件,检查异步执行情况.
"""

from pathlib import Path


def check_async_status():
    """检查异步执行状态."""
    # 找到最新的日志文件
    log_dir = Path("logs")
    if not log_dir.exists():
        print("ERR logs目录不存在")
        return

    log_file = log_dir / "collision.log"
    if not log_file.exists():
        print("ERR 日志文件不存在: collision.log")
        return

    # 读取日志
    try:
        with open(log_file, encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        print(f"ERR 读取日志失败: {e}")
        return

    # 获取最后100行
    last_lines = lines[-100:] if len(lines) > 100 else lines
    "".join(last_lines)

    print("=" * 80)
    print("  GPU异步功能状态检查")
    print("=" * 80)
    print()

    # 检查关键指标
    checks = {
        "GPU设备初始化": False,
        "双队列创建": False,
        "计算队列": False,
        "传输队列": False,
        "异步执行启用(配置)": False,
        "异步执行禁用(传统)": False,
        "异步执行器初始化": False,
        "异步执行模式启动": False,
        "同步执行模式启动": False,
        "batch_size=1000000": False,
        "batch_size=262144": False,
    }

    for line in last_lines:
        if "创建双队列(计算+传输)" in line:
            checks["双队列创建"] = True
        if "计算队列: 已创建" in line:
            checks["计算队列"] = True
        if "传输队列: 已创建" in line:
            checks["传输队列"] = True
        if "GPU异步执行已启用(配置)" in line:
            checks["异步执行启用(配置)"] = True
        if "Intel 异步执行: 已启用" in line:
            checks["异步执行启用(配置)"] = True
        if "Intel 异步执行: 已禁用" in line or "GPU异步执行未启用" in line:
            checks["异步执行禁用(传统)"] = True
        if "异步GPU执行器已初始化" in line:
            checks["异步执行器初始化"] = True
        if "使用GPU异步执行模式" in line:
            checks["异步执行模式启动"] = True
        if "使用GPU同步执行模式" in line:
            checks["同步执行模式启动"] = True
        if "batch_size: 1000000" in line or "batch_size=1000000" in line:
            checks["batch_size=1000000"] = True
        if "batch_size: 262144" in line or "batch_size=262144" in line:
            checks["batch_size=262144"] = True
        if "GPU设备初始化成功" in line or "GPU 引擎初始化成功" in line:
            checks["GPU设备初始化"] = True

    # 显示结果
    print("【基础检查】")
    for key in ["GPU设备初始化", "batch_size=1000000", "batch_size=262144"]:
        if checks[key]:
            print(f"  OK {key}")
        elif key.startswith("batch_size"):
            continue
        else:
            print(f"  ERR {key}")

    print()
    print("【异步执行检查】")

    if checks["双队列创建"]:
        print("  OK 双队列创建")
        print(f"    - 计算队列: {'OK' if checks['计算队列'] else 'ERR'}")
        print(f"    - 传输队列: {'OK' if checks['传输队列'] else 'ERR'}")
    else:
        print("  ERR 双队列创建 - 未检测到")

    if checks["异步执行启用(配置)"]:
        print("  OK 异步执行已启用")
    elif checks["异步执行禁用(传统)"]:
        print("  ERR 异步执行未启用 - 使用传统模式")

    if checks["异步执行器初始化"]:
        print("  OK 异步执行器已初始化")
    else:
        print("  ERR 异步执行器未初始化")

    print()
    print("【运行模式】")
    if checks["异步执行模式启动"]:
        print("  OK 异步执行模式(双缓冲)")
    elif checks["同步执行模式启动"]:
        print("  ERR 同步执行模式(单队列)")
    else:
        print("  WARN 未检测到运行模式")

    print()
    print("=" * 80)

    # 总结
    if checks["双队列创建"] and checks["异步执行模式启动"]:
        print("OK 异步功能已完全启用!")
        print("   - 双队列: OK")
        print("   - 双缓冲: OK")
        print("   - 异步执行: OK")
    elif checks["双队列创建"]:
        print("WARN 部分启用 - 双队列已创建,但异步执行未启动")
        print("   建议: 检查配置或手动启用异步执行")
    else:
        print("ERR 异步功能未启用 - 使用传统同步模式")
        print("   建议: 检查配置文件或启动参数")

    print("=" * 80)

    # 显示吞吐量信息
    print()
    print("【性能信息】")
    for line in reversed(last_lines):
        if "吞吐量" in line or "keys/s" in line:
            print(f"  {line.strip()}")
            break
    else:
        print("  未检测到性能数据")


if __name__ == "__main__":
    check_async_status()

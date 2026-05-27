"""GPU对撞UI卡死检测工具.

功能:
1. 检测GUI进程是否在运行
2. 检查日志文件最后更新时间
3. 检查checkpoint文件是否更新
4. 判断是否真正卡死还是正常运行
"""

import os
import sys
from datetime import datetime

import psutil


def check_gui_process():
    """检查GUI进程状态."""
    print("=" * 60)
    print("GPU对撞UI卡死检测工具")
    print("=" * 60)
    print()

    # 1. 检查Python进程
    print("📊 检查进程状态...")
    gui_processes = []

    for proc in psutil.process_iter(["pid", "name", "cmdline", "create_time"]):
        try:
            cmdline = " ".join(proc.info["cmdline"] or [])
            if "python" in proc.info["name"].lower() and "key_collision_gui.py" in cmdline:
                gui_processes.append(
                    {
                        "pid": proc.info["pid"],
                        "create_time": datetime.fromtimestamp(proc.info["create_time"]),
                        "cmdline": cmdline,
                    },
                )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    if not gui_processes:
        print("❌ 未找到GUI进程")
        return False

    print(f"✅ 找到 {len(gui_processes)} 个GUI进程:")
    for i, proc in enumerate(gui_processes, 1):
        print(f"  [{i}] PID: {proc['pid']}")
        print(f"      启动时间: {proc['create_time']}")
        print(f"      运行时长: {datetime.now() - proc['create_time']}")
    print()

    # 2. 检查日志文件
    print("📝 检查日志文件...")
    log_files = [
        "logs/gui.log",
        "logs/collision.log",
        "data_logs/current_data.json",
        "data_logs/history_data.json",
    ]

    for log_file in log_files:
        if os.path.exists(log_file):
            stat = os.stat(log_file)
            last_modified = datetime.fromtimestamp(stat.st_mtime)
            time_ago = datetime.now() - last_modified

            status = (
                "✅"
                if time_ago.total_seconds() < 60
                else "⚠️"
                if time_ago.total_seconds() < 300
                else "❌"
            )

            print(f"  {status} {log_file}")
            print(f"      最后更新: {last_modified}")
            print(f"      距今: {time_ago}")
        else:
            print(f"  ❓ {log_file} (不存在)")
    print()

    # 3. 检查checkpoint文件
    print("💾 检查checkpoint文件...")
    checkpoint_files = ["src/collision/collision_checkpoint.json", "data_logs/checkpoint.json"]

    for ckpt_file in checkpoint_files:
        if os.path.exists(ckpt_file):
            stat = os.stat(ckpt_file)
            last_modified = datetime.fromtimestamp(stat.st_mtime)
            time_ago = datetime.now() - last_modified

            # 读取checkpoint内容
            try:
                import json

                with open(ckpt_file, encoding="utf-8") as f:
                    data = json.load(f)
                    checked = data.get("checked", 0)
                    matches = data.get("matches", 0)

                status = "✅" if time_ago.total_seconds() < 10 else "⚠️"
                print(f"  {status} {ckpt_file}")
                print(f"      最后更新: {last_modified}")
                print(f"      已检查: {checked:,}")
                print(f"      匹配数: {matches}")
                print(f"      距今: {time_ago}")
            except Exception as e:
                print(f"  ⚠️ {ckpt_file} (读取失败: {e})")
        else:
            print(f"  ❓ {ckpt_file} (不存在)")
    print()

    # 4. 综合判断
    print("🔍 综合判断...")

    # 检查最近的日志
    most_recent_log = None
    most_recent_time = None

    for log_file in log_files + checkpoint_files:
        if os.path.exists(log_file):
            stat = os.stat(log_file)
            if most_recent_time is None or stat.st_mtime > most_recent_time:
                most_recent_time = stat.st_mtime
                most_recent_log = log_file

    if most_recent_log:
        time_ago = datetime.now() - datetime.fromtimestamp(most_recent_time)

        if time_ago.total_seconds() < 30:
            print("✅ 程序正常运行中")
            print(f"   最新文件: {most_recent_log}")
            print(f"   更新时间: {time_ago}")
            print()
            print("💡 提示: 如果界面无响应，但文件持续更新，可能是:")
            print("   1. GPU计算繁忙，UI更新被延迟")
            print("   2. 日志输出间隔较大（正常）")
            print("   3. 性能监控正在后台运行")
            return True
        if time_ago.total_seconds() < 300:
            print("⚠️ 程序可能卡顿")
            print(f"   最新文件: {most_recent_log}")
            print(f"   更新时间: {time_ago}")
            print()
            print("💡 建议:")
            print("   1. 等待1-2分钟观察是否恢复")
            print("   2. 检查任务管理器中的CPU/GPU使用率")
            print("   3. 如果持续无响应，考虑重启程序")
            return False
        print("❌ 程序可能已卡死")
        print(f"   最新文件: {most_recent_log}")
        print(f"   更新时间: {time_ago}")
        print()
        print("💡 建议:")
        print("   1. 强制关闭程序")
        print("   2. 检查日志文件中的错误信息")
        print("   3. 重新启动程序")
        return False

    return False


if __name__ == "__main__":
    try:
        result = check_gui_process()
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️ 检测被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ 检测失败: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(2)

#!/usr/bin/env python3
"""快速检查异步优化状态."""

from datetime import datetime
from pathlib import Path


def main():
    print("=" * 80)
    print("  GPU异步优化状态检查")
    print(f"  检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    print()

    log_file = Path("logs/collision.log")

    if not log_file.exists():
        print("[ERROR] 日志文件不存在")
        return

    try:
        with open(log_file, encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        print("最新日志(最后30行):")
        print("-" * 80)

        for line in lines[-30:]:
            line = line.strip()
            if not line:
                continue

            # 简化显示
            if "ERROR" in line:
                print(f"  [ERROR] {line[24:]}")
            elif "WARNING" in line or "WARN" in line:
                print(f"  [WARN]  {line[24:]}")
            elif "INFO" in line:
                msg = line[24:]
                # 高亮显示关键信息
                if any(
                    kw in msg for kw in ["异步", "async", "双队列", "双缓冲", "batch_size", "吞吐量"]
                ):
                    print(f"  [KEY]   {msg}")
                else:
                    print(f"  [INFO]  {msg}")

        print()
        print("=" * 80)

        # 检查异步关键字
        recent_content = "".join(lines[-100:])

        print("异步优化状态:")
        print("-" * 80)

        all_found = True
        for keyword, desc in [
            ("GPU异步执行已启用", "异步配置"),
            ("创建双队列", "双队列创建"),
            ("异步执行器已初始化", "执行器初始化"),
            ("使用GPU异步执行模式", "异步模式"),
        ]:
            found = keyword in recent_content
            if found:
                print(f"  [PASS] {desc}: 已启用")
            else:
                print(f"  [FAIL] {desc}: 未检测到")
                all_found = False

        print()

        if all_found:
            print("[SUCCESS] OK 异步优化已完全启用!")
            print()
            print("下一步:")
            print("  1. 观察5-10分钟")
            print("  2. 检查吞吐量是否达到80k+ keys/s")
            print("  3. 确认无间歇性停顿")
        else:
            print("[WARN] WARN 异步优化未完全启用")
            print()
            print("可能原因:")
            print("  1. 程序未重启(需要重启加载新代码)")
            print("  2. 配置未生效(检查config.intel_arc.json)")
            print("  3. 使用了错误的配置文件")

    except Exception as e:
        print(f"[ERROR] 检查失败: {e}")

    print()


if __name__ == "__main__":
    main()

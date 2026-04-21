#!/usr/bin/env python3
"""测试日志匹配失败时的提示信息"""

import sys
import io
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_no_targets_in_log():
    """测试日志中没有目标地址数量时的提示"""
    print("=" * 80)
    print("  测试: 日志中无目标地址数量")
    print("=" * 80)
    
    # 临时修改日志文件为空
    log_file = Path("logs/collision.log")
    backup_file = Path("logs/collision.log.backup")
    
    # 备份原日志
    if log_file.exists():
        log_file.rename(backup_file)
    
    # 创建空日志
    log_file.write_text("", encoding='utf-8')
    
    # 捕获输出
    from tools import diagnose_gui_performance
    captured_output = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = captured_output
    
    try:
        diagnose_gui_performance.diagnose_performance()
    finally:
        sys.stdout = old_stdout
    
    # 恢复原日志
    if backup_file.exists():
        log_file.unlink()
        backup_file.rename(log_file)
    
    # 检查输出
    output = captured_output.getvalue()
    
    print(output)
    
    # 验证提示信息
    assert "未检测到目标地址数量" in output, "应该显示未检测到提示"
    assert "使用默认值0" in output, "应该说明使用默认值"
    assert "可能原因" in output, "应该给出可能原因"
    
    print("\n✅ 测试通过: 正确显示匹配失败提示\n")


def test_targets_in_log():
    """测试日志中有目标地址数量时的正常显示"""
    print("=" * 80)
    print("  测试: 日志中有目标地址数量")
    print("=" * 80)
    
    # 临时修改日志文件
    log_file = Path("logs/collision.log")
    backup_file = Path("logs/collision.log.backup")
    
    # 备份原日志
    if log_file.exists():
        log_file.rename(backup_file)
    
    # 创建测试日志
    test_log = """2026-04-21 15:00:00 [INFO] GPU碰撞引擎启动
2026-04-21 15:00:01 [INFO] 加载38个目标地址
2026-04-21 15:00:02 [INFO] 当前=50,000 keys/s 峰值=2,800,000 keys/s 退化率=1.5%
2026-04-21 15:00:03 [INFO] 使用GPU异步执行模式,双缓冲机制
"""
    log_file.write_text(test_log, encoding='utf-8')
    
    # 捕获输出
    from tools import diagnose_gui_performance
    captured_output = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = captured_output
    
    try:
        diagnose_gui_performance.diagnose_performance()
    finally:
        sys.stdout = old_stdout
    
    # 恢复原日志
    if backup_file.exists():
        log_file.unlink()
        backup_file.rename(log_file)
    
    # 检查输出
    output = captured_output.getvalue()
    
    print(output)
    
    # 验证正常显示
    assert "目标地址数量: 38" in output, "应该显示目标数量38"
    assert "未检测到目标地址数量" not in output, "不应显示未检测到提示"
    
    print("\n✅ 测试通过: 正确显示目标地址数量\n")


if __name__ == "__main__":
    print("\n")
    print("=" * 80)
    print("  diagnose_gui_performance.py - 日志匹配失败提示测试")
    print("=" * 80)
    print("\n")
    
    try:
        test_no_targets_in_log()
        test_targets_in_log()
        
        print("=" * 80)
        print("  ✅ 所有测试通过!")
        print("=" * 80)
        print("\n")
        print("改进效果:")
        print("  ✅ 日志格式变化时: 显示友好提示,而非静默失败")
        print("  ✅ 程序未启动时: 说明可能原因,引导用户检查")
        print("  ✅ 正常运行时: 正常显示目标数量,无额外提示")
        print("\n")
        
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

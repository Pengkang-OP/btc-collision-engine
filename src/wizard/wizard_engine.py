#!/usr/bin/env python3
"""向导引擎

协调各选择器工作，实现完整的交互式引导流程。
"""

import logging
import sys
import time
from collections.abc import Callable

from .config_builder import ConfigBuilder
from .events import EventDispatcher, WizardEventType
from .gpu_selector import GPUSelector
from .interfaces import WizardConfig, WizardMode, WizardResult
from .message_queue import WizardMessageQueue, get_message_queue
from .mode_selector import ModeSelector
from .option_selector import OptionSelector
from .target_selector import TargetSelector

logger = logging.getLogger(__name__)


class WizardEngine:
    """向导引擎

    协调各选择器工作，实现完整的交互式引导流程。

    使用示例：
        wizard = WizardEngine()
        result = wizard.run()

        if result.success:
            print(f"配置完成: {result.command}")
        else:
            print(f"向导取消或出错: {result.error_message}")
    """

    def __init__(
        self,
        config: WizardConfig | None = None,
        message_queue: WizardMessageQueue | None = None,
    ):
        """初始化向导引擎

        Args:
            config: 向导配置，默认使用标准配置
            message_queue: 消息队列实例，默认使用全局单例。
                          支持注入自定义/模拟队列用于测试。

        """
        self.config = config or WizardConfig()
        self.result = WizardResult()
        self.event_dispatcher = EventDispatcher()
        self.message_queue = message_queue or get_message_queue()
        self._running = False
        self._step_handlers = {
            "target": self._select_target,
            "mode": self._select_mode,
            "options": self._select_options,
            "gpu": self._select_gpu,
            "build": self._build_config,
        }

    def run(self) -> WizardResult:
        """运行向导

        Returns:
            WizardResult: 向导结果

        """
        self._running = True
        self.message_queue.send_wizard_start({"mode": self.config.mode.value})

        try:
            if self.config.show_intro:
                self._show_intro()

            # 执行各步骤
            for step_name in ["target", "mode", "options", "gpu", "build"]:
                if not self._running:
                    break
                handler = self._step_handlers.get(step_name)
                if handler:
                    handler()

            if self._running and not self.result.error_message:
                self._complete()
            elif not self._running:
                self._cancelled()

        except KeyboardInterrupt:
            self._cancelled()
        except Exception as e:
            logger.error("Wizard engine error: %s", e, exc_info=True)
            self._error(f"{type(e).__name__}: {e}")
        finally:
            self._running = False

        return self.result

    def _show_intro(self):
        """显示引导介绍"""
        print()
        print("─" * 60)
        print("  BTC碰撞引擎 - 交互式向导")
        print("─" * 60)
        print()
        print("  本向导将帮助您配置碰撞引擎的各项参数")
        print("  按 Ctrl+C 可随时退出")
        print()
        time.sleep(0.5)

    def _select_target(self):
        """选择目标地址"""
        selector = TargetSelector()
        targets, target_file = selector.select(compact=(self.config.mode == WizardMode.COMPACT))
        self.result.targets = targets
        self.result.target_file = target_file
        self.message_queue.send_target_selected(targets, target_file)

    def _select_mode(self):
        """选择碰撞模式"""
        selector = ModeSelector()
        mode, start_key, end_key = selector.select(compact=(self.config.mode == WizardMode.COMPACT))
        self.result.mode = mode
        self.result.start_key = start_key
        self.result.end_key = end_key
        self.message_queue.send_mode_selected(mode, start_key, end_key)

    def _select_options(self):
        """选择功能选项"""
        selector = OptionSelector()
        checkpoint, dedup, duration = selector.select(compact=(self.config.mode == WizardMode.COMPACT))
        self.result.checkpoint = checkpoint
        self.result.dedup = dedup
        self.result.duration = duration
        self.message_queue.send_options_selected(checkpoint, dedup, duration)

    def _select_gpu(self):
        """选择GPU设备"""
        selector = GPUSelector()
        gpu_indices, use_multi_gpu = selector.select(compact=(self.config.mode == WizardMode.COMPACT))
        self.result.gpu_indices = gpu_indices
        self.result.use_multi_gpu = use_multi_gpu
        self.message_queue.send_gpu_selected(gpu_indices, use_multi_gpu)

    def _build_config(self):
        """构建配置"""
        builder = ConfigBuilder()
        try:
            command = builder.build(self.result)
        except ValueError as e:
            self._error(f"Config validation failed: {e}")
            return
        self.result.command = command
        self.message_queue.send(WizardEventType.CONFIG_BUILT, {"command": command})

    def _complete(self):
        """向导完成"""
        self.result.success = True
        self.message_queue.send_wizard_complete(self.result.to_dict())

        if self.config.show_summary:
            self._show_summary()

        if not self.config.auto_continue:
            response = input("\n是否立即执行? [y/n] (推荐: Y): ").strip().lower()
            if response and response[0] != "y":
                self.result.success = False
                self.result.error_message = "用户取消执行"
                return

        self._execute()

    def _cancelled(self):
        """向导取消"""
        self.result.success = False
        self.result.error_message = "用户取消"
        self.message_queue.send_wizard_cancelled()
        print("\n\n[INFO] 向导已取消")

    def _error(self, error_message: str):
        """向导出错"""
        self.result.success = False
        self.result.error_message = error_message
        self.message_queue.send_wizard_error(error_message)
        print(f"\n\n[ERROR] 向导出错: {error_message}")

    def _show_summary(self):
        """显示配置摘要"""
        print()
        print("╭" + "─" * 58 + "╮")
        print("│" + " " * 15 + "启动配置" + " " * 33 + "│")
        print("├" + "─" * 58 + "┤")

        target_info = self.result.target_file or ", ".join(self.result.targets[:2])
        if len(self.result.targets) > 2:
            target_info += f" (+{len(self.result.targets) - 2} more)"

        print(f"│   目标地址          {target_info:<38} │")
        print(f"│   碰撞模式          {self.result.mode:<38} │")
        print(f"│   断点续传          {'启用' if self.result.checkpoint else '禁用':<38} │")
        print(f"│   去重过滤          {'启用' if self.result.dedup else '禁用':<38} │")

        duration_str = "不限制" if self.result.duration == 0 else f"{self.result.duration}秒"
        print(f"│   运行时长          {duration_str:<38} │")

        gpu_str = "多GPU" if self.result.use_multi_gpu else "单GPU"
        if self.result.gpu_indices:
            gpu_str += f" ({', '.join(map(str, self.result.gpu_indices))})"
        print(f"│   GPU模式           {gpu_str:<38} │")

        print("╰" + "─" * 58 + "╯")

    def _execute(self):
        """执行生成的命令"""
        if not self.result.command:
            print("[ERROR] 没有可执行的命令")
            return

        print()
        print("─" * 60)
        print("  正在启动碰撞引擎...")
        print("─" * 60)
        print()

        import subprocess

        try:
            subprocess.run(self.result.command, shell=False)  # nosec B603
        except (subprocess.SubprocessError, FileNotFoundError, OSError) as e:
            logger.error("Command execution failed: %s", e)
            print(f"[ERROR] 执行失败: {e}")

    def stop(self):
        """停止向导"""
        self._running = False

    def is_running(self) -> bool:
        """检查向导是否正在运行"""
        return self._running

    def register_step_handler(self, step_name: str, handler: Callable):
        """注册步骤处理器

        Args:
            step_name: 步骤名称
            handler: 处理函数

        """
        self._step_handlers[step_name] = handler

    def unregister_step_handler(self, step_name: str):
        """取消注册步骤处理器"""
        self._step_handlers.pop(step_name, None)


def main():
    """独立运行向导"""
    import argparse

    parser = argparse.ArgumentParser(description="BTC碰撞引擎 - 交互式向导")
    parser.add_argument("--compact", action="store_true", help="紧凑模式（跳过帮助信息）")
    parser.add_argument("--auto", action="store_true", help="自动模式（使用默认值）")
    parser.add_argument("--output", type=str, help="保存配置到文件")

    args = parser.parse_args()

    # 配置向导模式
    if args.auto:
        config = WizardConfig(mode=WizardMode.AUTO, show_intro=False, show_summary=True)
    elif args.compact:
        config = WizardConfig(mode=WizardMode.COMPACT, show_intro=False, show_summary=True)
    else:
        config = WizardConfig(mode=WizardMode.INTERACTIVE)

    # 运行向导
    wizard = WizardEngine(config=config)
    result = wizard.run()

    # 保存配置
    if args.output and result.success:
        result.save_to_file(args.output)
        print(f"[OK] 配置已保存到: {args.output}")

    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())

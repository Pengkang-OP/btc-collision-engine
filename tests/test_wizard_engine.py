#!/usr/bin/env python3
"""WizardEngine 单元测试

覆盖 src/wizard/wizard_engine.py 中未充分测试的 WizardEngine 类：
- 初始化与依赖注入
- run() 生命周期 (success/cancel/error)
- _complete() / _cancelled() / _error()
- _show_intro() / _show_summary()
- register_step_handler / unregister_step_handler
- is_running() 状态检查
- 消息队列注入
"""

from unittest.mock import Mock, patch

from src.wizard.events import WizardEventType
from src.wizard.interfaces import WizardConfig, WizardMode, WizardResult
from src.wizard.message_queue import WizardMessageQueue
from src.wizard.wizard_engine import WizardEngine

# ============================================================================
# 辅助函数
# ============================================================================


def _mock_all_selectors():
    """模拟所有选择器成功返回，确保 run() 正常走完全流程

    Returns:
        tuple: (patchers_dict, mocks_dict) - 需要调用方管理生命周期
    """
    patchers = {
        "target_selector": patch("src.wizard.wizard_engine.TargetSelector", autospec=True),
        "mode_selector": patch("src.wizard.wizard_engine.ModeSelector", autospec=True),
        "option_selector": patch("src.wizard.wizard_engine.OptionSelector", autospec=True),
        "gpu_selector": patch("src.wizard.wizard_engine.GPUSelector", autospec=True),
        "config_builder": patch("src.wizard.wizard_engine.ConfigBuilder", autospec=True),
    }
    # 启动所有 patcher 并收集 mock
    mocks = {}
    targets = ["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"]
    for name, p in patchers.items():
        mocks[name] = p.start()
    # 配置选择器实例返回值 (autospec=True 下，调用类返回实例 mock)
    mocks["target_selector"].return_value.select.return_value = (targets, None)
    mocks["mode_selector"].return_value.select.return_value = ("random", None, None)
    mocks["option_selector"].return_value.select.return_value = (True, True, 0)
    mocks["gpu_selector"].return_value.select.return_value = ([], False)
    mocks["config_builder"].return_value.build.return_value = ["python", "-m", "src.cli.main"]
    return patchers, mocks


def _stop_all_patches(patchers: dict):
    """停止所有 patcher"""
    for p in patchers.values():
        p.stop()


# ============================================================================
# 1. WizardEngine 初始化测试
# ============================================================================


class TestWizardEngineInit:
    """WizardEngine 初始化测试"""

    def test_default_initialization(self):
        """默认初始化应设置正确的默认值"""
        engine = WizardEngine()
        assert engine.config.mode == WizardMode.INTERACTIVE
        assert isinstance(engine.result, WizardResult)
        assert engine._running is False
        assert len(engine._step_handlers) == 5
        assert "target" in engine._step_handlers
        assert "mode" in engine._step_handlers
        assert "options" in engine._step_handlers
        assert "gpu" in engine._step_handlers
        assert "build" in engine._step_handlers

    def test_custom_config(self):
        """应接受自定义 WizardConfig"""
        config = WizardConfig(mode=WizardMode.COMPACT, show_intro=False)
        engine = WizardEngine(config=config)
        assert engine.config.mode == WizardMode.COMPACT
        assert engine.config.show_intro is False

    def test_custom_message_queue(self):
        """应接受注入的消息队列"""
        mq = WizardMessageQueue(maxsize=50)
        engine = WizardEngine(message_queue=mq)
        assert engine.message_queue is mq

    def test_is_running_initial(self):
        """初始状态下 is_running 应为 False"""
        engine = WizardEngine()
        assert engine.is_running() is False


# ============================================================================
# 2. run() 生命周期测试
# ============================================================================


class TestWizardEngineRun:
    """WizardEngine.run() 测试"""

    def test_run_success_flow(self):
        """模拟完整成功流程"""
        patchers, _ = _mock_all_selectors()
        try:
            config = WizardConfig(auto_continue=True)  # 跳过 input() 提示
            engine = WizardEngine(config=config)
            with patch("subprocess.run") as mock_run:
                result = engine.run()
                assert result.success is True
                assert engine.is_running() is False  # run() 完成后应停止
                mock_run.assert_called_once()
        finally:
            _stop_all_patches(patchers)

    def test_run_compact_mode(self):
        """紧凑模式下也应成功"""
        patchers, _ = _mock_all_selectors()
        try:
            config = WizardConfig(mode=WizardMode.COMPACT, auto_continue=True)
            engine = WizardEngine(config=config)
            with patch("subprocess.run"):
                result = engine.run()
                assert result.success is True
        finally:
            _stop_all_patches(patchers)

    def test_run_auto_mode(self):
        """自动模式下也应成功"""
        patchers, _ = _mock_all_selectors()
        try:
            config = WizardConfig(mode=WizardMode.AUTO, auto_continue=True)
            engine = WizardEngine(config=config)
            result = engine.run()
            assert result.success is True
        finally:
            _stop_all_patches(patchers)

    def test_run_config_build_error(self):
        """ConfigBuilder 抛出 ValueError 时不应崩溃"""
        patchers, mocks = _mock_all_selectors()
        try:
            # 让 ConfigBuilder 实例的 build 抛出异常
            mocks["config_builder"].return_value.build.side_effect = ValueError("No targets")
            engine = WizardEngine()
            result = engine.run()
            assert result.success is False
            assert "Config validation failed" in (result.error_message or "")
        finally:
            _stop_all_patches(patchers)

    def test_run_exception_handling(self):
        """内部异常应被捕获并设置 error"""
        patchers, mocks = _mock_all_selectors()
        try:
            # 让 TargetSelector 构造时抛异常，模拟内部错误
            mocks["target_selector"].side_effect = RuntimeError("Unexpected")
            engine = WizardEngine()
            result = engine.run()
            assert result.success is False
            assert "RuntimeError" in (result.error_message or "")
        finally:
            _stop_all_patches(patchers)


# ============================================================================
# 3. stop() 和状态测试
# ============================================================================


class TestWizardEngineStop:
    """WizardEngine.stop() 测试"""

    def test_stop_sets_running_false(self):
        """stop() 应设置 _running = False"""
        engine = WizardEngine()
        engine._running = True
        engine.stop()
        assert engine._running is False
        assert engine.is_running() is False

    def test_stop_during_run(self):
        """运行中调用 stop 应中断流程"""
        patchers, _ = _mock_all_selectors()
        try:
            engine = WizardEngine()
            # 通过 _step_handlers 注入 stop，因为 __init__ 中已捕获原始引用
            original = engine._step_handlers["target"]

            def select_and_stop():
                engine.stop()
                return original()

            engine._step_handlers["target"] = select_and_stop
            result = engine.run()
            # 流程被中断，result 应为取消状态，且不会走到 _complete()
            assert result.success is False
            assert "取消" in (result.error_message or "")
        finally:
            _stop_all_patches(patchers)


# ============================================================================
# 4. _show_intro 和 _show_summary 测试
# ============================================================================


class TestWizardEngineDisplay:
    """显示方法测试"""

    def test_show_intro(self):
        """_show_intro 不应抛出异常"""
        engine = WizardEngine()
        engine._show_intro()  # 打印到 stdout，不应出错

    def test_show_summary_with_targets(self):
        """_show_summary 应处理多目标"""
        engine = WizardEngine()
        engine.result.targets = [
            "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            "1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH",
        ]
        engine.result.mode = "random"
        engine.result.gpu_indices = [0]
        engine.result.use_multi_gpu = False
        engine._show_summary()  # 不应出错

    def test_show_summary_with_target_file(self):
        """_show_summary 应处理 target_file"""
        engine = WizardEngine()
        engine.result.targets = []
        engine.result.target_file = "targets.txt"
        engine.result.mode = "range"
        engine.result.gpu_indices = [0, 1]
        engine.result.use_multi_gpu = True
        engine._show_summary()  # 不应出错

    def test_show_summary_empty(self):
        """_show_summary 应处理空结果"""
        engine = WizardEngine()
        engine.result.mode = "random"
        engine._show_summary()  # 不应出错


# ============================================================================
# 5. _execute 测试
# ============================================================================


class TestWizardEngineExecute:
    """_execute 方法测试"""

    def test_execute_no_command(self):
        """无命令时不应执行"""
        engine = WizardEngine()
        engine._execute()  # 无命令，应直接返回不报错

    def test_execute_with_command(self):
        """有命令时应调用 subprocess.run"""
        engine = WizardEngine()
        engine.result.command = ["echo", "test"]
        with patch("subprocess.run") as mock_run:
            engine._execute()
            mock_run.assert_called_once_with(["echo", "test"])


# ============================================================================
# 6. 步骤处理器注册/取消 测试
# ============================================================================


class TestWizardEngineStepHandlers:
    """步骤处理器管理测试"""

    def test_register_step_handler(self):
        """注册新步骤处理器"""
        engine = WizardEngine()
        handler = Mock()
        engine.register_step_handler("custom_step", handler)
        assert "custom_step" in engine._step_handlers
        assert engine._step_handlers["custom_step"] is handler

    def test_unregister_step_handler(self):
        """取消注册步骤处理器"""
        engine = WizardEngine()
        handler = Mock()
        engine.register_step_handler("custom_step", handler)
        engine.unregister_step_handler("custom_step")
        assert "custom_step" not in engine._step_handlers

    def test_unregister_nonexistent(self):
        """取消不存在的步骤处理器不应报错"""
        engine = WizardEngine()
        engine.unregister_step_handler("nonexistent")  # 不应抛出异常

    def test_override_existing_handler(self):
        """覆盖现有步骤处理器"""
        engine = WizardEngine()
        original = engine._step_handlers["target"]
        new_handler = Mock()
        engine.register_step_handler("target", new_handler)
        assert engine._step_handlers["target"] is not original
        assert engine._step_handlers["target"] is new_handler


# ============================================================================
# 7. 消息队列集成测试
# ============================================================================


class TestWizardEngineMessageQueue:
    """消息队列集成测试"""

    def test_run_sends_wizard_start(self):
        """run() 应发送 wizard_start 事件"""
        patchers, _ = _mock_all_selectors()
        try:
            mq = WizardMessageQueue()
            config = WizardConfig(auto_continue=True)  # 跳过 input() 提示
            engine = WizardEngine(config=config, message_queue=mq)
            with patch("subprocess.run"):
                engine.run()
            events = mq.receive_all()
            assert len(events) >= 1
            assert events[0].event_type == WizardEventType.WIZARD_START
        finally:
            _stop_all_patches(patchers)

    def test_complete_sends_wizard_complete(self):
        """_complete 应发送 wizard_complete 事件"""
        patchers, _ = _mock_all_selectors()
        try:
            mq = WizardMessageQueue()
            config = WizardConfig(auto_continue=True)  # 跳过用户交互
            engine = WizardEngine(config=config, message_queue=mq)
            engine.run()
            events = mq.receive_all()
            event_types = [e.event_type for e in events]
            assert WizardEventType.WIZARD_COMPLETE in event_types
        finally:
            _stop_all_patches(patchers)

    def test_cancelled_sends_wizard_cancelled(self):
        """_cancelled 应发送 wizard_cancelled 事件"""
        mq = WizardMessageQueue()
        engine = WizardEngine(message_queue=mq)
        engine._cancelled()
        events = mq.receive_all()
        assert len(events) == 1
        assert events[0].event_type == WizardEventType.WIZARD_CANCELLED

    def test_error_sends_wizard_error(self):
        """_error 应发送 wizard_error 事件"""
        mq = WizardMessageQueue()
        engine = WizardEngine(message_queue=mq)
        engine._error("Test error")
        events = mq.receive_all()
        assert len(events) == 1
        assert events[0].event_type == WizardEventType.WIZARD_ERROR

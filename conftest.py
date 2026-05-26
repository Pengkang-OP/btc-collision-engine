"""根目录 conftest.py - 防御性兼容性补丁

修复 pytest 在 io.TextIOWrapper 未设置 closefd=False 时的 capture 崩溃问题。

解决方案:
1. 修补 FDCapture/FDCaptureBase/SysCapture 安全处理已关闭的 tmpfile
2. 修补 logging.StreamHandler.emit() 安全处理已关闭的流（log_cli 兼容性）

v4.5.1: 已修复所有已知的 TextIOWrapper 根因（添加 closefd=False）。
此补丁保留为防御性保护，防止未来新引入的代码出现同类问题。
"""


def pytest_configure(config):
    """在 pytest 配置阶段应用 capture/logging 兼容性补丁。

    问题根因: platform_utils/测试代码 中用 io.TextIOWrapper 包装 sys.stdout
    未使用 closefd=False，导致底层 fd 被意外关闭。pytest capture 的 tmpfile
    因此变成 closed 状态。此补丁对 Python 3.12+ 均适用。
    """
    _apply_python314_capture_patch()
    _apply_python314_logging_patch()
    _apply_pyopencl_editable_install_fix()


def _apply_python314_capture_patch():
    """为 pytest capture 模块应用兼容补丁。

    v4.5.1: 已修复所有已知的 TextIOWrapper 根因（添加 closefd=False）。
    保留为防御性保护，待确认长期无触发后可移除。
    """
    try:
        import tempfile

        import _pytest.capture as capture_mod

        # 补丁1: FDCapture.snap() - 安全处理已关闭的 tmpfile
        _orig_fdcapture_snap = capture_mod.FDCapture.snap

        def _safe_fdcapture_snap(self) -> str:
            if self.tmpfile.closed:
                return ""
            return _orig_fdcapture_snap(self)

        capture_mod.FDCapture.snap = _safe_fdcapture_snap

        # 补丁2: FDCaptureBinary.snap() - 安全处理已关闭的 tmpfile
        _orig_fdcapturebinary_snap = capture_mod.FDCaptureBinary.snap

        def _safe_fdcapturebinary_snap(self) -> bytes:
            if self.tmpfile.closed:
                return b""
            return _orig_fdcapturebinary_snap(self)

        capture_mod.FDCaptureBinary.snap = _safe_fdcapturebinary_snap

        # 补丁3: SysCapture.snap() - 安全处理已关闭的 tmpfile
        _orig_syscapture_snap = capture_mod.SysCapture.snap

        def _safe_syscapture_snap(self) -> str:
            if self.tmpfile.closed:
                return ""
            return _orig_syscapture_snap(self)

        capture_mod.SysCapture.snap = _safe_syscapture_snap

        # 补丁4: SysCaptureBinary.snap() - 安全处理已关闭的 tmpfile
        _orig_syscapturebinary_snap = capture_mod.SysCaptureBinary.snap

        def _safe_syscapturebinary_snap(self) -> bytes:
            if self.tmpfile.closed:
                return b""
            return _orig_syscapturebinary_snap(self)

        capture_mod.SysCaptureBinary.snap = _safe_syscapturebinary_snap

        # 补丁5: FDCaptureBase.resume() - 在 tmpfile 已关闭时重建 tmpfile
        _orig_fdcapturebase_resume = capture_mod.FDCaptureBase.resume

        def _safe_fdcapturebase_resume(self) -> None:
            """Python 3.14 兼容的 resume: 若 tmpfile 已关闭则重新创建。"""
            if self.tmpfile.closed:
                # 重新创建一个新的 EncodedFile 以替换已关闭的 tmpfile
                self.tmpfile = capture_mod.EncodedFile(
                    tempfile.TemporaryFile(buffering=0),
                    encoding="utf-8",
                    errors="replace",
                    newline="",
                    write_through=True,
                )
                # 同时更新 syscapture 的 tmpfile 引用
                patchsysdict = {0: "stdin", 1: "stdout", 2: "stderr"}
                if hasattr(self, "syscapture") and self.targetfd in patchsysdict:
                    self.syscapture.tmpfile = self.tmpfile
                # 更新 state 以允许 resume 被调用
                self._state = "suspended"
            _orig_fdcapturebase_resume(self)

        capture_mod.FDCaptureBase.resume = _safe_fdcapturebase_resume

    except Exception:
        # 补丁失败时静默跳过，不影响正常功能
        pass


def _apply_python314_logging_patch():
    """修补 logging.StreamHandler 以安全处理 Python 3.14 中已关闭的流。

    Python 3.14 中，pytest live logging (log_cli=true) 使用的 stream 可能在
    测试之间被关闭，导致后续测试的 logging 输出触发 ValueError。
    此补丁让 StreamHandler.emit() 在流已关闭时静默跳过（而不是崩溃）。
    """
    try:
        import logging

        _orig_emit = logging.StreamHandler.emit

        def _safe_emit(self, record):
            """Python 3.14 兼容的 emit: 若 stream 已关闭则静默跳过。"""
            try:
                stream = self.stream
                if stream is not None and hasattr(stream, "closed") and stream.closed:
                    return
                _orig_emit(self, record)
            except ValueError as e:
                if "I/O operation on closed file" in str(e):
                    # Python 3.14: stream 已关闭，静默忽略
                    return
                raise
            except Exception:
                self.handleError(record)

        logging.StreamHandler.emit = _safe_emit

    except Exception:
        pass


def _apply_pyopencl_editable_install_fix():
    """预导入 pyopencl 关键子模块，解决 editable install 下名称空间解析失败。

    问题根因: editable install 的 MetaPathFinder 会干扰 pyopencl 内部
    'from pyopencl.XXX import YYY' 语句的模块解析，导致
    ModuleNotFoundError: No module named 'pyopencl.XXX'; 'pyopencl' is not a package

    解决方案: 预导入 pyopencl build() 路径依赖的所有子模块/subpackage。
    """
    try:
        import pyopencl._cl  # noqa: F401
        import pyopencl.cache  # noqa: F401
        import pyopencl.characterize  # noqa: F401
        import pyopencl.cl  # noqa: F401
        import pyopencl.compyte  # noqa: F401
        import pyopencl.tools  # noqa: F401
        import pyopencl.version  # noqa: F401
    except ImportError:
        pass


import time as _poll_time

# ============================================================================
# 共享测试工具
# ============================================================================


def poll_until(condition, timeout=2.0, interval=0.01):
    """轮询直到条件成立或超时。比 time.sleep() 更稳定，适应慢 CI 环境。

    Args:
        condition: 返回 bool 的可调用对象
        timeout: 最大等待时间（秒）
        interval: 轮询间隔（秒）

    Returns:
        条件成立返回 True，超时返回最后一次 condition() 的结果
    """
    deadline = _poll_time.time() + timeout
    result = condition()
    while not result and _poll_time.time() < deadline:
        _poll_time.sleep(interval)
        result = condition()
    return result

"""
根目录 conftest.py - Python 3.14 兼容性补丁

修复 pytest 9.0.x 在 Python 3.14 上的 capture 崩溃问题。

问题根因: Python 3.14 中 io.TextIOWrapper.close() 行为变化：
当 sys.stdout 被设置为一个 TextIOWrapper 对象后，close() 该对象会导致
sys.stdout.closed = True，使后续所有写操作失败。

解决方案:
1. 修补 FDCapture.snap() 在 tmpfile 已关闭时返回空字符串
2. 修补 FDCaptureBase.resume() 在 tmpfile 已关闭时重新创建一个新的 tmpfile
3. 修补 SysCapture 相关方法安全处理已关闭的 IO
4. 修补 logging.StreamHandler.emit() 安全处理已关闭的流（log_cli 兼容性）
"""
import sys


def pytest_configure(config):
    """在 pytest 配置阶段应用 capture/logging 兼容性补丁。

    问题根因: platform_utils/测试代码 中用 io.TextIOWrapper 包装 sys.stdout
    未使用 closefd=False，导致底层 fd 被意外关闭。pytest capture 的 tmpfile
    因此变成 closed 状态。此补丁对 Python 3.12+ 均适用。
    """
    _apply_python314_capture_patch()
    _apply_python314_logging_patch()


def _apply_python314_capture_patch():
    """为 pytest capture 模块应用 Python 3.14 兼容补丁。"""
    try:
        import _pytest.capture as capture_mod
        import tempfile
        import os

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
                if hasattr(self, 'syscapture') and self.targetfd in patchsysdict:
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
                if stream is not None and hasattr(stream, 'closed') and stream.closed:
                    return
                _orig_emit(self, record)
            except ValueError as e:
                if 'I/O operation on closed file' in str(e):
                    # Python 3.14: stream 已关闭，静默忽略
                    return
                raise
            except Exception:
                self.handleError(record)

        logging.StreamHandler.emit = _safe_emit

    except Exception:
        pass

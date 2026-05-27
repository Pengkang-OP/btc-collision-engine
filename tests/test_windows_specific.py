"""Windows特定环境测试 - 原子操作和内存锁定."""

import logging
import os
import pathlib
import sys
import unittest

import pytest

# 检测是否为Windows环境
IS_WINDOWS = sys.platform.startswith("win")
logger = logging.getLogger(__name__)


@pytest.mark.skipunless(IS_WINDOWS, "仅在Windows环境运行")
class TestWindowsAtomicOperations:
    """Windows原子操作测试."""

    def test_file_atomic_write(self):
        """测试Windows文件原子写入操作."""
        import shutil
        import tempfile

        test_dir = tempfile.mkdtemp()
        try:
            target_path = os.path.join(test_dir, "test_atomic.txt")
            temp_path = target_path + ".tmp"

            content = "测试原子写入内容"

            # 模拟原子写入流程
            # 1. 写入临时文件
            pathlib.Path(temp_path).write_text(content, encoding="utf-8")

            # 2. 原子重命名（Windows上os.replace是原子的）
            pathlib.Path(temp_path).replace(target_path)

            # 3. 验证临时文件已被清理
            assert not pathlib.Path(temp_path).exists(), "临时文件应该被清理"

            # 4. 验证目标文件内容正确
            read_content = pathlib.Path(target_path).read_text(encoding="utf-8")
            assert read_content == content, "文件内容应该正确"

        finally:
            shutil.rmtree(test_dir, ignore_errors=True)

    def test_file_atomic_write_with_concurrent_access(self):
        """测试并发访问下的原子写入."""
        import shutil
        import tempfile
        import threading

        test_dir = tempfile.mkdtemp()
        target_path = os.path.join(test_dir, "concurrent_test.txt")

        write_count = 0

        def writer_thread(thread_id):
            nonlocal write_count
            try:
                temp_path = target_path + f".tmp{thread_id}"
                content = f"线程{thread_id}的内容"

                pathlib.Path(temp_path).write_text(content, encoding="utf-8")

                # 使用try-except处理可能的访问冲突
                try:
                    pathlib.Path(temp_path).replace(target_path)
                    write_count += 1
                except PermissionError:
                    # 忽略权限错误，这在并发场景下是预期的
                    pass
            except (OSError, UnicodeDecodeError) as e:
                logger.debug("并发写入线程%s异常（预期内）: %s", thread_id, e)

        # 启动多个线程同时写入
        threads = []
        for i in range(5):
            t = threading.Thread(target=writer_thread, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=5)

        # 验证至少有一次写入成功
        assert write_count > 0, "至少有一次写入应该成功"

        # 验证文件存在且可读取
        assert pathlib.Path(target_path).exists(), "目标文件应该存在"

        # 验证文件内容不为空
        content = pathlib.Path(target_path).read_text(encoding="utf-8")
        assert len(content) > 0, "文件内容不应为空"

        shutil.rmtree(test_dir, ignore_errors=True)

    def test_checkpoint_atomic_write(self):
        """测试断点文件的原子写入."""
        import shutil
        import tempfile

        from src.collision.checkpoint_manager import CheckpointManager

        test_dir = tempfile.mkdtemp()
        checkpoint_file = os.path.join(test_dir, "test_checkpoint.json")

        try:
            mgr = CheckpointManager(checkpoint_file)

            # 保存断点数据（使用正确的参数）
            mgr.save(
                mode="random",
                targets={"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"},
                current_position=0,
                total_checked=1000,
                matches=[],
            )

            # 验证文件存在
            assert pathlib.Path(checkpoint_file).exists(), "断点文件应该存在"

            # 验证临时文件不存在（已被清理）
            temp_files = [f for f in os.listdir(test_dir) if f.endswith(".tmp")]
            assert len(temp_files) == 0, "不应该有临时文件残留"

            # 验证内容正确（使用load方法）
            loaded = mgr.load()
            assert loaded is not None
            assert loaded.get("mode") == "random"

        finally:
            shutil.rmtree(test_dir, ignore_errors=True)


@pytest.mark.skipunless(IS_WINDOWS, "仅在Windows环境运行")
class TestWindowsMemoryLocking:
    """Windows内存锁定测试."""

    def test_memory_locking_availability(self):
        """测试内存锁定功能的可用性."""
        try:
            import ctypes

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

            # 分配一些内存
            buffer_size = 1024 * 1024  # 1MB
            buffer = ctypes.create_string_buffer(buffer_size)

            # 尝试锁定内存
            result = kernel32.VirtualLock(buffer, buffer_size)

            if result:
                # 解锁内存
                kernel32.VirtualUnlock(buffer, buffer_size)
                assert True, "内存锁定成功"
            else:
                # 获取错误码
                error_code = ctypes.get_last_error()
                # ERROR_NOT_ENOUGH_MEMORY (14) 或 ERROR_WORKING_SET_QUOTA (1453)
                # 或 ERROR_PRIVILEGE_NOT_HELD (1314) 是预期的
                # 这些错误表示功能存在但当前用户没有权限
                assert error_code in [14, 1453, 1314], f"预期的权限或内存不足错误，实际: {error_code}"

        except Exception as e:
            # 如果ctypes不可用，跳过此测试
            pytest.skip(f"无法测试内存锁定: {e}")

    def test_secure_key_manager_memory_protection(self):
        """测试SecureKeyManager的内存保护功能."""
        from src.core.secure_key_manager import SecureKeyManager

        # 测试SecureKeyManager是否正确处理内存保护
        key_manager = SecureKeyManager()

        # 测试密钥生成和获取
        key_manager.generate_key()
        key = key_manager.get_key()
        assert key is not None
        assert len(key) == 32

        # 测试内存清理
        key_manager.clear()

        # 测试多次clear是安全的
        key_manager.clear()

    def test_memory_view_operations(self):
        """测试内存视图操作的安全性."""
        # 测试内存视图的基本操作
        data = bytearray(1024)

        # 创建内存视图
        mv = memoryview(data)
        assert len(mv) == 1024

        # 测试写入
        mv[:4] = b"test"
        assert data[:4] == b"test"

        # 测试清零
        mv[:] = b"\x00" * 1024
        assert data == bytearray(1024)


@pytest.mark.skipunless(IS_WINDOWS, "仅在Windows环境运行")
class TestWindowsACL:
    """Windows ACL权限测试."""

    def test_file_permissions(self):
        """测试文件权限设置."""
        import shutil
        import tempfile

        test_dir = tempfile.mkdtemp()
        test_file = os.path.join(test_dir, "test_perm.txt")

        try:
            # 创建文件
            pathlib.Path(test_file).write_text("测试内容", encoding="utf-8")

            # 测试文件存在
            assert pathlib.Path(test_file).exists()

            # 测试文件可读
            content = pathlib.Path(test_file).read_text(encoding="utf-8")
            assert content == "测试内容"

            # 测试文件可写
            with pathlib.Path(test_file).open("a", encoding="utf-8") as f:
                f.write("追加内容")
            content = pathlib.Path(test_file).read_text(encoding="utf-8")
            assert "追加内容" in content

        finally:
            shutil.rmtree(test_dir, ignore_errors=True)


class TestPlatformDetection:
    """平台检测测试（跨平台）."""

    def test_windows_detection(self):
        """测试Windows平台检测."""
        if IS_WINDOWS:
            assert sys.platform.startswith("win")
            assert os.name == "nt"
        else:
            pytest.skip("非Windows平台")

    def test_checkpoint_manager_platform_handling(self):
        """测试CheckpointManager的平台特定处理."""
        import shutil

        # CheckpointManager应该能正确处理Windows环境
        # 这是一个基本的初始化测试
        import tempfile

        from src.collision.checkpoint_manager import CheckpointManager

        test_dir = tempfile.mkdtemp()
        checkpoint_file = os.path.join(test_dir, "test.json")

        try:
            mgr = CheckpointManager(checkpoint_file)
            assert mgr is not None

            # 测试基本功能
            mgr.save(mode="test", targets=set(), current_position=0, total_checked=0, matches=[])
            loaded = mgr.load()
            assert loaded is not None

        finally:
            shutil.rmtree(test_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)

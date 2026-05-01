#!/usr/bin/env python3
"""系统健康检查 (HealthChecker) 单元测试

覆盖：
- Python 版本检查
- 依赖检查
- 配置文件检查
- 磁盘空间检查
- 目录权限检查
- GPU 可用性检查
- 监控系统检查
- 网络连通性检查
- 端口检查
- 进程状态检查
- 依赖版本检查
- 报告生成
"""

import os
import json
import sys
import tempfile
import pytest
from unittest.mock import Mock, patch, MagicMock

from src.utils.health_check import HealthChecker, main


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def checker():
    """创建 HealthChecker 实例（临时目录）"""
    with tempfile.TemporaryDirectory() as tmpdir:
        c = HealthChecker(project_root=tmpdir)
        yield c


@pytest.fixture
def checker_with_config():
    """创建带配置文件的 HealthChecker"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建 config.json
        config_path = os.path.join(tmpdir, "config.json")
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump({"collision": {}, "gpu": {}, "logging": {}}, f)

        # 创建必要目录
        for d in ["logs", "data_logs", "monitoring_data"]:
            os.makedirs(os.path.join(tmpdir, d), exist_ok=True)

        c = HealthChecker(project_root=tmpdir)
        yield c


# ============================================================================
# Python 版本检查
# ============================================================================

@pytest.mark.unit
class TestPythonVersionCheck:
    """Python 版本检查测试"""

    def test_current_python_version_passes(self, checker):
        passed, message = checker.check_python_version()
        # 项目要求 Python >= 3.9
        if sys.version_info >= (3, 9):
            assert passed is True
            assert "Python版本" in message
        else:
            assert passed is False  # pragma: no cover


# ============================================================================
# 依赖检查
# ============================================================================

@pytest.mark.unit
class TestDependencyCheck:
    """依赖检查测试"""

    def test_check_dependencies(self, checker):
        passed, message = checker.check_dependencies()
        # 根据环境可能通过或不通过
        assert isinstance(passed, bool)
        assert isinstance(message, str)
        assert len(message) > 5  # 应有有意义的描述信息
        if passed:
            assert "已安装" in message
        else:
            assert "缺少" in message

    def test_check_dependency_versions(self, checker):
        passed, message = checker.check_dependency_versions()
        assert isinstance(passed, bool)
        assert isinstance(message, str)
        assert len(message) > 5  # 应有有意义的描述信息


# ============================================================================
# 配置文件检查
# ============================================================================

@pytest.mark.unit
class TestConfigFileCheck:
    """配置文件检查测试"""

    def test_no_config_file(self, checker):
        passed, message = checker.check_config_file()
        assert passed is False
        assert "不存在" in message

    def test_valid_config_file(self, checker_with_config):
        passed, message = checker_with_config.check_config_file()
        assert passed is True
        assert "有效" in message

    def test_invalid_json_config(self, checker):
        """无效 JSON 配置文件"""
        config_path = os.path.join(checker.project_root, "config.json")
        with open(config_path, "w", encoding="utf-8") as f:
            f.write("not valid json{{{")

        passed, message = checker.check_config_file()
        assert passed is False
        assert "JSON" in message

    def test_config_not_dict(self, checker):
        """配置文件根节点不是字典"""
        config_path = os.path.join(checker.project_root, "config.json")
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(["list", "not", "dict"], f)

        passed, message = checker.check_config_file()
        # 列表作为根节点应被拒绝
        assert passed is False
        assert "JSON" in message or "格式" in message or "对象" in message

    def test_check_all_config_files(self, checker_with_config):
        passed, message = checker_with_config.check_config_files()
        assert isinstance(passed, bool)
        assert isinstance(message, str)
        assert len(message) > 5


# ============================================================================
# 磁盘空间检查
# ============================================================================

@pytest.mark.unit
class TestDiskSpaceCheck:
    """磁盘空间检查测试"""

    def test_check_disk_space(self, checker):
        passed, message = checker.check_disk_space(min_mb=1)
        assert isinstance(passed, bool)
        assert isinstance(message, str)
        assert "MB" in message or "磁盘" in message

    def test_check_disk_space_insufficient(self, checker):
        """要求极大空间时检查应失败"""
        passed, message = checker.check_disk_space(min_mb=10 * 1024 * 1024)  # 10TB
        # 10TB 基本不可能有，应返回失败
        assert passed is False
        assert "不足" in message or "MB" in message


# ============================================================================
# 目录权限检查
# ============================================================================

@pytest.mark.unit
class TestDirectoryCheck:
    """目录检查测试"""

    def test_no_directories(self, checker):
        passed, message = checker.check_directories()
        assert passed is False
        assert "不存在" in message

    def test_directories_exist(self, checker_with_config):
        passed, message = checker_with_config.check_directories()
        assert passed is True
        assert "正常" in message


# ============================================================================
# GPU 检查
# ============================================================================

@pytest.mark.unit
class TestGPUCheck:
    """GPU 设备检查测试"""

    def test_check_gpu_availability(self, checker):
        passed, message = checker.check_gpu_availability()
        assert isinstance(passed, bool)
        assert isinstance(message, str)
        assert len(message) > 5  # 应有有意义的描述信息

    def test_check_gpu_pyopencl_not_installed(self, checker):
        """模拟 pyopencl 未安装"""
        with patch('builtins.__import__') as mock_import:
            original_import = __import__
            def selective_import(name, *args, **kwargs):
                if name == 'pyopencl':
                    raise ImportError("No module named 'pyopencl'")
                return original_import(name, *args, **kwargs)
            mock_import.side_effect = selective_import
            passed, message = checker.check_gpu_availability()
            assert passed is False
            assert "未安装" in message or "PyOpenCL" in message


# ============================================================================
# 监控系统检查
# ============================================================================

@pytest.mark.unit
class TestMonitoringCheck:
    """监控系统检查测试"""

    def test_check_monitoring_system(self, checker):
        passed, message = checker.check_monitoring_system()
        assert isinstance(passed, bool)
        assert isinstance(message, str)
        assert len(message) > 5


# ============================================================================
# 网络检查
# ============================================================================

@pytest.mark.unit
class TestNetworkCheck:
    """网络检查测试"""

    @patch('socket.socket')
    def test_check_network_connectivity(self, mock_socket_class, checker):
        mock_sock = Mock()
        mock_sock.connect_ex.return_value = 0  # 连接成功
        mock_socket_class.return_value = mock_sock

        passed, message = checker.check_network_connectivity()
        assert passed is True

    @patch('socket.socket')
    def test_check_network_connectivity_failure(self, mock_socket_class, checker):
        mock_sock = Mock()
        mock_sock.connect_ex.return_value = 1  # 连接失败
        mock_socket_class.return_value = mock_sock

        passed, message = checker.check_network_connectivity()
        assert passed is False


# ============================================================================
# 端口检查
# ============================================================================

@pytest.mark.unit
class TestPortCheck:
    """端口检查测试"""

    @patch('socket.socket')
    def test_check_port_availability_all_free(self, mock_socket_class, checker):
        mock_sock = Mock()
        mock_sock.__enter__ = Mock(return_value=mock_sock)
        mock_sock.__exit__ = Mock(return_value=False)
        mock_sock.connect_ex.return_value = 1  # 端口空闲
        mock_socket_class.return_value = mock_sock

        passed, message = checker.check_port_availability([9090])
        assert passed is True


# ============================================================================
# 进程状态检查
# ============================================================================

@pytest.mark.unit
class TestProcessCheck:
    """进程状态检查测试"""

    def test_check_process_status(self, checker):
        passed, message = checker.check_process_status()
        assert isinstance(passed, bool)
        assert isinstance(message, str)
        assert len(message) > 3


# ============================================================================
# 综合测试
# ============================================================================

@pytest.mark.unit
class TestHealthCheckerIntegration:
    """综合测试"""

    def test_run_all_checks(self, checker):
        results = checker.run_all_checks(include_gpu=False, include_network=False)
        assert isinstance(results, dict)
        assert len(results) > 0
        # 每个结果应为 (bool, str) 元组
        for key, (passed, message) in results.items():
            assert isinstance(passed, bool)
            assert isinstance(message, str)

    def test_generate_report(self, checker):
        checker.results = {
            "Python版本": (True, "Python版本: 3.x.x"),
            "依赖安装": (True, "所有依赖已安装"),
        }
        report = checker.generate_report()
        assert "Python版本" in report
        assert "依赖安装" in report

    def test_results_attribute(self, checker):
        checker.results = {"Python版本": (True, "ok")}
        assert "Python版本" in checker.results

    def test_config_check_permissions(self, checker_with_config):
        passed, message = checker_with_config.check_config_permissions()
        assert isinstance(passed, bool)
        assert isinstance(message, str)
        assert len(message) > 5
        if passed:
            assert "安全" in message


# ============================================================================
# CLI 入口测试
# ============================================================================

@pytest.mark.unit
class TestHealthCheckCLI:
    """CLI 入口测试"""

    @patch('sys.argv', ['health_check.py'])
    def test_main_basic(self, checker):
        """基本运行不应崩溃"""
        with patch('src.utils.health_check.HealthChecker') as mock_cls:
            mock_instance = Mock()
            mock_instance.run_all_checks.return_value = {
                "test": (True, "all good")
            }
            mock_cls.return_value = mock_instance
            try:
                main()
            except SystemExit:
                pass

    @patch('sys.argv', ['health_check.py', '--gpu', '--network'])
    def test_main_with_options(self):
        with patch('src.utils.health_check.HealthChecker') as mock_cls:
            mock_instance = Mock()
            mock_instance.run_all_checks.return_value = {"test": (True, "ok")}
            mock_cls.return_value = mock_instance
            try:
                main()
            except SystemExit:
                pass

    @patch('sys.argv', ['health_check.py', '--report', 'report.txt'])
    def test_main_with_report(self, checker):
        with patch('src.utils.health_check.HealthChecker') as mock_cls:
            mock_instance = Mock()
            mock_instance.run_all_checks.return_value = {"test": (True, "ok")}
            mock_instance.generate_report.return_value = "report content"
            mock_cls.return_value = mock_instance
            try:
                main()
            except SystemExit:
                pass

# -*- coding: utf-8 -*-
"""验收测试共享配置文件 - 提供全局 Fixture 和测试配置

本文件包含:
- 验收测试共享的 pytest fixtures
- GPU 引擎测试的 Mock 配置
- 测试数据加载和验证辅助函数
- 测试环境配置和清理

设计原则:
1. 高可读性: 清晰的文档字符串和注释
2. 易维护: 模块化的 fixture 设计
3. 全面性: 覆盖所有验收测试需求
4. 隔离性: 每个测试独立运行，互不干扰
"""

import json
import os
import shutil
import tempfile
import time
from contextlib import suppress
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Set, Tuple
from unittest.mock import MagicMock, Mock, patch

import pytest

# ============================================================================
# 测试常量定义
# ============================================================================

class AcceptanceTestConstants:
    """验收测试常量集合

    集中管理测试中的硬编码值，提高可维护性
    """

    # 测试目标地址（真实的 Bitcoin 地址，仅用于测试）
    VALID_P2PKH_ADDRESS = "1A1zP1eP5QGefi2DMPTFTL5SLmv7DivfNa"  # Genesis block
    VALID_P2SH_ADDRESS = "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy"
    VALID_BECH32_ADDRESS = "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh"

    # 无效的地址（用于边界测试）
    INVALID_ADDRESS_FORMAT = "2A1zP1eP5QGefi2DMPTFTL5SLmv7DivfNa"
    INVALID_ADDRESS_CHECKSUM = "1A1zP1eP5QGefi2DMPTFTL5SLmv7DivfNb"
    INVALID_ADDRESS_LENGTH = "1A1zP1eP5QGefi"

    # 测试私钥（仅用于测试，非真实私钥）
    TEST_PRIVATE_KEY_HEX = "1" * 64  # 256-bit 全1
    TEST_PRIVATE_KEY_BYTES = bytes.fromhex(TEST_PRIVATE_KEY_HEX)

    # GPU 测试常量
    DEFAULT_GPU_BATCH_SIZE = 65536
    DEFAULT_GPU_MEM_SIZE = 8 * 1024 ** 3  # 8GB

    # 搜索模式
    SEARCH_MODE_RANDOM = "random"
    SEARCH_MODE_RANGE = "range_scan"
    SEARCH_MODE_BRUTE_FORCE = "brute_force"

    # 状态常量
    STATE_INITIALIZED = "initialized"
    STATE_RUNNING = "running"
    STATE_STOPPED = "stopped"
    STATE_ERROR = "error"

    # 性能基准
    MAX_ACCEPTABLE_TIME_SEC = 5.0  # 单个测试用例最大可接受时间
    MAX_MEMORY_USAGE_MB = 1024  # 单个测试用例最大内存使用


# ============================================================================
# 公共 Mock 创建函数
# ============================================================================

def create_mock_gpu_device(
    device_name: str = "Test GPU",
    vendor: str = "NVIDIA Corporation",
    global_mem_size: int = AcceptanceTestConstants.DEFAULT_GPU_MEM_SIZE,
    batch_size: int = AcceptanceTestConstants.DEFAULT_GPU_BATCH_SIZE,
) -> Mock:
    """创建标准 GPU Mock 设备

    Args:
        device_name: GPU 设备名称
        vendor: GPU 厂商名称
        global_mem_size: 显存大小（字节）
        batch_size: 批次大小

    Returns:
        Mock: 配置好的 GPU 设备 Mock 对象
    """
    mock_device = Mock()
    mock_device.name = device_name
    mock_device.vendor = vendor
    mock_device.global_mem_size = global_mem_size
    mock_device.max_compute_units = 40
    mock_device.max_work_group_size = 256

    # 模拟设备初始化
    mock_device.initialize = Mock(return_value=True)
    mock_device.cleanup = Mock(return_value=True)
    mock_device.is_available = Mock(return_value=True)

    # 模拟设备信息
    mock_device.get_device_info = Mock(
        return_value={
            "name": device_name,
            "vendor": vendor,
            "global_mem_size": global_mem_size,
            "max_compute_units": 40,
        }
    )

    return mock_device


def create_mock_gpu_context(
    device: Optional[Mock] = None,
    batch_size: int = AcceptanceTestConstants.DEFAULT_GPU_BATCH_SIZE,
) -> Mock:
    """创建标准 GPU Mock 上下文

    Args:
        device: GPU 设备 Mock 对象（如果为 None，则自动创建）
        batch_size: 批次大小

    Returns:
        Mock: 配置好的 GPU 上下文 Mock 对象
    """
    if device is None:
        device = create_mock_gpu_device()

    mock_context = Mock()
    mock_context.device = device
    mock_context.batch_size = batch_size

    # 模拟上下文方法
    mock_context.compile_kernel = Mock(return_value=Mock())
    mock_context.allocate_buffer = Mock(return_value=Mock())
    mock_context.free_buffer = Mock(return_value=True)
    mock_context.calculate_batch_size = Mock(return_value=batch_size)

    return mock_context


def create_mock_gpu_kernel(
    batch_size: int = AcceptanceTestConstants.DEFAULT_GPU_BATCH_SIZE,
) -> Mock:
    """创建标准 GPU Mock 内核

    Args:
        batch_size: 批次大小

    Returns:
        Mock: 配置好的 GPU 内核 Mock 对象
    """
    mock_kernel = Mock()
    mock_kernel.batch_size = batch_size
    mock_kernel.max_batch_size = batch_size * 2

    # 模拟内核方法
    mock_kernel.run_batch = Mock(return_value=[])  # 返回空匹配列表
    mock_kernel.set_targets = Mock(return_value=True)
    mock_kernel.cleanup = Mock(return_value=True)
    mock_kernel.get_performance_stats = Mock(
        return_value={
            "keys_per_second": 1000000,
            "batch_time_ms": 10.0,
        }
    )

    return mock_kernel


def create_mock_checkpoint_data(
    version: int = 2,
    total_keys_checked: int = 1000000,
    matches_found: int = 2,
) -> Dict[str, Any]:
    """创建模拟的检查点数据

    Args:
        version: 检查点版本号
        total_keys_checked: 已检查的私钥总数
        matches_found: 找到的匹配数

    Returns:
        Dict[str, Any]: 检查点数据字典
    """
    return {
        "version": version,
        "timestamp": time.time(),
        "engine_type": "KeyCollisionEngine",
        "search_mode": AcceptanceTestConstants.SEARCH_MODE_RANDOM,
        "total_keys_checked": total_keys_checked,
        "matches_found": matches_found,
        "start_time": time.time() - 600,  # 10 分钟前开始
        "elapsed_time": 600.0,
        "checkpoint_interval": 30,
        "targets": [
            AcceptanceTestConstants.VALID_P2PKH_ADDRESS,
            AcceptanceTestConstants.VALID_P2SH_ADDRESS,
        ],
        "last_key_index": total_keys_checked,
        "random_seed": 12345,
        "stats": {
            "keys_per_second": 1666.67,
            "cpu_usage_percent": 85.2,
            "memory_usage_mb": 512.5,
        },
    }


# ============================================================================
# Pytest Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def test_data_dir() -> Path:
    """获取测试数据目录路径

    Returns:
        Path: 测试数据目录的 Path 对象
    """
    return Path(__file__).parent / "test_data"


# ============================================================================
# 关键修复：Mock DataLogger 避免文件轮转超时
# ============================================================================
# 在导入任何可能导入 DataLogger 的模块之前，先 patch get_configured_logger
# 这样所有后续导入都会使用 mock 的 logger

import logging

# 创建一个简单的内存 logger，不写入任何文件
_mock_test_logger = logging.getLogger("TestDataLogger")
_mock_test_logger.setLevel(logging.CRITICAL)  # 测试时只显示严重错误
_mock_test_logger.handlers.clear()
_mock_test_logger.addHandler(logging.NullHandler())
_mock_test_logger.propagate = False


def _mock_get_configured_logger(name: str) -> logging.Logger:
    """Mock get_configured_logger 返回内存 logger"""
    return _mock_test_logger


# 应用 patch 到 src.utils 模块
# 注意：这会影响所有导入 get_configured_logger 的模块
_patch_get_configured_logger = patch(
    "src.utils.get_configured_logger",
    side_effect=_mock_get_configured_logger,
)
_patch_get_configured_logger.start()


@pytest.fixture(scope="function", autouse=True)
def setup_test_logging() -> Generator[None, None, None]:
    """为测试配置临时日志目录

    这个 fixture 自动应用于每个测试函数，将日志系统配置为使用内存 logger，
    避免日志文件被其他进程占用导致的超时问题。
    """
    # get_configured_logger 已经被 patch 了，这里只需要 yield
    yield


# ============================================================================
# 其他 Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def temp_dir() -> Generator[Path, None, None]:
    """创建临时目录用于测试

    Yields:
        Path: 临时目录的 Path 对象

    Note:
        测试结束后自动清理临时目录
    """
    temp_path = Path(tempfile.mkdtemp(prefix="btc_acceptance_test_"))
    yield temp_path
    # 清理临时目录
    if temp_path.exists():
        shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture(scope="function")
def mock_gpu_chain() -> Generator[Tuple[Mock, Mock, Mock], None, None]:
    """提供完整的 GPU Mock 链，用于 GPU 碰撞引擎测试

    这个 fixture 封装了 GPU 设备、上下文和内核的 Mock 对象，
    避免在每个测试中重复编写 Mock 代码。

    Yields:
        Tuple[Mock, Mock, Mock]: (mock_device, mock_context, mock_kernel)

    Example:
        >>> def test_gpu_engine(mock_gpu_chain):
        ...     mock_device, mock_context, mock_kernel = mock_gpu_chain
        ...     # 测试代码...
    """
    mock_device = create_mock_gpu_device()
    mock_context = create_mock_gpu_context(mock_device)
    mock_kernel = create_mock_gpu_kernel()

    # 应用 Mock 补丁
    with patch("src.gpu.device.GPUDevice", return_value=mock_device), patch(
        "src.gpu.context.GPUContext", return_value=mock_context
    ), patch("src.gpu.kernel.GPUKernel", return_value=mock_kernel), patch(
        "src.collision.gpu.engine.PYOPENCL_AVAILABLE", True
    ), patch(
        "src.gpu.device.GPUDeviceDetector.is_gpu_available", return_value=True
    ):
        yield mock_device, mock_context, mock_kernel


@pytest.fixture(scope="function")
def mock_checkpoint_manager(temp_dir: Path) -> Any:
    """创建模拟的 CheckpointManager 实例

    Args:
        temp_dir: 临时目录 fixture

    Returns:
        CheckpointManager: 配置好的 CheckpointManager 实例

    Note:
        使用临时目录存储检查点文件，避免污染项目目录
    """
    from src.collision.checkpoint_manager import CheckpointManager

    checkpoint_path = temp_dir / "test_checkpoint.json"
    manager = CheckpointManager(filepath=checkpoint_path, interval=1)

    yield manager

    # 清理
    if checkpoint_path.exists():
        checkpoint_path.unlink()


@pytest.fixture(scope="function")
def mock_event_bus() -> Any:
    """创建模拟的 EventBus 实例

    Returns:
        EventBus: 配置好的 EventBus 实例
    """
    from src.collision.event_bus import EventBus

    event_bus = EventBus()
    yield event_bus
    event_bus.clear()


@pytest.fixture(scope="function")
def mock_target_resolver() -> Any:
    """创建模拟的 TargetResolver 实例

    Returns:
        TargetResolver: 配置好的 TargetResolver 实例
    """
    from src.collision.targets.resolver import TargetResolver

    resolver = TargetResolver()
    yield resolver


@pytest.fixture(scope="function")
def sample_target_addresses() -> Set[str]:
    """提供样本目标地址集合

    Returns:
        Set[str]: 目标地址集合
    """
    return {
        AcceptanceTestConstants.VALID_P2PKH_ADDRESS,
        AcceptanceTestConstants.VALID_P2SH_ADDRESS,
        AcceptanceTestConstants.VALID_BECH32_ADDRESS,
    }


@pytest.fixture(scope="function")
def mock_collision_stats() -> Any:
    """创建模拟的 CollisionStats 实例

    Returns:
        CollisionStats: 配置好的 CollisionStats 实例
    """
    from src.collision.collision_stats import CollisionStats

    stats = CollisionStats()
    yield stats


@pytest.fixture(scope="function")
def mock_deduplication_filter() -> Any:
    """创建模拟的 DeduplicationFilter 实例

    Returns:
        DeduplicationFilter: 配置好的 DeduplicationFilter 实例
    """
    from src.collision.deduplication_filter import DeduplicationFilter

    filter_instance = DeduplicationFilter(max_size=10000)
    yield filter_instance


@pytest.fixture(scope="function")
def mock_crypto_backend() -> Any:
    """创建模拟的 CryptoBackendManager 实例

    Returns:
        Mock: 配置好的 CryptoBackendManager Mock 对象
    """
    from unittest.mock import Mock, MagicMock

    mock_backend = Mock()
    
    # 模拟后端管理方法
    mock_backend.initialize = Mock(return_value=True)
    mock_backend.cleanup = Mock(return_value=True)
    mock_backend.get_available_backends = Mock(
        return_value=["pure_python", "openssl", "coincurve", "ecdsa"]
    )
    mock_backend.get_current_backend = Mock(return_value="pure_python")
    mock_backend.switch_backend = Mock(return_value=True)
    
    # 模拟密码学方法
    mock_backend.generate_public_key = Mock(
        return_value=b"\x02" + b"\x11" * 32  # 压缩公钥格式
    )
    mock_backend.scalar_multiply = Mock(
        return_value=b"\x02" + b"\x22" * 32
    )
    mock_backend.verify_signature = Mock(return_value=True)
    
    # 模拟性能统计
    mock_backend.get_performance_stats = Mock(
        return_value={
            "keys_per_second": 100000,
            "backend": "pure_python",
            "memory_usage_mb": 10.5,
        }
    )
    
    yield mock_backend


@pytest.fixture(scope="function")
def valid_addresses(test_data_dir: Path) -> List[str]:
    """加载有效地址列表

    Args:
        test_data_dir: 测试数据目录 fixture

    Returns:
        List[str]: 有效地址列表
    """
    valid_file = test_data_dir / "valid_addresses.txt"
    if not valid_file.exists():
        return [AcceptanceTestConstants.VALID_P2PKH_ADDRESS]

    with open(valid_file, "r") as f:
        addresses = [
            line.strip()
            for line in f
            if line.strip() and not line.strip().startswith("#")
        ]
    return addresses


@pytest.fixture(scope="function")
def invalid_addresses(test_data_dir: Path) -> List[str]:
    """加载无效地址列表

    Args:
        test_data_dir: 测试数据目录 fixture

    Returns:
        List[str]: 无效地址列表
    """
    invalid_file = test_data_dir / "invalid_addresses.txt"
    if not invalid_file.exists():
        return [AcceptanceTestConstants.INVALID_ADDRESS_FORMAT]

    with open(invalid_file, "r") as f:
        addresses = [
            line.strip()
            for line in f
            if line.strip() and not line.strip().startswith("#")
        ]
    return addresses


# ============================================================================
# 辅助断言函数
# ============================================================================

def assert_valid_bitcoin_address(address: str, message: Optional[str] = None) -> None:
    """断言给定的字符串是有效的 Bitcoin 地址

    Args:
        address: 要验证的地址字符串
        message: 自定义断言失败消息

    Raises:
        AssertionError: 如果地址无效
    """
    assert isinstance(address, str), message or f"地址必须是字符串类型，实际类型: {type(address)}"
    assert address, message or "地址不能为空"

    # 检查地址前缀
    valid_prefixes = ("1", "3", "bc1")
    assert any(
        address.startswith(prefix) for prefix in valid_prefixes
    ), message or f"地址必须以 {valid_prefixes} 之一开头，实际: {address}"


def assert_valid_private_key(private_key: bytes, message: Optional[str] = None) -> None:
    """断言给定的字节串是有效的私钥

    Args:
        private_key: 要验证的私钥字节串
        message: 自定义断言失败消息

    Raises:
        AssertionError: 如果私钥无效
    """
    assert isinstance(private_key, bytes), (
        message or f"私钥必须是 bytes 类型，实际类型: {type(private_key)}"
    )
    assert len(private_key) == 32, (
        message or f"私钥必须是 32 字节，实际长度: {len(private_key)}"
    )

    # 检查私钥范围 (1 <= private_key <= n-1)
    private_key_int = int.from_bytes(private_key, "big")
    assert 1 <= private_key_int <= 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364140 - 1, (
        message or f"私钥超出有效范围: {private_key_int}"
    )


def assert_engine_state(
    engine: Any,
    expected_state: str,
    message: Optional[str] = None,
) -> None:
    """断言引擎处于预期状态

    Args:
        engine: 要检查的引擎实例
        expected_state: 预期状态（'initialized', 'running', 'stopped', 'error'）
        message: 自定义断言失败消息

    Raises:
        AssertionError: 如果引擎状态不符合预期
    """
    assert engine is not None, message or "引擎实例不能为 None"

    if expected_state == AcceptanceTestConstants.STATE_INITIALIZED:
        assert not engine.is_running(), (
            message or "引擎应该处于初始化状态，但 is_running() 返回 True"
        )
    elif expected_state == AcceptanceTestConstants.STATE_RUNNING:
        assert engine.is_running(), (
            message or "引擎应该处于运行状态，但 is_running() 返回 False"
        )
    elif expected_state == AcceptanceTestConstants.STATE_STOPPED:
        assert not engine.is_running(), (
            message or "引擎应该处于停止状态，但 is_running() 返回 True"
        )
    elif expected_state == AcceptanceTestConstants.STATE_ERROR:
        assert hasattr(engine, "_error"), (
            message or "引擎应该处于错误状态，但缺少 _error 属性"
        )


def assert_pipeline_stage_complete(
    stage_name: str,
    stage_result: Any,
    expected_type: Optional[type] = None,
    message: Optional[str] = None,
) -> None:
    """断言 Pipeline 阶段完成且结果有效

    Args:
        stage_name: Pipeline 阶段名称
        stage_result: 阶段执行结果
        expected_type: 预期的结果类型
        message: 自定义断言失败消息

    Raises:
        AssertionError: 如果阶段结果无效
    """
    assert stage_result is not None, (
        message or f"Pipeline 阶段 '{stage_name}' 的结果不能为 None"
    )

    if expected_type is not None:
        assert isinstance(stage_result, expected_type), (
            message
            or f"Pipeline 阶段 '{stage_name}' 的结果类型必须是 {expected_type}，实际类型: {type(stage_result)}"
        )


# ============================================================================
# Pytest 配置钩子
# ============================================================================

def pytest_configure(config: Any) -> None:
    """配置 pytest 环境，注册自定义 marker

    Args:
        config: pytest 配置对象
    """
    # 验收测试相关 marker
    config.addinivalue_line("markers", "acceptance: 验收测试（端到端功能验证）")
    config.addinivalue_line("markers", "pipeline: Pipeline 集成测试（多步骤数据流转）")
    config.addinivalue_line("markers", "white_box: 白盒测试（基于内部代码结构）")
    config.addinivalue_line("markers", "black_box: 黑盒测试（基于规格说明）")
    config.addinivalue_line("markers", "lifecycle: 生命周期测试（组件完整生命周期）")
    config.addinivalue_line("markers", "aux_function: 辅助功能测试（辅助函数和工具）")
    config.addinivalue_line("markers", "aux_data: 辅助数据测试（数据辅助工具和转换）")

    # 功能层测试 marker
    config.addinivalue_line("markers", "functional: 功能层测试（功能正确性、调用、判断）")

    # 数据层测试 marker
    config.addinivalue_line("markers", "data_layer: 数据层测试（数据、数据流、数据管道）")

    # 逻辑层测试 marker
    config.addinivalue_line("markers", "logic_layer: 逻辑层测试（代码正确性、逻辑、判断）")


def pytest_collection_modifyitems(config: Any, items: List[Any]) -> None:
    """修改测试项集合，根据 marker 对测试进行分类

    Args:
        config: pytest 配置对象
        items: 测试项列表
    """
    # 为验收测试添加超时标记
    acceptance_timeout_marker = pytest.mark.timeout(
        AcceptanceTestConstants.MAX_ACCEPTABLE_TIME_SEC
    )

    for item in items:
        # 为所有验收测试添加超时保护
        if "acceptance" in item.keywords or "pipeline" in item.keywords:
            item.add_marker(acceptance_timeout_marker)

        # 为 Pipeline 测试添加特殊标记
        if "pipeline" in item.keywords:
            # Pipeline 测试通常需要更多时间
            pipeline_timeout_marker = pytest.mark.timeout(
                AcceptanceTestConstants.MAX_ACCEPTABLE_TIME_SEC * 2
            )
            item.add_marker(pipeline_timeout_marker)


# ============================================================================
# 清理函数
# ============================================================================

@pytest.fixture(scope="session", autouse=True)
def cleanup_after_all_tests() -> Generator[None, None, None]:
    """所有测试结束后执行全局清理

    Yields:
        None

    Note:
        这个 fixture 会自动执行，无需手动调用
    """
    yield

    # 清理可能的临时文件
    temp_dirs = [
        Path(tempfile.gettempdir()) / "btc_acceptance_test_*",
    ]

    for temp_dir_pattern in temp_dirs:
        for temp_dir in Path(tempfile.gettempdir()).glob("btc_acceptance_test_*"):
            if temp_dir.is_dir():
                shutil.rmtree(temp_dir, ignore_errors=True)

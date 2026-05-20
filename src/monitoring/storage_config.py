"""统一数据存储配置

规范所有监控和日志数据的存储路径，避免多套系统并存导致的数据不一致问题。
"""

import os

# P2-05修复: 缓存项目根目录，避免多次计算
_project_root: str | None = None


def _get_project_root() -> str:
    """P2-05修复: 获取项目根目录

    使用多种策略检测项目根目录，比简单的 __file__ 回溯更鲁棒：
    1. 环境变量 BTC_ENGINE_ROOT（最高优先级）
    2. 从 __file__ 向上查找包含 pyproject.toml 或 .git 的目录
    3. 回退到 os.getcwd()（容错）
    """
    global _project_root
    if _project_root is not None:
        return _project_root

    # 策略1: 环境变量
    env_root = os.environ.get("BTC_ENGINE_ROOT")
    if env_root and os.path.isdir(env_root):
        _project_root = os.path.abspath(env_root)
        return _project_root

    # 策略2: 从 __file__ 向上查找项目标记文件
    current = os.path.dirname(os.path.abspath(__file__))
    for _ in range(5):  # 最多向上5层
        if os.path.exists(os.path.join(current, "pyproject.toml")) or os.path.exists(
            os.path.join(current, ".git")
        ):
            _project_root = current
            return _project_root
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent

    # 策略3: 回退到当前工作目录
    _project_root = os.getcwd()
    return _project_root


class DataStorageConfig:
    """统一数据存储配置

    所有数据存储组件（DataStorage、DataLogger等）都应使用此配置
    确定的存储路径，确保数据一致性。
    """

    # 唯一数据源目录
    DEFAULT_STORAGE_DIR: str = "data_logs"

    # 历史数据最大条数
    MAX_HISTORY_RECORDS: int = 1000

    # 错误日志最大条数
    MAX_ERROR_RECORDS: int = 500

    # 性能日志文件
    PERFORMANCE_LOG_FILE: str = "performance.log"

    @classmethod
    def get_storage_path(cls, storage_dir: str | None = None) -> str:
        """获取存储路径

        Args:
            storage_dir: 自定义存储目录（可选）

        Returns:
            绝对路径
        """
        if storage_dir:
            return os.path.abspath(storage_dir)

        # P2-05修复: 使用鲁棒的项目根目录检测，替代脆弱的 __file__ 回溯
        project_root = _get_project_root()
        return os.path.join(project_root, cls.DEFAULT_STORAGE_DIR)

    @classmethod
    def ensure_storage_dir(cls, storage_dir: str | None = None) -> str:
        """确保存储目录存在

        Args:
            storage_dir: 存储目录

        Returns:
            存储目录绝对路径
        """
        path = cls.get_storage_path(storage_dir)
        os.makedirs(path, exist_ok=True)
        return path

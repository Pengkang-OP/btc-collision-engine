"""统一数据存储配置

规范所有监控和日志数据的存储路径，避免多套系统并存导致的数据不一致问题。
"""

import os
from typing import Optional


class DataStorageConfig:
    """统一数据存储配置

    所有数据存储组件（DataStorage、DataLogger等）都应使用此配置
    确定的存储路径，确保数据一致性。
    """

    # 唯一数据源目录
    DEFAULT_STORAGE_DIR = "data_logs"

    # 历史数据最大条数
    MAX_HISTORY_RECORDS = 1000

    # 错误日志最大条数
    MAX_ERROR_RECORDS = 500

    # 性能日志文件
    PERFORMANCE_LOG_FILE = "performance.log"

    @classmethod
    def get_storage_path(cls, storage_dir: Optional[str] = None) -> str:
        """获取存储路径

        Args:
            storage_dir: 自定义存储目录（可选）

        Returns:
            绝对路径
        """
        if storage_dir:
            return os.path.abspath(storage_dir)

        # 默认使用项目根目录下的data_logs
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(project_root, cls.DEFAULT_STORAGE_DIR)

    @classmethod
    def ensure_storage_dir(cls, storage_dir: Optional[str] = None) -> str:
        """确保存储目录存在

        Args:
            storage_dir: 存储目录

        Returns:
            存储目录绝对路径
        """
        path = cls.get_storage_path(storage_dir)
        os.makedirs(path, exist_ok=True)
        return path

"""KeyCollisionEngine 模块级常量配置.

从 key_collision_engine.py 拆分，提高可维护性。
"""

# 每批处理的私钥数量
BATCH_SIZE = 1000

# 进度回调最小间隔（秒）
PROGRESS_INTERVAL_SEC = 0.5

# 每N次检测触发一次进度回调（与 DEFAULT_BATCH_SIZE 区分：此为进度上报粒度）
PROGRESS_INTERVAL_COUNT = 1000
PROGRESS_INTERVAL_COUNT_DEFAULT = PROGRESS_INTERVAL_COUNT  # 别名，向后兼容

# 每N次记录保存一次数据日志
DATA_LOG_SAVE_FREQUENCY = 3

# 错误日志记录间隔（秒）
ERROR_LOG_INTERVAL_SEC = 5.0

# CPU使用率缓存更新间隔（秒）
CPU_CACHE_INTERVAL_SEC = 1.0

# P3-9: Batch自动调优参数
BATCH_TUNE_1_2_CORE = 500
BATCH_TUNE_4_CORE = 1000
BATCH_TUNE_8_CORE = 2000
BATCH_TUNE_16_CORE = 4000
BATCH_TUNE_32_CORE = 6000
BATCH_TUNE_64_PLUS_CORE = 8000

# 内存监控降级参数 (P1-6)
MEMORY_HIGH_THRESHOLD_MB = 2048  # 内存警报阈值 2GB
MEMORY_CRITICAL_THRESHOLD_MB = 3072  # 内存临界阈值 3GB
MEMORY_DOWNGRADE_COOLDOWN_SEC = 30.0  # 降级冷却时间（秒）

# 去重缓存参数
DEDUP_MAX_RECENT_SIZE = 10000  # 短期去重缓存大小
COMPRESSION_AUTO_THRESHOLD = 10000  # 双格式检查自动切换阈值
COMPRESSION_FORCE_SINGLE_THRESHOLD = 50000  # 强制仅压缩格式的阈值

# 匹配结果批量提交阈值（从 collision.constants 引入，避免重复定义）
from .constants import MATCH_BATCH_FLUSH_THRESHOLD  # noqa: F401, E402

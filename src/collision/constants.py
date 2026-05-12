"""碰撞引擎常量定义

集中管理所有魔法数字和配置常量，提高代码可读性和可维护性。
"""

# ========== 私钥相关常量 ==========
PRIVATE_KEY_SIZE = 32  # 私钥长度（字节）
PRIVATE_KEY_MIN = 1  # 私钥最小值
COMPRESSED_FLAG = b"\x01"  # 压缩公钥标志

# ========== 批次大小常量 ==========
BATCH_SIZE_DEFAULT = 1000  # 默认批次大小
BATCH_SIZE_GPU_DEFAULT = 65536  # GPU默认批次大小
BATCH_SIZE_LARGE = 1_000_000  # 大批次大小（用于GPU优化）

# ========== 进度和间隔常量 ==========
PROGRESS_INTERVAL_COUNT = 1000  # 进度回调间隔（每N次检测）
CHECKPOINT_INTERVAL_DEFAULT = 30  # 断点保存间隔（秒）
DATA_LOGGING_INTERVAL_DEFAULT = 10  # 数据日志记录间隔（秒）

# ========== 去重和缓存常量 ==========
DEDUP_MAX_SIZE_DEFAULT = 1_000_000  # 去重过滤器默认最大容量
BLOOM_FILTER_MAX_SIZE = 10_000_000  # Bloom过滤器最大容量
BLOOM_FILTER_FALSE_POSITIVE_RATE = 0.001  # Bloom过滤器误报率

# ========== 队列和缓冲区常量 ==========
RESULT_QUEUE_MAX_SIZE = 1000  # 结果队列最大容量
GPU_BUFFER_TRACKER_MAX = 1000  # GPU缓冲区追踪器最大数量
GPU_BUFFER_TIMEOUT = 300  # GPU缓冲区超时时间（秒，5分钟）

# ========== 性能和限制常量 ==========
MAX_WORKERS_DEFAULT = None  # 默认最大工作线程数（None=自动）
MAX_RETRY_COUNT = 100  # 最大重试次数
MAX_HISTORY_RECORDS = 1000  # 最大历史记录数
MAX_ALERT_HISTORY = 1000  # 最大告警历史数

# ========== 超时常量 ==========
THREAD_JOIN_TIMEOUT_MIN = 10.0  # 线程等待最小超时（秒）
THREAD_JOIN_TIMEOUT_PER_TARGET = 0.001  # 每个目标增加的超时（秒）
ASYNC_GENERATION_TIMEOUT = 30.0  # 异步私钥生成超时（秒）
STATS_UPDATE_TIMEOUT = 5.0  # 统计更新等待超时（秒）

# ========== 文件大小和权限常量 ==========
FILE_PERMISSION_RESTRICTED = 0o600  # 文件权限：仅所有者可读写
LOG_MAX_BYTES = 10_485_760  # 日志文件最大大小（10MB）
LOG_BACKUP_COUNT = 5  # 日志备份数量

# ========== GPU相关常量 ==========
GPU_MEMORY_RATIO_DEFAULT = 0.5  # GPU内存使用比例默认值
INTEL_SAFE_MEMORY_RATIO = 0.45  # Intel GPU 安全显存使用率（保守策略，避免TDR超时）
GPU_DEVICE_AUTO_SELECT = -1  # GPU设备自动选择标志
GPU_COMPILE_TIMEOUT = 60  # GPU编译超时（秒）

# ========== 重试和延迟常量 ==========
MAX_RETRIES = 3  # 最大重试次数
RETRY_DELAY = 0.5  # 重试延迟（秒）
RETRY_DELAY_INCREMENT = 0.1  # 重试延迟递增（秒）

# ========== 告警常量 ==========
ALERT_RATE_LIMIT_MAX = 10  # 每分钟最大告警数
ALERT_RATE_LIMIT_WINDOW = 60  # 告警速率限制窗口（秒）
ALERT_DEDUP_LOOKBACK = 10  # 告警去重回溯数量

# ========== 监控常量 ==========
PERFORMANCE_TRACKING_MAX_RECORDS = 10000  # 性能跟踪最大记录数
SLOW_OPERATION_THRESHOLD_MS = 1000  # 慢操作阈值（毫秒）

# ========== 地址格式常量 ==========
P2PKH_VERSION_BYTE = 0x00  # P2PKH地址版本字节
WIF_VERSION_BYTE = 0x80  # WIF版本字节
ADDRESS_MIN_LENGTH = 26  # 地址最小长度
ADDRESS_MAX_LENGTH = 35  # 地址最大长度

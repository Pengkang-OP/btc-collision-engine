"""地址持久化存储

提供多种存储后端保存和加载目标地址:
- JSON文件存储(默认)
- SQLite数据库
- CSV导出

支持元数据保存和版本控制。
跨平台编码兼容。
"""

import csv
import json
import os
import re
import sqlite3
from collections.abc import Callable
from datetime import datetime
from typing import Any

# 导入日志配置
from ...utils import get_configured_logger, init_logging
from ...utils.encoding_utils import EncodingUtils

# 初始化日志系统
init_logging()
logger = get_configured_logger("AddressStorage")

# 比特币地址验证正则表达式
ADDRESS_PATTERNS = {
    "P2PKH": re.compile(r"^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$"),  # 1或3开头
    "P2SH": re.compile(r"^3[a-km-zA-HJ-NP-Z1-9]{25,34}$"),  # 3开头
    "BECH32": re.compile(r"^(bc1|tb1|bc1p)[a-zA-HJ-NP-Z0-9]{25,62}$"),  # bc1开头
}


def validate_bitcoin_address(address: str) -> bool:
    """验证比特币地址格式

    参数:
        address: 比特币地址字符串

    返回:
        bool: 地址格式是否有效
    """
    if not address or not isinstance(address, str):
        return False

    # 检查长度
    if len(address) < 26 or len(address) > 62:
        return False

    # 检查是否包含危险字符（防SQL注入）
    if any(c in address for c in [";", "--", "'", '"', "\\", "/", "*"]):
        return False

    # 匹配地址模式
    for pattern_name, pattern in ADDRESS_PATTERNS.items():
        if pattern.match(address):
            return True

    return False


class AddressStorage:
    """地址持久化存储管理器

    支持多种存储格式保存目标地址集合和元数据。

    示例:
        >>> storage = AddressStorage(storage_type='json', path='targets_data')
        >>> storage.save_targets({'1A1z...', '1B2x...'}, metadata={'name': 'test'})
        >>> targets, metadata = storage.load_targets()
    """

    def __init__(self, storage_type: str = "json", path: str = "targets_data") -> None:
        """
        初始化地址存储管理器

        参数:
            storage_type: 存储类型,可选 'json', 'sqlite', 'csv'
            path: 存储路径(文件路径或目录路径)
        """
        self.storage_type = storage_type
        self.path = path

        # 确保目录存在
        if storage_type in ("json", "csv") or storage_type == "sqlite":
            os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)

        logger.info(f"AddressStorage 初始化: 类型={storage_type}, 路径={path}")

    def save_targets(self, targets: set[str], metadata: dict | None = None) -> bool:
        """
        保存目标地址集合

        参数:
            targets: 目标地址集合
            metadata: 可选的元数据字典

        返回:
            True表示保存成功,False表示失败
        """
        try:
            if self.storage_type == "json":
                return self._save_json(targets, metadata)
            elif self.storage_type == "sqlite":
                return self._save_sqlite(targets, metadata)
            elif self.storage_type == "csv":
                return self._save_csv(targets, metadata)
            else:
                logger.error(f"不支持的存储类型: {self.storage_type}")
                return False
        except Exception as e:
            logger.error(f"保存目标地址失败: {e}")
            return False

    def load_targets(self) -> tuple[set[str], dict | None]:
        """
        加载目标地址集合和元数据

        返回:
            (目标地址集合, 元数据字典) 元组
        """
        try:
            if self.storage_type == "json":
                return self._load_json()
            elif self.storage_type == "sqlite":
                return self._load_sqlite()
            elif self.storage_type == "csv":
                return self._load_csv()
            else:
                logger.error(f"不支持的存储类型: {self.storage_type}")
                return set(), None
        except Exception as e:
            logger.error(f"加载目标地址失败: {e}")
            return set(), None

    def _save_json(self, targets: set[str], metadata: dict | None = None) -> bool:
        """保存为JSON格式"""
        data = {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "target_count": len(targets),
            "targets": sorted(list(targets)),
            "metadata": metadata or {},
        }

        # 使用统一的编码工具写入
        try:
            content = json.dumps(data, ensure_ascii=False, indent=2)
            EncodingUtils.write_file(self.path, content, encoding="utf-8")
            logger.info(f"JSON保存成功: {len(targets)} 个目标 -> {self.path}")
            return True
        except Exception as e:
            logger.error(f"JSON保存失败: {e}")
            return False

    def _load_json(self) -> tuple[set[str], dict | None]:
        """从JSON加载"""
        if not os.path.exists(self.path):
            logger.warning(f"文件不存在: {self.path}")
            return set(), None

        try:
            # 使用统一的编码工具读取
            content = EncodingUtils.read_file(self.path, encoding="utf-8", try_multiple=True)
            data = json.loads(content)

            targets = set(data.get("targets", []))
            metadata = data.get("metadata")

            logger.info(f"JSON加载成功: {len(targets)} 个目标 <- {self.path}")
            return targets, metadata
        except Exception as e:
            logger.error(f"JSON加载失败: {e}")
            return set(), None

    def _save_sqlite(self, targets: set[str], metadata: dict | None = None) -> bool:
        """保存到SQLite数据库（带输入验证）"""
        # 输入验证
        validated_targets = set()
        invalid_count = 0

        for addr in targets:
            if validate_bitcoin_address(addr):
                validated_targets.add(addr)
            else:
                invalid_count += 1
                logger.warning(f"跳过无效地址: {addr[:10]}...")

        if invalid_count > 0:
            logger.warning(f"已过滤 {invalid_count} 个无效地址")

        if not validated_targets:
            logger.error("没有有效地址可保存")
            return False

        conn = sqlite3.connect(self.path)
        cursor = conn.cursor()

        try:
            # 创建表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS targets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    address TEXT UNIQUE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)

            # 插入目标地址（使用参数化查询 + 验证后的数据）
            inserted = 0
            for addr in validated_targets:
                try:
                    # 参数化查询防止SQL注入
                    cursor.execute("INSERT OR IGNORE INTO targets (address) VALUES (?)", (addr,))
                    inserted += cursor.rowcount
                except sqlite3.IntegrityError as e:  # noqa: F841
                    logger.debug(f"地址已存在，跳过: {addr[:10]}...")
                except (sqlite3.Error, ValueError) as e:
                    logger.warning(f"插入地址失败 {addr[:10]}...: {e}")

            # 保存元数据（验证键名）
            if metadata:
                for key, value in metadata.items():
                    # 验证元数据键名
                    if not isinstance(key, str) or len(key) > 100:
                        logger.warning(f"跳过无效元数据键: {key}")
                        continue

                    # 防止SQL注入：验证键名只包含安全字符
                    if not re.match(r"^[a-zA-Z0-9_-]+$", key):
                        logger.warning(f"元数据键包含不安全字符: {key}")
                        continue

                    cursor.execute(
                        "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
                        (key, json.dumps(value)),
                    )

            conn.commit()
            logger.info(f"SQLite保存成功: {inserted} 个新目标 -> {self.path}")
            return True

        except Exception as e:
            conn.rollback()
            logger.error(f"SQLite保存失败: {e}")
            return False
        finally:
            conn.close()

    def _load_sqlite(self) -> tuple[set[str], dict | None]:
        """从SQLite加载"""
        if not os.path.exists(self.path):
            logger.warning(f"数据库不存在: {self.path}")
            return set(), None

        conn = sqlite3.connect(self.path)
        cursor = conn.cursor()

        try:
            # 加载目标地址
            cursor.execute("SELECT address FROM targets")
            targets = set(row[0] for row in cursor.fetchall())

            # 加载元数据
            cursor.execute("SELECT key, value FROM metadata")
            metadata = {}
            for key, value in cursor.fetchall():
                try:
                    metadata[key] = json.loads(value)
                except (json.JSONDecodeError, ValueError, TypeError) as e:
                    # JSON解析失败，保留原始字符串值
                    logger.debug(f"元数据JSON解析失败 [{key}]: {type(e).__name__}，使用原始值")
                    metadata[key] = value

            logger.info(f"SQLite加载成功: {len(targets)} 个目标 <- {self.path}")
            return targets, metadata if metadata else None

        except Exception as e:
            logger.error(f"SQLite加载失败: {e}")
            return set(), None
        finally:
            conn.close()

    def _save_csv(self, targets: set[str], metadata: dict | None = None) -> bool:
        """保存为CSV格式"""
        try:
            # 使用统一的编码工具
            import io

            output = io.StringIO()
            writer = csv.writer(output)

            # 写入头部
            writer.writerow(["address", "index"])

            # 写入数据
            for idx, addr in enumerate(sorted(targets), 1):
                writer.writerow([addr, idx])

            # 写入文件
            EncodingUtils.write_file(self.path, output.getvalue(), encoding="utf-8")

            # 元数据保存为单独的JSON文件
            if metadata:
                metadata_path = self.path.replace(".csv", "_metadata.json")
                metadata_content = json.dumps(metadata, ensure_ascii=False, indent=2)
                EncodingUtils.write_file(metadata_path, metadata_content, encoding="utf-8")

            logger.info(f"CSV保存成功: {len(targets)} 个目标 -> {self.path}")
            return True
        except Exception as e:
            logger.error(f"CSV保存失败: {e}")
            return False

    def _load_csv(self) -> tuple[set[str], dict | None]:
        """从CSV加载"""
        if not os.path.exists(self.path):
            logger.warning(f"文件不存在: {self.path}")
            return set(), None

        try:
            # 使用统一的编码工具读取
            content = EncodingUtils.read_file(self.path, encoding="utf-8", try_multiple=True)
            import io

            reader = csv.reader(io.StringIO(content))
            next(reader)  # 跳过头部

            targets = set()
            for row in reader:
                if row:
                    targets.add(row[0])

            # 加载元数据
            metadata = None
            metadata_path = self.path.replace(".csv", "_metadata.json")
            if os.path.exists(metadata_path):
                metadata_content = EncodingUtils.read_file(
                    metadata_path, encoding="utf-8", try_multiple=True
                )
                metadata = json.loads(metadata_content)

            logger.info(f"CSV加载成功: {len(targets)} 个目标 <- {self.path}")
            return targets, metadata
        except Exception as e:
            logger.error(f"CSV加载失败: {e}")
            return set(), None

    def export_csv(self, targets: set[str], output_path: str) -> bool:
        """
        导出为CSV文件(临时导出,不改变存储类型)

        参数:
            targets: 目标地址集合
            output_path: 输出文件路径

        返回:
            True表示导出成功
        """
        try:
            import io

            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["address"])

            for addr in sorted(targets):
                writer.writerow([addr])

            # 使用统一的编码工具写入
            EncodingUtils.write_file(output_path, output.getvalue(), encoding="utf-8")

            logger.info(f"CSV导出成功: {len(targets)} 个目标 -> {output_path}")
            return True

        except Exception as e:
            logger.error(f"CSV导出失败: {e}")
            return False

    def get_storage_info(self) -> dict[str, Any]:
        """
        获取存储信息

        返回:
            包含存储信息的字典
        """
        info = {
            "storage_type": self.storage_type,
            "path": self.path,
            "exists": os.path.exists(self.path),
        }

        if info["exists"]:
            info["size_bytes"] = os.path.getsize(self.path)

        return info

    def import_addresses(
        self,
        source_path: str,
        storage_dir: str | None = None,
        validate: bool = True,
        storage_type: str = "json",
        progress_callback: Callable | None = None,
    ) -> dict[str, Any]:
        """
        从外部源导入地址并自动保存到持久化存储

        参数:
            source_path: 源文件路径(支持txt, csv, json格式)
            storage_dir: 存储目录(如果不指定则使用当前目录下的targets_data)
            validate: 是否验证地址格式,默认True
            storage_type: 存储类型,默认'json'
            progress_callback: 进度回调函数,接收(processed, total, address)参数

        返回:
            导入结果字典,包含:
            - success: 是否成功
            - imported_count: 成功导入的地址数
            - invalid_count: 无效地址数
            - total_count: 总处理地址数
            - invalid_addresses: 无效地址列表
            - storage_path: 存储路径
            - error: 错误信息(如果有)
        """
        result = {
            "success": False,
            "imported_count": 0,
            "invalid_count": 0,
            "total_count": 0,
            "invalid_addresses": [],
            "storage_path": "",
            "error": None,
        }

        try:
            # 设置存储目录
            if storage_dir is None:
                storage_dir = os.path.join(os.getcwd(), "targets_data")

            # 规范化并验证存储目录路径
            storage_dir = os.path.abspath(storage_dir)
            allowed_dirs = [
                os.path.abspath(os.getcwd()),
                os.path.abspath(os.environ.get("TEMP", "/tmp")),  # nosec B108: 仅用于路径验证，非实际temp文件
                os.path.abspath(os.environ.get("TMP", "/tmp")),  # nosec B108: 仅用于路径验证，非实际temp文件
            ]
            if not any(storage_dir.startswith(allowed_dir) for allowed_dir in allowed_dirs):
                result["error"] = "存储目录必须在允许的路径范围内"
                logger.error(f"安全警告: 存储目录超出允许范围: {storage_dir}")
                return result

            os.makedirs(storage_dir, exist_ok=True)

            # 生成存储文件路径(使用时间戳+唯一ID避免冲突)
            import uuid

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            unique_id = str(uuid.uuid4())[:8]
            if storage_type == "json":
                storage_path = os.path.join(
                    storage_dir, f"imported_addresses_{timestamp}_{unique_id}.json"
                )
            elif storage_type == "sqlite":
                storage_path = os.path.join(
                    storage_dir, f"imported_addresses_{timestamp}_{unique_id}.db"
                )
            elif storage_type == "csv":
                storage_path = os.path.join(
                    storage_dir, f"imported_addresses_{timestamp}_{unique_id}.csv"
                )
            else:
                result["error"] = f"不支持的存储类型: {storage_type}"
                return result

            # 初始化存储
            storage = AddressStorage(storage_type=storage_type, path=storage_path)

            # 获取源文件真实路径
            real_source_path = os.path.realpath(source_path)

            # 读取源文件
            logger.info(f"开始导入地址: 源文件={real_source_path}, 存储类型={storage_type}")

            if not os.path.exists(real_source_path):
                result["error"] = f"源文件不存在: {source_path}"
                return result

            # 检查文件大小
            file_size = os.path.getsize(real_source_path)
            if file_size > 100 * 1024 * 1024:  # 100MB
                result["error"] = "文件过大(>100MB)"
                logger.error(f"文件过大: {real_source_path}, 大小={file_size / 1024 / 1024:.1f}MB")
                return result

            # 根据文件扩展名选择读取方式
            file_ext = os.path.splitext(real_source_path)[1].lower()
            source_addresses = []

            if file_ext == ".json":
                source_addresses = self._read_json_source(real_source_path)
            elif file_ext == ".csv":
                source_addresses = self._read_csv_source(real_source_path)
            else:  # 默认按文本文件处理
                source_addresses = self._read_text_source(real_source_path)

            # 限制导入数量
            max_addresses = 1_000_000  # 最多100万个地址
            if len(source_addresses) > max_addresses:
                logger.warning(f"地址数量超过限制({max_addresses}), 仅处理前{max_addresses}个")
                source_addresses = source_addresses[:max_addresses]

            result["total_count"] = len(source_addresses)
            logger.info(f"从源文件读取到 {len(source_addresses)} 个地址")

            # 地址验证
            valid_addresses = set()
            invalid_addresses = []

            if validate:
                from .validator import AddressBatchValidator

                validator = AddressBatchValidator(max_workers=4)

                # 分批验证
                batch_size = 100
                for i in range(0, len(source_addresses), batch_size):
                    batch = source_addresses[i : i + batch_size]
                    validation_results = validator.validate_batch(batch)

                    for addr, validation_result in validation_results.items():
                        if validation_result.valid:
                            valid_addresses.add(addr)
                        else:
                            invalid_addresses.append(
                                {"address": addr, "error": validation_result.error}
                            )

                        # 调用进度回调
                        if progress_callback:
                            progress_callback(
                                len(valid_addresses) + len(invalid_addresses),
                                len(source_addresses),
                                addr,
                            )
            else:
                # 不验证,直接导入
                valid_addresses = set(source_addresses)
                if progress_callback:
                    for i, addr in enumerate(source_addresses):
                        progress_callback(i + 1, len(source_addresses), addr)

            result["imported_count"] = len(valid_addresses)
            result["invalid_count"] = len(invalid_addresses)
            result["invalid_addresses"] = invalid_addresses

            # 保存有效地址
            if valid_addresses:
                metadata = {
                    "import_time": datetime.now().isoformat(),
                    "source_file": source_path,
                    "imported_count": len(valid_addresses),
                    "invalid_count": len(invalid_addresses),
                    "total_processed": len(source_addresses),
                    "validation_enabled": validate,
                    "storage_type": storage_type,
                }

                success = storage.save_targets(valid_addresses, metadata)
                if success:
                    result["success"] = True
                    result["storage_path"] = storage_path
                    logger.info(
                        f"地址导入成功: {len(valid_addresses)} 个有效地址已保存到 {storage_path}"
                    )
                else:
                    result["error"] = "保存地址到存储失败"
                    logger.error("地址导入失败: 保存操作失败")
            else:
                result["error"] = "没有有效的地址可导入"
                logger.warning("地址导入完成: 没有有效地址")

            return result

        except Exception as e:
            result["error"] = f"导入过程中发生错误: {str(e)}"
            logger.error(f"地址导入失败: {e}", exc_info=True)
            return result

    def _read_json_source(self, file_path: str) -> list[str]:
        """从JSON文件读取地址"""
        try:
            content = EncodingUtils.read_file(file_path, encoding="utf-8", try_multiple=True)
            data = json.loads(content)

            addresses = []
            # 支持多种JSON格式
            if isinstance(data, list):
                addresses = [str(addr).strip() for addr in data if str(addr).strip()]
            elif isinstance(data, dict):
                if "addresses" in data:
                    addresses = [
                        str(addr).strip() for addr in data["addresses"] if str(addr).strip()
                    ]
                elif "targets" in data:
                    addresses = [str(addr).strip() for addr in data["targets"] if str(addr).strip()]
                else:
                    # 尝试从字典值中提取地址
                    for value in data.values():
                        if isinstance(value, str) and value.strip():
                            addresses.append(value.strip())

            return addresses
        except Exception as e:
            logger.error(f"读取JSON源文件失败: {e}")
            return []

    def _read_csv_source(self, file_path: str) -> list[str]:
        """从CSV文件读取地址"""
        try:
            content = EncodingUtils.read_file(file_path, encoding="utf-8", try_multiple=True)
            import io

            reader = csv.reader(io.StringIO(content))

            addresses = []
            header_skipped = False
            for row in reader:
                if not row:  # 跳过空行
                    continue

                if not header_skipped:
                    # 更健壮的头部检测
                    first_cell = row[0].strip().lower()
                    is_header = (
                        first_cell in ("address", "addresses", "addr", "target", "targets")
                        or first_cell.startswith("#")
                        or not (
                            first_cell.startswith("1")
                            or first_cell.startswith("3")
                            or first_cell.startswith("bc1")
                        )
                    )
                    if is_header:
                        header_skipped = True
                        continue
                    header_skipped = True

                if row[0].strip():
                    addresses.append(row[0].strip())

            return addresses
        except Exception as e:
            logger.error(f"读取CSV源文件失败: {e}")
            return []

    def _read_text_source(self, file_path: str) -> list[str]:
        """从文本文件读取地址(每行一个地址)"""
        try:
            lines = EncodingUtils.read_file_lines(file_path, try_multiple=True)
            addresses = []

            for line in lines:
                line = line.strip()
                # 跳过空行和注释
                if line and not line.startswith("#"):
                    addresses.append(line)

            return addresses
        except Exception as e:
            logger.error(f"读取文本源文件失败: {e}")
            return []

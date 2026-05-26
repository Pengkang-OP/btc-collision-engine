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
import pathlib
import re
import sqlite3
import tempfile
import types
from collections.abc import Callable
from datetime import datetime
from typing import Any

# 导入日志配置
from ...utils import get_configured_logger
from ...utils.encoding_utils import EncodingUtils

# 日志系统由CLI/main.py入口统一初始化
logger = get_configured_logger("AddressStorage")

# 比特币地址验证正则表达式（不可变）
ADDRESS_PATTERNS = types.MappingProxyType(
    {
        "P2PKH": re.compile(r"^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$"),  # 1或3开头
        "P2SH": re.compile(r"^3[a-km-zA-HJ-NP-Z1-9]{25,34}$"),  # 3开头
        "BECH32": re.compile(r"^(bc1|tb1|bc1p)[a-zA-HJ-NP-Z0-9]{25,62}$"),  # bc1开头
    }
)


def validate_bitcoin_address(address: str) -> bool:
    """验证比特币地址格式

    Args:
        address: 比特币地址字符串

    Returns:
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
    return any(pattern.match(address) for _pattern_name, pattern in ADDRESS_PATTERNS.items())


class AddressStorage:
    """地址持久化存储管理器

    支持多种存储格式保存目标地址集合和元数据。

    Example:
        >>> storage = AddressStorage(storage_type='json', path='targets_data')
        >>> storage.save_targets({'1A1z...', '1B2x...'}, metadata={'name': 'test'})
        >>> targets, metadata = storage.load_targets()
    """

    def __init__(self, storage_type: str = "json", path: str = "targets_data") -> None:
        """初始化地址存储管理器

        Args:
            storage_type: 存储类型,可选 'json', 'sqlite', 'csv'
            path: 存储路径(文件路径或目录路径)
        """
        self.storage_type = storage_type
        self.path = path

        # 确保目录存在
        if storage_type in ("json", "csv") or storage_type == "sqlite":
            pathlib.Path(os.path.dirname(path) if os.path.dirname(path) else ".").mkdir(
                exist_ok=True, parents=True
            )

        logger.info("AddressStorage 初始化: 类型=%s, 路径=%s", storage_type, path)

    def save_targets(self, targets: set[str], metadata: dict | None = None) -> bool:
        """保存目标地址集合到持久化存储

        根据 storage_type 选择对应的存储后端执行保存操作。

        Args:
            targets: 目标地址集合
            metadata: 可选的元数据字典（存储内容因后端而异）

        Returns:
            True 表示保存成功，False 表示失败

        """
        try:
            if self.storage_type == "json":
                return self._save_json(targets, metadata)
            if self.storage_type == "sqlite":
                return self._save_sqlite(targets, metadata)
            if self.storage_type == "csv":
                return self._save_csv(targets, metadata)
            logger.error(f"不支持的存储类型: {self.storage_type}")
            return False
        except Exception as e:
            logger.error("保存目标地址失败: %s", e)
            return False

    def load_targets(self) -> tuple[set[str], dict | None]:
        """从持久化存储加载目标地址集合和元数据

        根据 storage_type 选择对应的存储后端执行加载操作。

        Returns:
            (目标地址集合, 元数据字典) 元组，加载失败返回 (set(), None)

        """
        try:
            if self.storage_type == "json":
                return self._load_json()
            if self.storage_type == "sqlite":
                return self._load_sqlite()
            if self.storage_type == "csv":
                return self._load_csv()
            logger.error(f"不支持的存储类型: {self.storage_type}")
            return set(), None
        except Exception as e:
            logger.error("加载目标地址失败: %s", e)
            return set(), None

    def _save_json(self, targets: set[str], metadata: dict | None = None) -> bool:
        """保存为JSON格式"""
        data = {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "target_count": len(targets),
            "targets": sorted(targets),
            "metadata": metadata or {},
        }

        # 使用统一的编码工具写入
        try:
            content = json.dumps(data, ensure_ascii=False, indent=2)
            EncodingUtils.write_file(self.path, content, encoding="utf-8")
            logger.info(f"JSON保存成功: {len(targets)} 个目标 -> {self.path}")
            return True
        except Exception as e:
            logger.error("JSON保存失败: %s", e)
            return False

    def _load_json(self) -> tuple[set[str], dict | None]:
        """从JSON加载"""
        if not pathlib.Path(self.path).exists():
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
            logger.error("JSON加载失败: %s", e)
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
            logger.warning("已过滤 %s 个无效地址", invalid_count)

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
                except sqlite3.IntegrityError:
                    logger.debug(f"地址已存在，跳过: {addr[:10]}...")
                except (sqlite3.Error, ValueError) as e:
                    logger.warning(f"插入地址失败 {addr[:10]}...: {e}")

            # 保存元数据（验证键名）
            if metadata:
                for key, value in metadata.items():
                    # 验证元数据键名
                    if not isinstance(key, str) or len(key) > 100:
                        logger.warning("跳过无效元数据键: %s", key)
                        continue

                    # 防止SQL注入：验证键名只包含安全字符
                    if not re.match(r"^[a-zA-Z0-9_-]+$", key):
                        logger.warning("元数据键包含不安全字符: %s", key)
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
            logger.error("SQLite保存失败: %s", e)
            return False
        finally:
            conn.close()

    def _load_sqlite(self) -> tuple[set[str], dict | None]:
        """从SQLite加载"""
        if not pathlib.Path(self.path).exists():
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
            return targets, metadata or None

        except Exception as e:
            logger.error("SQLite加载失败: %s", e)
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
            logger.error("CSV保存失败: %s", e)
            return False

    def _load_csv(self) -> tuple[set[str], dict | None]:
        """从CSV加载"""
        if not pathlib.Path(self.path).exists():
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
            if pathlib.Path(metadata_path).exists():
                metadata_content = EncodingUtils.read_file(
                    metadata_path,
                    encoding="utf-8",
                    try_multiple=True,
                )
                metadata = json.loads(metadata_content)

            logger.info(f"CSV加载成功: {len(targets)} 个目标 <- {self.path}")
            return targets, metadata
        except Exception as e:
            logger.error("CSV加载失败: %s", e)
            return set(), None

    def export_csv(self, targets: set[str], output_path: str) -> bool:
        """导出目标地址为CSV文件（临时导出，不改变存储类型）

        Args:
            targets: 目标地址集合
            output_path: 输出文件路径

        Returns:
            True 表示导出成功

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
            logger.error("CSV导出失败: %s", e)
            return False

    def get_storage_info(self) -> dict[str, Any]:
        """获取存储信息

        Returns:
            包含存储信息的字典
        """
        info = {
            "storage_type": self.storage_type,
            "path": self.path,
            "exists": pathlib.Path(self.path).exists(),
        }

        if info["exists"]:
            info["size_bytes"] = pathlib.Path(self.path).stat().st_size

        return info

    # ── import_addresses 辅助方法（降低 C901） ────────────────────

    @staticmethod
    def _ensure_storage_dir(storage_dir: str | None) -> str:
        """验证并创建存储目录，返回规范化后的绝对路径。

        Raises:
            ValueError: 目录不在允许范围内。

        """
        if storage_dir is None:
            storage_dir = os.path.join(os.getcwd(), "targets_data")
        storage_dir = os.path.abspath(storage_dir)
        allowed_dirs = [
            os.path.abspath(os.getcwd()),
            os.path.abspath(os.environ.get("TEMP", tempfile.gettempdir())),
            os.path.abspath(os.environ.get("TMP", tempfile.gettempdir())),
        ]
        # 使用 normcase 处理 Windows 大小写不敏感的文件系统
        storage_dir_norm = os.path.normcase(storage_dir)
        if not any(
            storage_dir_norm.startswith(os.path.normcase(d) + os.sep)
            or storage_dir_norm == os.path.normcase(d)
            for d in allowed_dirs
        ):
            raise ValueError(f"存储目录必须在允许的路径范围内: {storage_dir}")
        pathlib.Path(storage_dir).mkdir(exist_ok=True, parents=True)
        return storage_dir

    @staticmethod
    def _generate_storage_path(storage_dir: str, storage_type: str) -> str:
        """生成带时间戳+唯一ID的存储文件路径。

        Raises:
            ValueError: 不支持的存储类型。

        """
        import uuid

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        unique_id = str(uuid.uuid4())[:8]
        ext_map = {"json": ".json", "sqlite": ".db", "csv": ".csv"}
        if storage_type not in ext_map:
            raise ValueError(f"不支持的存储类型: {storage_type}")
        return os.path.join(
            storage_dir,
            f"imported_addresses_{timestamp}_{unique_id}{ext_map[storage_type]}",
        )

    def _read_source_addresses(self, real_source_path: str) -> list[str]:
        """根据文件扩展名读取源文件中的地址，并限制最大数量。"""
        file_ext = os.path.splitext(real_source_path)[1].lower()
        if file_ext == ".json":
            source_addresses = self._read_json_source(real_source_path)
        elif file_ext == ".csv":
            source_addresses = self._read_csv_source(real_source_path)
        else:
            source_addresses = self._read_text_source(real_source_path)

        max_addresses = 1_000_000
        if len(source_addresses) > max_addresses:
            logger.warning("地址数量超过限制(%s), 仅处理前%s个", max_addresses, max_addresses)
            source_addresses = source_addresses[:max_addresses]
        return source_addresses

    @staticmethod
    def _batch_validate_addresses(
        source_addresses: list[str],
        progress_callback: Callable | None,
    ) -> tuple[set, list]:
        """分批验证源地址，返回 (valid_addresses, invalid_addresses)。"""
        from .validator import AddressBatchValidator

        valid_addresses: set = set()
        invalid_addresses: list = []
        validator = AddressBatchValidator(max_workers=4)
        batch_size = 100
        for i in range(0, len(source_addresses), batch_size):
            batch = source_addresses[i : i + batch_size]
            for addr, vr in validator.validate_batch(batch).items():
                if vr.valid:
                    valid_addresses.add(addr)
                else:
                    invalid_addresses.append({"address": addr, "error": vr.error})
                if progress_callback:
                    progress_callback(
                        len(valid_addresses) + len(invalid_addresses),
                        len(source_addresses),
                        addr,
                    )
        return valid_addresses, invalid_addresses

    def import_addresses(
        self,
        source_path: str,
        storage_dir: str | None = None,
        validate: bool = True,
        storage_type: str = "json",
        progress_callback: Callable | None = None,
    ) -> dict[str, Any]:
        """从外部源导入地址并自动保存到持久化存储。"""
        result: dict[str, Any] = {
            "success": False,
            "imported_count": 0,
            "invalid_count": 0,
            "total_count": 0,
            "invalid_addresses": [],
            "storage_path": "",
            "error": None,
        }

        try:
            storage_dir = self._ensure_storage_dir(storage_dir)
            storage_path = self._generate_storage_path(storage_dir, storage_type)

            real_source_path = os.path.realpath(source_path)
            logger.info("开始导入地址: 源文件=%s, 存储类型=%s", real_source_path, storage_type)

            if not pathlib.Path(real_source_path).exists():
                result["error"] = f"源文件不存在: {source_path}"
                return result

            file_size = pathlib.Path(real_source_path).stat().st_size
            if file_size > 100 * 1024 * 1024:
                result["error"] = "文件过大(>100MB)"
                logger.error(f"文件过大: {real_source_path}, 大小={file_size / 1024 / 1024:.1f}MB")
                return result

            source_addresses = self._read_source_addresses(real_source_path)
            result["total_count"] = len(source_addresses)
            logger.info(f"从源文件读取到 {len(source_addresses)} 个地址")

            if validate:
                valid_addresses, invalid_addresses = self._batch_validate_addresses(
                    source_addresses,
                    progress_callback,
                )
            else:
                valid_addresses = set(source_addresses)
                invalid_addresses = []
                if progress_callback:
                    for i, addr in enumerate(source_addresses):
                        progress_callback(i + 1, len(source_addresses), addr)

            result["imported_count"] = len(valid_addresses)
            result["invalid_count"] = len(invalid_addresses)
            result["invalid_addresses"] = invalid_addresses

            if valid_addresses:
                storage = AddressStorage(storage_type=storage_type, path=storage_path)
                metadata = {
                    "import_time": datetime.now().isoformat(),
                    "source_file": source_path,
                    "imported_count": len(valid_addresses),
                    "invalid_count": len(invalid_addresses),
                    "total_processed": len(source_addresses),
                    "validation_enabled": validate,
                    "storage_type": storage_type,
                }
                if storage.save_targets(valid_addresses, metadata):
                    result["success"] = True
                    result["storage_path"] = storage_path
                    logger.info(
                        f"地址导入成功: {len(valid_addresses)} 个有效地址已保存到 {storage_path}",
                    )
                else:
                    result["error"] = "保存地址到存储失败"
                    logger.error("地址导入失败: 保存操作失败")
            else:
                result["error"] = "没有有效的地址可导入"
                logger.warning("地址导入完成: 没有有效地址")

            return result
        except ValueError as e:
            result["error"] = str(e)
            logger.error("地址导入失败: %s", e)
            return result
        except Exception as e:
            result["error"] = f"导入过程中发生错误: {e!s}"
            logger.error("地址导入失败: %s", e, exc_info=True)
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
                    addresses = [str(addr).strip() for addr in data["addresses"] if str(addr).strip()]
                elif "targets" in data:
                    addresses = [str(addr).strip() for addr in data["targets"] if str(addr).strip()]
                else:
                    # 尝试从字典值中提取地址
                    for value in data.values():
                        if isinstance(value, str) and value.strip():
                            addresses.append(value.strip())

            return addresses
        except Exception as e:
            logger.error("读取JSON源文件失败: %s", e)
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
                    first_cell_lower = row[0].strip().lower()
                    is_header = (
                        first_cell_lower in ("address", "addresses", "addr", "target", "targets")
                        or first_cell_lower.startswith("#")
                        or not (
                            first_cell_lower.startswith("1")
                            or first_cell_lower.startswith("3")
                            or first_cell_lower.startswith("bc1")
                            or first_cell_lower.startswith("tb1")
                            or first_cell_lower.startswith("tb1p")
                            or first_cell_lower.startswith("m")
                            or first_cell_lower.startswith("n")
                            or first_cell_lower.startswith("2")
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
            logger.error("读取CSV源文件失败: %s", e)
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
            logger.error("读取文本源文件失败: %s", e)
            return []

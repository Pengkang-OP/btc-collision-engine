# -*- coding: utf-8 -*-
"""文件编码检测和处理工具

提供跨平台的文件编码自动检测和适配功能：
- 支持UTF-8、GBK、Latin-1等多种编码
- 自动编码检测和降级策略
- 统一的文件读写接口
- 跨平台兼容性（Windows、Linux、macOS）
"""

import os
from typing import Any, List, Optional
import chardet

# 直接从具体模块导入，避免循环导入
from .logging_config import init_logging, get_configured_logger
from .platform_utils import PlatformUtils

# 初始化日志系统
init_logging()
logger = get_configured_logger("EncodingUtils")


class EncodingUtils:
    """文件编码检测和处理的工具类

    提供智能的编码检测和文件操作功能，确保跨平台兼容性。

    示例:
        >>> from src.utils.encoding_utils import EncodingUtils
        >>> content = EncodingUtils.read_file('data.txt')
        >>> EncodingUtils.write_file('output.txt', content)
    """

    # 支持的编码列表（按优先级排序）
    SUPPORTED_ENCODINGS = ["utf-8", "gbk", "gb2312", "gb18030", "latin-1", "ascii"]

    # 默认编码
    DEFAULT_ENCODING = "utf-8"

    # 采样策略阈值
    SMALL_FILE_THRESHOLD = 10 * 1024  # 10KB
    MEDIUM_FILE_THRESHOLD = 1024 * 1024  # 1MB
    MAX_SAMPLE_SIZE = 100 * 1024  # 100KB
    MIN_SAMPLE_SIZE = 1024  # 1KB

    @staticmethod
    def detect_file_encoding(
        filepath: str, max_sample_size: Optional[int] = None, use_dynamic_sampling: bool = True
    ) -> str:
        """
        检测文件编码

        使用chardet库进行编码检测，如果检测失败则返回默认编码。
        采用动态采样策略，根据文件大小自动调整采样大小。

        参数:
            filepath: 文件路径
            max_sample_size: 最大采样大小（字节），默认None（使用MAX_SAMPLE_SIZE=100KB）
            use_dynamic_sampling: 是否使用动态采样策略，默认True

        返回:
            检测到的编码名称
        """
        try:
            if not os.path.exists(filepath):
                logger.warning(f"文件不存在: {filepath}")
                return EncodingUtils.DEFAULT_ENCODING

            # 处理max_sample_size默认值
            if max_sample_size is None:
                actual_max_size = EncodingUtils.MAX_SAMPLE_SIZE
            else:
                actual_max_size = max_sample_size

            # 获取文件大小
            file_size = os.path.getsize(filepath)

            if use_dynamic_sampling:
                # 动态采样策略：
                # - 小文件(<10KB): 读取全部
                # - 中文件(10KB-1MB): 读取50%
                # - 大文件(>1MB): 读取10%，最多actual_max_size
                if file_size < EncodingUtils.SMALL_FILE_THRESHOLD:
                    actual_size = file_size
                    strategy = "全量读取"
                elif file_size < EncodingUtils.MEDIUM_FILE_THRESHOLD:
                    # 中文件：读取50%，但至少1KB，最多actual_max_size
                    actual_size = min(
                        max(int(file_size * 0.5), EncodingUtils.MIN_SAMPLE_SIZE), actual_max_size
                    )
                    strategy = "50%采样"
                else:
                    # 大文件：读取10%，最少1KB，最多actual_max_size
                    actual_size = min(
                        max(int(file_size * 0.1), EncodingUtils.MIN_SAMPLE_SIZE), actual_max_size
                    )
                    strategy = "10%采样"

                logger.debug(
                    f"编码检测采样: 文件={file_size}B, 策略={strategy}, "
                    f"采样={actual_size}B, 上限={actual_max_size}B"
                )
            else:
                # 固定采样大小
                actual_size = min(file_size, actual_max_size)
                logger.debug(f"编码检测采样: 文件={file_size}B, 固定采样={actual_size}B")

            # 读取文件样本
            with open(filepath, "rb") as f:
                sample = f.read(actual_size)

            # 空文件处理
            if not sample:
                logger.debug(f"空文件: {filepath}, 使用默认编码")
                return EncodingUtils.DEFAULT_ENCODING

            # 使用chardet检测编码
            result = chardet.detect(sample)
            encoding = result.get("encoding", EncodingUtils.DEFAULT_ENCODING)
            confidence = result.get("confidence", 0)

            if encoding and confidence > 0.7:
                logger.debug(f"编码检测成功: {filepath}, 编码={encoding}, 置信度={confidence:.2f}")
                return encoding.lower()
            else:
                logger.debug(f"编码检测置信度低: {filepath}, 置信度={confidence:.2f}, 使用默认编码")
                return EncodingUtils.DEFAULT_ENCODING

        except Exception as e:
            logger.warning(f"编码检测失败: {filepath}, 错误={e}, 使用默认编码")
            return EncodingUtils.DEFAULT_ENCODING

    @staticmethod
    def detect_encoding_from_bytes(data: bytes) -> str:
        """
        从字节数据检测编码

        参数:
            data: 字节数据

        返回:
            检测到的编码名称
        """
        try:
            result = chardet.detect(data)
            encoding = result.get("encoding", EncodingUtils.DEFAULT_ENCODING)
            confidence = result.get("confidence", 0)

            if encoding and confidence > 0.7:
                return encoding.lower()
            else:
                return EncodingUtils.DEFAULT_ENCODING

        except Exception as e:
            logger.warning(f"字节数据编码检测失败: 错误={e}")
            return EncodingUtils.DEFAULT_ENCODING

    @staticmethod
    def read_file(filepath: str, encoding: Optional[str] = None, try_multiple: bool = True) -> str:
        """
        读取文件内容，自动处理编码问题

        参数:
            filepath: 文件路径
            encoding: 指定编码，如果为None则自动检测
            try_multiple: 是否尝试多种编码（当指定编码失败时）

        返回:
            文件内容字符串

        异常:
            FileNotFoundError: 文件不存在
            UnicodeDecodeError: 所有编码尝试都失败
        """
        import time

        start_time = time.perf_counter()

        if not os.path.exists(filepath):
            raise FileNotFoundError(f"文件不存在: {filepath}")

        # 如果未指定编码，尝试自动检测
        if encoding is None:
            encoding = EncodingUtils.detect_file_encoding(filepath)

        # 尝试读取文件
        encodings_to_try = [encoding]
        if try_multiple:
            # 添加备用编码
            for enc in EncodingUtils.SUPPORTED_ENCODINGS:
                if enc != encoding and enc not in encodings_to_try:
                    encodings_to_try.append(enc)

        for enc in encodings_to_try:
            try:
                with open(filepath, "r", encoding=enc) as f:
                    content = f.read()
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                logger.debug(f"文件读取成功: {filepath}, 编码={enc}, 耗时={elapsed_ms:.2f}ms")
                return content
            except UnicodeDecodeError as e:
                logger.debug(f"编码 {enc} 尝试失败: {e}")
                continue
            except Exception as e:
                logger.error(f"文件读取失败: {filepath}, 错误={e}")
                raise

        # 所有编码都失败
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        error_msg = (
            f"无法读取文件 {filepath}，尝试了编码: {encodings_to_try}, 耗时={elapsed_ms:.2f}ms"
        )
        logger.error(error_msg)
        raise UnicodeDecodeError("unknown", b"", 0, 1, error_msg)

    @staticmethod
    def read_file_lines(
        filepath: str, encoding: Optional[str] = None, try_multiple: bool = True
    ) -> List[str]:
        """
        读取文件行列表

        参数:
            filepath: 文件路径
            encoding: 指定编码
            try_multiple: 是否尝试多种编码

        返回:
            行列表
        """
        content = EncodingUtils.read_file(filepath, encoding, try_multiple)
        return content.splitlines()

    @staticmethod
    def write_file(
        filepath: str, content: str, encoding: str = "utf-8", ensure_dir: bool = True
    ) -> None:
        """
        写入文件内容

        参数:
            filepath: 文件路径
            content: 内容字符串
            encoding: 编码，默认UTF-8
            ensure_dir: 是否确保目录存在
        """
        if ensure_dir:
            dir_path = os.path.dirname(filepath)
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)

        with open(filepath, "w", encoding=encoding) as f:
            f.write(content)

        logger.debug(f"文件写入成功: {filepath}, 编码={encoding}")

    @staticmethod
    def write_file_lines(
        filepath: str,
        lines: List[str],
        encoding: str = "utf-8",
        ensure_dir: bool = True,
        newline: str = "\n",
    ) -> None:
        """
        写入行列表到文件

        参数:
            filepath: 文件路径
            lines: 行列表
            encoding: 编码
            ensure_dir: 是否确保目录存在
            newline: 换行符
        """
        content = newline.join(lines)
        EncodingUtils.write_file(filepath, content, encoding, ensure_dir)

    @staticmethod
    def convert_file_encoding(
        src_path: str,
        dst_path: str,
        src_encoding: Optional[str] = None,
        dst_encoding: str = "utf-8",
    ) -> bool:
        """
        转换文件编码

        参数:
            src_path: 源文件路径
            dst_path: 目标文件路径
            src_encoding: 源编码，None则自动检测
            dst_encoding: 目标编码

        返回:
            True表示成功，False表示失败
        """
        try:
            content = EncodingUtils.read_file(src_path, src_encoding)
            EncodingUtils.write_file(dst_path, content, dst_encoding)
            logger.info(
                f"文件编码转换成功: {src_path} ({src_encoding}) -> {dst_path} ({dst_encoding})"
            )
            return True
        except Exception as e:
            logger.error(f"文件编码转换失败: {src_path} -> {dst_path}, 错误={e}")
            return False

    @staticmethod
    def safe_open(
        filepath: str, mode: str = "r", encoding: Optional[str] = None, try_multiple: bool = True
    ) -> Any:
        """
        安全地打开文件（上下文管理器）

        参数:
            filepath: 文件路径
            mode: 打开模式 ('r', 'w', 'a'等)
            encoding: 编码
            try_multiple: 读取模式下是否尝试多种编码

        返回:
            文件对象
        """
        if "r" in mode and try_multiple and encoding is None:
            # 读取模式且未指定编码，先检测
            encoding = EncodingUtils.detect_file_encoding(filepath)

        # 对于写入模式，默认使用UTF-8
        if ("w" in mode or "a" in mode) and encoding is None:
            encoding = "utf-8"

        return open(filepath, mode, encoding=encoding)

    @staticmethod
    def get_platform_default_encoding() -> str:
        """
        获取平台默认编码

        返回:
            平台默认编码
        """
        if PlatformUtils.is_windows():
            return "gbk"
        elif PlatformUtils.is_macos():
            return "utf-8"
        else:
            # Linux和其他Unix系统
            return "utf-8"

    @staticmethod
    def ensure_utf8_compatible(text: str) -> str:
        """
        确保字符串是UTF-8兼容的

        移除或替换不兼容的字符。

        参数:
            text: 输入字符串

        返回:
            UTF-8兼容的字符串
        """
        try:
            # 尝试编码和解码以确保UTF-8兼容
            return text.encode("utf-8", errors="replace").decode("utf-8")
        except Exception as e:
            logger.warning(f"UTF-8兼容处理失败: {e}")
            return text

"""Encoding utility functions for Bitcoin data formats."""

import chardet


class EncodingUtils:
    """Encoding utility class for Bitcoin data formats."""

    @staticmethod
    def detect_file_encoding(file_path: str) -> str:
        """Detect file encoding by reading the file as bytes."""
        with open(file_path, "rb") as f:
            raw = f.read()
        return EncodingUtils.detect_encoding_from_bytes(raw)

    @staticmethod
    def detect_encoding_from_bytes(data: bytes) -> str:
        """Detect encoding from byte data."""
        result = chardet.detect(data)
        return result.get("encoding", "utf-8") or "utf-8"

    @staticmethod
    def ensure_utf8_compatible(text: str) -> str:
        """Ensure text is UTF-8 compatible."""
        return text.encode("utf-8", errors="replace").decode("utf-8")

    @staticmethod
    def convert_file_encoding(
        src_path: str,
        dst_path: str,
        dst_encoding: str = "utf-8",
    ) -> bool:
        """Convert file encoding from source to destination."""
        # Use read_file with multi-encoding fallback to properly decode
        content = EncodingUtils.read_file(src_path, try_multiple=True)
        with open(dst_path, "w", encoding=dst_encoding) as f:
            f.write(content)
        return True

    @staticmethod
    def bytes_to_hex(data: bytes) -> str:
        """Convert bytes to hex string."""
        return data.hex()

    @staticmethod
    def hex_to_bytes(hex_str: str) -> bytes:
        """Convert hex string to bytes."""
        return bytes.fromhex(hex_str)

    @staticmethod
    def int_to_bytes(value: int, length: int = 32) -> bytes:
        """Convert integer to bytes (big-endian)."""
        return value.to_bytes(length, "big")

    @staticmethod
    def bytes_to_int(data: bytes) -> int:
        """Convert bytes to integer (big-endian)."""
        return int.from_bytes(data, "big")

    @staticmethod
    def read_file_lines(file_path: str, try_multiple: bool = True) -> list[str]:
        """Read file lines with multiple encoding fallback."""
        encodings = ["utf-8", "gbk", "latin-1"]
        errors = []

        for enc in encodings:
            try:
                with open(file_path, encoding=enc) as f:
                    return f.readlines()
            except UnicodeDecodeError as e:
                errors.append(f"{enc}: {e}")
                if not try_multiple:
                    raise
                continue
            except OSError:
                raise

        raise UnicodeDecodeError(
            "utf-8",
            b"",
            0,
            0,
            f"Failed to decode {file_path} with all encodings: {errors}",
        )

    @staticmethod
    def read_file(file_path: str, encoding: str = "utf-8", try_multiple: bool = False) -> str:
        """Read entire file content with optional encoding fallback."""
        encodings = [encoding, "utf-8", "gbk", "latin-1"] if try_multiple else [encoding]
        errors = []

        for enc in encodings:
            try:
                with open(file_path, encoding=enc) as f:
                    return f.read()
            except UnicodeDecodeError as e:
                errors.append(f"{enc}: {e}")
                if not try_multiple:
                    raise
                continue
            except OSError:
                raise

        raise UnicodeDecodeError(
            "utf-8",
            b"",
            0,
            0,
            f"Failed to decode {file_path} with all encodings: {errors}",
        )

    @staticmethod
    def write_file(file_path: str, content: str, encoding: str = "utf-8") -> None:
        """Write string content to a file."""
        with open(file_path, "w", encoding=encoding) as f:
            f.write(content)

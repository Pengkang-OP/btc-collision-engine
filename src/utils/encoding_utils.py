"""Encoding utility functions for Bitcoin data formats."""


class EncodingUtils:
    """Encoding utility class for Bitcoin data formats."""

    @staticmethod
    def bytes_to_hex(data: bytes) -> str:
        return data.hex()

    @staticmethod
    def hex_to_bytes(hex_str: str) -> bytes:
        return bytes.fromhex(hex_str)

    @staticmethod
    def int_to_bytes(value: int, length: int = 32) -> bytes:
        return value.to_bytes(length, "big")

    @staticmethod
    def bytes_to_int(data: bytes) -> int:
        return int.from_bytes(data, "big")

    @staticmethod
    def read_file_lines(file_path: str, try_multiple: bool = True):
        """Read file lines with multiple encoding fallback.

        Args:
            file_path: Path to the file to read.
            try_multiple: If True, try multiple encodings on decode error.

        Returns:
            List of lines from the file.

        Raises:
            OSError: If file cannot be read.
            UnicodeDecodeError: If all encodings fail.
        """
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
            "utf-8", b"", 0, 0, f"Failed to decode {file_path} with all encodings: {errors}"
        )

    @staticmethod
    def read_file(file_path: str, encoding: str = "utf-8", try_multiple: bool = False) -> str:
        """Read entire file content with optional encoding fallback.

        Args:
            file_path: Path to the file to read.
            encoding: Primary encoding to try.
            try_multiple: If True, try multiple encodings on decode error.

        Returns:
            File content as string.

        Raises:
            OSError: If file cannot be read.
            UnicodeDecodeError: If all encodings fail.
        """
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
            "utf-8", b"", 0, 0, f"Failed to decode {file_path} with all encodings: {errors}"
        )

    @staticmethod
    def write_file(file_path: str, content: str, encoding: str = "utf-8") -> None:
        """Write string content to a file.

        Args:
            file_path: Path to the file to write.
            content: String content to write.
            encoding: Encoding to use.

        Raises:
            OSError: If file cannot be written.
        """
        with open(file_path, "w", encoding=encoding) as f:
            f.write(content)


def bytes_to_hex(data: bytes) -> str:
    return data.hex()


def hex_to_bytes(hex_str: str) -> bytes:
    return bytes.fromhex(hex_str)


def int_to_bytes(value: int, length: int = 32) -> bytes:
    return value.to_bytes(length, "big")


def bytes_to_int(data: bytes) -> int:
    return int.from_bytes(data, "big")

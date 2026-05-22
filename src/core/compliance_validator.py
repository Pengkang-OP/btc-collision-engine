"""Bitcoin Core compliance validation."""

from ..utils import get_configured_logger
from .secp256k1 import Secp256k1

logger = get_configured_logger("BitcoinComplianceValidator")


class BitcoinComplianceValidator:
    """
    Bitcoin Core specification compliance validator.

    Validates that generated key pairs and addresses conform to
    Bitcoin Core technical specifications, ensuring full
    compatibility with the standard Bitcoin network.

    Usage:
        >>> validator = BitcoinComplianceValidator()
        >>> is_valid, issues = validator.validate(data)
    """

    COMPRESSED_PUBKEY_LEN = 33
    UNCOMPRESSED_PUBKEY_LEN = 65
    PRIVKEY_LEN = 32
    HASH160_BYTES_LEN = 20
    HASH160_HEX_LEN = 40
    UNCOMPRESSED_WIF_LEN = 51
    COMPRESSED_WIF_LEN = 52
    P2PKH_LEN_1 = 33
    P2PKH_LEN_2 = 34

    BASE58_CHARS = set(
        "123456789ABCDEFGHJKLMNPQRSTUVWXYZ"
        "abcdefghijkmnopqrstuvwxyz"
    )

    def __init__(self) -> None:
        """Initialize validator."""
        logger.info(
            "BitcoinComplianceValidator initialized"
        )

    def validate(
        self, data: dict
    ) -> tuple[bool, list[str]]:
        """
        Validate Bitcoin specification compliance.

        Args:
            data: Data dictionary to validate.
                Should contain:
                - private_key: Private key (bytes)
                - public_key: Public key (bytes)
                - address: Bitcoin address
                - wif: WIF formatted key
                - hash160: Hash160 value
                - compressed: Whether compressed format

        Returns:
            (is_compliant, issues_list)
        """
        issues = []
        issues.extend(self._validate_private_key(data))
        issues.extend(self._validate_public_key(data))
        issues.extend(self._validate_address(data))
        issues.extend(self._validate_wif(data))
        issues.extend(self._validate_hash160(data))

        is_valid = len(issues) == 0
        if is_valid:
            logger.debug("Compliance validation passed")
        else:
            logger.warning(
                "Compliance validation failed: "
                "%d issues",
                len(issues),
            )
        return is_valid, issues

    def _validate_private_key(
        self, data: dict
    ) -> list[str]:
        issues = []
        private_key = data.get("private_key")
        if private_key is None:
            issues.append("Missing private key")
            return issues
        if not isinstance(private_key, (bytes, bytearray)):
            issues.append("Private key must be bytes")
            return issues
        if len(private_key) != self.PRIVKEY_LEN:
            issues.append(
                f"Private key length must be {self.PRIVKEY_LEN} bytes, "
                f"got {len(private_key)}"
            )
        key_int = int.from_bytes(private_key, "big")
        if key_int < 1:
            issues.append("Private key must be > 0")
        if key_int >= Secp256k1.N:
            issues.append(
                "Private key must be less than "
                "secp256k1 curve order"
            )
        return issues

    def _validate_public_key(
        self, data: dict
    ) -> list[str]:
        issues = []
        public_key = data.get("public_key")
        compressed = data.get("compressed", True)
        if public_key is None:
            issues.append("Missing public key")
            return issues
        if not isinstance(
            public_key, (bytes, bytearray)
        ):
            issues.append("Public key must be bytes")
            return issues
        if compressed:
            if len(public_key) != self.COMPRESSED_PUBKEY_LEN:
                issues.append(
                    f"Compressed public key must be "
                    f"{self.COMPRESSED_PUBKEY_LEN} bytes, "
                    f"got {len(public_key)}"
                )
            if public_key[0] not in [0x02, 0x03]:
                issues.append(
                    f"Compressed public key prefix must be "
                    f"0x02 or 0x03, got 0x{public_key[0]:02x}"
                )
        else:
            if len(public_key) != self.UNCOMPRESSED_PUBKEY_LEN:
                issues.append(
                    f"Uncompressed public key must be "
                    f"{self.UNCOMPRESSED_PUBKEY_LEN} bytes, "
                    f"got {len(public_key)}"
                )
            if public_key[0] != 0x04:
                issues.append(
                    f"Uncompressed public key prefix must be "
                    f"0x04, got 0x{public_key[0]:02x}"
                )
        return issues

    def _validate_address(
        self, data: dict
    ) -> list[str]:
        issues = []
        address = data.get("address")
        if address is None:
            issues.append("Missing address")
            return issues
        if not isinstance(address, str):
            issues.append("Address must be a string")
            return issues
        if not address.startswith("1"):
            issues.append(
                f"P2PKH address must start with '1', "
                f"got '{address[0]}'"
            )
        if len(address) not in [
            self.P2PKH_LEN_1,
            self.P2PKH_LEN_2,
        ]:
            issues.append(
                f"P2PKH address length must be "
                f"{self.P2PKH_LEN_1} or {self.P2PKH_LEN_2}, "
                f"got {len(address)}"
            )
        if not all(
            c in self.BASE58_CHARS for c in address
        ):
            issues.append(
                "Address contains invalid Base58 chars"
            )
        return issues

    def _validate_wif(self, data: dict) -> list[str]:
        issues = []
        wif = data.get("wif")
        if wif is None:
            issues.append("Missing WIF")
            return issues
        if not isinstance(wif, str):
            issues.append("WIF must be a string")
            return issues
        if not wif.startswith(("5", "K", "L")):
            issues.append(
                f"WIF must start with '5', 'K' or 'L', "
                f"got '{wif[0]}'"
            )
        if wif.startswith("5"):
            if len(wif) != self.UNCOMPRESSED_WIF_LEN:
                issues.append(
                    f"Uncompressed WIF must be "
                    f"{self.UNCOMPRESSED_WIF_LEN} chars, "
                    f"got {len(wif)}"
                )
        else:
            if len(wif) != self.COMPRESSED_WIF_LEN:
                issues.append(
                    f"Compressed WIF must be "
                    f"{self.COMPRESSED_WIF_LEN} chars, "
                    f"got {len(wif)}"
                )
        if not all(
            c in self.BASE58_CHARS for c in wif
        ):
            issues.append(
                "WIF contains invalid Base58 chars"
            )
        return issues

    def _validate_hash160(
        self, data: dict
    ) -> list[str]:
        issues = []
        hash160 = data.get("hash160")
        if hash160 is None:
            issues.append("Missing Hash160")
            return issues
        if isinstance(hash160, bytes):
            if len(hash160) != self.HASH160_BYTES_LEN:
                issues.append(
                    f"Hash160 must be "
                    f"{self.HASH160_BYTES_LEN} bytes, "
                    f"got {len(hash160)}"
                )
        elif isinstance(hash160, str):
            if len(hash160) != self.HASH160_HEX_LEN:
                issues.append(
                    f"Hash160 hex must be "
                    f"{self.HASH160_HEX_LEN} chars, "
                    f"got {len(hash160)}"
                )
        else:
            issues.append(
                "Hash160 must be bytes or hex string"
            )
        return issues

    def validate_batch(
        self, data_list: list[dict]
    ) -> list[tuple[bool, list[str]]]:
        """
        Batch validation.

        Args:
            data_list: List of data dictionaries

        Returns:
            List of validation results
        """
        results = []
        for data in data_list:
            is_valid, issues = self.validate(data)
            results.append((is_valid, issues))

        valid_count = sum(
            1 for is_valid, _ in results if is_valid
        )
        logger.info(
            "Batch validation complete: "
            "%d/%d passed",
            valid_count,
            len(data_list),
        )
        return results

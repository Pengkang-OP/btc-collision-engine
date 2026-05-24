#!/usr/bin/env python3
"""Core cryptographic function tests for the BTC collision engine."""

import secrets

import pytest

from src.core.address_generator import P2PKHAddressGenerator
from src.core.base58 import Base58
from src.core.hash_utils import HashUtils
from src.core.secp256k1 import ECPoint, EllipticCurve, Secp256k1
from src.core.wif import WIF


class TestSecp256k1:
    """secp256k1 curve parameter tests."""

    def test_curve_order_valid(self):
        """N should be a valid curve order (N < P)"""
        assert Secp256k1.N < Secp256k1.P

    def test_generator_point_on_curve(self):
        """Generator point G should satisfy y² = x³ + 7 (mod p)"""
        lhs = pow(Secp256k1.Gy, 2, Secp256k1.P)
        rhs = (pow(Secp256k1.Gx, 3, Secp256k1.P) + 7) % Secp256k1.P
        assert lhs == rhs

    def test_scalar_mult_identity(self):
        """1 * G should equal G"""
        ec = EllipticCurve()
        g = ECPoint(Secp256k1.Gx, Secp256k1.Gy)
        result = ec.scalar_multiply_const_time(1, g)
        assert result.x == Secp256k1.Gx
        assert result.y == Secp256k1.Gy

    def test_known_key_address(self):
        """Known private key 1 should produce known address"""
        priv = (1).to_bytes(32, "big")
        gen = P2PKHAddressGenerator()
        addr, _, _ = gen.generate_address(priv)
        assert addr.startswith("1")

    def test_large_private_key(self):
        """Large valid private key should work"""
        priv = (Secp256k1.N - 1).to_bytes(32, "big")
        gen = P2PKHAddressGenerator()
        addr, _, _ = gen.generate_address(priv)
        assert addr.startswith("1")


class TestHashUtils:
    """Hash utility function tests."""

    def test_sha256_hello(self):
        result = HashUtils.sha256(b"hello")
        assert len(result) == 32

    def test_sha256_known_value(self):
        result = HashUtils.sha256(b"hello")
        expected = bytes.fromhex(
            "2cf24dba5fb0a30e26e83b2ac5b9e29e"
            "1b161e5c1fa7425e73043362938b9824",
        )
        assert result == expected

    def test_double_sha256(self):
        result = HashUtils.double_sha256(b"test")
        assert len(result) == 32

    @pytest.mark.parametrize("length", [0, 16, 24, 31, 33, 48, 64])
    def test_private_key_invalid_length(self, length):
        gen = P2PKHAddressGenerator()
        pk = bytes(length)
        with pytest.raises(ValueError) as excinfo:
            gen.generate_address(pk)
        assert "length" in str(excinfo.value).lower()
        assert "32" in str(excinfo.value)


class TestBase58:
    """Base58 encode/decode tests."""

    def test_encode_decode_roundtrip(self):
        data = b"hello world"
        encoded = Base58.encode(data)
        decoded = Base58.decode(encoded)
        assert decoded == data

    def test_check_encode_decode_roundtrip(self):
        payload = secrets.token_bytes(20)
        encoded = Base58.check_encode(0x00, payload)
        version, decoded = Base58.check_decode(encoded)
        assert version == 0x00
        assert decoded == payload

    def test_base58_empty_string(self):
        assert Base58.decode("") == b""

    def test_base58_leading_ones(self):
        data = b"\x00\x00hello"
        encoded = Base58.encode(data)
        assert encoded.startswith("11")

    def test_bitcoin_genesis_address(self):
        addr = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
        version, payload = Base58.check_decode(addr)
        assert version == 0x00
        assert len(payload) == 20

    def test_base58_invalid_character_zero(self):
        with pytest.raises(ValueError) as excinfo:
            Base58.decode("10ABC")
        assert "Invalid Base58 character" in str(excinfo.value)
        assert "'0'" in str(excinfo.value)

    def test_base58_invalid_character_O(self):
        with pytest.raises(ValueError) as excinfo:
            Base58.decode("1OABC")
        assert "Invalid Base58 character" in str(excinfo.value)

    def test_base58_invalid_character_I(self):
        with pytest.raises(ValueError) as excinfo:
            Base58.decode("1IABC")
        assert "Invalid Base58 character" in str(excinfo.value)

    def test_base58_invalid_character_l(self):
        with pytest.raises(ValueError) as excinfo:
            Base58.decode("1lABC")
        assert "Invalid Base58 character" in str(excinfo.value)

    def test_base58_invalid_character_special(self):
        for char in "!@#$%+=?":
            with pytest.raises(ValueError) as excinfo:
                Base58.decode(f"1{char}ABC")
            assert "Invalid Base58 character" in str(excinfo.value)

    def test_base58_invalid_character_space(self):
        with pytest.raises(ValueError) as excinfo:
            Base58.decode("1 ABC")
        assert "Invalid Base58 character" in str(excinfo.value)

    def test_base58_invalid_checksum(self):
        with pytest.raises(ValueError) as excinfo:
            Base58.check_decode("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNb")
        assert "checksum" in str(excinfo.value).lower()


class TestP2PKHAddressGenerator:
    """P2PKH address generator tests."""

    def setup_method(self):
        self.gen = P2PKHAddressGenerator()

    def test_generate_valid_address(self):
        addr, pub_comp, pub_uncomp = self.gen.generate_address()
        assert len(pub_comp) == 33
        assert len(pub_uncomp) == 65
        assert addr.startswith("1")

    def test_deterministic_generation(self):
        pk = (1).to_bytes(32, "big")
        addr1, _, _ = self.gen.generate_address(pk)
        addr2, _, _ = self.gen.generate_address(pk)
        assert addr1 == addr2

    def test_different_keys_different_addresses(self):
        pk1 = (1).to_bytes(32, "big")
        pk2 = (2).to_bytes(32, "big")
        addr1, _, _ = self.gen.generate_address(pk1)
        addr2, _, _ = self.gen.generate_address(pk2)
        assert addr1 != addr2

    def test_private_key_minimum_valid(self):
        pk = (1).to_bytes(32, "big")
        addr, pub, _ = self.gen.generate_address(pk)
        assert addr.startswith("1")
        assert len(pub) in (33, 65)
        assert pub[0] in (2, 3, 4)

    def test_private_key_maximum_valid(self):
        pk = (Secp256k1.N - 1).to_bytes(32, "big")
        addr, _, _ = self.gen.generate_address(pk)
        assert addr.startswith("1")

    def test_private_key_zero_rejected(self):
        pk_zero = (0).to_bytes(32, "big")
        with pytest.raises(ValueError) as excinfo:
            self.gen.generate_address(pk_zero)
        assert "cannot be zero" in str(excinfo.value).lower()

    def test_private_key_curve_order_rejected(self):
        pk_n = Secp256k1.N.to_bytes(32, "big")
        with pytest.raises(ValueError) as excinfo:
            self.gen.generate_address(pk_n)
        assert "exceeds" in str(excinfo.value).lower()

    def test_private_key_greater_than_curve_order_rejected(self):
        pk_too_large = (Secp256k1.N + 1).to_bytes(32, "big")
        with pytest.raises(ValueError) as excinfo:
            self.gen.generate_address(pk_too_large)
        assert "exceeds" in str(excinfo.value).lower()

    def test_private_key_random_generation_valid_range(self):
        for _ in range(10):
            pk = self.gen.generate_private_key()
            pk_int = int.from_bytes(pk, "big")
            assert 1 <= pk_int < Secp256k1.N

    def test_pub_key_prefix(self):
        pk = (1).to_bytes(32, "big")
        _, pub, _ = self.gen.generate_address(pk)
        assert pub[0] in (2, 3, 4)

    def test_pub_key_length(self):
        pk = (1).to_bytes(32, "big")
        _, pub_compressed, pub_uncompressed = self.gen.generate_address(pk)
        assert len(pub_compressed) == 33
        assert len(pub_uncompressed) == 65


class TestWIF:
    """WIF encode/decode tests."""

    def test_encode_decode_compressed(self):
        pk = secrets.token_bytes(32)
        wif = WIF.encode(pk, compressed=True)
        decoded, compressed = WIF.decode(wif)
        assert decoded == pk
        assert compressed is True
        assert wif.startswith(("K", "L"))

    def test_encode_decode_uncompressed(self):
        pk = secrets.token_bytes(32)
        wif = WIF.encode(pk, compressed=False)
        decoded, compressed = WIF.decode(wif)
        assert decoded == pk
        assert compressed is False
        assert wif.startswith("5")

    def test_private_key_1_wif(self):
        pk = (1).to_bytes(32, "big")
        wif = WIF.encode(pk, compressed=True)
        decoded, _ = WIF.decode(wif)
        assert decoded == pk

    def test_invalid_wif_raises(self):
        with pytest.raises(Exception):
            WIF.decode("invalid_wif_string")

    def test_wif_length(self):
        pk = secrets.token_bytes(32)
        wif_comp = WIF.encode(pk, compressed=True)
        wif_uncomp = WIF.encode(pk, compressed=False)
        assert len(wif_comp) == 52
        assert len(wif_uncomp) == 51


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

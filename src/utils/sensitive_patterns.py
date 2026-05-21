#!/usr/bin/env python3
"""
敏感数据模式常量模块

集中维护所有敏感数据检测的正则表达式模式，
供 SecurityLogFilter 和 SensitiveDataFilter 共享使用。

v4.5.1: 提取公共模式，消除两处过滤器的正则重复。
"""

import re

# ====================================================================
# 私钥模式
# ====================================================================

# 64位十六进制（32字节私钥），支持0x前缀
# 使用负向前瞻确保不在其他十六进制字符串中间匹配
PRIVATE_KEY_HEX = re.compile(r"(?<![0-9a-fA-F])(?:0x)?[0-9a-fA-F]{64}(?![0-9a-fA-F])")

# WIF 格式 - 非压缩: 以5开头，总长51字符
WIF_UNCOMPRESSED = re.compile(r"\b5[HJK][1-9A-HJ-NP-Za-km-z]{48,49}\b")
# WIF 格式 - 压缩: 以K或L开头，总长52字符
WIF_COMPRESSED = re.compile(r"\b[KL][1-9A-HJ-NP-Za-km-z]{50,51}\b")

# 原始字节模式（32字节）
# P2-07修复: 添加路径分隔符负向前瞻，避免误匹配 Windows 路径中的反斜杠序列
RAW_KEY = re.compile(
    r"(?<![\\/:a-zA-Z0-9])b'\\x[0-9a-fA-F]{2}(?:\\x[0-9a-fA-F]{2}){31}'(?![\\/])"
)

# PrivateKey 上下文模式（仅在 SensitiveDataFilter 中使用）
PRIVATE_KEY_CONTEXT = re.compile(
    r'PrivateKey["\']?\s*[:=]\s*["\']?[0-9a-fA-F]{64}'
)

# ====================================================================
# 比特币地址模式
# ====================================================================

# P2PKH: 以 1 开头，25-34 字符 Base58
P2PKH_ADDRESS = re.compile(r"\b1[1-9A-HJ-NP-Za-km-z]{24,33}\b")
# P2SH: 以 3 开头，25-34 字符 Base58
P2SH_ADDRESS = re.compile(r"\b3[1-9A-HJ-NP-Za-km-z]{24,33}\b")
# Bech32: 以 bc1 开头，42 或 62 字符（P2WPKH/P2WSH）
BECH32_ADDRESS = re.compile(r"\bbc1[ac-hj-np-z02-9]{38,58}\b")
# Bech32m (Taproot): 以 bc1p 开头，62 字符
BECH32M_ADDRESS = re.compile(r"\bbc1p[ac-hj-np-z02-9]{58}\b")

# ====================================================================
# BIP32 扩展密钥模式
# ====================================================================

BIP32_EXTENDED_KEY = re.compile(r"\b[xXtT]prv[1-9A-HJ-NP-Za-km-z]{107,108}\b")
BIP32_EXTENDED_PUBKEY = re.compile(r"\b[xXtT]pub[1-9A-HJ-NP-Za-km-z]{107,108}\b")

# ====================================================================
# BIP39 种子短语模式
# ====================================================================

# BIP39 上下文关键词 — 仅当包含这些上下文时才应用 BIP39 检测
BIP39_CONTEXT_KEYWORDS = re.compile(
    r"\b(seed|mnemonic|recovery|phrase|bip39|助记词|种子短语|恢复短语)\b", re.IGNORECASE
)

# BIP39 种子短语 (12 个助记词)
BIP39_PHRASE_12 = re.compile(r"\b(?:[a-z]{3,8}\s+){11}[a-z]{3,8}\b", re.IGNORECASE)
# BIP39 种子短语 (24 个助记词) — 注意: 必须在 12 词之前匹配
BIP39_PHRASE_24 = re.compile(r"\b(?:[a-z]{3,8}\s+){23}[a-z]{3,8}\b", re.IGNORECASE)

# ====================================================================
# 掩码替换模板（供 SecurityLogFilter 使用）
# ====================================================================

WIF_UNCOMPRESSED_MASK = "[WIF_UNCOMPRESSED_KEY]"
WIF_COMPRESSED_MASK = "[WIF_COMPRESSED_KEY]"
RAW_KEY_MASK = "[RAW_PRIVATE_KEY]"
P2PKH_ADDRESS_MASK = "[P2PKH_ADDRESS]"
P2SH_ADDRESS_MASK = "[P2SH_ADDRESS]"
BECH32_ADDRESS_MASK = "[BECH32_ADDRESS]"
BECH32M_ADDRESS_MASK = "[BECH32M_ADDRESS]"
BIP32_EXTENDED_KEY_MASK = "[BIP32_EXTENDED_KEY]"
BIP32_EXTENDED_PUBKEY_MASK = "[BIP32_EXTENDED_PUBKEY]"
BIP39_PHRASE_12_MASK = "[BIP39_PHRASE_12_WORDS]"
BIP39_PHRASE_24_MASK = "[BIP39_PHRASE_24_WORDS]"

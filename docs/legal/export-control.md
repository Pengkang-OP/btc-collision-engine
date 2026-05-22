# 加密出口管制声明

> **版本**: v4.5.1 | **最后更新**: 2026-05-22

## 概述

本软件包含加密功能，可能受到各国出口管制法规的约束。本文件提供了本软件中使用的加密技术的详细信息。

## 使用的加密技术

| 加密功能 | 算法 | 用途 | 标准 |
|---------|------|------|------|
| 椭圆曲线运算 | secp256k1 | 比特币私钥/公钥生成 | ANSI X9.62 |
| 哈希函数 | SHA-256 | 比特币地址生成 (HASH160) | FIPS 180-4 |
| 哈希函数 | RIPEMD-160 | 比特币地址生成 (HASH160) | ISO/IEC 10118-3 |
| 对称加密 | AES (pycryptodome) | 密钥存储加密 (可选) | FIPS 197 |
| 非对称加密 | ECC (cryptography) | 密钥管理 | SP 800-56A |
| 随机数生成 | CSPRNG (secrets) | 私钥生成 | NIST SP 800-90A |

## 出口管制分类

### 美国出口管制 (EAR)

本软件可能受美国出口管理条例 (EAR, 15 CFR Parts 730-774) 的约束，具体为：

- **ECC 分类**: 5A002 (加密物品)
- **相关条款**: EAR 742.15 (加密物品)
- **管制理由**: 国家安全 (NS) + 反恐 (AT)

### 欧洲出口管制

本软件可能受欧盟双重用途条例 (EU 2021/821) 的约束。

### 其他司法管辖区

用户有责任遵守其所在国家和地区的出口管制法规。

## 用户责任

1. **遵守当地法律**: 用户必须确保使用本软件符合当地法律法规
2. **出口许可**: 如果需要出口或再出口本软件，可能需要申请相应的出口许可
3. **禁止用途**: 不得用于非法目的，包括但不限于未经授权的访问、数据窃取等

## 免责声明

本软件按"原样"提供，作者不对因使用本软件而导致的任何出口管制违规行为承担责任。用户应自行评估并遵守适用的出口管制法规。

## 相关资源

- [美国 BIS 网站](https://www.bis.gov/)
- [EAR 742.15](https://www.ecfr.gov/current/title-15/subtitle-B/chapter-VII/subchapter-C/part-742/section-742.15)
- [EU 双重用途条例](https://ec.europa.eu/trade/import-and-export-rules/export-from-eu/dual-use-controls/)

---

## 相关文档

- [许可证兼容性](license-compatibility.md)
- [第三方代码归属](third-party-attribution.md)
- [安全指南](../security/security-guidelines.md)

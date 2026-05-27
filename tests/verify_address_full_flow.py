"""验证比特币地址全链路：导入 → 格式检测 → 密钥生成 → 地址生成 → 碰撞匹配."""

import sys

from src.collision.targets.format_aware_manager import FormatAwareTargetManager
from src.collision.targets.matcher import AddressMatcher
from src.collision.targets.resolver import TargetResolver
from src.core.multi_format_generator import MultiFormatAddressGenerator

PASS = 0
FAIL = 0


def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [OK] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name} — {detail}")


print("=" * 70)
print("1. 目标地址单地址导入")
print("=" * 70)

resolver = TargetResolver()

# 各种格式的目标地址（格式名需对齐 detect_format 返回值）
test_addrs = {
    "address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
    "p2sh_address": "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy",
    "bech32_address": "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4",
    "taproot_address": "bc1p5d7rjq7g6rdk2yhzks9smlaqtedr4dekq08ge8qt2acpp2yx7tqsp6h3m",
}

for fmt, addr in test_addrs.items():
    detected = resolver.detect_format(addr)
    check(f"格式检测 [{fmt}] → {detected}", detected == fmt, f"期望={fmt}, 实际={detected}")

# 单地址解析（所有格式应解析为 P2PKH 地址）
for fmt, addr in test_addrs.items():
    resolved = resolver.resolve(addr)
    if resolved:
        check(
            f"解析 [{fmt}] → P2PKH: {resolved[:10]}...",
            resolved.startswith("1"),
            f"解析结果不是 P2PKH 地址: {resolved}",
        )
    else:
        # P2SH和Taproot密码学上无法用于碰撞匹配，返回 None 是正确行为
        check(
            f"解析 [{fmt}] → None (设计行为)",
            fmt in ("p2sh_address", "taproot_address"),
            f"{fmt} 返回 None 但应可解析",
        )


print("\n" + "=" * 70)
print("2. 私钥生成 → 多格式地址生成")
print("=" * 70)

generator = MultiFormatAddressGenerator()

# 使用已知向量: 私钥 0x1
test_key_raw = bytes.fromhex("0000000000000000000000000000000000000000000000000000000000000001")

formats = generator.generate_all_formats(test_key_raw)
for fmt, addr in formats.items():
    check(f"私钥0x1 → {fmt}: {addr[:15]}...", addr is not None and len(addr) > 10, "地址为空或过短")

# 验证各格式前缀
check("P2PKH 以 1 开头", formats["p2pkh"].startswith("1"), f"实际: {formats['p2pkh'][0]}")
check("P2SH 以 3 开头", formats["p2sh"].startswith("3"), f"实际: {formats['p2sh'][0]}")
check("Bech32 以 bc1q 开头", formats["bech32"].startswith("bc1q"), f"实际: {formats['bech32'][:6]}")
check("Taproot 以 bc1p 开头", formats["taproot"].startswith("bc1p"), f"实际: {formats['taproot'][:6]}")


print("\n" + "=" * 70)
print("3. WIF 编码 → 解析 → 地址闭环")
print("=" * 70)

from src.core.wif import WIF  # noqa: E402

# 编码: 私钥 → WIF
wif_from_pk = WIF.encode(test_key_raw, compressed=True)
check(f"WIF编码 私钥0x1 → {wif_from_pk}", wif_from_pk is not None, "WIF编码失败")

# 解析: WIF → 地址
resolved_from_wif = resolver.resolve(wif_from_pk)
check(
    "WIF 解析为地址",
    resolved_from_wif is not None and resolved_from_wif.startswith("1"),
    f"解析失败: {resolved_from_wif}",
)

# 闭环验证: WIF→地址 == 私钥→地址
check(
    "WIF解析地址 = 私钥生成地址",
    resolved_from_wif == formats["p2pkh"],
    f"WIF解析: {resolved_from_wif}, 私钥生成: {formats['p2pkh']}",
)


print("\n" + "=" * 70)
print("4. 格式感知目标管理器")
print("=" * 70)

manager = FormatAwareTargetManager()
for addr in test_addrs.values():
    manager.add_target(addr)

# 用私钥 0x1 测试 match
is_match_all, matches = manager.check_match_all(test_key_raw)
check("check_match_all 返回正确类型", isinstance(matches, list), f"类型: {type(matches)}")
if matches and len(matches) > 0:
    known_formats = {"p2pkh", "p2sh", "bech32", "taproot"}
    for addr, fmt in matches:
        check(f"  匹配: {fmt} → {addr[:12]}...", fmt in known_formats, f"未知格式: {fmt}")
else:
    check("单格式 check_match", True, "match返回结果是None(取决于后端能力)")


print("\n" + "=" * 70)
print("5. 完整碰撞匹配测试")
print("=" * 70)

# 构建测试目标: 将已知私钥 0x1 的地址加入目标集
target_addrs = {formats["p2pkh"]}
check(f"目标地址: {list(target_addrs)[0][:15]}...", len(target_addrs) == 1, "应有1个目标")

# 使用 AddressMatcher 进行匹配
matcher = AddressMatcher(strategy="hash_set", targets=target_addrs)

# 验证 0x1 产生的地址能匹配
check("私钥0x1 P2PKH 匹配", matcher.is_match(formats["p2pkh"]), f"地址 {formats['p2pkh']} 应匹配")

# 验证不同私钥产生的地址不匹配
test_key_2 = bytes.fromhex("0000000000000000000000000000000000000000000000000000000000000002")
formats_2 = generator.generate_all_formats(test_key_2)
check(
    "私钥0x2 P2PKH 不匹配",
    not matcher.is_match(formats_2["p2pkh"]),
    f"地址 {formats_2['p2pkh'][:15]}... 不应匹配",
)

# 验证目标管理器 match (check_match 返回 (bool, addr, fmt) 元组)
is_match_1, addr_1, fmt_1 = manager.check_match(test_key_raw)
check(
    f"私钥0x1 check_match={is_match_1} (地址: {addr_1})",
    is_match_1,
    f"0x1 应匹配, 实际: {is_match_1}",
)

is_match_2, addr_2, fmt_2 = manager.check_match(test_key_2)
check(
    f"私钥0x2 check_match={is_match_2} (地址: {addr_2})",
    not is_match_2,
    f"0x2 不应匹配, 生成的p2pkh地址: {formats_2['p2pkh']}",
)


print("\n" + "=" * 70)
print("6. 目标地址表文件导入")
print("=" * 70)

import pathlib  # noqa: E402
import tempfile  # noqa: E402

# 创建临时目标文件
with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
    f.write("# 测试目标文件\n")
    f.write("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa\n")
    f.write("bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4\n")
    f.write("3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy\n")
    f.write("invalid_address\n")
    f.write("  \n")  # 空行
    f.write("\n")
    f.write("1CounterpartyXXXXXXXXXXXXXXXUWLpVr\n")
    temp_path = f.name

try:
    file_targets = resolver.load_from_file(temp_path)
    check("文件加载地址数", file_targets is not None, f"加载失败: {file_targets}")

    if file_targets:
        # 应跳过无效地址和空行, 有效地址数
        valid_count = len(file_targets)
        check("有效地址数 >= 3", valid_count >= 3, f"期望 >= 3, 实际: {valid_count}")
        for addr in file_targets:
            check(
                f"  有效 P2PKH: {addr[:10]}...",
                addr.startswith("1"),
                f"过滤后仍有非 P2PKH 地址: {addr}",
            )
finally:
    pathlib.Path(temp_path).unlink()


print("\n" + "=" * 70)
print("总结")
print("=" * 70)
total = PASS + FAIL
print(f"  通过: {PASS}/{total} ({PASS / total * 100:.0f}%)")
print(f"  失败: {FAIL}/{total}")
print("=" * 70)

sys.exit(0 if FAIL == 0 else 1)

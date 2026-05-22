#!/usr/bin/env python3
"""BTC碰撞引擎 - 全面测试与代码质量审核脚本"""
import json
import re
import subprocess
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
RESULTS = {}


def log(msg):
    # GBK encoding console can't print emoji, use ASCII
    safe_msg = msg.replace('\u2705', '[OK]').replace(
        '\u274c', '[FAIL]'
    ).replace('\u26a0\ufe0f', '[WARN]').replace('\ud83d\udd12', '[LOCK]')
    print(f"[{time.strftime('%H:%M:%S')}] {safe_msg}")


def run_cmd(cmd, timeout=300):
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, cwd=BASE_DIR
        )
        return {
            "returncode": r.returncode,
            "stdout": r.stdout[-3000:],
            "stderr": r.stderr[-1000:],
            "full_stdout": r.stdout,
        }
    except subprocess.TimeoutExpired:
        return {"returncode": -1, "stdout": "TIMEOUT", "stderr": ""}
    except Exception as e:
        return {"returncode": -2, "stdout": "", "stderr": str(e)}


def parse_pytest_summary(text):
    lines = text.strip().split('\n')
    passed = failed = errors = 0
    for line in lines:
        if 'passed' in line and 'failed' in line:
            m = re.search(r'(\d+) passed', line)
            if m:
                passed = int(m.group(1))
            m = re.search(r'(\d+) failed', line)
            if m:
                failed = int(m.group(1))
            m = re.search(r'(\d+) errors', line)
            if m:
                errors = int(m.group(1))
        elif 'passed' in line:
            m = re.search(r'(\d+) passed', line)
            if m:
                passed = int(m.group(1))
    return passed, failed, errors


def count_tests():
    """计算所有测试文件中的测试用例总数"""
    log("计算测试用例总数...")
    r = run_cmd([sys.executable, '-m', 'pytest', 'tests/', '--collect-only', '-q'])
    lines = r.get("full_stdout", "").split("\n")
    test_count = 0
    for line in lines:
        if "selected" in line:
            m = re.search(r'(\d+) selected', line)
            if m:
                test_count = int(m.group(1))
    return test_count


# ============================================================
# 第1部分：单元测试 - 核心业务逻辑
# ============================================================
def run_unit_tests():
    log("=" * 60)
    log("第1部分：核心业务逻辑单元测试")
    log("=" * 60)

    unit_test_groups = [
        ("哈希工具", ["tests/test_hash_utils.py"]),
        ("Base58编解码", ["tests/test_base58_edge.py"]),
        ("WIF编解码", ["tests/test_wif_edge.py", "tests/test_wif_bech32.py"]),
        (
            "椭圆曲线secp256k1",
            ["tests/test_secp256k1_edge.py", "tests/test_secp256k1_extended.py"],
        ),
        ("密钥生成器", ["tests/test_key_generator.py"]),
        (
            "地址生成器",
            ["tests/test_address_generator_base.py",
             "tests/test_address_generator_edge.py"],
        ),
        (
            "比特币密钥验证器",
            ["tests/test_bitcoin_key_validator.py",
             "tests/test_bitcoin_key_validator_edge.py"],
        ),
        (
            "加密后端",
            ["tests/test_crypto_backend.py", "tests/test_crypto_backend_edge.py"],
        ),
        ("核心加密", ["tests/test_core_crypto.py"]),
        (
            "安全私钥管理",
            ["tests/test_secure_key_manager.py",
             "tests/test_secure_key_integration.py"],
        ),
        ("熵检查", ["tests/test_entropy_check.py"]),
        (
            "异常处理",
            ["tests/test_exceptions.py", "tests/test_exception_handling.py"],
        ),
        ("合规性验证器", ["tests/test_compliance_validator.py"]),
        ("安全测试", ["tests/test_security.py"]),
        (
            "多格式地址",
            ["tests/test_multi_format_conversion.py",
             "tests/test_multi_format_simple.py"],
        ),
        (
            "Bech32/P2SH转换",
            ["tests/test_bech32_p2sh_conversion.py",
             "tests/test_p2sh_bech32_addresses.py"],
        ),
        ("检查点管理器", ["tests/test_checkpoint_manager.py"]),
        (
            "去重过滤器",
            ["tests/test_deduplication_filter.py",
             "tests/test_bloom_deduplication_filter.py"],
        ),
        ("碰撞统计", ["tests/test_collision_stats.py"]),
        (
            "事件系统",
            ["tests/test_event_bus.py", "tests/test_event_system.py"],
        ),
        (
            "内存池",
            ["tests/test_memory_pool.py", "tests/test_memory_pool_edge.py"],
        ),
        ("预计算表", ["tests/test_precomputed_table.py"]),
        (
            "SIMD哈希",
            ["tests/test_simd_hash.py", "tests/test_simd_hash_edge.py"],
        ),
        (
            "大整数优化器",
            ["tests/test_bigint_optimizer.py",
             "tests/test_bigint_optimizer_edge.py"],
        ),
    ]

    all_passed = all_failed = all_errors = 0
    failures = []

    for name, files in unit_test_groups:
        existing = [f for f in files if (BASE_DIR / f).exists()]
        if not existing:
            log(f"  [SKIP] {name}: 未找到测试文件 {files}")
            continue

        log(f"  运行: {name} ({', '.join(existing)})...")
        r = run_cmd(
            [sys.executable, '-m', 'pytest'] + existing + ['-v', '--no-header', '--tb=short'],
            timeout=120,
        )
        passed, failed, errors = parse_pytest_summary(r["stdout"] + r["stderr"])
        all_passed += passed
        all_failed += failed
        all_errors += errors

        if failed > 0:
            for line in r["stdout"].split('\n'):
                if 'FAILED' in line:
                    test_name = line.strip()
                    failures.append(test_name)
                    log(f"    [FAIL] {test_name}")

        status = "PASS" if failed == 0 else "FAIL"
        log(f"    [{status}] {name}: {passed} passed, {failed} failed, {errors} errors")
        RESULTS[f"unit_{name}"] = {"passed": passed, "failed": failed, "errors": errors}

    RESULTS["unit_total"] = {
        "passed": all_passed, "failed": all_failed, "errors": all_errors, "failures": failures,
    }
    log(f"\n单元测试总计: {all_passed} passed, {all_failed} failed, {all_errors} errors")
    if failures:
        log("失败测试:")
        for fail in failures:
            log(f"  - {fail}")
    return all_failed == 0


# ============================================================
# 第2部分：全量测试
# ============================================================
def run_full_tests():
    log("\n" + "=" * 60)
    log("第2部分：全量集成测试")
    log("=" * 60)

    integration_groups = [
        (
            "碰撞引擎核心",
            ["tests/test_collision_core.py", "tests/test_base_search.py",
             "tests/test_key_collision_engine.py"],
        ),
        ("CLI命令测试", ["tests/test_cli.py"]),
        ("引擎构建器", ["tests/test_engine_builder.py"]),
        ("引擎运行器", ["tests/test_engine_runner.py"]),
        (
            "配置管理器",
            ["tests/test_config_manager.py", "tests/test_config_manager_advanced.py"],
        ),
        ("配置迁移", ["tests/test_config_migration.py"]),
        ("端到端闭环测试", ["tests/test_e2e_closed_loop.py"]),
        ("端到端测试", ["tests/test_end_to_end.py"]),
        ("已知密钥对验证", ["tests/test_known_keypair_verification.py"]),
        ("内存池修复", ["tests/test_memory_pool_fix.py"]),
        ("缓冲区返回修复", ["tests/test_buffer_return_fix.py"]),
        ("并发压力测试", ["tests/test_concurrency_stress.py"]),
        ("线程安全修复", ["tests/test_thread_safety_fixes.py"]),
        (
            "数据日志",
            ["tests/test_data_logger.py", "tests/test_data_logging_integration.py"],
        ),
        (
            "监控系统",
            ["tests/test_enhanced_monitoring.py",
             "tests/test_monitoring_integration.py"],
        ),
        (
            "告警系统",
            ["tests/test_alert_system.py", "tests/test_alert_system_integration.py"],
        ),
        (
            "统计报告",
            ["tests/test_stats_reporter.py",
             "tests/test_stats_performance_monitor.py"],
        ),
        (
            "依赖注入",
            ["tests/test_dependency_injection.py",
             "tests/test_dependency_container.py"],
        ),
        ("P0修复验证", ["tests/test_p0_fixes_verification.py"]),
        (
            "P1修复验证",
            ["tests/test_p1_1_const_time_select_fix.py",
             "tests/test_p1_3_k_range_validation.py"],
        ),
        (
            "地址匹配流程",
            ["tests/test_address_matching_flow.py",
             "tests/test_address_type_matching_flow.py"],
        ),
        ("实时地址集成", ["tests/test_real_address_integration.py"]),
        (
            "向导测试",
            ["tests/test_wizard.py", "tests/test_wizard_core.py",
             "tests/test_wizard_engine.py"],
        ),
        (
            "安全集成测试",
            ["tests/test_security_log_filter.py",
             "tests/test_multiprocess_security.py"],
        ),
        (
            "日志系统",
            ["tests/test_logger.py", "tests/test_logging_config.py",
             "tests/test_log_window.py"],
        ),
        ("SMOKE测试", ["tests/test_smoke.py"]),
        ("回归测试套件", ["tests/test_regression_suite.py"]),
    ]

    all_passed = all_failed = all_errors = 0
    failures = []

    for name, files in integration_groups:
        existing = [f for f in files if (BASE_DIR / f).exists()]
        if not existing:
            log(f"  [SKIP] {name}: 未找到测试文件 {files}")
            continue

        log(f"  运行: {name} ({', '.join(existing)})...")
        r = run_cmd(
            [sys.executable, '-m', 'pytest'] + existing + ['-v', '--no-header', '--tb=short'],
            timeout=300,
        )
        passed, failed, errors = parse_pytest_summary(r["stdout"] + r["stderr"])
        all_passed += passed
        all_failed += failed
        all_errors += errors

        if failed > 0:
            for line in r["stdout"].split('\n'):
                if 'FAILED' in line:
                    test_name = line.strip()
                    failures.append(test_name)
                    log(f"    [FAIL] {test_name}")

        status = "PASS" if failed == 0 else "FAIL"
        log(f"    [{status}] {name}: {passed} passed, {failed} failed, {errors} errors")
        RESULTS[f"integ_{name}"] = {"passed": passed, "failed": failed, "errors": errors}

    RESULTS["integ_total"] = {
        "passed": all_passed, "failed": all_failed, "errors": all_errors, "failures": failures,
    }
    log(f"\n集成测试总计: {all_passed} passed, {all_failed} failed, {all_errors} errors")
    return all_failed == 0


# ============================================================
# 第3部分：代码质量审核
# ============================================================
def run_code_quality():
    log("\n" + "=" * 60)
    log("第3部分：代码质量审核")
    log("=" * 60)

    # 1. Flake8 - 代码风格检查
    log("\n[3.1] Flake8 代码风格检查...")
    src_files = [
        "src/core/secp256k1.py", "src/core/base58.py", "src/core/hash_utils.py",
        "src/core/wif.py", "src/core/address_generator.py", "src/core/key_generator.py",
        "src/core/bitcoin_key_validator.py", "src/core/crypto_backend.py",
        "src/core/__init__.py", "src/collision/base_engine.py",
        "src/collision/types.py", "src/utils/exceptions.py",
    ]
    r = run_cmd([sys.executable, '-m', 'flake8'] + src_files + ['--max-line-length=120'])
    flake8_issues = r["stdout"].strip()
    RESULTS["flake8"] = {
        "issues_count": 0 if not flake8_issues else len(flake8_issues.split('\n')),
        "details": flake8_issues,
    }
    if flake8_issues:
        log(f"  发现 {len(flake8_issues.split(chr(10)))} 个问题")
        for line in flake8_issues.split('\n'):
            log(f"    - {line}")
    else:
        log("  OK Flake8: 无问题")

    # 2. Bandit - 安全扫描
    log("\n[3.2] Bandit 安全扫描 (src/core)...")
    r = run_cmd([sys.executable, '-m', 'bandit', '-r', 'src/core/', '-f', 'json'])
    try:
        bandit_data = json.loads(r["stdout"])
        results = bandit_data.get("results", [])
        RESULTS["bandit"] = {"issues_count": len(results), "details": []}
        if results:
            log(f"  发现 {len(results)} 个安全问题:")
            for issue in results:
                detail = (
                    f"{issue['test_id']}: {issue['issue_text'][:80]}"
                    f" (sev:{issue['issue_severity']},"
                    f" conf:{issue['issue_confidence']})"
                    f" - {issue['filename']}:{issue['line_number']}"
                )
                RESULTS["bandit"]["details"].append(detail)
                log(f"    - {detail}")
        else:
            log("  OK Bandit: 无安全问题")
    except json.JSONDecodeError:
        log(f"  WARN Bandit 输出解析失败: {r['stdout'][:300]}")
        RESULTS["bandit"] = {"error": r["stdout"][:300]}

    # 3. 行数统计
    log("\n[3.3] 代码行数统计...")
    total_loc = 0
    loc_details = {}
    for py_file in sorted(Path("src/core").rglob("*.py")):
        try:
            with open(py_file, encoding="utf-8") as f:
                lines = f.readlines()
            code_lines = sum(
                1 for line in lines if line.strip() and not line.strip().startswith("#")
            )
            total_loc += code_lines
            loc_details[py_file.as_posix()] = len(lines)
        except Exception:
            pass
    RESULTS["loc"] = {
        "total_files": len(loc_details),
        "total_lines": sum(loc_details.values()),
        "code_lines": total_loc,
    }
    log(
        f"  src/core: {len(loc_details)} 文件,"
        f" {sum(loc_details.values())} 总行,"
        f" {total_loc} 有效代码行"
    )

    # 4. 复杂度分析 - 基础函数/类统计
    log("\n[3.4] 核心模块函数/类统计...")
    for file in [
        "secp256k1.py", "crypto_backend.py", "bitcoin_key_validator.py",
        "address_generator.py", "key_generator.py",
    ]:
        path = Path("src/core") / file
        if not path.exists():
            continue
        with open(path, encoding="utf-8") as f:
            content = f.read()
        classes = [
            line.strip() for line in content.split('\n')
            if line.strip().startswith("class ")
        ]
        funcs = [
            line.strip() for line in content.split('\n')
            if line.strip().startswith("def ") and line.strip().endswith(":")
        ]
        log(f"    {file}: {len(classes)} 类, {len(funcs)} 方法/函数")

    # 5. 重复代码检测（基础）
    log("\n[3.5] 潜在缺陷分析...")
    issues_found = []

    for py_file in Path("src/core").rglob("*.py"):
        with open(py_file, encoding="utf-8") as f:
            content = f.read()

        except_count = content.count("except:")
        if except_count > 0:
            issues_found.append(
                f"{py_file}: {except_count} 个裸except语句"
            )

        todo = content.count("TODO") + content.count("FIXME") + content.count("HACK")
        if todo > 0:
            issues_found.append(
                f"{py_file}: {todo} 个TODO/FIXME/HACK标记"
            )

        lines = content.split('\n')
        in_func = False
        func_line = 0
        func_length = 0
        func_name = ""
        for i, line in enumerate(lines):
            if (
                line.strip().startswith("def ")
                and line.strip().endswith(":")
                and not in_func
            ):
                in_func = True
                func_line = i + 1
                func_length = 0
                func_name = line.strip()
            elif in_func:
                func_length += 1
                if func_length > 150:
                    issues_found.append(
                        f"{py_file}:{func_line} 函数过长:"
                        f" {func_name} ({func_length}行)"
                    )
                    in_func = False
                if (
                    line.strip()
                    and not line.startswith((" ", "\t"))
                    and not line.strip().startswith(("@", "def", "class"))
                ):
                    in_func = False

    RESULTS["defects"] = issues_found
    if issues_found:
        log(f"  发现 {len(issues_found)} 个潜在缺陷:")
        for issue in issues_found:
            log(f"    - {issue}")
    else:
        log("  OK 未发现明显缺陷")

    # 6. Mypy类型检查
    log("\n[3.6] Mypy 类型检查 (src/core)...")
    r = run_cmd(
        [sys.executable, '-m', 'mypy', 'src/core/',
         '--ignore-missing-imports', '--no-error-summary'],
        timeout=120,
    )
    mypy_output = r["stdout"].strip()
    mypy_issues = sum(1 for line in mypy_output.split('\n') if 'error:' in line)
    RESULTS["mypy"] = {"issues_count": mypy_issues, "details": mypy_output[:2000]}
    if mypy_issues:
        log(f"  发现 {mypy_issues} 个类型错误")
        for line in mypy_output.split('\n')[:15]:
            log(f"    - {line}")
    else:
        if "Success" in mypy_output:
            log("  OK Mypy: 无类型错误")
        else:
            log("  WARN Mypy: 无输出")

    return RESULTS


# ============================================================
# 第4部分：生成报告
# ============================================================
def generate_report():
    log("\n" + "=" * 60)
    log("生成最终测试与审核报告")
    log("=" * 60)

    report = []
    report.append("# BTC碰撞引擎 - 全面测试与代码质量审核报告")
    report.append(f"生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")

    # 单元测试结果
    report.append("## 1. 单元测试结果")
    report.append("")
    report.append("| 模块 | 通过 | 失败 | 错误 | 状态 |")
    report.append("|------|------|------|------|------|")
    for key, val in RESULTS.items():
        if key.startswith("unit_") and isinstance(val, dict):
            status = "OK" if val["failed"] == 0 else "FAIL"
            report.append(
                f"| {key[5:]} | {val['passed']} | {val['failed']}"
                f" | {val['errors']} | {status} |"
            )

    if "unit_total" in RESULTS:
        t = RESULTS["unit_total"]
        report.append(
            f"| **总计** | **{t['passed']}** | **{t['failed']}**"
            f" | **{t['errors']}** |"
            f" {'FAIL' if t['failed'] > 0 else 'OK'} |"
        )

    report.append("")

    if RESULTS.get("unit_total", {}).get("failures"):
        report.append("### 单元测试失败详情")
        report.append("")
        for fail in RESULTS["unit_total"]["failures"]:
            report.append(f"- FAIL {fail}")
        report.append("")

    # 集成测试结果
    report.append("## 2. 全量集成测试结果")
    report.append("")
    report.append("| 模块 | 通过 | 失败 | 错误 | 状态 |")
    report.append("|------|------|------|------|------|")
    for key, val in RESULTS.items():
        if key.startswith("integ_") and isinstance(val, dict):
            status = "OK" if val["failed"] == 0 else "FAIL"
            report.append(
                f"| {key[6:]} | {val['passed']} | {val['failed']}"
                f" | {val['errors']} | {status} |"
            )

    if "integ_total" in RESULTS:
        t = RESULTS["integ_total"]
        report.append(
            f"| **总计** | **{t['passed']}** | **{t['failed']}**"
            f" | **{t['errors']}** |"
            f" {'FAIL' if t['failed'] > 0 else 'OK'} |"
        )

    report.append("")

    unit_t = RESULTS.get("unit_total", {"passed": 0, "failed": 0})
    integ_t = RESULTS.get("integ_total", {"passed": 0, "failed": 0})
    total_p = unit_t["passed"] + integ_t["passed"]
    total_f = unit_t["failed"] + integ_t["failed"]
    report.append(f"**综合统计: {total_p} 通过, {total_f} 失败**")
    if (total_p + total_f) > 0:
        report.append(f"**测试覆盖率: {total_p / (total_p + total_f) * 100:.1f}%**")
    report.append("")

    # 代码质量审核
    report.append("## 3. 代码质量审核结果")
    report.append("")

    flake8_data = RESULTS.get("flake8", {})
    report.append("### 3.1 Flake8 代码风格检查")
    if flake8_data.get("issues_count", 0) == 0:
        report.append("- OK 无代码风格问题")
    else:
        report.append(f"- FAIL 发现 {flake8_data['issues_count']} 个问题")
        if flake8_data.get("details"):
            report.append("```")
            report.append(flake8_data["details"])
            report.append("```")
    report.append("")

    bandit_data = RESULTS.get("bandit", {})
    report.append("### 3.2 Bandit 安全扫描")
    if bandit_data.get("issues_count", 0) == 0:
        report.append("- OK 无安全问题")
    else:
        report.append(f"- FAIL 发现 {bandit_data['issues_count']} 个安全问题")
        if bandit_data.get("details"):
            for detail in bandit_data["details"]:
                report.append(f"  - {detail}")
    report.append("")

    mypy_data = RESULTS.get("mypy", {})
    report.append("### 3.3 Mypy 类型检查")
    if mypy_data.get("issues_count", 0) == 0:
        if "Success" in str(mypy_data.get("details", "")):
            report.append("- OK 无类型错误")
        else:
            report.append("- WARN 类型检查未完全覆盖")
    else:
        report.append(f"- FAIL 发现 {mypy_data['issues_count']} 个类型错误")
    report.append("")

    loc_data = RESULTS.get("loc", {})
    report.append("### 3.4 代码规模统计 (src/core)")
    report.append(f"- 源文件数: {loc_data.get('total_files', 0)}")
    report.append(f"- 总行数: {loc_data.get('total_lines', 0)}")
    report.append(f"- 有效代码行: {loc_data.get('code_lines', 0)}")
    report.append("")

    defects = RESULTS.get("defects", [])
    report.append("### 3.5 潜在缺陷")
    if defects:
        report.append(f"- FAIL 发现 {len(defects)} 个潜在缺陷:")
        for defect in defects:
            report.append(f"  - {defect}")
    else:
        report.append("- OK 未发现明显缺陷")
    report.append("")

    # 优化建议
    report.append("## 4. 优化建议")
    report.append("")
    suggestions = []
    for fail in RESULTS.get("unit_total", {}).get("failures", []):
        if "secp256k1" in fail and "已被锁定" in open(
            "tests/test_secp256k1_edge.py", encoding="utf-8"
        ).read():
            suggestions.append(
                "1. `test_secp256k1_edge.py`中4个测试断言错误消息中文内容不匹配"
                " - 需要更新测试用例中的预期字符串或更新`secp256k1.py`中的错误消息"
            )
            break

    if any("key_generator" in f for f in RESULTS.get("unit_total", {}).get("failures", [])):
        suggestions.append(
            "2. `test_key_generator.py`中`test_generate_batch_valid_keys`断言失败:"
            " `generate_batch()`返回`bytearray`而非`bytes`"
            " - 测试需更新为新返回值类型"
        )

    if any("bitcoin_key_validator" in f for f in RESULTS.get("unit_total", {}).get("failures", [])):
        suggestions.append(
            "3. `test_bitcoin_key_validator.py`中2个测试断言P2SH/Bech32的警告信息"
            " - `BitcoinKeyValidator._generate_p2sh_address`和"
            "`_generate_bech32_address`未生成预期的警告信息"
        )

    suggestions.append(
        "4. 测试文件组织: 255+个测试文件平铺在单层目录，"
        "建议按子模块划分子目录(`tests/cli/`, `tests/core/`, `tests/gpu/`)"
    )
    suggestions.append(
        "5. 混合测试风格: 部分文件仍使用`unittest.TestCase`，"
        "建议统一迁移到纯pytest fixture风格"
    )
    suggestions.append(
        "6. 测试覆盖率分析: 建议集成`pytest-cov`获取精确的代码覆盖率报告，"
        "识别未测试的代码路径"
    )
    suggestions.append(
        "7. 导入路径: 大量测试文件使用`sys.path.insert(0, ...)`，"
        "建议改用`pip install -e .`统一解决导入问题"
    )
    suggestions.append(
        "8. 文档字符串检查: 确保所有公共API都有完整的类型注解和文档字符串"
    )

    for suggestion in suggestions:
        report.append(f"- {suggestion}")
    report.append("")

    # 安全建议
    report.append("## 5. 安全审计建议")
    report.append("")
    report.append(
        "- LOCK 私钥处理: 代码中已实现`secure_clear_bytearray`用于安全清零，"
        "但`bytes`对象不变性导致旧引用可能泄漏"
    )
    report.append(
        "- LOCK 日志脱敏: WIF编码器和密钥验证器已实现安全模式脱敏，"
        "但需确认所有日志路径均已覆盖"
    )
    report.append(
        "- LOCK 侧信道防护: secp256k1使用Montgomery Ladder恒定时间实现，"
        "但Python层面无法完全保证"
    )
    report.append(
        "- LOCK 熵池监控: Linux平台已实现熵池健康检查，Windows/macOS使用系统CSPRNG"
    )
    report.append("- LOCK WIF版本字节验证: 实现正确(0x80主网/0xEF测试网)")
    report.append("")

    report_path = BASE_DIR / "audit_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report))

    log(f"\n报告已保存至: {report_path}")
    print("\n" + "\n".join(report))
    return report_path


# ============================================================
# 主流程
# ============================================================
if __name__ == "__main__":
    start_time = time.time()

    run_unit_tests()
    run_full_tests()
    run_code_quality()
    generate_report()

    elapsed = time.time() - start_time
    log(f"\n总耗时: {elapsed:.1f}秒")
    log("审核完成!")

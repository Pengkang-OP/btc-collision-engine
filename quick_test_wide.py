"""更广泛地测试所有之前可能有问题的文件"""
import sys
import subprocess

files = [
    "tests/unit/crypto/test_secp256k1_comprehensive.py",
    "tests/unit/crypto/test_secp256k1_edge.py",
    "tests/unit/crypto/test_secp256k1_extended.py",
    "tests/unit/crypto/test_wif_edge.py",
    "tests/unit/crypto/test_key_generator.py",
    "tests/unit/crypto/test_crypto_backend.py",
    "tests/unit/crypto/test_crypto_backend_edge.py",
    "tests/unit/crypto/test_base58_edge.py",
    "tests/unit/crypto/test_address_generator_edge.py",
    "tests/unit/crypto/test_crypto_config.py",
    "tests/unit/crypto/test_bitcoin_key_validator.py",
    "tests/unit/crypto/test_key_collision_engine.py",
    "tests/unit/config/test_config_manager.py",
    "tests/unit/config/test_config_manager_advanced.py",
    "tests/unit/config/test_config_hot_reload.py",
    "tests/unit/config/test_config_validation_consistency.py",
    "tests/unit/cli/test_output.py",
    "tests/unit/engine/test_engine_checkpoint.py",
    "tests/unit/logging/test_log_compatibility.py",
    "tests/unit/web/test_web.py",
    "tests/test_multi_gpu.py",
    "tests/test_driver_manager.py",
    "tests/test_data_storage.py",
    "tests/test_p1_5_live_range_count_fix.py",
]

for f in files:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", f, "--timeout=60", "--tb=line", "-q"],
        capture_output=True, text=True, cwd="f:/Qoder/btc-collision-engine",
        timeout=120,
    )
    lines = result.stdout.strip().split("\n")
    summary = lines[-1] if lines else "NO OUTPUT"
    # Also show FAILED/ERROR lines
    fails = [line for line in lines if 'FAILED' in line or 'ERROR' in line]
    fail_str = f" [{', '.join(fails)}]" if fails else ""
    print(f"{f:60s} => {summary}{fail_str}")

"""快速运行 test_data_storage.py 并显示错误"""
import sys
import subprocess

result = subprocess.run(
    [sys.executable, "-m", "pytest", "tests/test_data_storage.py", "--timeout=60", "--tb=short"],
    capture_output=True, text=True, cwd="f:/Qoder/btc-collision-engine"
)
print(result.stdout[-3000:] if len(result.stdout) > 3000 else result.stdout)
print(result.stderr[-3000:] if len(result.stderr) > 3000 else result.stderr)
print(f"Exit code: {result.returncode}")

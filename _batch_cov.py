"""Run pytest with coverage in batches, appending coverage data each time."""
import subprocess
import sys
import os
import glob

os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTEST_NO_FORCE_EXIT"] = "1"

# Clean up old coverage
cov_file = ".coverage"
if os.path.exists(cov_file):
    os.remove(cov_file)

# Collect all non-GPU test files
test_dir = "tests"
all_tests = sorted(glob.glob(f"{test_dir}/test_*.py"))
# Filter out GPU tests
gpu_kw = ("gpu", "intel")
non_gpu = [t for t in all_tests
           if not any(k in os.path.basename(t) for k in gpu_kw)]
# Add the non-gpu non-test_ files
extra = [
    "tests/monitoring_logging_test.py",
    "tests/comprehensive_test.py",
    "tests/performance_test.py",
    "tests/production_test.py",
]
for e in extra:
    if os.path.exists(e) and e not in non_gpu:
        non_gpu.append(e)

print(f"Total non-GPU test files: {len(non_gpu)}")

# Split into batches of ~30 test files each
batch_size = 30
batches = [non_gpu[i:i + batch_size] for i in range(0, len(non_gpu), batch_size)]
print(f"Split into {len(batches)} batches of up to {batch_size} files each")

log_file = "test_results/cov_batch_log.txt"
total = len(batches)
success_count = 0

with open(log_file, "w", encoding="utf-8") as log:
    sep = "=" * 60
    for idx, batch in enumerate(batches):
        batch_num = idx + 1
        print(f"\n{sep}")
        print(f"Batch {batch_num}/{total}: {len(batch)} test files")
        print(sep)
        log.write(f"\n{sep}\n")
        log.write(f"Batch {batch_num}/{total}: {len(batch)} test files\n")
        log.write(f"{sep}\n")
        log.flush()

        cmd = [
            sys.executable, "-m", "pytest",
            "--tb=no", "-q", "--no-header",
            "-p", "no:cacheprovider",
            "--cov=src", "--cov-append",
            "--cov-report=",
        ] + batch

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )

            line_count = 0
            for line in proc.stdout:
                line_count += 1
                if line_count % 100 == 0:
                    # Print progress dot every 100 lines
                    print(".", end="", flush=True)
                log.write(line)

            proc.wait()
            rc = proc.returncode
            print(f" [exit={rc}]")
            log.write(f"\nExit code: {rc}\n")
            log.flush()
            success_count += 1

        except Exception as ex:
            print(f" ERROR: {ex}")
            log.write(f"ERROR: {ex}\n")
            log.flush()

print(f"\n\n{'=' * 60}")
print(f"Completed {success_count}/{total} batches")
print(f"Log: {log_file}")
print(f"Coverage data: {cov_file}")

# Now run coverage report
print("\nGenerating coverage report...")
report_file = "test_results/cov_batch_report.txt"
cmd = [sys.executable, "-m", "coverage", "report", "--show-missing"]
with open(report_file, "w", encoding="utf-8") as rf:
    proc = subprocess.run(cmd, stdout=rf, stderr=subprocess.STDOUT, text=True)
print(f"Report: {report_file}")
print("Done!")

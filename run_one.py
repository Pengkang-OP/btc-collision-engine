import subprocess
import sys
import os

os.chdir(r"f:\Qoder\btc-collision-engine")

result = subprocess.run(
    [sys.executable, "-m", "pytest",
     "tests/acceptance/test_acceptance_pipeline.py::TestKeyGenerationPipeline::test_pipeline_address_generation_to_collision_detection",
     "-v", "--tb=short", "--no-header"],
    capture_output=True,
    text=True,
    timeout=30,
)

output = result.stdout + result.stderr
for line in output.split('\n'):
    if any(kw in line for kw in ['PASSED', 'FAILED', 'ERROR', 'assert ']):
        print(line[:200])
print(f"RC: {result.returncode}")

import subprocess
import sys
import os
import re

os.chdir(r"f:\Qoder\btc-collision-engine")

result = subprocess.run(
    [sys.executable, "-m", "pytest", "tests/acceptance/",
     "tests/acceptance/test_acceptance_pipeline.py::TestKeyGenerationPipeline::test_pipeline_address_generation_to_collision_detection",
     "-q", "--tb=short", "--no-header"],
    capture_output=True,
    text=True,
    timeout=60,
)

all_output = result.stdout + result.stderr
print(all_output[-1000:])

match = re.search(r'(\d+)\s+failed.*?(\d+)\s+passed.*?(\d+)\s+skipped', all_output)
if match:
    print(f"\n=== {match.group(1)} failed, {match.group(2)} passed, {match.group(3)} skipped ===")

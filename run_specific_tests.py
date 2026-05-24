import subprocess
import sys

tests = [
    "tests/acceptance/test_acceptance_pipeline.py::TestKeyGenerationPipeline::test_pipeline_key_generation_to_address_generation",
    "tests/acceptance/test_acceptance_lifecycle.py::TestDeduplicationFilterLifecycle::test_lifecycle_checking",
    "tests/acceptance/test_acceptance_engine.py::TestKeyCollisionEngineLogicLayer::test_logic_batch_size_auto_tune",
    "tests/acceptance/test_acceptance_engine.py::TestKeyCollisionEngineMultiState::test_state_initialized",
]

result = subprocess.run(
    [sys.executable, "-m", "pytest"] + tests + ["-v", "--tb=short", "--no-header"],
    capture_output=True,
    text=True,
    cwd=r"f:\Qoder\btc-collision-engine",
)

output = result.stdout + "\n" + result.stderr
# Print only relevant lines
for line in output.split('\n'):
    if any(kw in line for kw in ['PASSED', 'FAILED', 'ERROR', 'AssertionError', 'Error', 'assert', 'E ']):
        print(line)
print(f"\nSummary: {result.returncode}")

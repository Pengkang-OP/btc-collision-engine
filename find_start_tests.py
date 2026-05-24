import re

files = [
    "tests/acceptance/test_acceptance_engine.py",
    "tests/acceptance/test_acceptance_pipeline.py",
]

for f in files:
    with open(f, "r") as fh:
        content = fh.readlines()
    
    print(f"\n=== {f} ===")
    for i, line in enumerate(content, 1):
        if "engine.start()" in line or "engine.start(" in line:
            # Find the enclosing test method
            for j in range(i-1, max(0, i-30), -1):
                if "def test_" in content[j]:
                    print(f"  Line {i}: engine.start() in {content[j].strip()} at line {j+1}")
                    break

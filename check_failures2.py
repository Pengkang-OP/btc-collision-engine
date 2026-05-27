"""Find actual collection errors in the CI output."""

with open("ci_collect_output.txt", "r", encoding="utf-8") as f:
    lines = f.readlines()

results = []
for i, line in enumerate(lines):
    stripped = line.strip()
    if stripped.startswith("ERROR ") or "ERROR collecting" in stripped or stripped == "ERRORS":
        results.append(f"{i + 1}:{stripped}")
        for j in range(i + 1, min(i + 5, len(lines))):
            results.append(f"  {j + 1}:{lines[j].rstrip()}")
        results.append("")

with open("ci_errors_found.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(results) if results else "No collection errors found!")

print(f"Found {len(results)} lines, written to ci_errors_found.txt")

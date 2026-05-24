import os
import re
from collections import Counter

os.chdir(r"f:\Qoder\btc-collision-engine")
test_dir = "tests/acceptance"

skip_pattern = re.compile(r'@pytest\.mark\.skip\(reason=[\'"](.+?)[\'"]\)')

reasons = Counter()
by_file = Counter()
class_in_skip = False

for root, dirs, files in os.walk(test_dir):
    for fname in sorted(files):
        if not fname.endswith('.py'):
            continue
        fpath = os.path.join(root, fname)
        with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        
        # Find all skip reasons
        lines = content.split('\n')
        for i, line in enumerate(lines):
            m = skip_pattern.search(line)
            if m:
                reason = m.group(1)
                # Check if this is a class-level skip (next non-empty line has 'class ')
                if '@pytest.mark.skip' in line:
                    # Look ahead for class or def
                    for j in range(i+1, min(i+5, len(lines))):
                        if 'class ' in lines[j] and 'Test' in lines[j]:
                            reasons[f"[CLASS] {reason}"] += 1
                            break
                        elif 'def test_' in lines[j]:
                            reasons[reason] += 1
                            break
                    else:
                        reasons[reason] += 1
                
                short = fname.replace('test_acceptance_', '')
                by_file[short] += 1

print(f"{'='*70}")
print(f"162 个跳过测试 — 精准分类")
print(f"{'='*70}")

total = sum(reasons.values())
print(f"\n总计: {total} skips\n")

for reason, count in reasons.most_common():
    pct = count / total * 100
    label = reason[:90]
    print(f"  [{count:3d}] ({pct:4.1f}%) {label}")

print(f"\n{'='*70}")
print("按文件分布:")
print(f"{'='*70}")
for fname, count in by_file.most_common():
    print(f"  [{count:3d}] {fname}")

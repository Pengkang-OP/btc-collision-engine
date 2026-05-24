import os
os.chdir(r"f:\Qoder\btc-collision-engine")

# Try different encodings
for enc in ['utf-8', 'utf-16', 'utf-16-le', 'cp1252', 'gbk']:
    try:
        with open('test_result.txt', 'r', encoding=enc) as f:
            content = f.read()
        # Print last 30 lines
        lines = content.strip().split('\n')
        for line in lines[-30:]:
            print(line[:200])
        break
    except:
        continue

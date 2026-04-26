import json

try:
    with open(r'F:\Qoder\btc-collision-tools\src\i18n\locales\zh_CN.json') as f:
        zh_data = json.load(f)
    print("[OK] zh_CN.json is valid JSON")
except Exception as e:
    print(f"[ERROR] zh_CN.json: {e}")

try:
    with open(r'F:\Qoder\btc-collision-tools\src\i18n\locales\en_US.json') as f:
        en_data = json.load(f)
    print("[OK] en_US.json is valid JSON")
except Exception as e:
    print(f"[ERROR] en_US.json: {e}")

# Compare keys
def get_all_keys(d, prefix=""):
    keys = set()
    for k, v in d.items():
        full_key = f"{prefix}.{k}" if prefix else k
        keys.add(full_key)
        if isinstance(v, dict):
            keys.update(get_all_keys(v, full_key))
    return keys

zh_keys = get_all_keys(zh_data)
en_keys = get_all_keys(en_data)

print(f"\nzh_CN keys: {len(zh_keys)}")
print(f"en_US keys: {len(en_keys)}")

missing_in_en = zh_keys - en_keys
missing_in_zh = en_keys - zh_keys

if missing_in_en:
    print(f"\n[WARN] Missing in en_US: {list(missing_in_en)[:5]}")
if missing_in_zh:
    print(f"\n[WARN] Missing in zh_CN: {list(missing_in_zh)[:5]}")
    
if not missing_in_en and not missing_in_zh:
    print("\n[OK] All keys match between zh_CN and en_US")

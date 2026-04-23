"""验证 vendor 匹配修复：configure_for_device 路由正确性"""
import sys, logging
sys.path.insert(0, '.')
logging.disable(logging.CRITICAL)
from src.gpu.auto_config import GPUAutoConfigurator

c = GPUAutoConfigurator()

cases = [
    # (label, device_dict, expected_branch, expected_enable_async, expected_workaround)
    ('NVIDIA full name',    {'vendor': 'NVIDIA Corporation',           'name': 'GTX 1660 Ti', 'global_mem_size': 6*1024**3},  'NVIDIA', True,  False),
    ('NVIDIA short',        {'vendor': 'nvidia',                       'name': 'RTX 3090',    'global_mem_size': 24*1024**3}, 'NVIDIA', True,  False),
    ('Intel full name (A770)', {'vendor': 'Intel(R) Corporation',      'name': 'Intel(R) Arc(TM) A770 Graphics', 'global_mem_size': 15*1024**3}, 'INTEL', True, True),
    ('Intel short',         {'vendor': 'intel',                        'name': 'Arc A750',    'global_mem_size': 8*1024**3},  'INTEL',  True,  True),
    ('Intel OpenCL variant', {'vendor': 'Intel(R) OpenCL',             'name': 'Intel HD',    'global_mem_size': 2*1024**3},  'INTEL',  True,  True),
    ('AMD full name',       {'vendor': 'Advanced Micro Devices, Inc.', 'name': 'RX 6800 XT',  'global_mem_size': 16*1024**3}, 'AMD',    True,  False),
    ('AMD short',           {'vendor': 'amd',                          'name': 'RX 580',       'global_mem_size': 8*1024**3},  'AMD',    True,  False),
    ('Unknown vendor',      {'vendor': 'SomeOtherVendor',              'name': 'Unknown GPU',  'global_mem_size': 4*1024**3},  'UNKNOWN',False, False),
    ('Empty vendor',        {'vendor': '',                             'name': 'No vendor',    'global_mem_size': 4*1024**3},  'UNKNOWN',False, False),
]

print(f"{'测试场景':<32} {'分支':^8} {'async':^6} {'workaround':^10} {'状态':^6}")
print('-' * 68)

passed = 0
failed = 0

for label, dev, exp_branch, exp_async, exp_workaround in cases:
    cfg = c.configure_for_device(dev)
    vendor_l = dev.get('vendor', '').lower()
    if 'nvidia' in vendor_l:
        branch = 'NVIDIA'
    elif 'amd' in vendor_l or 'advanced micro' in vendor_l:
        branch = 'AMD'
    elif 'intel' in vendor_l:
        branch = 'INTEL'
    else:
        branch = 'UNKNOWN'

    ok_branch    = branch == exp_branch
    ok_async     = cfg['enable_async'] == exp_async
    ok_workaround = cfg['use_uint32_workaround'] == exp_workaround
    ok = ok_branch and ok_async and ok_workaround

    status = 'PASS' if ok else 'FAIL'
    if ok:
        passed += 1
    else:
        failed += 1

    print(f"{label:<32} {branch:^8} {str(cfg['enable_async']):^6} {str(cfg['use_uint32_workaround']):^10} {status:^6}")
    if not ok:
        if not ok_branch:
            print(f"  [!] branch: got={branch}, want={exp_branch}")
        if not ok_async:
            print(f"  [!] enable_async: got={cfg['enable_async']}, want={exp_async}")
        if not ok_workaround:
            print(f"  [!] workaround: got={cfg['use_uint32_workaround']}, want={exp_workaround}")

print('-' * 68)
print(f"结果: {passed} PASS / {failed} FAIL / {len(cases)} 总计")

# 额外验证：Intel Arc A770 的 batch_size 和 work_group_size
arc_dev = {'vendor': 'Intel(R) Corporation', 'name': 'Intel(R) Arc(TM) A770 Graphics', 'global_mem_size': 15*1024**3}
arc_cfg = GPUAutoConfigurator().configure_for_device(arc_dev)
print()
print("Intel Arc A770 完整配置验证:")
print(f"  batch_size      = {arc_cfg['batch_size']:,}   (期望 262144)")
print(f"  work_group_size = {arc_cfg['work_group_size']}       (期望 512)")
print(f"  enable_async    = {arc_cfg['enable_async']}      (期望 True)")
print(f"  workaround      = {arc_cfg['use_uint32_workaround']}      (期望 True)")
assert arc_cfg['batch_size'] == 262144,    f"batch_size 错误: {arc_cfg['batch_size']}"
assert arc_cfg['work_group_size'] == 512,  f"work_group_size 错误: {arc_cfg['work_group_size']}"
assert arc_cfg['enable_async'] == True,    f"enable_async 错误"
assert arc_cfg['use_uint32_workaround'] == True, "workaround 错误"
print("  Arc A770 所有关键字段: PASS")

sys.exit(failed)

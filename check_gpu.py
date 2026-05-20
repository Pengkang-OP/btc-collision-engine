#!/usr/bin/env python3
"""GPU 检测脚本"""

import sys
sys.path.insert(0, ".")

from src.gpu.device import GPUDeviceDetector

print("=" * 60)
print("  Intel Arc OpenCL Detection")
print("=" * 60)

try:
    devices = GPUDeviceDetector.detect_devices()
    print(f"\nDetected {len(devices)} GPU device(s):\n")

    for i, d in enumerate(devices):
        name = d.get("name", "Unknown")
        platform = d.get("platform", "Unknown")
        device_type = d.get("type", "Unknown")
        print(f"  [{i}] {name}")
        print(f"      Platform: {platform}")
        print(f"      Type: {device_type}")

        if "Intel" in name or "Arc" in name:
            print(f"      [OK] Intel Arc GPU detected")

        opencl = d.get("opencl_available", False)
        lz = d.get("level_zero_available", False)
        print(f"      OpenCL: {'Available' if opencl else 'Not Available'}")
        print(f"      Level Zero: {'Available' if lz else 'Not Available'}")
        print()

    if not devices:
        print("  [WARN] No GPU devices detected")
        print("  Possible causes:")
        print("    1. Intel Arc driver not installed")
        print("    2. OpenCL runtime not installed")
        print("    3. Need Intel oneAPI Base Toolkit")

except Exception as e:
    print(f"\n[ERROR] GPU detection failed: {e}")
    import traceback
    traceback.print_exc()

print("=" * 60)

"""Detect all GPU devices - write to file to avoid encoding issues."""
import sys, os
sys.stdout = open(os.path.join(os.path.dirname(__file__), '_gpu_list.txt'), 'w', encoding='utf-8')
sys.stderr = sys.stdout

try:
    from src.gpu.device import GPUDeviceDetector
    devices = GPUDeviceDetector.detect_devices()
    print(f"Total devices: {len(devices)}")
    for i, d in enumerate(devices):
        name = d.get("name", "Unknown")
        vendor = d.get("vendor", "Unknown")
        platform = d.get("platform", "Unknown")
        mem = d.get("global_mem_size", 0) / (1024**3)
        vtype = d.get("device_type", "Unknown")
        print(f"Device[{i}]: {name}")
        print(f"  vendor={vendor}  platform={platform}  mem={mem:.1f}GB  type={vtype}")
        print(f"  opencl_device={d.get('device','N/A')}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    sys.stdout.close()

"""Direct test of MultiGPUCollisionEngine with cross-vendor GPUs."""
import sys, os, time

sys.stdout = open(os.path.join(os.path.dirname(__file__), '_multi_gpu_direct.txt'), 'w', encoding='utf-8')
sys.stderr = sys.stdout

targets = {'1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'}

try:
    from src.gpu.multi_gpu_engine import MultiGPUCollisionEngine

    print("=" * 60)
    print("MultiGPUCollisionEngine Cross-Vendor Test")
    print("=" * 60)

    # Test 1: Auto-detect all GPUs
    print("\n[Test 1] Auto-detect all GPUs")
    engine = MultiGPUCollisionEngine()
    engine.initialize(device_count=2)
    print(f"Devices detected: {len(engine._devices)}")
    for i, d in enumerate(engine._devices):
        print(f"  Device[{i}]: {d.get('name','?')} | {d.get('vendor','?')} | {d.get('platform','?')}")

    try:
        engine.start(targets=targets, mode='random', total_keys=2000000)
        print("Engine started successfully")
        time.sleep(3)
        stats = engine.get_combined_stats()
        total_k = stats.get('total_keys_checked', 0)
        speed = stats.get('throughput', 0)
        print(f"Stats: {total_k:,} keys | {speed:,.0f} keys/s")
        engine.stop()
        print("Engine stopped OK")
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)
    print("Test Complete")
    print("=" * 60)

except Exception as e:
    print(f"FATAL: {e}")
    import traceback
    traceback.print_exc()
finally:
    sys.stdout.close()

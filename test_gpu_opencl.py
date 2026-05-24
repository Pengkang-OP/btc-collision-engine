#!/usr/bin/env python3
"""GPU OpenCL Kernel Compilation Test"""

import sys
import time

from src.gpu.device import GPUDevice

print("=" * 60)
print("  Intel Arc A770 OpenCL Kernel Compilation Test")
print("=" * 60)

# Initialize GPU
print("\n[1/3] Initializing GPU device...")
gpu = GPUDevice()

try:
    start = time.time()
    gpu.initialize(device_index=1)  # Intel Arc A770 at index 1
    init_time = time.time() - start
    print(f"    GPU initialized in {init_time:.2f}s")
    print(f"    Device: {gpu.device_info['name']}")
    print(f"    Platform: {gpu.device_info['platform']}")
except Exception as e:
    print(f"    [ERROR] GPU init failed: {e}")
    sys.exit(1)

# Test simple kernel compilation
print("\n[2/3] Testing simple kernel compilation...")
test_kernel = """
__kernel void test_add(__global float* output, __global float* input, float scalar) {
    int id = get_global_id(0);
    output[id] = input[id] + scalar;
}
"""

try:
    import pyopencl as cl
    
    start = time.time()
    program = cl.Program(gpu.context, test_kernel).build()
    build_time = time.time() - start
    print(f"    Simple kernel compiled in {build_time:.2f}s")
    print(f"    [OK] OpenCL kernel compilation working")
except Exception as e:
    print(f"    [ERROR] Kernel compilation failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test with actual execution
print("\n[3/3] Testing kernel execution with data transfer...")
try:
    import numpy as np
    
    # Create test data
    input_data = np.random.rand(1000).astype(np.float32)
    output_data = np.zeros(1000, dtype=np.float32)
    
    mf = cl.mem_flags
    input_buf = cl.Buffer(gpu.context, mf.READ_ONLY | mf.COPY_HOST_PTR, hostbuf=input_data)
    output_buf = cl.Buffer(gpu.context, mf.WRITE_ONLY, output_data.nbytes)
    
    # Create kernel with proper arguments
    kernel = cl.Kernel(program, "test_add")
    kernel.set_args(output_buf, input_buf, np.float32(5.0))
    
    # Execute
    start = time.time()
    cl.enqueue_nd_range_kernel(gpu.queue, kernel, (1000,), None)
    gpu.queue.finish()
    exec_time = time.time() - start
    
    # Read back results
    cl.enqueue_copy(gpu.queue, output_data, output_buf)
    gpu.queue.finish()
    
    # Verify
    expected = input_data + 5.0
    if np.allclose(output_data, expected, rtol=1e-5):
        print(f"    Kernel executed and verified in {exec_time*1000:.2f}ms")
        print(f"    [OK] Data transfer and execution working")
    else:
        print(f"    [WARN] Results don't match expected values")
    
except Exception as e:
    print(f"    [ERROR] Execution test failed: {e}")
    import traceback
    traceback.print_exc()

# Cleanup
gpu.cleanup()

print("\n" + "=" * 60)
print("  OpenCL Compilation Test Complete")
print("=" * 60)

#!/usr/bin/env python3
"""GPU Engine Debug Test"""

import os
os.environ['PYOPENCL_COMPILER_OUTPUT'] = '1'

import sys
sys.path.insert(0, '.')
import time
import traceback
import threading

output_file = "test_output.txt"

def log(msg):
    with open(output_file, "a", encoding="utf-8") as f:
        f.write(str(msg) + "\n")
    print(msg)

try:
    from src.collision.gpu.engine import GPUCollisionEngine
    from src.collision.collision_stats import CollisionStats

    # Test targets (mock)
    test_targets = {"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"}  # Genesis block address

    log("=" * 60)
    log("  GPU Engine Debug Test")
    log("=" * 60)
    log("")

    log("[1/6] Creating engine instance...")
    start = time.time()
    engine = GPUCollisionEngine(
        targets=test_targets,
        batch_size=1000000,
    )
    log(f"    Engine created in {time.time() - start:.2f}s")
    log(f"    engine.stats id: {id(engine.stats)}")
    log(f"    engine._core.stats id: {id(engine._core.stats)}")
    log(f"    Same object: {engine.stats is engine._core.stats}")

    log("")
    log("[2/6] Checking search mode stats reference...")
    coordinator = engine._search_coordinator
    random_mode = coordinator.get_mode_instance("random")
    log(f"    random_mode.engine.stats id: {id(random_mode.engine.stats)}")
    log(f"    Same as engine.stats: {random_mode.engine.stats is engine.stats}")

    log("")
    log("[3/6] Starting engine in thread...")
    engine.start(mode="random")
    log(f"    Engine started")
    log(f"    engine.stats.start_time: {engine.stats.start_time}")
    
    # Check stats in a loop
    log("")
    log("[4/6] Monitoring stats for 5 seconds...")
    for i in range(10):
        time.sleep(0.5)
        stats_id = id(engine.stats)
        total = engine.stats.total_checked
        elapsed = engine.stats.elapsed
        running = engine._running
        stop_set = engine._stop_event.is_set()
        log(f"    [{i*0.5:.1f}s] total_checked={total}, elapsed={elapsed:.2f}, running={running}, stop={stop_set}")
        
        if stop_set:
            log("    Stop event was set - checking for errors...")
            break
    
    log("")
    log("[5/6] Final stats...")
    log(f"    total_checked: {engine.stats.total_checked}")
    log(f"    elapsed: {engine.stats.elapsed}")
    log(f"    speed: {engine.stats.speed}")
    log(f"    matches: {len(engine.stats.matches)}")

    log("")
    log("[6/6] Stopping engine...")
    engine.stop(timeout=5)

    log("")
    log("=" * 60)
    log("  Test completed!")
    log("=" * 60)

except Exception as e:
    log(f"\n[ERROR] Test failed: {e}")
    traceback.print_exc()

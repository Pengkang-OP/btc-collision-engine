#!/usr/bin/env python3
"""测试 GPU 引擎初始化"""
import sys
sys.argv = ['key_collision_cli.py', '-t', '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa', '-m', 'random', '--use-gpu', '--gpu-device', '1', '--duration', '5']

from src.cli.arg_parser import parse_args
from src.cli.engine_builder import build_engine

args = parse_args()
print('=== Testing GPU Engine Build ===')
print(f'use_gpu: {args.use_gpu}')
print(f'gpu_device: {args.gpu_device}')

targets = ['1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa']
try:
    engine, engine_type = build_engine(args, targets, on_progress=lambda s: None, on_match=lambda a,b,c: None)
    print(f'Engine built successfully!')
    print(f'Engine type: {engine_type}')
except Exception as e:
    print(f'Error building engine: {e}')
    import traceback
    traceback.print_exc()

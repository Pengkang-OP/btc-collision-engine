#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CLI高级功能扩展模块

包含:
- 配置模板系统
- 参数智能推荐
- 进度数据导出
- 匹配结果导出
- GPU错误处理增强
"""

import json
import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any


# ─────────────────────────────────────────────────────────────────────────────
# 配置模板系统
# ─────────────────────────────────────────────────────────────────────────────

CONFIG_TEMPLATES = {
    'gpu-performance': {
        'name': 'GPU性能优化配置',
        'description': '适用于单GPU高性能碰撞场景',
        'updates': {
            'collision': {
                'use_performance_optimization': True,
                'precomputed_window_size': 8,
                'use_simd_hash': True,
                'use_memory_pool': True,
                'max_workers': 1,
            },
            'gpu': {
                'mode': 'single',
                'use_new_module': True,
                'auto_detect': True,
                'memory_usage_ratio': 0.8,
                'enable_vendor_optimizations': True,
                'auto_tuning': True,
            },
        }
    },
    'gpu-multi': {
        'name': '多GPU负载均衡配置',
        'description': '适用于多GPU并行碰撞场景',
        'updates': {
            'collision': {
                'use_performance_optimization': True,
                'precomputed_window_size': 8,
                'use_simd_hash': True,
                'use_memory_pool': True,
            },
            'gpu': {
                'mode': 'multi',
                'use_new_module': True,
                'auto_detect': True,
                'device_indices': [-1],
                'load_balancing': 'performance',
                'enable_vendor_optimizations': True,
                'auto_tuning': True,
            },
        }
    },
    'long-running': {
        'name': '长时间运行配置',
        'description': '适用于7x24小时持续碰撞场景',
        'updates': {
            'collision': {
                'checkpoint_interval': 60,
                'dedup_max_size': 10000000,
                'use_performance_optimization': True,
            },
            'monitoring': {
                'enabled': True,
                'collection_interval': 10,
                'auto_cleanup': {
                    'enabled': True,
                    'max_age_days': 7,
                },
            },
            'logging': {
                'level': 'INFO',
                'max_bytes': 52428800,
                'backup_count': 10,
                'rotation_type': 'size',
            },
        }
    },
    'quick-test': {
        'name': '快速测试配置',
        'description': '适用于功能测试和验证',
        'updates': {
            'collision': {
                'use_performance_optimization': False,
                'max_workers': 2,
                'checkpoint_interval': 10,
            },
            'monitoring': {
                'enabled': False,
            },
            'logging': {
                'level': 'DEBUG',
            },
        }
    },
}


def deep_merge(base: dict, override: dict) -> None:
    """深度合并字典"""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            deep_merge(base[key], value)
        else:
            base[key] = value


def apply_template(template_name: str, config_path: str = "config.json") -> bool:
    """
    应用配置模板
    
    Args:
        template_name: 模板名称
        config_path: 配置文件路径
        
    Returns:
        是否成功
    """
    if template_name not in CONFIG_TEMPLATES:
        print(f"\n[ERROR] 未知模板: {template_name}")
        print(f"\n[Info] 可用模板:")
        for name, info in CONFIG_TEMPLATES.items():
            print(f"   - {name}: {info['description']}")
        print(f"\n[Tip] 用法: python key_collision_cli.py --template gpu-performance")
        return False
    
    template = CONFIG_TEMPLATES[template_name]
    config_file = Path(config_path)
    
    # 加载或创建配置
    config = {}
    if config_file.exists():
        print(f"\n[Info] 加载现有配置: {config_path}")
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except Exception as e:
            print(f"[WARN] 加载失败: {e}，将创建新配置")
            config = {}
    
    # 应用模板更新
    deep_merge(config, template['updates'])
    
    # 保存配置
    try:
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        print(f"\n[OK] 模板 '{template_name}' 已应用")
        print(f"[Info] 配置名称: {template['name']}")
        print(f"[Info] 配置文件: {config_path}")
        print(f"\n[Info] 应用的配置项:")
        for section, values in template['updates'].items():
            print(f"   [{section}]")
            for key, value in values.items():
                print(f"     {key} = {value}")
        print(f"\n[Tip] 现在可以运行碰撞引擎")
        print(f"   python key_collision_cli.py -t <地址> -m random")
        return True
    except Exception as e:
        print(f"\n[ERROR] 保存配置失败: {e}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# 参数智能推荐
# ─────────────────────────────────────────────────────────────────────────────

def recommend_parameters(args) -> dict:
    """
    根据目标和系统信息推荐最优参数
    
    Args:
        args: 命令行参数
        
    Returns:
        推荐参数字典
    """
    recommendations = []
    reasons = []
    
    # 1. 根据目标数量推荐
    target_count = 0
    if args.targets:
        target_count = len(args.targets)
    elif args.file:
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                lines = [l.strip() for l in f if l.strip() and not l.startswith('#')]
                target_count = len(lines)
        except (OSError, ValueError, UnicodeDecodeError):
            pass
    
    if target_count > 10:
        recommendations.append('--dedup')
        reasons.append(f"目标地址较多 ({target_count}个)，启用去重避免重复检测")
    
    # 2. 根据模式推荐
    if args.mode == 'random':
        recommendations.append('--checkpoint')
        reasons.append("随机模式建议启用断点续传，避免中断后重新开始")
        if '--dedup' not in recommendations:
            recommendations.append('--dedup')
            reasons.append("随机模式启用去重，避免重复检测相同私钥")
    
    if args.mode in ['range', 'brute_force']:
        start_val = int(args.start, 16) if args.start else 0
        end_val = int(args.end, 16) if args.end else 0
        total_range = end_val - start_val if end_val > start_val else 0
        
        if total_range >= 2**32:  # 大于等于2^32时推荐断点续传
            recommendations.append('--checkpoint')
            recommendations.append('--checkpoint-interval')
            recommendations.append('60')
            reasons.append(f"搜索范围较大 ({total_range:,}个私钥)，建议启用断点续传")
    
    # 3. 检查GPU可用性
    try:
        import pyopencl
        recommendations.append('--use-gpu')
        reasons.append("检测到GPU可用，建议启用GPU加速（速度提升1000-2000倍）")
    except ImportError:
        reasons.append("未检测到GPU (pyopencl未安装)，使用CPU模式")
    
    # 4. 系统信息
    cpu_count = os.cpu_count() or 4
    if cpu_count > 8:
        reasons.append(f"系统CPU核心数较多 ({cpu_count}核)，可充分利用多线程")
    
    reasons.append("如需长时间运行，建议添加 --duration <秒数>")
    
    return {
        'recommendations': recommendations,
        'reasons': reasons,
        'target_count': target_count,
        'cpu_count': cpu_count,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 进度数据导出
# ─────────────────────────────────────────────────────────────────────────────

def export_progress_data(stats, mode: str, engine_type: str, 
                         output_file: str, total_range: Optional[int] = None) -> bool:
    """
    导出进度数据到JSON文件
    
    Args:
        stats: 碰撞统计数据
        mode: 碰撞模式
        engine_type: 引擎类型 (cpu/gpu/multi_gpu)
        output_file: 输出文件路径
        total_range: 总范围（可选）
        
    Returns:
        是否成功
    """
    try:
        progress_data = {
            'timestamp': __import__('time').time(),
            'mode': mode,
            'engine_type': engine_type,
            'total_checked': stats.total_checked,
            'elapsed_seconds': stats.elapsed,
            'elapsed_formatted': stats.format_elapsed(),
            'speed': stats.format_speed(),
            'matches_count': len(stats.matches),
            'matches': stats.matches,
        }
        
        if total_range and total_range > 0:
            progress_data['total_range'] = total_range
            progress_data['progress_percent'] = min(100.0, stats.total_checked / total_range * 100)
        
        output_path = Path(output_file)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(progress_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n[OK] 进度数据已导出: {output_file}")
        print(f"[Info] 总检查数: {stats.total_checked:,}")
        print(f"[Info] 运行时间: {stats.format_elapsed()}")
        print(f"[Info] 匹配数: {len(stats.matches)}")
        return True
        
    except Exception as e:
        print(f"\n[ERROR] 导出进度数据失败: {e}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# 匹配结果导出
# ─────────────────────────────────────────────────────────────────────────────

def export_matches(matches: list, output_file: str) -> bool:
    """
    导出匹配结果到JSON文件
    
    Args:
        matches: 匹配结果列表
        output_file: 输出文件路径
        
    Returns:
        是否成功
    """
    try:
        export_data = {
            'timestamp': __import__('time').time(),
            'total_matches': len(matches),
            'matches': matches
        }
        
        output_path = Path(output_file)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n[OK] 匹配结果已导出: {output_file}")
        print(f"[Info] 总匹配数: {len(matches)}")
        return True
        
    except Exception as e:
        print(f"\n[ERROR] 导出匹配结果失败: {e}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# GPU错误处理增强
# ─────────────────────────────────────────────────────────────────────────────

class GPUErrorHandler:
    """GPU错误处理器"""
    
    @staticmethod
    def handle_initialization_error(error: Exception) -> dict:
        """
        处理GPU初始化错误
        
        Args:
            error: 异常对象
            
        Returns:
            错误信息和建议
        """
        error_msg = str(error).lower()
        
        result = {
            'error': str(error),
            'type': 'unknown',
            'solution': '',
            'recoverable': False,
        }
        
        if 'no platform' in error_msg or 'no gpu' in error_msg:
            result['type'] = 'no_gpu'
            result['solution'] = '未检测到GPU设备，请检查GPU驱动是否安装'
            result['recoverable'] = False
            
        elif 'out of memory' in error_msg or 'memory' in error_msg:
            result['type'] = 'out_of_memory'
            result['solution'] = 'GPU显存不足，建议: 1) 减小--gpu-batch-size 2) 关闭其他GPU程序'
            result['recoverable'] = True
            
        elif 'driver' in error_msg or 'version' in error_msg:
            result['type'] = 'driver_issue'
            result['solution'] = 'GPU驱动版本问题，建议更新到最新驱动'
            result['recoverable'] = False
            
        else:
            result['solution'] = f'GPU初始化失败: {error}\n建议: 1) 检查GPU驱动 2) 运行 --health-check 3) 使用CPU模式'
        
        return result
    
    @staticmethod
    def suggest_batch_size_adjustment(current_size: int, error: Exception) -> int:
        """
        根据错误建议新的batch_size
        
        Args:
            current_size: 当前batch_size
            error: 异常对象
            
        Returns:
            建议的新batch_size
        """
        error_msg = str(error).lower()
        
        if 'out of memory' in error_msg:
            # 显存不足，减半
            new_size = max(1024, current_size // 2)
            print(f"[WARN] GPU显存不足，自动调整 batch_size: {current_size} -> {new_size}")
            return new_size
        
        return current_size

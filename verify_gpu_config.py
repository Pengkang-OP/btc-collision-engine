#!/usr/bin/env python3
"""
GPU配置完整性验证脚本

验证配置文件的完整性和一致性
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple


class GPUConfigValidator:
    """GPU配置验证器"""
    
    # 必需的GPU参数
    REQUIRED_GPU_PARAMS = [
        'async_execution',
        'uint32_workaround',
        'timeout_protection',
        'memory_usage_ratio',
        'gpu_memory_pool',
        'batch_size',
        'enable_vendor_optimizations'
    ]
    
    # 推荐的GPU参数
    RECOMMENDED_GPU_PARAMS = [
        'max_buffers',
        'max_memory_mb',
        'base_timeout_seconds',
        'adaptive_timeout'
    ]
    
    # 参数合理范围
    PARAM_RANGES = {
        'memory_usage_ratio': (0.5, 0.85),
        'batch_size': (65536, 2097152),
        'max_buffers': (50, 500),
        'max_memory_mb': (1024, 16384),
        'base_timeout_seconds': (10, 120)
    }
    
    @classmethod
    def validate_config(cls, config: Dict, config_name: str) -> Dict:
        """验证配置完整性
        
        Args:
            config: 配置字典
            config_name: 配置文件名称
            
        Returns:
            验证结果字典
        """
        result = {
            'config_name': config_name,
            'valid': True,
            'missing': [],
            'warnings': [],
            'errors': [],
            'score': 100
        }
        
        # 检查GPU参数
        gpu_config = config.get('gpu', {})
        optimization_config = config.get('optimization', {})
        engine_config = config.get('engine', {})
        
        # 合并配置（从gpu、optimization和engine中合并）
        merged_config = {**gpu_config}
        if optimization_config:
            # uint32_workaround, adaptive_timeout等在optimization中
            for key in ['uint32_workaround', 'adaptive_timeout', 
                       'disable_async_transfer', 'conservative_memory_policy']:
                if key in optimization_config:
                    merged_config[key] = optimization_config[key]
        
        # 从engine配置中获取batch_size（如果gpu中没有）
        if 'batch_size' not in merged_config and 'batch_size' in engine_config:
            merged_config['batch_size'] = engine_config['batch_size']
        
        # 检查必需参数
        for param in cls.REQUIRED_GPU_PARAMS:
            if param not in merged_config:
                result['missing'].append(param)
                result['valid'] = False
                result['score'] -= 12  # 每个缺失扣12分
        
        # 检查推荐参数
        for param in cls.RECOMMENDED_GPU_PARAMS:
            if param not in merged_config:
                result['warnings'].append(f"推荐参数缺失: {param}")
                result['score'] -= 3  # 每个缺失扣3分
        
        # 检查参数值范围
        for param, (min_val, max_val) in cls.PARAM_RANGES.items():
            if param in merged_config:
                value = merged_config[param]
                if isinstance(value, (int, float)):
                    if value < min_val or value > max_val:
                        result['errors'].append(
                            f"{param}={value} 超出合理范围 [{min_val}, {max_val}]"
                        )
                        result['score'] -= 10
        
        # 检查特定参数冲突
        if merged_config.get('async_execution') is False:
            result['warnings'].append(
                "async_execution=false 将导致性能下降约61%"
            )
            result['score'] -= 5
        
        if merged_config.get('uint32_workaround') is False:
            result['errors'].append(
                "uint32_workaround=false 将导致Intel Arc GPU hang bug"
            )
            result['score'] -= 15
        
        # 检查batch_size合理性
        batch_size = merged_config.get('batch_size')
        if batch_size:
            if batch_size < 262144:
                result['warnings'].append(
                    f"batch_size={batch_size} 偏小，建议 >= 262144 (256K)"
                )
                result['score'] -= 5
            elif batch_size > 1048576:
                result['warnings'].append(
                    f"batch_size={batch_size} 较大，确保显存充足"
                )
        
        # 确保分数不低于0
        result['score'] = max(0, result['score'])
        
        return result
    
    @classmethod
    def compare_configs(cls, configs: Dict[str, Dict]) -> Dict:
        """比较多个配置文件的差异
        
        Args:
            configs: {config_name: config_dict}
            
        Returns:
            比较结果
        """
        comparison = {
            'differences': [],
            'consistency_score': 100
        }
        
        if len(configs) < 2:
            return comparison
        
        # 提取所有配置的所有参数
        all_params = set()
        for config in configs.values():
            gpu_config = config.get('gpu', {})
            opt_config = config.get('optimization', {})
            all_params.update(gpu_config.keys())
            all_params.update(opt_config.keys())
        
        # 比较每个参数
        for param in sorted(all_params):
            values = {}
            for name, config in configs.items():
                gpu_config = config.get('gpu', {})
                opt_config = config.get('optimization', {})
                
                if param in gpu_config:
                    values[name] = gpu_config[param]
                elif param in opt_config:
                    values[name] = opt_config[param]
            
            # 检查是否有差异
            unique_values = set(str(v) for v in values.values())
            if len(unique_values) > 1:
                comparison['differences'].append({
                    'param': param,
                    'values': values
                })
                comparison['consistency_score'] -= 2
        
        comparison['consistency_score'] = max(0, comparison['consistency_score'])
        
        return comparison


def load_config(filepath: str) -> Dict:
    """加载配置文件"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ 加载配置文件失败 {filepath}: {e}")
        return {}


def print_validation_result(result: Dict):
    """打印验证结果"""
    print(f"\n{'='*60}")
    print(f"📋 配置文件: {result['config_name']}")
    print(f"{'='*60}")
    
    # 评分
    score = result['score']
    if score >= 90:
        emoji = "✅"
        level = "优秀"
    elif score >= 70:
        emoji = "⚠️"
        level = "良好"
    elif score >= 50:
        emoji = "❌"
        level = "中等"
    else:
        emoji = "❌"
        level = "差"
    
    print(f"\n{emoji} 完整性评分: {score}/100 ({level})")
    
    # 缺失参数
    if result['missing']:
        print(f"\n❌ 缺失参数 ({len(result['missing'])}个):")
        for param in result['missing']:
            print(f"  - {param}")
    
    # 警告
    if result['warnings']:
        print(f"\n⚠️ 警告 ({len(result['warnings'])}个):")
        for warning in result['warnings']:
            print(f"  - {warning}")
    
    # 错误
    if result['errors']:
        print(f"\n🚨 错误 ({len(result['errors'])}个):")
        for error in result['errors']:
            print(f"  - {error}")
    
    # 状态
    if result['valid']:
        print(f"\n✅ 配置验证通过")
    else:
        print(f"\n❌ 配置验证失败")


def print_comparison_result(comparison: Dict, config_names: List[str]):
    """打印比较结果"""
    print(f"\n{'='*60}")
    print(f"📊 配置文件一致性比较")
    print(f"{'='*60}")
    
    print(f"\n一致性评分: {comparison['consistency_score']}/100")
    
    if comparison['differences']:
        print(f"\n⚠️ 发现 {len(comparison['differences'])} 个参数差异:")
        for diff in comparison['differences']:
            param = diff['param']
            values = diff['values']
            print(f"\n  {param}:")
            for name, value in values.items():
                if name in config_names:
                    print(f"    - {name}: {value}")
    else:
        print(f"\n✅ 所有配置文件参数一致")


def main():
    """主函数"""
    print("🔍 GPU配置完整性验证工具")
    print("="*60)
    
    # 配置文件路径
    project_root = Path(__file__).parent
    config_files = {
        'config.intel_arc.json': project_root / 'config.intel_arc.json',
        'config.json': project_root / 'config.json',
        'config.optimized.json': project_root / 'config.optimized.json'
    }
    
    # 加载配置
    configs = {}
    for name, filepath in config_files.items():
        if filepath.exists():
            configs[name] = load_config(str(filepath))
            print(f"✅ 已加载: {filepath.name}")
        else:
            print(f"⚠️  未找到: {filepath.name}")
    
    if not configs:
        print("\n❌ 未找到任何配置文件")
        sys.exit(1)
    
    # 验证每个配置
    results = []
    for name, config in configs.items():
        result = GPUConfigValidator.validate_config(config, name)
        results.append(result)
        print_validation_result(result)
    
    # 比较配置
    if len(configs) >= 2:
        comparison = GPUConfigValidator.compare_configs(configs)
        print_comparison_result(comparison, list(configs.keys()))
    
    # 总结
    print(f"\n{'='*60}")
    print(f"📊 验证总结")
    print(f"{'='*60}")
    
    total_score = sum(r['score'] for r in results)
    avg_score = total_score / len(results) if results else 0
    
    print(f"\n平均完整性评分: {avg_score:.1f}/100")
    
    for result in results:
        score = result['score']
        if score >= 90:
            status = "✅ 优秀"
        elif score >= 70:
            status = "⚠️  良好"
        else:
            status = "❌ 需改进"
        print(f"  - {result['config_name']}: {score}/100 ({status})")
    
    # 退出码
    if all(r['valid'] for r in results):
        print(f"\n✅ 所有配置验证通过")
        sys.exit(0)
    else:
        print(f"\n❌ 部分配置验证失败，请检查缺失参数")
        sys.exit(1)


if __name__ == '__main__':
    main()

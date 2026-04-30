# -*- coding: utf-8 -*-
"""GPU配置验证器

验证GPU配置参数的合法性,提供配置建议和错误提示。
"""

import logging
from ..utils import init_logging, get_configured_logger
from typing import Dict, List, Tuple

logger = get_configured_logger("GPUConfigValidator")


class GPUConfigValidator:
    """GPU配置验证器
    
    验证GPU配置参数的合法性和合理性。
    
    使用示例:
        validator = GPUConfigValidator()
        
        # 验证配置
        is_valid, errors = validator.validate_config(config)
        
        # 获取推荐配置
        recommended = validator.suggest_config(devices)
    """
    
    # 有效GPU模式
    VALID_MODES = {'auto', 'single', 'multi'}
    
    # 有效负载均衡策略
    VALID_BALANCING = {'performance', 'equal'}
    
    # 参数范围限制
    PARAM_RANGES = {
        'batch_size': (1024, 1048576),      # 1K - 1M
        'work_group_size': (64, 2048),       # 64 - 2K
        'memory_usage_ratio': (0.1, 0.95),   # 10% - 95%
    }
    
    def __init__(self) -> None:
        """初始化配置验证器"""
        pass
    
    def validate_config(self, config: Dict) -> Tuple[bool, List[str]]:
        """验证GPU配置
        
        Args:
            config: GPU配置字典
            
        Returns:
            (is_valid, errors) 元组
        """
        errors = []
        
        # 验证模式
        mode = config.get('mode', 'auto')
        if mode not in self.VALID_MODES:
            errors.append(
                f"无效的GPU模式: '{mode}', "
                f"必须是 {self.VALID_MODES}"
            )
        
        # 验证设备索引
        device_indices = config.get('device_indices', [-1])
        if not isinstance(device_indices, list):
            errors.append("device_indices必须是列表")
        elif not device_indices:
            errors.append("device_indices不能为空")
        else:
            for idx in device_indices:
                if not isinstance(idx, int):
                    errors.append(f"设备索引必须是整数: {idx}")
                elif idx < -1:
                    errors.append(f"设备索引不能小于-1: {idx}")
        
        # 验证负载均衡策略
        balancing = config.get('load_balancing', 'performance')
        if balancing not in self.VALID_BALANCING:
            errors.append(
                f"无效的负载均衡策略: '{balancing}', "
                f"必须是 {self.VALID_BALANCING}"
            )
        
        # 验证自动调优
        auto_tuning = config.get('auto_tuning', True)
        if not isinstance(auto_tuning, bool):
            errors.append("auto_tuning必须是布尔值")
        
        # 验证每个设备的配置
        per_device_config = config.get('per_device_config', {})
        if per_device_config and isinstance(per_device_config, dict):
            for device_idx_str, device_config in per_device_config.items():
                device_errors = self._validate_device_config(
                    device_idx_str, device_config
                )
                errors.extend(device_errors)
        
        is_valid = len(errors) == 0
        
        if is_valid:
            logger.debug("GPU配置验证通过")
        else:
            logger.warning(f"GPU配置验证失败: {errors}")
        
        return is_valid, errors
    
    def _validate_device_config(
        self,
        device_idx_str: str,
        device_config: Dict
    ) -> List[str]:
        """验证单个设备的配置
        
        Args:
            device_idx_str: 设备索引(字符串)
            device_config: 设备配置字典
            
        Returns:
            错误列表
        """
        errors = []
        
        # 验证设备索引格式
        try:
            device_idx = int(device_idx_str)
            if device_idx < 0:
                errors.append(f"设备索引不能为负数: {device_idx_str}")
        except ValueError:
            errors.append(f"无效的设备索引: {device_idx_str}")
            return errors
        
        # 验证批次大小
        batch_size = device_config.get('batch_size')
        if batch_size is not None:
            if not isinstance(batch_size, int):
                errors.append(
                    f"设备{device_idx}: batch_size必须是整数"
                )
            else:
                min_val, max_val = self.PARAM_RANGES['batch_size']
                if batch_size < min_val or batch_size > max_val:
                    errors.append(
                        f"设备{device_idx}: batch_size({batch_size}) "
                        f"超出范围[{min_val}, {max_val}]"
                    )
        
        # 验证工作组大小
        work_group = device_config.get('work_group_size')
        if work_group is not None:
            if not isinstance(work_group, int):
                errors.append(
                    f"设备{device_idx}: work_group_size必须是整数"
                )
            else:
                min_val, max_val = self.PARAM_RANGES['work_group_size']
                if work_group < min_val or work_group > max_val:
                    errors.append(
                        f"设备{device_idx}: work_group_size({work_group}) "
                        f"超出范围[{min_val}, {max_val}]"
                    )
        
        return errors
    
    def suggest_config(
        self,
        devices: List[Dict],
        mode: str = 'auto'
    ) -> Dict:
        """根据检测设备推荐配置
        
        Args:
            devices: 设备列表
            mode: GPU模式
            
        Returns:
            推荐的配置字典
        """
        if not devices:
            return self._get_default_config()
        
        config = {
            'mode': mode,
            'device_indices': [],
            'load_balancing': 'performance',
            'auto_tuning': True,
            'per_device_config': {}
        }
        
        if mode == 'auto':
            # 自动选择最佳GPU（传递-1让底层自动选择）
            config['device_indices'] = [-1]
            
        elif mode == 'single':
            # 单GPU模式：使用评分最高的设备
            # 注意：实际使用时应该由GUI传入用户选择的设备索引
            # 这里为了向后兼容，仍然返回最佳设备
            best_device = max(devices, key=lambda d: d.get('score', 0))
            config['device_indices'] = [best_device['global_index']]
            
        elif mode == 'multi':
            # 多GPU模式(使用所有设备)
            config['device_indices'] = [
                d['global_index'] for d in devices
            ]
            
            # 为每个设备生成配置
            from .auto_config import get_gpu_configurator
            configurator = get_gpu_configurator()
            
            for device in devices:
                device_config = configurator.configure_for_device(device)
                config['per_device_config'][str(device['global_index'])] = {
                    'batch_size': device_config['batch_size'],
                    'work_group_size': device_config['work_group_size']
                }
        
        return config
    
    def _get_default_config(self) -> Dict:
        """获取默认配置
        
        Returns:
            默认配置字典
        """
        return {
            'mode': 'auto',
            'device_indices': [-1],
            'load_balancing': 'performance',
            'auto_tuning': True,
            'per_device_config': {}
        }
    
    def validate_device_compatibility(
        self,
        devices: List[Dict]
    ) -> Tuple[bool, List[str]]:
        """验证设备兼容性
        
        Args:
            devices: 设备列表
            
        Returns:
            (is_compatible, warnings) 元组
        """
        warnings = []
        
        if not devices:
            return False, ["无可用GPU设备"]
        
        # 检查厂商混合
        vendors = set(d.get('vendor', 'unknown') for d in devices)
        if len(vendors) > 1:
            warnings.append(
                f"检测到混合厂商GPU: {vendors}\n"
                f"可能导致性能不均衡,建议手动配置负载分配"
            )
        
        # 检查显存差异
        memories = [d.get('global_mem_gb', 0) for d in devices]
        if memories:
            max_mem = max(memories)
            min_mem = min(memories)
            if max_mem > 0 and (max_mem / min_mem) > 3:
                warnings.append(
                    f"GPU显存差异较大: {min_mem:.1f}GB - {max_mem:.1f}GB\n"
                    f"建议使用'performance'负载均衡策略"
                )
        
        # 检查Intel Arc(需要特殊配置)
        for device in devices:
            if device.get('vendor') == 'intel':
                warnings.append(
                    "Intel Arc GPU需要特殊配置:\n"
                    "- 启用uint32 workaround\n"
                    "- 禁用快速数学运算\n"
                    "- 使用较小批次大小"
                )
                break
        
        is_compatible = len(warnings) == 0
        
        return is_compatible, warnings
    
    def format_validation_report(
        self,
        config: Dict,
        devices: List[Dict] = None
    ) -> str:
        """格式化验证报告
        
        Args:
            config: 配置字典
            devices: 设备列表(可选)
            
        Returns:
            格式化字符串
        """
        lines = ["GPU配置验证报告", "=" * 60]
        
        # 验证配置
        is_valid, errors = self.validate_config(config)
        
        lines.append(f"\n配置验证: {'✅ 通过' if is_valid else '❌ 失败'}")
        
        if errors:
            lines.append("\n错误:")
            for error in errors:
                lines.append(f"  ❌ {error}")
        
        # 验证兼容性
        if devices:
            is_compatible, warnings = self.validate_device_compatibility(devices)
            lines.append(f"\n兼容性检查: {'✅ 通过' if is_compatible else '⚠️ 警告'}")
            
            if warnings:
                lines.append("\n警告:")
                for warning in warnings:
                    lines.append(f"  ⚠️ {warning}")
        
        return '\n'.join(lines)

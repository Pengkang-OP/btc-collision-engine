"""GPU型号数据库加载器

负责加载和管理GPU型号配置数据库。
"""

import json
import os
import logging
from typing import Dict, Optional, List, Any

logger = logging.getLogger(__name__)


class GPUProfileLoader:
    """GPU型号配置加载器"""
    
    def __init__(self, profile_file: str = None):
        """
        初始化加载器
        
        Args:
            profile_file: JSON配置文件路径,None则使用默认路径
        """
        if profile_file is None:
            # 使用当前文件同目录下的gpu_profiles.json
            profile_file = os.path.join(os.path.dirname(__file__), 'gpu_profiles.json')
        
        self.profile_file = profile_file
        self.profiles = {}
        self._load_profiles()
    
    def _load_profiles(self):
        """加载JSON配置文件"""
        try:
            if not os.path.exists(self.profile_file):
                logger.warning(f"GPU配置文件不存在: {self.profile_file}")
                self.profiles = {}
                return
            
            with open(self.profile_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 版本检查
            version = data.get('_version', '1.0')
            if version != '1.0':
                logger.warning(
                    f"不支持的配置文件版本: {version}, "
                    f"当前支持1.0。可能导致配置加载错误"
                )
            
            self.profiles = data
            
            vendor_count = len([k for k in self.profiles.keys() if not k.startswith('_')])
            logger.info(f"GPU型号数据库加载成功: {vendor_count} 个厂商 (版本 {version})")
            
        except json.JSONDecodeError as e:
            logger.error(f"GPU配置文件JSON格式错误: {e}")
            self.profiles = {}
        except Exception as e:
            logger.error(f"加载GPU配置文件失败: {e}")
            self.profiles = {}
    
    def get_profile(self, vendor: str, model_name: str) -> Optional[Dict[str, Any]]:
        """
        根据厂商和型号获取配置
        
        Args:
            vendor: 厂商名称(nvidia/amd/intel)
            model_name: GPU型号名称(如"RTX 3080")
            
        Returns:
            配置字典,如果未找到则返回None
        """
        vendor = vendor.lower()
        
        if vendor not in self.profiles:
            logger.debug(f"未知厂商: {vendor}")
            return None
        
        vendor_data = self.profiles[vendor]
        
        # 遍历所有架构世代,查找匹配的型号
        for arch_name, arch_data in vendor_data.items():
            # 跳过元数据字段和default配置
            if arch_name.startswith('_') or arch_name == 'default':
                continue
            
            # 确保arch_data是字典（架构层级）
            if not isinstance(arch_data, dict):
                logger.warning(f"跳过无效的架构配置 {vendor}/{arch_name}: 期望dict, 得到{type(arch_data).__name__}")
                continue
            
            # 遍历该架构下的所有系列
            for series_name, series_data in arch_data.items():
                if series_name.startswith('_'):
                    continue
                
                # 确保series_data是字典
                if not isinstance(series_data, dict):
                    logger.warning(f"跳过无效的系列配置 {vendor}/{arch_name}/{series_name}: 期望dict, 得到{type(series_data).__name__}")
                    continue
                
                # 验证配置合法性
                if not self._validate_profile(series_data, f"{vendor}/{arch_name}/{series_name}"):
                    logger.warning(f"配置验证失败: {vendor}/{arch_name}/{series_name}")
                    continue
                
                # 检查型号是否在列表中
                models = series_data.get('models', [])
                if self._match_model(model_name, models):
                    logger.info(f"匹配GPU型号: {model_name} -> {vendor}/{arch_name}/{series_name}")
                    return series_data
        
        # 未找到具体型号,返回厂商默认配置
        logger.warning(f"未找到型号 {model_name} 的配置,使用厂商默认配置")
        return self.get_default_profile(vendor)
    
    def _match_model(self, model_name: str, model_list: List[str]) -> bool:
        """
        模糊匹配型号名称
        
        Args:
            model_name: 要匹配的型号名称
            model_list: 型号列表
            
        Returns:
            是否匹配成功
        """
        model_lower = model_name.lower()
        
        for candidate in model_list:
            candidate_lower = candidate.lower()
            
            # 完全匹配
            if model_lower == candidate_lower:
                return True
            
            # 包含匹配(避免误匹配,要求至少包含主要关键词)
            if model_lower in candidate_lower or candidate_lower in model_lower:
                return True
            
            # 部分匹配(提取关键部分,如"RTX 3080"匹配"GeForce RTX 3080")
            # 移除常见前缀
            cleaned_model = self._clean_model_name(model_lower)
            cleaned_candidate = self._clean_model_name(candidate_lower)
            
            if cleaned_model in cleaned_candidate or cleaned_candidate in cleaned_model:
                return True
        
        return False
    
    def _validate_profile(self, profile: Dict[str, Any], profile_path: str) -> bool:
        """
        验证GPU配置文件的合法性
        
        Args:
            profile: 配置字典
            profile_path: 配置路径(用于日志)
            
        Returns:
            配置是否合法
        """
        # 检查必需字段
        required_keys = ['models', 'recommended_batch_size', 'max_batch_size']
        for key in required_keys:
            if key not in profile:
                logger.error(f"配置 {profile_path} 缺少必需字段: {key}")
                return False
        
        # 验证batch_size关系
        if profile['max_batch_size'] < profile['recommended_batch_size']:
            logger.error(f"配置 {profile_path}: max_batch_size ({profile['max_batch_size']}) < recommended_batch_size ({profile['recommended_batch_size']})")
            return False
        
        # 验证batch_size为正数
        if profile['recommended_batch_size'] <= 0 or profile['max_batch_size'] <= 0:
            logger.error(f"配置 {profile_path}: batch_size必须为正数")
            return False
        
        # 验证memory_efficiency范围
        if 'memory_efficiency' in profile:
            eff = profile['memory_efficiency']
            if not (0.0 < eff <= 1.0):
                logger.warning(f"配置 {profile_path}: memory_efficiency ({eff}) 不在合理范围 (0.0, 1.0]")
        
        # 验证models为列表
        if not isinstance(profile['models'], list):
            logger.error(f"配置 {profile_path}: models必须为列表")
            return False
        
        return True
    
    def _clean_model_name(self, name: str) -> str:
        """清理型号名称,移除常见前缀和后缀"""
        # 移除常见前缀
        prefixes = ['nvidia ', 'amd ', 'intel ', 'geforce ', 'radeon ', 'arc ']
        for prefix in prefixes:
            if name.startswith(prefix):
                name = name[len(prefix):]
        
        # 移除常见后缀
        suffixes = [' graphics', ' gpu']
        for suffix in suffixes:
            if name.endswith(suffix):
                name = name[:-len(suffix)]
        
        return name.strip()
    
    def get_default_profile(self, vendor: str) -> Optional[Dict[str, Any]]:
        """
        获取厂商的默认配置
        
        Args:
            vendor: 厂商名称
            
        Returns:
            默认配置字典
        """
        vendor = vendor.lower()
        
        if vendor not in self.profiles:
            return None
        
        vendor_data = self.profiles[vendor]
        
        # 查找"default"配置
        if 'default' in vendor_data:
            return vendor_data['default']
        
        return None
    
    def get_all_vendors(self) -> List[str]:
        """获取所有支持的厂商列表"""
        return [k for k in self.profiles.keys() if not k.startswith('_')]
    
    def get_vendor_architectures(self, vendor: str) -> List[str]:
        """
        获取厂商的所有架构世代
        
        Args:
            vendor: 厂商名称
            
        Returns:
            架构名称列表
        """
        vendor = vendor.lower()
        
        if vendor not in self.profiles:
            return []
        
        vendor_data = self.profiles[vendor]
        return [k for k in vendor_data.keys() if not k.startswith('_') and k != 'default']
    
    def reload(self):
        """重新加载配置文件"""
        logger.info("重新加载GPU型号数据库...")
        self._load_profiles()

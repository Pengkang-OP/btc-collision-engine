"""GPU驱动版本检测和管理

提供驱动版本检测、兼容性检查和健康评估功能。
支持Windows和Linux平台。
"""

import logging
from ..utils import init_logging, get_configured_logger
import re
import subprocess
import platform
from typing import Dict, Optional, Tuple

logger = get_configured_logger("GPUDriverManager")


class DriverVersionParser:
    """驱动版本解析和比较工具"""
    
    @staticmethod
    def parse_version(version_str: str) -> Tuple[int, ...]:
        """
        解析驱动版本字符串为元组
        
        Args:
            version_str: 版本字符串,如 "520.67.03" 或 "23.20.15002"
            
        Returns:
            版本元组,如 (520, 67, 3)
        """
        if not version_str:
            return (0,)
        
        # 移除非数字字符(除了点号)
        cleaned = re.sub(r'[^0-9.]', '', version_str)
        
        # 分割并转换为整数
        try:
            parts = [int(p) for p in cleaned.split('.') if p]
            return tuple(parts) if parts else (0,)
        except ValueError:
            logger.warning(f"无法解析版本号: {version_str}")
            return (0,)
    
    @staticmethod
    def compare_versions(v1: str, v2: str) -> int:
        """
        比较两个版本号
        
        Args:
            v1: 版本1
            v2: 版本2
            
        Returns:
            -1: v1 < v2
             0: v1 == v2
             1: v1 > v2
        """
        t1 = DriverVersionParser.parse_version(v1)
        t2 = DriverVersionParser.parse_version(v2)
        
        # 补齐长度
        max_len = max(len(t1), len(t2))
        t1 = t1 + (0,) * (max_len - len(t1))
        t2 = t2 + (0,) * (max_len - len(t2))
        
        if t1 < t2:
            return -1
        elif t1 > t2:
            return 1
        else:
            return 0
    
    @staticmethod
    def is_version_compatible(current: str, minimum: str) -> bool:
        """
        检查当前版本是否满足最低要求
        
        Args:
            current: 当前版本
            minimum: 最低要求版本
            
        Returns:
            True如果兼容
        """
        return DriverVersionParser.compare_versions(current, minimum) >= 0


class DriverManager:
    """GPU驱动管理器"""
    
    # 检测超时配置(秒)
    DETECTION_TIMEOUT = 5
    
    # 驱动版本缓存(TTL: 3600秒)
    _driver_version_cache: Dict[str, Tuple[Optional[str], float]] = {}
    _cache_ttl: float = 3600  # 缓存有效期1小时
    
    # 已知的不稳定驱动版本黑名单
    # 数据来源: 厂商公告、用户反馈、社区报告
    # 最后更新: 2026-04-20
    UNSTABLE_DRIVERS = {
        'nvidia': [
            # 格式: (最低版本, 最高版本, 问题描述)
            ("450.00", "451.99", "内存泄漏问题"),
            ("470.00", "470.99", "OpenCL稳定性问题"),
            ("510.00", "510.99", "GPU内存管理问题"),
            ("515.00", "515.99", "CUDA驱动兼容性问题"),
        ],
        'amd': [
            ("21.10.0", "21.11.9", "已知崩溃问题"),
            ("22.10.0", "22.11.9", "OpenCL性能退化"),
            ("23.1.0", "23.1.9", "Vulkan驱动不稳定"),
        ],
        'intel': [
            ("31.0.100.0", "31.0.100.9999", "Arc早期驱动不稳定"),
            ("31.0.101.0", "31.0.101.3999", "Arc驱动性能问题"),
        ]
    }
    
    @staticmethod
    def detect_nvidia_driver_version() -> Optional[str]:
        """
        检测NVIDIA驱动版本(支持Windows和Linux)
        
        Returns:
            驱动版本字符串或None
        """
        try:
            system = platform.system()
            
            # 准备检测方法列表
            detection_methods = []
            
            if system == 'Windows':
                # Windows: 使用nvidia-smi
                detection_methods.append({
                    'name': 'nvidia-smi',
                    'cmd': ['nvidia-smi', '--query-gpu=driver_version', '--format=csv,noheader'],
                    'parser': 'nvidia_smi'
                })
            elif system == 'Darwin':
                # macOS: 检查 CUDA toolkit
                detection_methods.append({
                    'name': 'nvidia-smi-macos',
                    'cmd': ['nvidia-smi', '--query-gpu=driver_version', '--format=csv,noheader'],
                    'parser': 'nvidia_smi'
                })
                # 同时检查 CUDA toolkit 路径
                detection_methods.append({
                    'name': 'nvcc-version',
                    'cmd': ['/usr/local/cuda/bin/nvcc', '--version'],
                    'parser': 'nvcc'
                })
            else:
                # Linux: 尝试多种方式
                detection_methods.extend([
                    {
                        'name': 'nvidia-smi',
                        'cmd': ['nvidia-smi', '--query-gpu=driver_version', '--format=csv,noheader'],
                        'parser': 'nvidia_smi'
                    },
                    {
                        'name': '/proc/driver/nvidia/version',
                        'cmd': ['cat', '/proc/driver/nvidia/version'],
                        'parser': 'proc_driver'
                    }
                ])
            
            # 依次尝试各种检测方法
            for method in detection_methods:
                try:
                    result = subprocess.run(
                        method['cmd'],
                        capture_output=True,
                        text=True,
                        timeout=DriverManager.DETECTION_TIMEOUT
                    )
                    
                    if result.returncode == 0 and result.stdout.strip():
                        version = DriverManager._parse_nvidia_output(
                            result.stdout.strip(),
                            method['parser']
                        )
                        if version:
                            logger.info(f"检测到NVIDIA驱动版本({method['name']}): {version}")
                            return version
                            
                except FileNotFoundError:
                    logger.debug(f"检测方法 {method['name']} 不可用")
                    continue
                except subprocess.TimeoutExpired:
                    logger.warning(f"检测方法 {method['name']} 超时")
                    continue
                except Exception as e:
                    logger.debug(f"检测方法 {method['name']} 失败: {e}")
                    continue
            
            logger.warning("所有NVIDIA驱动检测方法都失败")
            return None
            
        except Exception as e:
            logger.warning(f"检测NVIDIA驱动版本失败: {e}")
            return None
    
    @staticmethod
    def _parse_nvidia_output(output: str, parser_type: str) -> Optional[str]:
        """
        解析NVIDIA驱动版本输出
        
        Args:
            output: 命令输出
            parser_type: 解析器类型('nvidia_smi'或'proc_driver')
            
        Returns:
            驱动版本字符串或None
        """
        try:
            if parser_type == 'nvidia_smi':
                # nvidia-smi输出格式: "520.67.03"
                return output.split('\n')[0].strip()
            
            elif parser_type == 'proc_driver':
                # /proc/driver/nvidia/version格式:
                # "NVRM version: NVIDIA UNIX x86_64 Kernel Module  520.67.03 ..."
                match = re.search(r'Kernel Module\s+([\d.]+)', output)
                if match:
                    return match.group(1)
            
            return None
        except Exception as e:
            logger.debug(f"解析NVIDIA输出失败: {e}")
            return None
    
    @staticmethod
    def detect_amd_driver_version() -> Optional[str]:
        """
        检测AMD驱动版本(支持Windows和Linux)
        
        Returns:
            驱动版本字符串或None
        """
        try:
            system = platform.system()
            
            if system == 'Windows':
                return DriverManager._detect_amd_windows()
            elif system == 'Darwin':
                # macOS: 使用 system_profiler 检测 AMD GPU
                try:
                    result = subprocess.run(
                        ['system_profiler', 'SPDisplaysDataType'],
                        capture_output=True, text=True, timeout=10
                    )
                    if result.returncode == 0 and 'AMD' in result.stdout:
                        # 从输出中提取版本信息
                        for line in result.stdout.split('\n'):
                            if 'Version' in line or 'Kernel Extension' in line:
                                version = line.split(':')[-1].strip()
                                if version:
                                    return version
                except (OSError, subprocess.SubprocessError, ValueError):
                    pass
                return None
            else:
                return DriverManager._detect_amd_linux()
                
        except Exception as e:
            logger.warning(f"检测AMD驱动版本失败: {e}")
            return None
    
    @staticmethod
    def _detect_amd_windows() -> Optional[str]:
        """Windows平台检测AMD驱动"""
        try:
            ps_command = (
                'Get-WmiObject Win32_PnPSignedDriver | '
                'Where-Object {$_.DeviceName -like "*AMD*"} | '
                'Select-Object -First 1 -ExpandProperty DriverVersion'
            )
            
            result = subprocess.run(
                ['powershell', '-Command', ps_command],
                capture_output=True,
                text=True,
                timeout=DriverManager.DETECTION_TIMEOUT
            )
            
            if result.returncode == 0 and result.stdout.strip():
                version = result.stdout.strip()
                logger.info(f"检测到AMD驱动版本: {version}")
                return version
            else:
                logger.warning("无法获取AMD驱动版本")
                return None
                
        except Exception as e:
            logger.debug(f"Windows AMD驱动检测失败: {e}")
            return None
    
    @staticmethod
    def _detect_amd_linux() -> Optional[str]:
        """Linux平台检测AMD驱动"""
        try:
            # 尝试多种方式
            methods = [
                ['cat', '/sys/module/amdgpu/version'],
                ['dpkg', '-l', 'xserver-xorg-video-amdgpu'],
            ]
            
            for cmd in methods:
                try:
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=DriverManager.DETECTION_TIMEOUT
                    )
                    
                    if result.returncode == 0 and result.stdout.strip():
                        version = result.stdout.strip()
                        # 如果是dpkg输出,需要解析
                        if 'Version:' in version:
                            for line in version.split('\n'):
                                if 'Version:' in line:
                                    version = line.split('Version:')[1].strip()
                                    break
                        
                        logger.info(f"检测到AMD驱动版本(Linux): {version}")
                        return version
                except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                    # 忽略常见的指令找不到/超时，继续尝试下一个方式
                    continue
            
            logger.warning("Linux AMD驱动检测失败")
            return None
            
        except Exception as e:
            logger.debug(f"Linux AMD驱动检测失败: {e}")
            return None
    
    @staticmethod
    def detect_intel_driver_version() -> Optional[str]:
        """
        检测Intel驱动版本(支持Windows和Linux)
        
        Returns:
            驱动版本字符串或None
        """
        try:
            system = platform.system()
            
            if system == 'Windows':
                return DriverManager._detect_intel_windows()
            elif system == 'Darwin':
                # macOS: 使用 system_profiler 检测 Intel GPU
                try:
                    result = subprocess.run(
                        ['system_profiler', 'SPDisplaysDataType'],
                        capture_output=True, text=True, timeout=10
                    )
                    if result.returncode == 0 and 'Intel' in result.stdout:
                        # 从输出中提取版本信息
                        for line in result.stdout.split('\n'):
                            if 'Version' in line or 'Kernel Extension' in line:
                                version = line.split(':')[-1].strip()
                                if version:
                                    return version
                except (OSError, subprocess.SubprocessError, ValueError):
                    pass
                return None
            else:
                return DriverManager._detect_intel_linux()
                
        except Exception as e:
            logger.warning(f"检测Intel驱动版本失败: {e}")
            return None
    
    @staticmethod
    def _detect_intel_windows() -> Optional[str]:
        """Windows平台检测Intel驱动"""
        try:
            ps_command = (
                'Get-WmiObject Win32_PnPSignedDriver | '
                'Where-Object {$_.DeviceName -like "*Intel*Graphics*"} | '
                'Select-Object -First 1 -ExpandProperty DriverVersion'
            )
            
            result = subprocess.run(
                ['powershell', '-Command', ps_command],
                capture_output=True,
                text=True,
                timeout=DriverManager.DETECTION_TIMEOUT
            )
            
            if result.returncode == 0 and result.stdout.strip():
                version = result.stdout.strip()
                logger.info(f"检测到Intel驱动版本: {version}")
                return version
            else:
                logger.warning("无法获取Intel驱动版本")
                return None
                
        except Exception as e:
            logger.debug(f"Windows Intel驱动检测失败: {e}")
            return None
    
    @staticmethod
    def _detect_intel_linux() -> Optional[str]:
        """Linux平台检测Intel驱动"""
        try:
            # 尝试多种方式
            methods = [
                ['cat', '/sys/module/i915/version'],
                ['glxinfo', '-B'],  # 需要mesa-utils包
            ]
            
            for cmd in methods:
                try:
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=DriverManager.DETECTION_TIMEOUT
                    )
                    
                    if result.returncode == 0 and result.stdout.strip():
                        version = result.stdout.strip()
                        # 如果是glxinfo输出,需要解析
                        if 'OpenGL version' in version:
                            for line in version.split('\n'):
                                if 'OpenGL version' in line:
                                    # 格式: "OpenGL version string: 4.6 ..."
                                    version = line.split(':')[1].strip().split()[0]
                                    break
                        
                        logger.info(f"检测到Intel驱动版本(Linux): {version}")
                        return version
                except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                    # 忽略常见的指令找不到/超时，继续尝试下一个方式
                    continue
            
            logger.warning("Linux Intel驱动检测失败")
            return None
            
        except Exception as e:
            logger.debug(f"Linux Intel驱动检测失败: {e}")
            return None
    
    @staticmethod
    def clear_driver_cache() -> None:
        """
        清除驱动版本缓存
        
        用于驱动更新后强制重新检测
        """
        DriverManager._driver_version_cache.clear()
        logger.info("驱动版本缓存已清除")
    
    @staticmethod
    def get_unstable_driver_report() -> Dict:
        """
        获取不稳定驱动报告
        
        Returns:
            包含不稳定驱动信息的字典
        """
        return {
            'last_updated': '2026-04-20',
            'total_unstable_versions': sum(
                len(versions) for versions in DriverManager.UNSTABLE_DRIVERS.values()
            ),
            'vendors': {
                vendor: len(versions) 
                for vendor, versions in DriverManager.UNSTABLE_DRIVERS.items()
            },
            'recommendations': [
                '定期检查驱动更新',
                '避免使用黑名单中的驱动版本',
                '关注厂商发布的驱动更新公告',
                '报告新的驱动稳定性问题以更新黑名单'
            ]
        }
    
    @staticmethod
    def add_unstable_driver(vendor: str, min_version: str, 
                           max_version: str, issue: str) -> None:
        """
        添加不稳定驱动版本到黑名单
        
        Args:
            vendor: 厂商标识('nvidia', 'amd', 'intel')
            min_version: 最低版本
            max_version: 最高版本
            issue: 问题描述
        """
        vendor_lower = vendor.lower()
        if vendor_lower not in DriverManager.UNSTABLE_DRIVERS:
            DriverManager.UNSTABLE_DRIVERS[vendor_lower] = []
        
        DriverManager.UNSTABLE_DRIVERS[vendor_lower].append(
            (min_version, max_version, issue)
        )
        logger.warning(f"已添加不稳定驱动: {vendor} {min_version}-{max_version} ({issue})")
    
    @staticmethod
    def detect_driver_version(vendor: str) -> Optional[str]:
        """
        根据厂商检测驱动版本(带缓存)
        
        Args:
            vendor: 厂商标识 ('nvidia', 'amd', 'intel')
            
        Returns:
            驱动版本字符串或None
        """
        import time
        
        vendor_lower = vendor.lower()
        
        # 检查缓存
        if vendor_lower in DriverManager._driver_version_cache:
            cached_version, cache_time = DriverManager._driver_version_cache[vendor_lower]
            elapsed = time.time() - cache_time
            
            if elapsed < DriverManager._cache_ttl:
                logger.debug(f"使用缓存的{vendor}驱动版本: {cached_version}")
                return cached_version
            else:
                logger.debug(f"{vendor}驱动版本缓存已过期")
                del DriverManager._driver_version_cache[vendor_lower]
        
        # 执行检测
        if 'nvidia' in vendor_lower:
            version = DriverManager.detect_nvidia_driver_version()
        elif 'amd' in vendor_lower or 'radeon' in vendor_lower:
            version = DriverManager.detect_amd_driver_version()
        elif 'intel' in vendor_lower:
            version = DriverManager.detect_intel_driver_version()
        else:
            logger.warning(f"未知厂商: {vendor},无法检测驱动版本")
            version = None
        
        # 更新缓存
        DriverManager._driver_version_cache[vendor_lower] = (version, time.time())
        logger.debug(f"已缓存{vendor}驱动版本: {version}")
        
        return version
    
    @staticmethod
    def check_driver_health(vendor: str, driver_version: str, 
                           profile: Optional[Dict] = None) -> Dict:
        """
        检查驱动健康状态
        
        Args:
            vendor: 厂商标识
            driver_version: 驱动版本
            profile: GPU型号配置(可选)
            
        Returns:
            健康检查结果:
            {
                'status': 'good' | 'warning' | 'critical',
                'message': '描述信息',
                'recommendations': ['建议列表']
            }
        """
        result = {
            'status': 'good',
            'message': '驱动版本正常',
            'recommendations': []
        }
        
        if not driver_version:
            result['status'] = 'warning'
            result['message'] = '无法检测驱动版本'
            result['recommendations'].append('请手动检查驱动版本')
            return result
        
        vendor_lower = vendor.lower()
        
        # 1. 检查黑名单中的不稳定版本
        if vendor_lower in DriverManager.UNSTABLE_DRIVERS:
            for min_ver, max_ver, issue in DriverManager.UNSTABLE_DRIVERS[vendor_lower]:
                if (DriverVersionParser.is_version_compatible(driver_version, min_ver) and
                    DriverVersionParser.compare_versions(driver_version, max_ver) <= 0):
                    result['status'] = 'warning'
                    result['message'] = f'使用已知不稳定的驱动版本: {driver_version} ({issue})'
                    result['recommendations'].append('建议更新驱动到最新稳定版')
                    break
        
        # 2. 检查是否满足最低驱动要求
        if profile:
            min_driver = profile.get('min_driver_version')
            recommended_driver = profile.get('recommended_driver_version')
            
            if min_driver:
                if not DriverVersionParser.is_version_compatible(driver_version, min_driver):
                    result['status'] = 'critical'
                    result['message'] = (
                        f'驱动版本过低: {driver_version}, '
                        f'最低要求: {min_driver}'
                    )
                    result['recommendations'].append(
                        f'请立即更新驱动到 {min_driver} 或更高版本'
                    )
                    return result
            
            if recommended_driver:
                if not DriverVersionParser.is_version_compatible(
                    driver_version, recommended_driver
                ):
                    if result['status'] == 'good':
                        result['status'] = 'warning'
                    result['message'] = (
                        f'驱动版本较旧: {driver_version}, '
                        f'推荐版本: {recommended_driver}'
                    )
                    result['recommendations'].append(
                        f'建议更新驱动到 {recommended_driver} 以获得最佳性能'
                    )
        
        # 3. 根据厂商给出特定建议
        if vendor_lower == 'intel':
            # Intel Arc驱动更新频繁,建议保持最新
            result['recommendations'].append(
                'Intel Arc驱动更新频繁,建议保持最新版本'
            )
        
        return result
    
    @staticmethod
    def get_driver_optimization_flags(vendor: str, driver_version: str,
                                     profile: Optional[Dict] = None) -> Dict[str, bool]:
        """
        根据驱动版本获取优化标志
        
        Args:
            vendor: 厂商标识
            driver_version: 驱动版本
            profile: GPU型号配置
            
        Returns:
            优化标志字典
        """
        # 默认使用保守模式(更安全)
        flags = {
            'enable_async_compute': False,   # 默认禁用,需要显式启用
            'enable_fast_math': True,        # 这个相对安全
            'enable_shader_cache': False,    # 默认禁用,需要显式启用
            'enable_shader_reordering': False,  # 明确标志,语义清晰
            'conservative_mode': True,       # 默认保守模式(更安全)
        }
        
        if not driver_version:
            # 无法检测驱动版本,保持保守模式
            logger.warning("无法检测驱动版本,使用保守优化模式")
            return flags
        
        vendor_lower = vendor.lower()
        
        # NVIDIA特定优化
        if vendor_lower == 'nvidia':
            # 旧驱动禁用某些优化
            if DriverVersionParser.compare_versions(driver_version, "470.00") < 0:
                logger.warning("NVIDIA驱动版本较旧(< 470.00),保持保守模式")
                # 保持默认保守设置
            else:
                # 470.00+ 启用异步计算
                flags['enable_async_compute'] = True
                flags['conservative_mode'] = False
                logger.info("NVIDIA驱动版本 >= 470.00,启用异步计算优化")
            
            # 520.00+ 启用额外优化
            if DriverVersionParser.compare_versions(driver_version, "520.00") >= 0:
                flags['enable_shader_cache'] = True
                flags['enable_shader_reordering'] = True
                logger.info("NVIDIA驱动版本 >= 520.00,启用着色器缓存和重排序优化")
        
        # AMD特定优化
        elif vendor_lower == 'amd' or 'radeon' in vendor_lower:
            # Adrenalin 22.10+ 支持更好的优化
            if DriverVersionParser.compare_versions(driver_version, "22.10.0") < 0:
                flags['enable_fast_math'] = False
                logger.warning("AMD驱动版本较旧(< 22.10.0),禁用快速数学优化")
            else:
                flags['enable_async_compute'] = True
                flags['conservative_mode'] = False
                logger.info("AMD驱动版本 >= 22.10.0,启用异步计算优化")
        
        # Intel特定优化
        elif vendor_lower == 'intel':
            # Arc驱动需要较新版本
            if DriverVersionParser.compare_versions(driver_version, "31.0.101.0") < 0:
                logger.warning("Intel驱动版本较旧(< 31.0.101.0),保持保守模式")
                # 保持默认保守设置
            else:
                flags['enable_async_compute'] = True
                flags['conservative_mode'] = False
                logger.info("Intel驱动版本 >= 31.0.101.0,启用异步计算优化")
        
        return flags

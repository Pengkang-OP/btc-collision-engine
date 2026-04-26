"""断点管理器"""
import os
import json
import time
import threading
from datetime import datetime
from typing import Dict, List, Optional, Set

# 导入日志配置
from ..utils import init_logging, get_configured_logger
from ..utils.platform_utils import PlatformUtils

# 初始化日志系统（如果尚未初始化）
init_logging()

# 获取模块日志记录器
logger = get_configured_logger("CheckpointManager")


class CheckpointManager:
    """断点管理器 - 保存和恢复对撞进度"""
    
    DEFAULT_FILE = "collision_checkpoint.json"
    
    def __init__(self, filepath: str = None, auto_save_interval: int = 30):
        # 修复: 默认断点路径使用data_logs目录（有写入权限）
        if filepath is None:
            # 获取项目根目录（src的父目录）
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            data_logs_dir = os.path.join(project_root, "data_logs")
            # 确保data_logs目录存在
            os.makedirs(data_logs_dir, exist_ok=True)
            self.filepath = os.path.join(data_logs_dir, self.DEFAULT_FILE)
        else:
            self.filepath = filepath
        self.auto_save_interval = auto_save_interval
        self._last_save_time = 0.0
        self._lock = threading.Lock()  # 线程锁保护文件操作
        self._dirty = False  # 脏标志，标记是否有未保存的更改
        self._buffer = None  # 缓冲区，用于批量保存
        logger.debug(f"CheckpointManager 初始化: 文件={self.filepath}, 自动保存间隔={auto_save_interval}秒")
    
    def save(self, mode: str, targets: Set[str], current_position: int, 
             total_checked: int, matches: List[Dict], 
             range_start: Optional[int] = None, range_end: Optional[int] = None, 
             force: bool = False) -> None:
        """保存断点到 JSON 文件（线程安全）
        
        安全说明:
        - 匹配的私钥信息不会被保存到断点文件
        - 仅保存地址和时间戳用于统计
        - 敏感数据通过回调单独处理
        
        参数:
            mode: 对撞模式
            targets: 目标地址集合
            current_position: 当前位置
            total_checked: 已检查数量
            matches: 匹配列表
            range_start: 范围起始值
            range_end: 范围结束值
            force: 是否强制保存（忽略缓冲区）
        """
        with self._lock:  # 确保线程安全
            # 清理敏感信息：仅保存地址，不保存私钥
            sanitized_matches = []
            for match in matches:
                # 只保留非敏感字段
                safe_match = {
                    "address": match.get("address", ""),
                    "timestamp": match.get("timestamp", 0)
                }
                # 可选：保存私钥的哈希值用于验证（不包含实际私钥）
                if "private_key_hash" in match:
                    safe_match["private_key_hash"] = match["private_key_hash"]
                sanitized_matches.append(safe_match)
            
            # 构建断点数据
            self._buffer = {
                "version": 1,
                "timestamp": datetime.now().isoformat(),
                "mode": mode,
                "targets": list(targets),
                "current_position": current_position,
                "total_checked": total_checked,
                "matches": sanitized_matches,  # 使用清理后的数据
                "range_start": range_start,
                "range_end": range_end,
                "security_note": "私钥信息未保存，仅用于运行时内存处理"
            }
            
            # 标记为脏
            self._dirty = True
            
            # 只有在强制保存或时间间隔达到时才写入文件
            if force or self.should_auto_save():
                self._flush_buffer()
    
    def _flush_buffer(self) -> None:
        """将缓冲区数据写入文件（内部方法）"""
        if not self._dirty or self._buffer is None:
            return
        
        temp_filepath = self.filepath + '.tmp'
        try:
            # 使用临时文件 + 原子重命名，防止写入中断导致文件损坏
            with open(temp_filepath, 'w', encoding='utf-8') as f:
                json.dump(self._buffer, f, ensure_ascii=False, indent=2)
            
            # 原子重命名
            # DA-1修复: 优化Windows原子操作
            if PlatformUtils.is_windows():  # Windows
                # Windows上os.replace()可能需要特殊处理
                try:
                    # 先尝试直接replace
                    os.replace(temp_filepath, self.filepath)
                except OSError as e:
                    # 如果失败，尝试先删除再重命名
                    logger.debug(f"os.replace()失败，尝试删除后重命名: {e}")
                    if os.path.exists(self.filepath):
                        os.remove(self.filepath)
                    os.rename(temp_filepath, self.filepath)
            else:
                # Unix/Linux: 直接使用os.replace（原子操作）
                os.replace(temp_filepath, self.filepath)
            
            # 设置文件权限
            # Linux/macOS: 使用chmod设置0o600
            # Windows: 通过环境变量控制ACL设置
            if not PlatformUtils.is_windows():  # nt = Windows
                try:
                    os.chmod(self.filepath, 0o600)  # 仅所有者可读写
                except OSError:
                    pass  # 权限设置失败不影响功能
            else:
                # Windows: ACL权限设置(可通过环境变量控制)
                # 环境变量: BTC_ENGINE_SKIP_ACL
                #   - 'true': 跳过ACL设置,使用Windows默认权限
                #   - 'false'或未设置: 尝试使用icacls设置严格权限
                # 安全说明:
                #   - 断点文件不包含私钥,仅包含地址和进度信息
                #   - 默认权限风险较低,但多用户环境建议启用ACL
                #   - 测试环境中如遇到权限错误,可设置BTC_ENGINE_SKIP_ACL=true
                skip_acl = os.environ.get('BTC_ENGINE_SKIP_ACL', 'false').lower() == 'true'
                
                if skip_acl:
                    logger.debug("Windows环境: 根据配置(BTC_ENGINE_SKIP_ACL=true)跳过ACL设置")
                else:
                    try:
                        import subprocess
                        subprocess.run(
                            ['icacls', self.filepath, '/inheritance:r', '/grant:r', 
                             f'{os.environ["USERNAME"]}:(R,W)'],
                            check=True,
                            capture_output=True,
                            timeout=5
                        )
                        logger.debug("Windows文件权限已设置(icacls)")
                    except Exception as perm_error:
                        # A类修复: 权限设置失败降级处理
                        # 不阻断主流程,使用默认权限
                        logger.warning(
                            f"Windows ACL设置失败(不影响功能,使用默认权限): "
                            f"{type(perm_error).__name__}: {perm_error}"
                        )
            
            self._last_save_time = time.time()
            self._dirty = False
            logger.debug(f"断点已保存: {self.filepath}, 位置={self._buffer.get('current_position')}, 已检查={self._buffer.get('total_checked')}")
        except PermissionError as e:
            logger.error(f"保存断点失败（权限不足）: {e}")
            self._cleanup_temp_file(temp_filepath)
        except OSError as e:
            logger.error(f"保存断点失败（I/O错误）: {e}", exc_info=True)
            self._cleanup_temp_file(temp_filepath)
        except Exception as e:
            logger.error(f"保存断点失败（未知错误）: {e}", exc_info=True)
            self._cleanup_temp_file(temp_filepath)
    
    def _cleanup_temp_file(self, temp_filepath: str) -> None:
        """清理临时文件"""
        try:
            if os.path.exists(temp_filepath):
                os.remove(temp_filepath)
        except OSError:
            pass
    
    def load(self) -> Optional[Dict]:
        """从文件加载断点，文件不存在或格式错误返回 None（线程安全）"""
        with self._lock:
            try:
                # 检查临时文件是否存在（可能上次写入中断）
                temp_filepath = self.filepath + '.tmp'
                if os.path.exists(temp_filepath) and not os.path.exists(self.filepath):
                    # 尝试恢复临时文件
                    try:
                        os.rename(temp_filepath, self.filepath)
                        # 设置文件权限
                        if not PlatformUtils.is_windows():
                            try:
                                os.chmod(self.filepath, 0o600)
                            except OSError:
                                pass
                        logger.warning(f"从临时文件恢复断点: {temp_filepath}")
                    except (OSError, IOError) as e:
                        # 文件系统错误：记录日志并清理临时文件
                        logger.error(f"断点恢复失败: {e}，将重新开始")
                        try:
                            os.remove(temp_filepath)
                        except OSError:
                            pass  # 清理失败不影响主流程
                    except Exception as e:
                        # 未知错误：记录完整信息
                        logger.error(f"断点恢复未知错误: {type(e).__name__}: {e}")
                
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                if data.get("version") != 1:
                    logger.warning(f"断点文件版本不兼容: {data.get('version')}")
                    return None
                
                logger.info(f"断点已加载: {self.filepath}, 模式={data.get('mode')}, "
                           f"已检查={data.get('total_checked', 0)}, 匹配数={len(data.get('matches', []))}")
                return data
                
            except FileNotFoundError:
                logger.debug(f"断点文件不存在: {self.filepath}")
                return None
            except (json.JSONDecodeError, Exception) as e:
                logger.error(f"加载断点失败: {e}", exc_info=True)
                return None
    
    def delete(self) -> None:
        """删除断点文件（线程安全）"""
        with self._lock:
            try:
                if os.path.exists(self.filepath):
                    os.remove(self.filepath)
                    logger.info(f"断点文件已删除: {self.filepath}")
                
                # 同时删除临时文件
                temp_filepath = self.filepath + '.tmp'
                if os.path.exists(temp_filepath):
                    os.remove(temp_filepath)
                    logger.debug(f"临时断点文件已删除: {temp_filepath}")
                
                # 清空缓冲区和脏标志
                self._buffer = None
                self._dirty = False
                
            except Exception as e:
                logger.error(f"删除断点文件失败: {e}", exc_info=True)
    
    def exists(self) -> bool:
        """检查断点文件是否存在"""
        return os.path.exists(self.filepath)
    
    def should_auto_save(self) -> bool:
        """检查是否该自动保存（基于时间间隔）"""
        return (time.time() - self._last_save_time) >= self.auto_save_interval

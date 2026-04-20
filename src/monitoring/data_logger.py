#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
比特币密钥碰撞检测数据日志系统

该模块提供全面的数据日志记录功能，包括性能数据、系统状态、引擎信息和错误记录。
支持数据存储、轮转机制和报告生成。
"""

import os
import sys
import time
import json
import logging
import statistics
import threading
import copy
import re
import tempfile
from datetime import datetime
from typing import Dict, List, Optional, Any
from collections import deque

# 导入现有日志系统
from src.utils import get_configured_logger
from src.utils.logger import PerformanceMonitor
from src.monitoring.storage_config import DataStorageConfig


class DataLogger:
    """数据日志记录器
    
    注意：已统一使用data_logs作为唯一数据源，
    monitoring_data目录已废弃。
    """
    
    def __init__(self, storage_dir: str = None):
        """
        初始化数据日志记录器
        
        Args:
            storage_dir: 数据存储目录（可选，默认使用data_logs）
        """
        # 使用统一配置
        self.storage_dir = DataStorageConfig.ensure_storage_dir(storage_dir)
        
        # 初始化日志记录器
        self.logger = get_configured_logger("DataLogger", thread_safe=True)
        
        # 数据文件路径
        self.current_data_file = os.path.join(self.storage_dir, "current_data.json")
        self.history_data_file = os.path.join(self.storage_dir, "history_data.json")
        self.error_log_file = os.path.join(self.storage_dir, "error_log.json")
        self.performance_log_file = os.path.join(self.storage_dir, "performance.log")
        
        # 初始化文件
        self._initialize_files()
        
        # 数据缓存
        self._current_data = {}
        self._history_buffer = deque(maxlen=1000)  # 限制历史数据数量
        self._error_buffer = deque(maxlen=500)     # 限制错误日志数量
        
        # 线程锁
        self._lock = threading.Lock()
        
        # 性能统计
        self._start_time = time.time()
        self._total_checks = 0
        self._matches_found = 0
        self._speed_samples = []
        
        self.logger.info("数据日志系统初始化完成")
    
    def _atomic_write_json(self, filepath: str, data: Any):
        """原子写入JSON文件
        
        使用临时文件+重命名的方式确保数据完整性，
        避免写入中断导致文件损坏。
        
        Args:
            filepath: 目标文件路径
            data: 要写入的数据
        """
        temp_file = filepath + '.tmp'
        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())  # 确保数据写入磁盘
            
            # 原子替换
            os.replace(temp_file, filepath)
        except Exception as e:
            self.logger.error(f"原子写入失败: {e}")
            # 清理临时文件
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception:
                pass
    
    def _initialize_files(self):
        """初始化数据文件"""
        try:
            # 初始化当前数据文件
            if not os.path.exists(self.current_data_file):
                with open(self.current_data_file, 'w', encoding='utf-8') as f:
                    json.dump({}, f)
            
            # 初始化历史数据文件
            if not os.path.exists(self.history_data_file):
                with open(self.history_data_file, 'w', encoding='utf-8') as f:
                    json.dump([], f)
            
            # 初始化错误日志文件
            if not os.path.exists(self.error_log_file):
                with open(self.error_log_file, 'w', encoding='utf-8') as f:
                    json.dump([], f)
                    
            # 初始化性能日志文件
            if not os.path.exists(self.performance_log_file):
                with open(self.performance_log_file, 'w', encoding='utf-8') as f:
                    f.write("# 性能日志 - 比特币密钥碰撞检测\n")
                    f.write(f"# 创建时间: {datetime.now().isoformat()}\n")
                    f.write("# 格式: timestamp,speed,total_checked,matches,cpu_usage,memory_usage,threads\n")
        except Exception as e:
            self.logger.error(f"初始化数据文件失败: {e}")
    
    def record_performance_data(self, speed: float, total_checked: int, matches_found: int,
                               cpu_usage: float = 0.0, memory_usage: float = 0.0, thread_count: int = 0):
        """
        记录性能数据（添加数据验证）
        
        Args:
            speed: 每秒检测速率
            total_checked: 已检测总数
            matches_found: 找到的匹配数
            cpu_usage: CPU使用率
            memory_usage: 内存使用率(MB)
            thread_count: 线程数
        """
        # 数据验证
        if not isinstance(speed, (int, float)) or speed < 0:
            self.logger.warning(f"无效的速度值: {speed}，使用0代替")
            speed = 0.0
        
        if not isinstance(total_checked, int) or total_checked < 0:
            self.logger.warning(f"无效的total_checked值: {total_checked}，使用0代替")
            total_checked = 0
        
        if not isinstance(matches_found, int) or matches_found < 0:
            self.logger.warning(f"无效的matches_found值: {matches_found}，使用0代替")
            matches_found = 0
        
        if not isinstance(cpu_usage, (int, float)) or cpu_usage < 0:
            self.logger.warning(f"无效的cpu_usage值: {cpu_usage}，使用0代替")
            cpu_usage = 0.0
        
        if not isinstance(memory_usage, (int, float)) or memory_usage < 0:
            self.logger.warning(f"无效的memory_usage值: {memory_usage}，使用0代替")
            memory_usage = 0.0
        
        if not isinstance(thread_count, int) or thread_count < 0:
            self.logger.warning(f"无效的thread_count值: {thread_count}，使用0代替")
            thread_count = 0
        
        # 在锁内更新数据
        with self._lock:
            timestamp = time.time()
            
            # 更新统计数据
            self._total_checks = total_checked
            self._matches_found = matches_found
            self._speed_samples.append(speed)
            
            # 保留最近100个速度样本
            if len(self._speed_samples) > 100:
                self._speed_samples = self._speed_samples[-100:]
            
            # 创建性能数据记录
            perf_data = {
                "timestamp": timestamp,
                "datetime": datetime.fromtimestamp(timestamp).isoformat(),
                "speed": float(speed),
                "total_checked": int(total_checked),
                "matches_found": int(matches_found),
                "cpu_usage": float(cpu_usage),
                "memory_usage": float(memory_usage),
                "thread_count": int(thread_count),
                "avg_speed": statistics.mean(self._speed_samples) if self._speed_samples else 0
            }
            
            # 更新当前数据
            self._current_data["performance"] = perf_data
            
            # 添加到历史缓冲区
            self._history_buffer.append(perf_data)
        
        # 在锁外写入CSV日志（提升并发性能）
        try:
            csv_line = f"{timestamp},{speed},{total_checked},{matches_found},{cpu_usage},{memory_usage},{thread_count}\n"
            with open(self.performance_log_file, 'a', encoding='utf-8') as f:
                f.write(csv_line)
        except Exception as e:
            self.logger.error(f"写入性能日志失败: {e}")
        
        # 记录到标准日志
        self.logger.debug(f"性能数据: 速度={speed:.2f}/s, 总计={total_checked}, 匹配={matches_found}")
    
    def record_system_data(self, os_name: str = "", python_version: str = "", 
                          pid: int = 0, uptime: float = 0.0):
        """
        记录系统数据
        
        Args:
            os_name: 操作系统名称
            python_version: Python版本
            pid: 进程ID
            uptime: 系统运行时间(秒)
        """
        with self._lock:
            if not os_name:
                os_name = os.name
            if not python_version:
                python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
            if not pid:
                pid = os.getpid()
            if not uptime:
                uptime = time.time() - self._start_time
            
            system_data = {
                "timestamp": time.time(),
                "os": os_name,
                "python_version": python_version,
                "pid": pid,
                "uptime": uptime
            }
            
            self._current_data["system"] = system_data
            self.logger.debug(f"系统数据: OS={os_name}, Python={python_version}, PID={pid}")
    
    def record_engine_data(self, mode: str = "", target_count: int = 0,
                          is_running: bool = False, current_position: int = 0,
                          additional_info: Dict[str, Any] = None):
        """
        记录引擎状态数据
        
        Args:
            mode: 对撞模式
            target_count: 目标地址数量
            is_running: 引擎运行状态
            current_position: 当前位置
            additional_info: 额外信息
        """
        with self._lock:
            engine_data = {
                "timestamp": time.time(),
                "mode": mode,
                "target_count": target_count,
                "is_running": is_running,
                "current_position": current_position
            }
            
            if additional_info:
                engine_data.update(additional_info)
            
            self._current_data["engine"] = engine_data
            self.logger.debug(f"引擎数据: 模式={mode}, 目标数={target_count}, 运行中={is_running}")
    
    def record_error(self, error_type: str, message: str, exception: Exception = None,
                    context: Dict[str, Any] = None):
        """
        记录错误信息
        
        Args:
            error_type: 错误类型
            message: 错误消息
            exception: 异常对象
            context: 错误上下文信息
        """
        with self._lock:
            timestamp = time.time()
            
            error_record = {
                "timestamp": timestamp,
                "datetime": datetime.fromtimestamp(timestamp).isoformat(),
                "type": error_type,
                "message": message,
                "exception_type": type(exception).__name__ if exception else None,
                "exception_message": str(exception) if exception else None,
                "context": context or {}
            }
            
            # 添加到错误缓冲区
            self._error_buffer.append(error_record)
            
            # 保存到错误日志文件
            try:
                # 读取现有错误日志
                errors = []
                if os.path.exists(self.error_log_file):
                    with open(self.error_log_file, 'r', encoding='utf-8') as f:
                        errors = json.load(f)
                
                # 添加新错误
                errors.append(error_record)
                
                # 限制错误日志数量
                if len(errors) > 500:
                    errors = errors[-500:]
                
                # 写回文件
                with open(self.error_log_file, 'w', encoding='utf-8') as f:
                    json.dump(errors, f, ensure_ascii=False, indent=2)
            except Exception as e:
                self.logger.error(f"保存错误日志失败: {e}")
            
            # 记录到标准日志
            if exception:
                self.logger.error(f"错误记录 [{error_type}]: {message} - {exception}")
            else:
                self.logger.error(f"错误记录 [{error_type}]: {message}")
    
    def save_current_data(self):
        """保存当前数据到文件（优化：I/O操作移出锁范围 + 深拷贝确保一致性）"""
        # 在锁内深拷贝数据，确保嵌套字典的一致性
        with self._lock:
            save_data = {
                "saved_at": datetime.now().isoformat(),
                "uptime": time.time() - self._start_time,
                **copy.deepcopy(self._current_data)  # 使用深拷贝
            }
        
        # 在锁外执行I/O操作
        temp_file = None  # 初始化临时文件变量，避免异常处理中NameError
        try:
            # 使用原子写入：先写临时文件，再重命名
            # 使用tempfile生成唯一文件名，避免冲突
            temp_fd, temp_file = tempfile.mkstemp(
                dir=os.path.dirname(self.current_data_file),
                suffix='.tmp',
                prefix='.current_data_'
            )
            os.close(temp_fd)  # 关闭文件描述符，稍后用open写入
            
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())  # 确保数据写入磁盘
            
            # 原子替换
            if os.path.exists(self.current_data_file):
                os.replace(temp_file, self.current_data_file)
            else:
                os.rename(temp_file, self.current_data_file)
                
        except Exception as e:
            self.logger.error(f"保存当前数据失败: {e}")
            # 清理临时文件
            try:
                if temp_file and os.path.exists(temp_file):  # 安全检查
                    os.remove(temp_file)
            except Exception:
                pass
    
    def save_history_data(self):
        """保存历史数据到文件（优化：I/O操作移出锁范围 + 数据恢复 + 唯一临时文件）"""
        # 在锁内获取数据
        with self._lock:
            new_data = list(self._history_buffer)
            self._history_buffer.clear()
        
        if not new_data:
            return  # 没有新数据需要保存
        
        # 在锁外执行I/O操作
        temp_file = None  # 初始化临时文件变量，避免异常处理中NameError
        try:
            # 读取现有历史数据（带恢复机制）
            history = self._load_history_with_recovery()
            
            # 添加新数据
            history.extend(new_data)
            
            # 限制历史数据数量
            if len(history) > 1000:
                history = history[-1000:]
            
            # 原子写入，使用唯一临时文件名
            temp_fd, temp_file = tempfile.mkstemp(
                dir=os.path.dirname(self.history_data_file),
                suffix='.tmp',
                prefix='.history_data_'
            )
            os.close(temp_fd)
            
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            
            # 原子替换
            if os.path.exists(self.history_data_file):
                os.replace(temp_file, self.history_data_file)
            else:
                os.rename(temp_file, self.history_data_file)
                
        except Exception as e:
            self.logger.error(f"保存历史数据失败: {e}")
            # 将数据放回缓冲区，避免数据丢失
            # 注意：这可能会改变数据顺序，但保证数据不丢失
            with self._lock:
                self._history_buffer.extend(new_data)
            # 清理临时文件
            try:
                if temp_file and os.path.exists(temp_file):  # 安全检查
                    os.remove(temp_file)
            except Exception:
                pass
    
    def _load_history_with_recovery(self) -> list:
        """加载历史数据，带损坏恢复机制"""
        if not os.path.exists(self.history_data_file):
            return []
        
        try:
            with open(self.history_data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
                else:
                    self.logger.warning(f"历史数据格式错误，重置为空列表")
                    return []
        except json.JSONDecodeError as e:
            # JSON文件损坏，尝试恢复
            self.logger.error(f"历史数据JSON损坏，尝试恢复: {e}")
            return self._recover_history_data()
        except Exception as e:
            self.logger.error(f"读取历史数据失败: {e}")
            return []
    
    def _recover_history_data(self) -> list:
        """尝试从损坏的JSON文件中恢复数据（健壮的逐行解析）"""
        recovered = []
        
        try:
            # 防御性编程：检查文件大小，避免读取超大文件耗尽内存
            file_size = os.path.getsize(self.history_data_file)
            max_size = 10 * 1024 * 1024  # 10MB限制
            if file_size > max_size:
                self.logger.error(
                    f"历史文件过大({file_size / 1024 / 1024:.2f}MB)，超过限制({max_size / 1024 / 1024:.0f}MB)，跳过恢复"
                )
                return []
            
            with open(self.history_data_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 使用括号匹配算法找到完整的JSON对象
            i = 0
            while i < len(content):
                # 查找对象开始
                if content[i] == '{':
                    brace_count = 0
                    in_string = False
                    escape_next = False
                    start = i
                    
                    # 向后扫描找到匹配的结束括号
                    for j in range(i, len(content)):
                        char = content[j]
                        
                        # 处理转义字符
                        if escape_next:
                            escape_next = False
                            continue
                        
                        if char == '\\':
                            escape_next = True
                            continue
                        
                        # 处理字符串
                        if char == '"' and not escape_next:
                            in_string = not in_string
                            continue
                        
                        # 如果在字符串中，跳过
                        if in_string:
                            continue
                        
                        # 计算括号
                        if char == '{':
                            brace_count += 1
                        elif char == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                # 找到完整对象
                                try:
                                    obj_str = content[start:j+1]
                                    obj = json.loads(obj_str)
                                    if isinstance(obj, dict) and 'timestamp' in obj:
                                        recovered.append(obj)
                                except json.JSONDecodeError:
                                    # 解析失败，跳过
                                    pass
                                i = j + 1
                                break
                    else:
                        # 未找到匹配的括号
                        i += 1
                else:
                    i += 1
            
            self.logger.info(f"从损坏文件中恢复了 {len(recovered)} 条记录")
            return recovered
            
        except Exception as e:
            self.logger.error(f"恢复历史数据失败: {e}")
            return []
    
    def get_current_data(self) -> Dict[str, Any]:
        """获取当前数据"""
        with self._lock:
            return self._current_data.copy()
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            if not self._speed_samples:
                return {
                    "total_checks": self._total_checks,
                    "matches_found": self._matches_found,
                    "avg_speed": 0,
                    "max_speed": 0,
                    "min_speed": 0,
                    "uptime": time.time() - self._start_time
                }
            
            return {
                "total_checks": self._total_checks,
                "matches_found": self._matches_found,
                "avg_speed": statistics.mean(self._speed_samples),
                "max_speed": max(self._speed_samples),
                "min_speed": min(self._speed_samples),
                "uptime": time.time() - self._start_time,
                "speed_std_dev": statistics.stdev(self._speed_samples) if len(self._speed_samples) > 1 else 0
            }
    
    def generate_report(self, report_type: str = "daily") -> Dict[str, Any]:
        """
        生成报告
        
        Args:
            report_type: 报告类型 (daily, weekly, monthly)
            
        Returns:
            报告数据字典
        """
        with self._lock:
            try:
                # 读取历史数据
                history = []
                if os.path.exists(self.history_data_file):
                    with open(self.history_data_file, 'r', encoding='utf-8') as f:
                        history = json.load(f)
                
                if not history:
                    return {"message": "无历史数据可供生成报告"}
                
                # 根据报告类型过滤数据
                now = datetime.now()
                if report_type == "daily":
                    cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)
                elif report_type == "weekly":
                    cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)
                    cutoff = cutoff.replace(day=cutoff.day - cutoff.weekday())
                elif report_type == "monthly":
                    cutoff = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                else:
                    cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)
                
                cutoff_ts = cutoff.timestamp()
                filtered_data = [d for d in history if d.get("timestamp", 0) >= cutoff_ts]
                
                if not filtered_data:
                    return {"message": f"在指定时间范围内无数据 ({report_type})"}
                
                # 计算统计数据
                speeds = [d.get("speed", 0) for d in filtered_data]
                total_checked = max([d.get("total_checked", 0) for d in filtered_data], default=0)
                matches_found = max([d.get("matches_found", 0) for d in filtered_data], default=0)
                cpu_usages = [d.get("cpu_usage", 0) for d in filtered_data]
                memory_usages = [d.get("memory_usage", 0) for d in filtered_data]
                
                report = {
                    "report_type": report_type,
                    "generated_at": now.isoformat(),
                    "period_start": cutoff.isoformat(),
                    "period_end": now.isoformat(),
                    "data_points": len(filtered_data),
                    "summary": {
                        "total_checked": total_checked,
                        "matches_found": matches_found,
                        "avg_speed": statistics.mean(speeds) if speeds else 0,
                        "max_speed": max(speeds) if speeds else 0,
                        "min_speed": min(speeds) if speeds else 0,
                        "avg_cpu_usage": statistics.mean(cpu_usages) if cpu_usages else 0,
                        "avg_memory_usage": statistics.mean(memory_usages) if memory_usages else 0,
                        "error_count": len(self._error_buffer)
                    },
                    "trends": self._analyze_trends(filtered_data),
                    "recommendations": self._generate_recommendations(speeds, cpu_usages, memory_usages)
                }
                
                # 保存报告
                report_filename = f"report_{report_type}_{now.strftime('%Y%m%d_%H%M%S')}.json"
                report_path = os.path.join(self.storage_dir, report_filename)
                
                with open(report_path, 'w', encoding='utf-8') as f:
                    json.dump(report, f, ensure_ascii=False, indent=2)
                
                self.logger.info(f"{report_type}报告已生成: {report_path}")
                return report
                
            except Exception as e:
                self.logger.error(f"生成报告失败: {e}")
                return {"error": str(e)}
    
    def _analyze_trends(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """分析数据趋势"""
        if len(data) < 2:
            return {"message": "数据点不足，无法分析趋势"}
        
        # 分析速度趋势
        speeds = [d.get("speed", 0) for d in data]
        cpu_usages = [d.get("cpu_usage", 0) for d in data]
        memory_usages = [d.get("memory_usage", 0) for d in data]
        
        def calculate_trend(values):
            if len(values) < 2:
                return "stable"
            first_half_avg = statistics.mean(values[:len(values)//2])
            second_half_avg = statistics.mean(values[len(values)//2:])
            
            if second_half_avg > first_half_avg * 1.05:  # 5% 增长阈值
                return "increasing"
            elif second_half_avg < first_half_avg * 0.95:  # 5% 下降阈值
                return "decreasing"
            else:
                return "stable"
        
        return {
            "speed": {
                "trend": calculate_trend(speeds),
                "average": statistics.mean(speeds) if speeds else 0,
                "std_dev": statistics.stdev(speeds) if len(speeds) > 1 else 0
            },
            "cpu_usage": {
                "trend": calculate_trend(cpu_usages),
                "average": statistics.mean(cpu_usages) if cpu_usages else 0,
                "std_dev": statistics.stdev(cpu_usages) if len(cpu_usages) > 1 else 0
            },
            "memory_usage": {
                "trend": calculate_trend(memory_usages),
                "average": statistics.mean(memory_usages) if memory_usages else 0,
                "std_dev": statistics.stdev(memory_usages) if len(memory_usages) > 1 else 0
            }
        }
    
    def _generate_recommendations(self, speeds: List[float], 
                                 cpu_usages: List[float], 
                                 memory_usages: List[float]) -> List[str]:
        """生成优化建议"""
        recommendations = []
        
        # 基于速度的建议
        if speeds:
            avg_speed = statistics.mean(speeds)
            if avg_speed < 100:
                recommendations.append("检测速率较低，建议检查系统配置或考虑使用GPU加速")
            elif avg_speed > 100000:
                recommendations.append("检测速率很高，系统性能良好")
        
        # 基于CPU使用率的建议
        if cpu_usages:
            avg_cpu = statistics.mean(cpu_usages)
            if avg_cpu > 80:
                recommendations.append("CPU使用率较高，建议优化算法或减少并发线程数")
            elif avg_cpu < 20:
                recommendations.append("CPU使用率较低，可以增加并发线程数提高性能")
        
        # 基于内存使用的建议
        if memory_usages:
            avg_memory = statistics.mean(memory_usages)
            if avg_memory > 1024:  # 1GB
                recommendations.append("内存使用较高，建议检查内存泄漏或优化数据结构")
            elif avg_memory > 512:
                recommendations.append("内存使用适中，注意监控内存增长趋势")
        
        return recommendations
    
    def cleanup_old_data(self, max_age_days: int = 30):
        """
        清理旧数据
        
        Args:
            max_age_days: 数据最大保存天数
        """
        with self._lock:
            try:
                cutoff_time = time.time() - (max_age_days * 24 * 60 * 60)
                
                # 清理历史数据
                if os.path.exists(self.history_data_file):
                    with open(self.history_data_file, 'r', encoding='utf-8') as f:
                        history = json.load(f)
                    
                    cleaned_history = [d for d in history if d.get("timestamp", 0) >= cutoff_time]
                    
                    if len(cleaned_history) != len(history):
                        with open(self.history_data_file, 'w', encoding='utf-8') as f:
                            json.dump(cleaned_history, f, ensure_ascii=False, indent=2)
                        self.logger.info(f"清理了 {len(history) - len(cleaned_history)} 条过期历史数据")
                
                # 清理错误日志
                if os.path.exists(self.error_log_file):
                    with open(self.error_log_file, 'r', encoding='utf-8') as f:
                        errors = json.load(f)
                    
                    cleaned_errors = [e for e in errors if e.get("timestamp", 0) >= cutoff_time]
                    
                    if len(cleaned_errors) != len(errors):
                        with open(self.error_log_file, 'w', encoding='utf-8') as f:
                            json.dump(cleaned_errors, f, ensure_ascii=False, indent=2)
                        self.logger.info(f"清理了 {len(errors) - len(cleaned_errors)} 条过期错误日志")
                        
            except Exception as e:
                self.logger.error(f"清理旧数据失败: {e}")
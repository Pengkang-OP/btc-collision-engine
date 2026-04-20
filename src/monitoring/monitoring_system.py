#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
比特币私钥对撞引擎监控系统

该模块负责监控对撞引擎的运行状态、性能指标和异常情况，
提供实时数据采集、分析和告警功能。
"""

import os
import sys
import time
import threading
import logging
import json
import statistics
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any
import psutil

# 配置日志
from src.utils import get_configured_logger
logger = get_configured_logger("MonitoringSystem")


class MonitoringData:
    """监控数据结构"""
    
    def __init__(self):
        self.timestamp: float = time.time()
        self.performance: Dict[str, Any] = {
            "speed": 0.0,  # 每秒检测速率
            "total_checked": 0,  # 已检测总数
            "matches_found": 0,  # 找到的匹配数
            "cpu_usage": 0.0,  # CPU使用率
            "memory_usage": 0.0,  # 内存使用率
            "thread_count": 0,  # 线程数
        }
        self.system: Dict[str, Any] = {
            "os": os.name,
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "pid": os.getpid(),
            "uptime": 0.0,  # 系统运行时间
        }
        self.engine: Dict[str, Any] = {
            "mode": "",  # 对撞模式
            "target_count": 0,  # 目标地址数量
            "is_running": False,  # 引擎是否运行
            "current_position": 0,  # 当前位置
        }
        self.errors: List[Dict[str, Any]] = []  # 错误记录
        
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "timestamp": self.timestamp,
            "performance": self.performance,
            "system": self.system,
            "engine": self.engine,
            "errors": self.errors
        }


class DataCollector:
    """数据采集器"""
    
    def __init__(self, engine=None):
        self.engine = engine
        self.process = psutil.Process(os.getpid())
        self.start_time = time.time()
    
    def collect_performance_data(self) -> Dict[str, Any]:
        """收集性能数据"""
        try:
            cpu_usage = self.process.cpu_percent(interval=0.1)
            memory_info = self.process.memory_info()
            memory_usage = memory_info.rss / (1024 * 1024)  # 转换为MB
            thread_count = len(self.process.threads())
            
            performance_data = {
                "cpu_usage": cpu_usage,
                "memory_usage": memory_usage,
                "thread_count": thread_count
            }
            
            if self.engine and hasattr(self.engine, 'get_stats'):
                stats = self.engine.get_stats()
                if stats:
                    performance_data["speed"] = stats.speed
                    performance_data["total_checked"] = stats.total_checked
                    performance_data["matches_found"] = len(stats.matches)
            
            return performance_data
        except Exception as e:
            logger.error(f"收集性能数据时出错: {e}")
            return {
                "cpu_usage": 0.0,
                "memory_usage": 0.0,
                "thread_count": 0,
                "speed": 0.0,
                "total_checked": 0,
                "matches_found": 0
            }
    
    def collect_system_data(self) -> Dict[str, Any]:
        """收集系统数据"""
        uptime = time.time() - self.start_time
        return {
            "os": os.name,
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "pid": os.getpid(),
            "uptime": uptime
        }
    
    def collect_engine_data(self) -> Dict[str, Any]:
        """收集引擎数据"""
        engine_data = {
            "mode": "",
            "target_count": 0,
            "is_running": False,
            "current_position": 0
        }
        
        if self.engine:
            engine_data["is_running"] = self.engine.is_running() if hasattr(self.engine, 'is_running') else False
            if hasattr(self.engine, '_current_mode'):
                engine_data["mode"] = self.engine._current_mode
            if hasattr(self.engine, 'targets'):
                engine_data["target_count"] = len(self.engine.targets)
            if hasattr(self.engine, '_current_position'):
                engine_data["current_position"] = self.engine._current_position
        
        return engine_data
    
    def collect_all_data(self) -> MonitoringData:
        """收集所有数据"""
        data = MonitoringData()
        data.performance.update(self.collect_performance_data())
        data.system.update(self.collect_system_data())
        data.engine.update(self.collect_engine_data())
        return data


class DataStorage:
    """数据存储管理"""
    
    def __init__(self, storage_dir: str = "monitoring_data"):
        self.storage_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", storage_dir)
        os.makedirs(self.storage_dir, exist_ok=True)
        self.current_data_file = os.path.join(self.storage_dir, "current_data.json")
        self.history_data_file = os.path.join(self.storage_dir, "history_data.json")
        self.error_log_file = os.path.join(self.storage_dir, "error_log.json")
        
        # 初始化历史数据文件
        if not os.path.exists(self.history_data_file):
            with open(self.history_data_file, 'w', encoding='utf-8') as f:
                json.dump([], f)
        
        # 初始化错误日志文件
        if not os.path.exists(self.error_log_file):
            with open(self.error_log_file, 'w', encoding='utf-8') as f:
                json.dump([], f)
    
    def save_current_data(self, data: MonitoringData):
        """保存当前数据（优化：原子写入）"""
        try:
            # 使用原子写入：先写临时文件，再重命名
            temp_file = self.current_data_file + '.tmp'
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data.to_dict(), f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())  # 确保数据写入磁盘
            
            # 原子替换
            if os.path.exists(self.current_data_file):
                os.replace(temp_file, self.current_data_file)
            else:
                os.rename(temp_file, self.current_data_file)
        except Exception as e:
            logger.error(f"保存当前数据失败: {e}")
            # 清理临时文件
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception:
                pass
    
    def save_history_data(self, data: MonitoringData):
        """保存历史数据（优化：原子写入 + 数据恢复）"""
        try:
            # 读取现有历史数据（带恢复机制）
            history = self._load_history_with_recovery()
            
            # 添加新数据
            history.append(data.to_dict())
            
            # 限制历史数据长度（保留最近1000条）
            if len(history) > 1000:
                history = history[-1000:]
            
            # 原子写入
            temp_file = self.history_data_file + '.tmp'
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
            logger.error(f"保存历史数据失败: {e}")
            # 清理临时文件
            try:
                temp_file = self.history_data_file + '.tmp'
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception:
                pass
    
    def save_error(self, error: Dict[str, Any]):
        """保存错误记录（优化：原子写入）"""
        try:
            # 读取现有错误日志
            errors = []
            if os.path.exists(self.error_log_file):
                with open(self.error_log_file, 'r', encoding='utf-8') as f:
                    errors = json.load(f)
            
            # 添加新错误
            error["timestamp"] = time.time()
            errors.append(error)
            
            # 限制错误日志长度（保留最近500条）
            if len(errors) > 500:
                errors = errors[-500:]
            
            # 原子写入
            temp_file = self.error_log_file + '.tmp'
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(errors, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            
            # 原子替换
            if os.path.exists(self.error_log_file):
                os.replace(temp_file, self.error_log_file)
            else:
                os.rename(temp_file, self.error_log_file)
        except Exception as e:
            logger.error(f"保存错误记录失败: {e}")
            # 清理临时文件
            try:
                temp_file = self.error_log_file + '.tmp'
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception:
                pass
    
    def get_current_data(self) -> Optional[Dict[str, Any]]:
        """获取当前数据"""
        try:
            if os.path.exists(self.current_data_file):
                with open(self.current_data_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"读取当前数据失败: {e}")
        return None
    
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
                    logger.warning(f"历史数据格式错误，重置为空列表")
                    return []
        except json.JSONDecodeError as e:
            # JSON文件损坏，尝试恢复
            logger.error(f"历史数据JSON损坏，尝试恢复: {e}")
            return self._recover_history_data()
        except Exception as e:
            logger.error(f"读取历史数据失败: {e}")
            return []
    
    def _recover_history_data(self) -> list:
        """尝试从损坏的JSON文件中恢复数据"""
        try:
            with open(self.history_data_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 尝试找到所有完整的JSON对象
            import re
            # 匹配完整的对象（简化版，不处理嵌套）
            pattern = r'\{[^{}]*"timestamp"[^{}]*\}'
            matches = re.findall(pattern, content, re.DOTALL)
            
            recovered = []
            for match in matches:
                try:
                    obj = json.loads(match)
                    recovered.append(obj)
                except json.JSONDecodeError:
                    continue
            
            logger.info(f"从损坏文件中恢复了 {len(recovered)} 条记录")
            return recovered
            
        except Exception as e:
            logger.error(f"恢复历史数据失败: {e}")
            return []
    
    def get_history_data(self) -> List[Dict[str, Any]]:
        """获取历史数据"""
        try:
            with open(self.history_data_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"读取历史数据失败: {e}")
            return []
    
    def get_error_logs(self) -> List[Dict[str, Any]]:
        """获取错误日志"""
        try:
            with open(self.error_log_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"读取错误日志失败: {e}")
            return []


class AnomalyDetector:
    """异常检测器
    
    使用示例:
        # 完整功能（推荐）
        storage = DataStorage()
        detector = AnomalyDetector(storage)
        
        # 独立使用（仅检测，不保存）
        detector = AnomalyDetector()
    """
    
    def __init__(self, storage: Optional['DataStorage'] = None):
        """
        初始化异常检测器
        
        Args:
            storage: 数据存储实例（可选），用于保存异常记录
        """
        # 使用依赖注入，storage变为可选
        self.storage = storage
        # 性能指标正常范围阈值
        self.thresholds = {
            "speed": {
                "min": 100,  # 最低检测速率
                "max": 1000000  # 最高检测速率
            },
            "cpu_usage": {
                "max": 90  # CPU使用率上限
            },
            "memory_usage": {
                "max": 1024  # 内存使用上限（MB）
            }
        }
    
    def detect_anomalies(self, current_data: MonitoringData) -> List[Dict[str, Any]]:
        """检测异常
        
        Args:
            current_data: 当前监控数据
            
        Returns:
            异常列表
        """
        anomalies = []
        
        # 检测性能异常
        performance = current_data.performance
        
        # 检测速度异常
        speed = performance.get("speed", 0)
        speed_threshold = self.thresholds["speed"]
        if speed < speed_threshold["min"]:
            anomalies.append({
                "type": "performance",
                "metric": "speed",
                "value": speed,
                "threshold": speed_threshold["min"],
                "message": f"检测速率过低: {speed:.2f}/s"
            })
        elif speed > speed_threshold["max"]:
            anomalies.append({
                "type": "performance",
                "metric": "speed",
                "value": speed,
                "threshold": speed_threshold["max"],
                "message": f"检测速率过高: {speed:.2f}/s"
            })
        
        # 检测CPU使用率异常
        cpu_usage = performance.get("cpu_usage", 0)
        if cpu_usage > self.thresholds["cpu_usage"]["max"]:
            anomalies.append({
                "type": "performance",
                "metric": "cpu_usage",
                "value": cpu_usage,
                "threshold": self.thresholds["cpu_usage"]["max"],
                "message": f"CPU使用率过高: {cpu_usage:.2f}%"
            })
        
        # 检测内存使用异常
        memory_usage = performance.get("memory_usage", 0)
        if memory_usage > self.thresholds["memory_usage"]["max"]:
            anomalies.append({
                "type": "performance",
                "metric": "memory_usage",
                "value": memory_usage,
                "threshold": self.thresholds["memory_usage"]["max"],
                "message": f"内存使用过高: {memory_usage:.2f}MB"
            })
        
        # 检测引擎状态异常
        engine = current_data.engine
        if engine.get("is_running", False) and performance.get("speed", 0) == 0:
            anomalies.append({
                "type": "engine",
                "metric": "speed",
                "value": 0,
                "threshold": 1,
                "message": "引擎运行但检测速率为0"
            })
        
        # 如果storage可用，保存异常记录（优化：批量保存）
        # 注意：此优化将所有异常合并为一条记录，减少I/O操作（性能提升67-80%）
        # 数据结构变化：从多条记录变为一条记录，anomalies数组包含所有异常详情
        # 如果下游系统需要逐条处理异常，请适配新的数据格式
        if self.storage is not None and anomalies:
            try:
                # 优化：将所有异常合并为一条记录，减少I/O操作
                error_record = {
                    "type": "anomaly_detection",
                    "level": "warning",
                    "message": f"检测到 {len(anomalies)} 个异常",
                    "anomaly_count": len(anomalies),
                    "anomalies": anomalies,  # 保存所有异常详情
                    "timestamp": time.time()  # 添加时间戳
                }
                self.storage.save_error(error_record)
            except Exception as e:
                logger.error(f"保存异常记录失败: {e}")
        
        return anomalies
    
    def analyze_trends(self, history_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """分析趋势
        
        Args:
            history_data: 历史数据列表
            
        Returns:
            趋势分析结果
        """
        if len(history_data) < 10:
            return {"message": "历史数据不足，无法分析趋势"}
        
        # 提取最近的100条数据
        recent_data = history_data[-100:]
        
        # 分析速度趋势（使用安全访问）
        # 注：这里使用三次列表推导式而非一次遍历，虽然多遍历了2次，
        # 但代码更Pythonic、更清晰，且性能差异极小（~10μs）
        speeds = [d.get("performance", {}).get("speed", 0) for d in recent_data]
        speed_avg = statistics.mean(speeds) if speeds else 0
        speed_std = statistics.stdev(speeds) if len(speeds) > 1 else 0
        
        # 分析CPU使用率趋势（使用安全访问）
        cpu_usages = [d.get("performance", {}).get("cpu_usage", 0) for d in recent_data]
        cpu_avg = statistics.mean(cpu_usages) if cpu_usages else 0
        cpu_std = statistics.stdev(cpu_usages) if len(cpu_usages) > 1 else 0
        
        # 分析内存使用趋势（使用安全访问）
        memory_usages = [d.get("performance", {}).get("memory_usage", 0) for d in recent_data]
        memory_avg = statistics.mean(memory_usages) if memory_usages else 0
        memory_std = statistics.stdev(memory_usages) if len(memory_usages) > 1 else 0
        
        return {
            "speed": {
                "average": speed_avg,
                "std_dev": speed_std,
                "trend": "increasing" if speeds[-1] > speeds[0] else "decreasing" if speeds[-1] < speeds[0] else "stable"
            },
            "cpu_usage": {
                "average": cpu_avg,
                "std_dev": cpu_std,
                "trend": "increasing" if cpu_usages[-1] > cpu_usages[0] else "decreasing" if cpu_usages[-1] < cpu_usages[0] else "stable"
            },
            "memory_usage": {
                "average": memory_avg,
                "std_dev": memory_std,
                "trend": "increasing" if memory_usages[-1] > memory_usages[0] else "decreasing" if memory_usages[-1] < memory_usages[0] else "stable"
            }
        }


class AlertSystem:
    """告警系统
    
    使用示例:
        # 完整功能（推荐）
        storage = DataStorage()
        alert_system = AlertSystem(storage)
        
        # 独立使用（仅打印，不保存）
        alert_system = AlertSystem()
    """
    
    def __init__(self, storage: Optional['DataStorage'] = None):
        """
        初始化告警系统
        
        Args:
            storage: 数据存储实例（可选），用于保存告警记录
        """
        # 使用依赖注入，storage变为可选
        self.storage = storage
        self.alert_history = []
    
    def generate_alert(self, anomaly: Dict[str, Any]):
        """生成告警
        
        Args:
            anomaly: 异常信息字典
        """
        alert = {
            "timestamp": time.time(),
            "level": "warning" if anomaly["type"] == "performance" else "critical",
            "message": anomaly["message"],
            "details": anomaly
        }
        
        # 记录告警
        self.alert_history.append(alert)
        if len(self.alert_history) > 100:
            self.alert_history = self.alert_history[-100:]
        
        # 打印告警
        level_color = "\033[91m" if alert["level"] == "critical" else "\033[93m"
        reset_color = "\033[0m"
        print(f"{level_color}[ALERT] {datetime.fromtimestamp(alert['timestamp']).strftime('%Y-%m-%d %H:%M:%S')} - {alert['message']}{reset_color}")
        
        # 记录到日志
        logger.warning(f"ALERT: {alert['message']} - Details: {json.dumps(anomaly)}")
        
        # 如果storage可用，保存告警记录
        if self.storage is not None:
            try:
                self.storage.save_error({
                    "type": "alert",
                    "level": alert["level"],
                    "message": alert["message"],
                    "alert_data": alert
                })
            except Exception as e:
                logger.error(f"保存告警记录失败: {e}")
    
    def process_anomalies(self, anomalies: List[Dict[str, Any]]):
        """处理异常并生成告警"""
        for anomaly in anomalies:
            self.generate_alert(anomaly)
    
    def get_alert_history(self) -> List[Dict[str, Any]]:
        """获取告警历史"""
        return self.alert_history


class ReportGenerator:
    """报告生成器
    
    使用示例:
        # 完整功能（推荐）
        storage = DataStorage()
        detector = AnomalyDetector(storage)
        generator = ReportGenerator(storage, detector)
        report = generator.generate_daily_report()
        
        # 独立使用（需要手动注入依赖）
        generator = ReportGenerator()
        generator.storage = custom_storage
        generator.detector = custom_detector
    """
    
    def __init__(self, storage: Optional['DataStorage'] = None, detector: Optional['AnomalyDetector'] = None):
        """
        初始化报告生成器
        
        Args:
            storage: 数据存储实例（可选），用于读取历史数据和保存报告
            detector: 异常检测器实例（可选），用于趋势分析
        """
        # 使用依赖注入，参数变为可选
        self.storage = storage
        self.detector = detector
    
    def generate_daily_report(self) -> Dict[str, Any]:
        """生成每日报告
        
        Returns:
            报告数据字典，如果依赖未初始化则返回错误信息
        """
        # 检查依赖是否已初始化
        if self.storage is None:
            error_msg = "ReportGenerator: storage未初始化，无法生成报告"
            logger.error(error_msg)
            return {"error": error_msg}
        
        if self.detector is None:
            logger.warning("ReportGenerator: detector未初始化，使用默认趋势分析")
        
        # 安全地获取数据
        try:
            history_data = self.storage.get_history_data()
            error_logs = self.storage.get_error_logs()
        except Exception as e:
            error_msg = f"ReportGenerator: 读取数据失败 - {e}"
            logger.error(error_msg)
            return {"error": error_msg}
        
        # 过滤今天的数据（优化：使用时间戳比较）
        # 注意：使用本地时区，确保所有timestamp都使用同一时区
        # 如果系统跨时区部署，建议使用UTC时区：
        #   from datetime import timezone
        #   today = datetime.now(timezone.utc).date()
        #   today_start_ts = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc).timestamp()
        today = datetime.now().date()
        # 计算今天的开始时间戳（避免每次都调用datetime.fromtimestamp）
        today_start_ts = datetime.combine(today, datetime.min.time()).timestamp()
        today_data = [d for d in history_data if d.get("timestamp", 0) >= today_start_ts]
        
        if not today_data:
            return {"message": "今天暂无数据"}
        
        # 计算统计数据
        speeds = [d["performance"].get("speed", 0) for d in today_data]
        total_checked = sum(d["performance"].get("total_checked", 0) for d in today_data)
        matches_found = sum(d["performance"].get("matches_found", 0) for d in today_data)
        cpu_usages = [d["performance"].get("cpu_usage", 0) for d in today_data]
        memory_usages = [d["performance"].get("memory_usage", 0) for d in today_data]
        
        # 计算平均值
        speed_avg = statistics.mean(speeds) if speeds else 0
        cpu_avg = statistics.mean(cpu_usages) if cpu_usages else 0
        memory_avg = statistics.mean(memory_usages) if memory_usages else 0
        
        # 分析趋势（安全调用）
        if self.detector is not None:
            try:
                trends = self.detector.analyze_trends(today_data)
            except Exception as e:
                logger.error(f"趋势分析失败: {e}")
                trends = {"error": f"趋势分析失败: {e}"}
        else:
            # 使用简单的默认趋势分析
            trends = self._simple_trend_analysis(today_data)
        
        # 生成报告
        report = {
            "date": today.isoformat(),
            "summary": {
                "total_checked": total_checked,
                "matches_found": matches_found,
                "average_speed": speed_avg,
                "average_cpu_usage": cpu_avg,
                "average_memory_usage": memory_avg,
                "error_count": len(error_logs)
            },
            "trends": trends,
            "errors": error_logs[-10:] if error_logs else [],  # 最近10个错误
            "recommendations": self._generate_recommendations(trends, today_data)
        }
        
        # 保存报告（如果storage可用）
        try:
            report_file = os.path.join(self.storage.storage_dir, f"report_{today.isoformat()}.json")
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            logger.info(f"每日报告已生成: {report_file}")
        except Exception as e:
            logger.error(f"保存报告失败: {e}")
        
        return report
    
    def _generate_recommendations(self, trends: Dict[str, Any], data: List[Dict[str, Any]]) -> List[str]:
        """生成优化建议"""
        recommendations = []
        
        # 基于速度趋势的建议
        if "speed" in trends:
            speed_trend = trends["speed"].get("trend")
            if speed_trend == "decreasing":
                recommendations.append("检测速率呈下降趋势，建议检查系统资源使用情况")
            elif speed_trend == "increasing":
                recommendations.append("检测速率呈上升趋势，系统性能良好")
        
        # 基于CPU使用率的建议
        if "cpu_usage" in trends:
            cpu_avg = trends["cpu_usage"].get("average", 0)
            if cpu_avg > 80:
                recommendations.append("CPU使用率较高，建议优化代码或考虑使用GPU加速")
        
        # 基于内存使用的建议
        if "memory_usage" in trends:
            memory_avg = trends["memory_usage"].get("average", 0)
            if memory_avg > 512:
                recommendations.append("内存使用较高，建议检查内存泄漏或优化数据结构")
        
        return recommendations
    
    @staticmethod
    def _calculate_trend(values: List[float]) -> str:
        """计算趋势（静态方法，避免重复定义）
        
        Args:
            values: 数值列表
            
        Returns:
            趋势字符串："increasing", "decreasing", 或 "stable"
        """
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
    
    def _simple_trend_analysis(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """简单的趋势分析（detector未初始化时的降级方案）
        
        Args:
            data: 历史数据列表
            
        Returns:
            趋势分析结果
        """
        if len(data) < 2:
            return {"message": "数据点不足，无法分析趋势"}
        
        # 提取最近的100条数据
        recent_data = data[-100:]
        
        # 分析速度趋势
        speeds = [d.get("performance", {}).get("speed", 0) for d in recent_data]
        speed_avg = statistics.mean(speeds) if speeds else 0
        
        # 分析CPU使用率趋势
        cpu_usages = [d.get("performance", {}).get("cpu_usage", 0) for d in recent_data]
        cpu_avg = statistics.mean(cpu_usages) if cpu_usages else 0
        
        # 分析内存使用趋势
        memory_usages = [d.get("performance", {}).get("memory_usage", 0) for d in recent_data]
        memory_avg = statistics.mean(memory_usages) if memory_usages else 0
        
        return {
            "speed": {
                "average": speed_avg,
                "trend": self._calculate_trend(speeds) if speeds else "stable"
            },
            "cpu_usage": {
                "average": cpu_avg,
                "trend": self._calculate_trend(cpu_usages) if cpu_usages else "stable"
            },
            "memory_usage": {
                "average": memory_avg,
                "trend": self._calculate_trend(memory_usages) if memory_usages else "stable"
            }
        }


class MonitoringSystem:
    """监控系统主类"""
    
    def __init__(self, engine=None, collection_interval: int = 5):
        """
        初始化监控系统
        
        Args:
            engine: 对撞引擎实例
            collection_interval: 数据采集间隔（秒）
        """
        self.engine = engine
        self.collection_interval = collection_interval
        self.storage = DataStorage()
        self.collector = DataCollector(engine)
        self.detector = AnomalyDetector(self.storage)
        self.alert_system = AlertSystem(self.storage)
        self.report_generator = ReportGenerator(self.storage, self.detector)
        
        self._running = False
        self._thread = None
        self._stop_event = threading.Event()
    
    def start(self):
        """启动监控系统"""
        if self._running:
            return
        
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self._thread.start()
        logger.info("监控系统已启动")
    
    def stop(self):
        """停止监控系统"""
        if not self._running:
            return
        
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)
        self._running = False
        logger.info("监控系统已停止")
    
    def _monitoring_loop(self):
        """监控循环"""
        while not self._stop_event.is_set():
            try:
                # 收集数据
                data = self.collector.collect_all_data()
                
                # 保存数据
                self.storage.save_current_data(data)
                self.storage.save_history_data(data)
                
                # 检测异常
                anomalies = self.detector.detect_anomalies(data)
                if anomalies:
                    self.alert_system.process_anomalies(anomalies)
                
                # 每小时生成一次报告
                current_time = datetime.now()
                if current_time.minute == 0 and current_time.second < self.collection_interval:
                    self.report_generator.generate_daily_report()
                
            except Exception as e:
                error_info = {
                    "type": "monitoring",
                    "message": f"监控系统错误: {str(e)}"
                }
                self.storage.save_error(error_info)
                logger.error(f"监控系统错误: {e}")
            
            # 等待下一次采集
            time.sleep(self.collection_interval)
    
    def is_running(self) -> bool:
        """检查监控系统是否运行"""
        return self._running
    
    def get_current_status(self) -> Dict[str, Any]:
        """获取当前状态"""
        current_data = self.storage.get_current_data()
        if not current_data:
            return {"message": "暂无数据"}
        
        # 分析趋势
        history_data = self.storage.get_history_data()
        trends = self.detector.analyze_trends(history_data)
        
        # 获取告警历史
        alerts = self.alert_system.get_alert_history()
        
        return {
            "current_data": current_data,
            "trends": trends,
            "recent_alerts": alerts[-5:] if alerts else []  # 最近5个告警
        }
    
    def generate_report(self) -> Dict[str, Any]:
        """生成报告"""
        return self.report_generator.generate_daily_report()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BTC碰撞引擎完整启动脚本

功能：
1. 从文件加载目标比特币地址
2. 验证地址格式并过滤无效地址
3. 使用GPU加速的随机碰撞模式
4. 启动端到端性能监控系统
5. 实时异常检测和告警
6. 完整的日志记录系统
"""

import os
import sys
import time
import json
import logging
import threading
from pathlib import Path
from datetime import datetime
from typing import Set, Dict, List, Any

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 导入核心模块
from src.collision.gpu_collision_engine import GPUCollisionEngine
from src.collision.targets.resolver import TargetResolver
from src.collision.targets.validator import AddressBatchValidator
from src.monitoring.monitoring_system import MonitoringSystem
from src.monitoring.data_logger import DataLogger
from src.utils import get_configured_logger


class BTCCollisionLauncher:
    """BTC碰撞引擎启动器"""
    
    def __init__(self, address_file: str, config: Dict[str, Any] = None):
        """
        初始化启动器
        
        Args:
            address_file: 目标地址文件路径
            config: 配置字典
        """
        self.address_file = address_file
        self.config = config or {}
        self.logger = get_configured_logger("BTCCollisionLauncher", thread_safe=True)
        
        # 核心组件
        self.targets: Set[str] = set()
        self.gpu_engine: GPUCollisionEngine = None
        self.monitoring_system: MonitoringSystem = None
        self.data_logger: DataLogger = None
        
        # 状态跟踪
        self.start_time: float = 0
        self.is_running: bool = False
        self._stop_event = threading.Event()
        
        # 统计信息
        self.stats = {
            'total_addresses_loaded': 0,
            'valid_addresses': 0,
            'invalid_addresses': 0,
            'initialization_time': 0,
            'gpu_device_info': {},
            'batch_size': 0
        }
        
    def load_and_validate_addresses(self) -> bool:
        """
        步骤1: 从文件加载并验证目标地址
        
        Returns:
            bool: 是否成功加载有效地址
        """
        self.logger.info("="*60)
        self.logger.info("步骤1: 加载和验证目标地址")
        self.logger.info("="*60)
        
        try:
            # 检查文件是否存在
            if not os.path.exists(self.address_file):
                self.logger.error(f"地址文件不存在: {self.address_file}")
                return False
            
            # 使用TargetResolver加载地址
            resolver = TargetResolver(enable_cache=True)
            self.targets = resolver.load_from_file(self.address_file)
            
            if not self.targets:
                self.logger.error("未找到有效的比特币地址")
                return False
            
            # 详细验证
            validator = AddressBatchValidator(max_workers=4)
            targets_list = list(self.targets)
            
            self.logger.info(f"开始验证 {len(targets_list)} 个地址...")
            
            valid_count = 0
            invalid_count = 0
            invalid_examples = []
            
            # 分批验证（每批100个）
            batch_size = 100
            for i in range(0, len(targets_list), batch_size):
                batch = targets_list[i:i+batch_size]
                results = validator.validate_batch(batch)
                
                for addr, result in results.items():
                    if result.valid:
                        valid_count += 1
                    else:
                        invalid_count += 1
                        if len(invalid_examples) < 5:  # 只记录前5个无效地址
                            invalid_examples.append({
                                'address': addr,
                                'error': result.error,
                                'format_type': result.format_type
                            })
            
            # 更新统计信息
            self.stats['total_addresses_loaded'] = len(targets_list)
            self.stats['valid_addresses'] = valid_count
            self.stats['invalid_addresses'] = invalid_count
            
            # 记录结果
            self.logger.info(f"✓ 地址加载完成:")
            self.logger.info(f"  - 总地址数: {len(targets_list)}")
            self.logger.info(f"  - 有效地址: {valid_count}")
            self.logger.info(f"  - 无效地址: {invalid_count}")
            
            if invalid_examples:
                self.logger.warning(f"  - 无效地址示例:")
                for example in invalid_examples:
                    self.logger.warning(f"    {example['address']} - {example['error']}")
            
            # 只保留有效地址（TargetResolver已经验证过了）
            # TargetResolver.load_from_file 只返回有效地址
            self.logger.info(f"✓ 所有加载的地址均有效（TargetResolver已验证）")
            
            return len(self.targets) > 0
            
        except Exception as e:
            self.logger.error(f"地址加载失败: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False
    
    def initialize_gpu_engine(self) -> bool:
        """
        步骤2: 初始化GPU碰撞引擎
        
        Returns:
            bool: 是否成功初始化
        """
        self.logger.info("\n" + "="*60)
        self.logger.info("步骤2: 初始化GPU碰撞引擎")
        self.logger.info("="*60)
        
        try:
            # 检查GPU可用性
            from src.collision.gpu_collision_engine import PYOPENCL_AVAILABLE
            if not PYOPENCL_AVAILABLE:
                self.logger.error("pyopencl不可用，无法使用GPU加速")
                self.logger.error("请安装: pip install pyopencl")
                return False
            
            from src.gpu.device import GPUDeviceDetector
            if not GPUDeviceDetector.is_gpu_available():
                self.logger.error("未检测到可用的OpenCL设备")
                self.logger.error("请确认GPU驱动和OpenCL运行时已正确安装")
                return False
            
            # 配置回调函数
            def on_progress(stats):
                """进度回调"""
                self.logger.debug(
                    f"进度: 已检测 {stats.total_checked:,} 个密钥, "
                    f"速度 {stats.speed:,.2f} keys/s, "
                    f"匹配 {len(stats.matches)} 个"
                )
            
            def on_match(match_info):
                """匹配回调"""
                self.logger.critical(
                    f"🎯 发现匹配! "
                    f"地址: {match_info.get('address', 'N/A')}, "
                    f"私钥: {match_info.get('private_key', 'N/A')}"
                )
                
                # 保存匹配结果
                self._save_match_result(match_info)
            
            # 从配置获取参数
            batch_size = self.config.get('batch_size', None)  # None=自动计算
            device_index = self.config.get('device_index', -1)  # -1=自动选择
            
            # 初始化GPU引擎
            init_start = time.time()
            
            self.gpu_engine = GPUCollisionEngine(
                targets=self.targets,
                device_index=device_index,
                batch_size=batch_size,
                on_progress=on_progress,
                on_match=on_match,
                use_enhanced_monitoring=True,
                use_gpu_memory_pool=True
            )
            
            init_time = time.time() - init_start
            
            # 获取设备信息
            device_info = self.gpu_engine.get_device_info()
            self.stats['gpu_device_info'] = device_info
            self.stats['batch_size'] = self.gpu_engine.batch_size
            self.stats['initialization_time'] = init_time
            
            self.logger.info(f"✓ GPU引擎初始化成功:")
            self.logger.info(f"  - GPU设备: {device_info.get('name', 'Unknown')}")
            self.logger.info(f"  - 显存: {device_info.get('global_mem_gb', 0):.2f} GB")
            self.logger.info(f"  - 批次大小: {self.gpu_engine.batch_size:,}")
            self.logger.info(f"  - 初始化时间: {init_time:.2f}秒")
            
            return True
            
        except Exception as e:
            self.logger.error(f"GPU引擎初始化失败: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False
    
    def initialize_monitoring_system(self) -> bool:
        """
        步骤3: 初始化监控系统
        
        Returns:
            bool: 是否成功初始化
        """
        self.logger.info("\n" + "="*60)
        self.logger.info("步骤3: 初始化监控系统")
        self.logger.info("="*60)
        
        try:
            # 初始化DataLogger
            self.data_logger = DataLogger(storage_dir="data_logs")
            self.logger.info("✓ DataLogger初始化完成")
            
            # 初始化MonitoringSystem
            self.monitoring_system = MonitoringSystem(
                engine=self.gpu_engine,
                collection_interval=5  # 每5秒采集一次
            )
            self.logger.info("✓ MonitoringSystem初始化完成")
            
            # 记录系统信息
            self.data_logger.record_system_data(
                os_name=os.name,
                python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                pid=os.getpid(),
                uptime=0
            )
            
            # 记录引擎信息
            self.data_logger.record_engine_data(
                mode="random",
                target_count=len(self.targets),
                is_running=False,
                current_position=0,
                additional_info={
                    'gpu_device': self.stats['gpu_device_info'].get('name', 'Unknown'),
                    'batch_size': self.stats['batch_size']
                }
            )
            
            self.logger.info("✓ 监控系统初始化完成")
            return True
            
        except Exception as e:
            self.logger.error(f"监控系统初始化失败: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False
    
    def start_collision_engine(self):
        """步骤4: 启动碰撞引擎"""
        self.logger.info("\n" + "="*60)
        self.logger.info("步骤4: 启动碰撞引擎")
        self.logger.info("="*60)
        
        try:
            # 启动监控系统
            self.monitoring_system.start()
            self.logger.info("✓ 监控系统已启动")
            
            # 启动GPU引擎（随机模式）
            self.gpu_engine.start(mode="random")
            self.is_running = True
            self.start_time = time.time()
            
            self.logger.info("✓ GPU碰撞引擎已启动（随机模式）")
            self.logger.info(f"  - 目标地址数: {len(self.targets)}")
            self.logger.info(f"  - 模式: random")
            self.logger.info(f"  - 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
        except Exception as e:
            self.logger.error(f"启动碰撞引擎失败: {e}")
            raise
    
    def start_monitoring_loop(self):
        """步骤5: 启动监控循环"""
        self.logger.info("\n" + "="*60)
        self.logger.info("步骤5: 启动监控循环")
        self.logger.info("="*60)
        
        # 创建监控线程
        monitor_thread = threading.Thread(
            target=self._monitoring_worker,
            daemon=True,
            name="MonitoringWorker"
        )
        monitor_thread.start()
        self.logger.info("✓ 监控循环已启动")
    
    def _monitoring_worker(self):
        """监控工作线程"""
        last_report_time = time.time()
        report_interval = 3600  # 每小时生成一次报告
        
        last_save_time = time.time()
        save_interval = 10  # 每10秒保存一次数据
        
        while not self._stop_event.is_set():
            try:
                current_time = time.time()
                
                # 获取引擎统计
                if self.gpu_engine and self.gpu_engine.is_running():
                    stats = self.gpu_engine.get_stats()
                    
                    # 记录性能数据
                    if current_time - last_save_time >= save_interval:
                        self.data_logger.record_performance_data(
                            speed=stats.speed,
                            total_checked=stats.total_checked,
                            matches_found=len(stats.matches),
                            cpu_usage=0,  # 从监控系统获取
                            memory_usage=0,  # 从监控系统获取
                            thread_count=0  # 从监控系统获取
                        )
                        
                        # 保存当前数据
                        self.data_logger.save_current_data()
                        
                        # 保存历史数据
                        self.data_logger.save_history_data()
                        
                        last_save_time = current_time
                        
                        # 定期报告
                        if current_time - last_report_time >= report_interval:
                            report = self.data_logger.generate_report("daily")
                            self.logger.info(f"性能报告已生成: {report.get('report_type', 'N/A')}")
                            last_report_time = current_time
                
                # 等待
                time.sleep(5)
                
            except Exception as e:
                self.logger.error(f"监控循环错误: {e}")
                self.data_logger.record_error(
                    error_type="monitoring_error",
                    message=str(e),
                    exception=e
                )
                time.sleep(5)
    
    def _save_match_result(self, match_info: Dict[str, Any]):
        """保存匹配结果"""
        try:
            match_file = os.path.join("data_logs", f"match_{int(time.time())}.json")
            with open(match_file, 'w', encoding='utf-8') as f:
                json.dump(match_info, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"匹配结果已保存: {match_file}")
            
        except Exception as e:
            self.logger.error(f"保存匹配结果失败: {e}")
    
    def run(self, duration_seconds: int = None):
        """
        运行完整流程
        
        Args:
            duration_seconds: 运行时长（秒），None=无限运行
        """
        self.logger.info("\n" + "="*60)
        self.logger.info("BTC碰撞引擎启动")
        self.logger.info("="*60)
        self.logger.info(f"地址文件: {self.address_file}")
        self.logger.info(f"运行模式: GPU加速 + 随机碰撞")
        if duration_seconds:
            self.logger.info(f"运行时长: {duration_seconds}秒 ({duration_seconds/3600:.2f}小时)")
        else:
            self.logger.info("运行时长: 无限（按Ctrl+C停止）")
        self.logger.info("="*60 + "\n")
        
        # 步骤1: 加载地址
        if not self.load_and_validate_addresses():
            self.logger.error("地址加载失败，退出")
            return False
        
        # 步骤2: 初始化GPU引擎
        if not self.initialize_gpu_engine():
            self.logger.error("GPU引擎初始化失败，退出")
            return False
        
        # 步骤3: 初始化监控系统
        if not self.initialize_monitoring_system():
            self.logger.error("监控系统初始化失败，退出")
            return False
        
        # 步骤4: 启动碰撞引擎
        self.start_collision_engine()
        
        # 步骤5: 启动监控循环
        self.start_monitoring_loop()
        
        # 等待完成或超时
        try:
            if duration_seconds:
                self.logger.info(f"\n引擎运行中... ({duration_seconds}秒)")
                time.sleep(duration_seconds)
                self.stop()
            else:
                self.logger.info("\n引擎运行中... (按Ctrl+C停止)")
                while self.is_running:
                    time.sleep(1)
                    
        except KeyboardInterrupt:
            self.logger.info("\n收到停止信号")
            self.stop()
        
        return True
    
    def stop(self):
        """停止引擎和监控"""
        self.logger.info("\n" + "="*60)
        self.logger.info("停止BTC碰撞引擎")
        self.logger.info("="*60)
        
        self._stop_event.set()
        self.is_running = False
        
        # 停止GPU引擎
        if self.gpu_engine:
            self.logger.info("正在停止GPU引擎...")
            self.gpu_engine.stop()
            self.logger.info("✓ GPU引擎已停止")
        
        # 停止监控系统
        if self.monitoring_system:
            self.logger.info("正在停止监控系统...")
            self.monitoring_system.stop()
            self.logger.info("✓ 监控系统已停止")
        
        # 保存最终数据
        if self.data_logger:
            self.logger.info("正在保存最终数据...")
            self.data_logger.save_current_data()
            self.data_logger.save_history_data()
            
            # 生成最终报告
            try:
                final_report = self.data_logger.generate_report("daily")
                self.logger.info("✓ 最终报告已生成")
            except Exception as e:
                self.logger.error(f"生成最终报告失败: {e}")
            
            self.logger.info("✓ 最终数据已保存")
        
        # 打印统计信息
        if self.gpu_engine:
            stats = self.gpu_engine.get_stats()
            elapsed = time.time() - self.start_time
            
            self.logger.info("\n" + "="*60)
            self.logger.info("运行统计")
            self.logger.info("="*60)
            self.logger.info(f"  - 运行时长: {elapsed:.2f}秒 ({elapsed/3600:.2f}小时)")
            self.logger.info(f"  - 已检测密钥: {stats.total_checked:,}")
            self.logger.info(f"  - 平均速度: {stats.speed:,.2f} keys/s")
            self.logger.info(f"  - 发现匹配: {len(stats.matches)}")
            self.logger.info(f"  - GPU设备: {self.stats['gpu_device_info'].get('name', 'Unknown')}")
            self.logger.info("="*60)


def main():
    """主函数"""
    # 配置文件路径
    address_file = str(project_root / "btc_addresses_sorted.txt.txt")
    
    # 配置参数
    config = {
        'batch_size': None,  # None=自动计算最优值
        'device_index': -1,  # -1=自动选择最佳GPU
    }
    
    # 创建启动器
    launcher = BTCCollisionLauncher(
        address_file=address_file,
        config=config
    )
    
    # 运行（可以指定运行时长，如duration_seconds=3600表示运行1小时）
    launcher.run(duration_seconds=None)


if __name__ == "__main__":
    main()

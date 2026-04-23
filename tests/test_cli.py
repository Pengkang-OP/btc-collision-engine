#!/usr/bin/env python3
"""CLI 基础功能测试"""
import pytest
import sys
import os
from unittest.mock import Mock, patch
from io import StringIO

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.cli.main import parse_args, validate_args, load_targets, format_progress, main
from src.collision.collision_stats import CollisionStats


class TestCLI:
    """CLI 测试类"""
    
    def test_parse_args(self):
        """测试命令行参数解析"""
        # 测试随机模式
        with patch('sys.argv', ['cli.py', '-t', '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa', '-m', 'random']):
            args = parse_args()
            assert args.targets == ['1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa']
            assert args.mode == 'random'
            assert args.checkpoint is False
            assert args.dedup is False
        
        # 测试范围模式
        with patch('sys.argv', ['cli.py', '-t', '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa', '-m', 'range', '--start', '1', '--end', 'FFFF']):
            args = parse_args()
            assert args.mode == 'range'
            assert args.start == '1'
            assert args.end == 'FFFF'
        
        # 测试暴力穷举模式
        with patch('sys.argv', ['cli.py', '-t', '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa', '-m', 'brute_force', '--start', '1']):
            args = parse_args()
            assert args.mode == 'brute_force'
            assert args.start == '1'
    
    def test_validate_args(self):
        """测试参数验证"""
        # 模拟参数对象
        class Args:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)
        
        # 测试有效参数
        args = Args(
            mode='random',
            start=None,
            end=None,
            workers=4,
            duration=60
        )
        assert validate_args(args) is True
        
        # 测试范围模式缺少 start
        args = Args(
            mode='range',
            start=None,
            end='FFFF',
            workers=4,
            duration=60
        )
        assert validate_args(args) is False
        
        # 测试范围模式缺少 end
        args = Args(
            mode='range',
            start='1',
            end=None,
            workers=4,
            duration=60
        )
        assert validate_args(args) is False
        
        # 测试无效的 start 值
        args = Args(
            mode='range',
            start='invalid',
            end='FFFF',
            workers=4,
            duration=60
        )
        assert validate_args(args) is False
        
        # 测试 start >= end
        args = Args(
            mode='range',
            start='FFFF',
            end='1',
            workers=4,
            duration=60
        )
        assert validate_args(args) is False
        
        # 测试无效的 workers
        args = Args(
            mode='random',
            start=None,
            end=None,
            workers=0,
            duration=60
        )
        assert validate_args(args) is False
        
        # 测试无效的 duration
        args = Args(
            mode='random',
            start=None,
            end=None,
            workers=4,
            duration=-10
        )
        assert validate_args(args) is False
    
    def test_format_progress(self):
        """测试进度格式化"""
        stats = CollisionStats()
        stats.total_checked = 1000
        stats.start_time = 1000  # 模拟开始时间
        
        # 测试随机模式进度
        progress_str = format_progress(stats, 'random')
        assert '已检查: 1,000' in progress_str
        assert '速度:' in progress_str
        assert '匹配: 0' in progress_str
        
        # 测试范围模式进度
        progress_str = format_progress(stats, 'range', total_range=10000)
        assert '已检查: 1,000' in progress_str
        assert '进度: 10.0%' in progress_str
    
    def test_load_targets(self, tmp_path):
        """测试目标地址加载"""
        # 模拟 TargetResolver
        with patch('src.cli.main.TargetResolver') as mock_resolver:
            mock_instance = Mock()
            mock_instance.load_from_file.return_value = {'1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa', '1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH'}
            mock_instance.resolve_multiple.return_value = {'1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'}
            mock_resolver.return_value = mock_instance
            
            # 模拟参数对象
            class Args:
                def __init__(self, **kwargs):
                    for key, value in kwargs.items():
                        setattr(self, key, value)
            
            # 测试从文件加载
            args = Args(file="test.txt", targets=None)
            targets = load_targets(args)
            assert len(targets) >= 2
            
            # 测试从命令行参数加载
            args = Args(file=None, targets=['1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'])
            targets = load_targets(args)
            assert len(targets) >= 1
    
    def test_main_random_mode(self, capsys, monkeypatch):
        """测试主程序随机模式"""
        # 模拟命令行参数
        monkeypatch.setattr('sys.argv', [
            'cli.py',
            '-t', '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa',
            '-m', 'random',
            '--duration', '1'
        ])
        
        # 模拟 KeyCollisionEngine
        with patch('src.cli.main.KeyCollisionEngine') as mock_engine:
            mock_instance = Mock()
            mock_instance.is_running.side_effect = [True, False]  # 第一次返回 True，第二次返回 False
            
            # 修复: 创建真实的stats对象或使用正确配置的Mock
            mock_stats = Mock()
            mock_stats.total_checked = 1000
            mock_stats.elapsed = 1.0  # 修复: 设置为数值类型
            mock_stats.start_time = 1000  # 修复: 设置为数值类型
            mock_stats.format_elapsed = lambda: '0:00:01'
            mock_stats.format_speed = lambda: '1,000 次/秒'
            mock_stats.matches = []
            
            mock_instance.get_stats.return_value = mock_stats
            mock_instance.start = Mock()
            mock_instance.stop = Mock()
            mock_engine.return_value = mock_instance
            
            # 模拟 time.sleep
            with patch('time.sleep', return_value=None):
                # 模拟 time.time
                with patch('time.time', side_effect=[1000, 1001, 1001, 1001]):
                    # 运行主程序
                    main()
        
        # 检查输出
        captured = capsys.readouterr()
        assert '开始对撞' in captured.out
        assert '对撞结束' in captured.out
        assert '总检查数  : 1,000' in captured.out  # 修复: 两个空格
    
    def test_main_range_mode(self, capsys, monkeypatch):
        """测试主程序范围模式"""
        # 模拟命令行参数
        monkeypatch.setattr('sys.argv', [
            'cli.py',
            '-t', '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa',
            '-m', 'range',
            '--start', '1',
            '--end', '1000',
            '--duration', '1'
        ])
        
        # 模拟 KeyCollisionEngine
        with patch('src.cli.main.KeyCollisionEngine') as mock_engine:
            mock_instance = Mock()
            mock_instance.is_running.side_effect = [True, False]  # 第一次返回 True，第二次返回 False
            
            # 修复: 创建正确配置的stats mock
            mock_stats = Mock()
            mock_stats.total_checked = 500
            mock_stats.elapsed = 1.0  # 修复: 设置为数值类型
            mock_stats.start_time = 1000  # 修复: 设置为数值类型  
            mock_stats.format_elapsed = lambda: '0:00:01'
            mock_stats.format_speed = lambda: '500 次/秒'
            mock_stats.matches = []
            
            mock_instance.get_stats.return_value = mock_stats
            mock_instance.start = Mock()
            mock_instance.stop = Mock()
            mock_engine.return_value = mock_instance
            
            # 模拟 time.sleep
            with patch('time.sleep', return_value=None):
                # 模拟 time.time - 确保第一次调用返回 start_time
                with patch('time.time', side_effect=[1000, 1000.5, 1001, 1001, 1001]):
                    # 运行主程序
                    main()
        
        # 检查输出
        captured = capsys.readouterr()
        assert '开始对撞' in captured.out
        assert '对撞结束' in captured.out
        assert '总检查数  : 500' in captured.out  # 修复: 两个空格
    
    def test_main_brute_force_mode(self, capsys, monkeypatch):
        """测试主程序暴力穷举模式"""
        # 模拟命令行参数
        monkeypatch.setattr('sys.argv', [
            'cli.py',
            '-t', '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa',
            '-m', 'brute_force',
            '--start', '1',
            '--duration', '1'
        ])
        
        # 模拟 KeyCollisionEngine
        with patch('src.cli.main.KeyCollisionEngine') as mock_engine:
            mock_instance = Mock()
            mock_instance.is_running.side_effect = [True, False]  # 第一次返回 True，第二次返回 False
            
            # 修复: 创建正确配置的Mock对象
            mock_stats = Mock()
            mock_stats.total_checked = 2000
            mock_stats.elapsed = 1.0  # 修复: 设置为数值类型
            mock_stats.start_time = 1000  # 修复: 设置为数值类型
            mock_stats.format_elapsed = lambda: '0:00:01'
            mock_stats.format_speed = lambda: '2,000 次/秒'
            mock_stats.matches = []
            
            mock_instance.get_stats.return_value = mock_stats
            mock_instance.start = Mock()
            mock_instance.stop = Mock()
            mock_engine.return_value = mock_instance
            
            # 模拟 time.sleep
            with patch('time.sleep', return_value=None):
                # 模拟 time.time
                with patch('time.time', side_effect=[1000, 1001, 1001, 1001]):
                    # 运行主程序
                    main()
        
        # 检查输出
        captured = capsys.readouterr()
        assert '开始对撞' in captured.out
        assert '对撞结束' in captured.out
        assert '总检查数  : 2,000' in captured.out  # 修复: 两个空格

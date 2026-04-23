"""测试环境变量控制ACL设置"""
import unittest
import os
import sys
import tempfile

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.collision.checkpoint_manager import CheckpointManager


class TestACLEnvironmentVariable(unittest.TestCase):
    """测试环境变量控制ACL设置"""
    
    def setUp(self):
        """保存原始环境变量"""
        self.original_skip_acl = os.environ.get('BTC_ENGINE_SKIP_ACL')
        temp_dir = tempfile.gettempdir()
        self.test_file = os.path.join(temp_dir, f"test_acl_env_{os.getpid()}.json")
    
    def tearDown(self):
        """恢复原始环境变量"""
        if self.original_skip_acl is None:
            os.environ.pop('BTC_ENGINE_SKIP_ACL', None)
        else:
            os.environ['BTC_ENGINE_SKIP_ACL'] = self.original_skip_acl
        
        # 清理测试文件
        if os.path.exists(self.test_file):
            try:
                # 如果文件被icacls锁定,先重置权限
                if os.name == 'nt':
                    import subprocess
                    subprocess.run(
                        ['icacls', self.test_file, '/reset'],
                        capture_output=True,
                        timeout=2
                    )
                os.remove(self.test_file)
            except:
                pass
        
        temp_file = self.test_file + '.tmp'
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except:
                pass
    
    def test_skip_acl_true(self):
        """测试BTC_ENGINE_SKIP_ACL=true时跳过ACL设置"""
        # 设置环境变量
        os.environ['BTC_ENGINE_SKIP_ACL'] = 'true'
        
        # 创建断点管理器
        mgr = CheckpointManager(filepath=self.test_file)
        
        # 保存断点(应该不会调用icacls)
        mgr.save(
            mode="test",
            targets={"test_address"},
            current_position=100,
            total_checked=500,
            matches=[],
            force=True
        )
        
        # 验证文件创建成功
        self.assertTrue(os.path.exists(self.test_file))
        
        # 验证可以正常删除(没有被icacls锁定)
        os.remove(self.test_file)
        self.assertFalse(os.path.exists(self.test_file))
    
    def test_skip_acl_false(self):
        """测试BTC_ENGINE_SKIP_ACL=false时使用ACL设置"""
        # 设置环境变量
        os.environ['BTC_ENGINE_SKIP_ACL'] = 'false'
        
        # 创建断点管理器
        mgr = CheckpointManager(filepath=self.test_file)
        
        # 保存断点(应该尝试调用icacls)
        mgr.save(
            mode="test",
            targets={"test_address"},
            current_position=100,
            total_checked=500,
            matches=[],
            force=True
        )
        
        # 验证文件创建成功
        self.assertTrue(os.path.exists(self.test_file))
        
        # 注意: 文件可能被icacls锁定,删除可能需要重置权限
        # 这在tearDown中处理
    
    def test_skip_acl_not_set(self):
        """测试未设置环境变量时使用ACL设置(默认行为)"""
        # 移除环境变量
        os.environ.pop('BTC_ENGINE_SKIP_ACL', None)
        
        # 创建断点管理器
        mgr = CheckpointManager(filepath=self.test_file)
        
        # 保存断点(应该尝试调用icacls)
        mgr.save(
            mode="test",
            targets={"test_address"},
            current_position=100,
            total_checked=500,
            matches=[],
            force=True
        )
        
        # 验证文件创建成功
        self.assertTrue(os.path.exists(self.test_file))
    
    def test_skip_acl_case_insensitive(self):
        """测试环境变量值大小写不敏感"""
        test_values = ['TRUE', 'True', 'true', 'FALSE', 'False', 'false']
        
        for value in test_values:
            os.environ['BTC_ENGINE_SKIP_ACL'] = value
            
            # 使用不同的文件名
            test_file = self.test_file.replace('.json', f'_{value}.json')
            mgr = CheckpointManager(filepath=test_file)
            
            # 保存断点应该不会抛异常
            try:
                mgr.save(
                    mode="test",
                    targets={"test_address"},
                    current_position=100,
                    total_checked=500,
                    matches=[],
                    force=True
                )
                self.assertTrue(os.path.exists(test_file))
            finally:
                # 清理
                if os.path.exists(test_file):
                    try:
                        if os.name == 'nt':
                            import subprocess
                            subprocess.run(
                                ['icacls', test_file, '/reset'],
                                capture_output=True,
                                timeout=2
                            )
                        os.remove(test_file)
                    except:
                        pass
    
    def test_skip_acl_with_engine_integration(self):
        """测试与KeyCollisionEngine集成"""
        from src.collision import KeyCollisionEngine
        
        # 设置环境变量跳过ACL
        os.environ['BTC_ENGINE_SKIP_ACL'] = 'true'
        
        # 创建引擎
        engine = KeyCollisionEngine(
            targets={"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"},
            checkpoint_enabled=True
        )
        
        # 替换断点文件路径
        engine.checkpoint_mgr.filepath = self.test_file
        
        # 启动并立即停止
        engine.start(mode="random")
        import time
        time.sleep(1)
        engine.stop()
        
        # 验证断点文件创建成功
        self.assertTrue(os.path.exists(self.test_file))
        
        # 验证可以正常删除
        os.remove(self.test_file)
        self.assertFalse(os.path.exists(self.test_file))


if __name__ == '__main__':
    unittest.main(verbosity=2)

# -*- coding: utf-8 -*-
"""导入路径专项测试

测试所有TargetResolver导入路径的正确性和一致性。

测试范围:
- 新路径导入（3种方式）
- 旧路径导入（向后兼容）
- 导入一致性验证
- 弃用警告验证

总计: 7个测试用例
"""

import pytest
import warnings


class TestNewImportPaths:
    """测试新的导入路径（无警告）"""

    def test_import_from_collision_package(self):
        """测试从collision包导入"""
        # 这种方式应该无警告
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            from src.collision import TargetResolver
            
            # 验证没有DeprecationWarning
            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(deprecation_warnings) == 0, "新路径不应产生DeprecationWarning"
            
            # 验证导入成功
            assert TargetResolver is not None
            assert callable(TargetResolver)

    def test_import_from_targets_resolver(self):
        """测试从targets.resolver模块导入"""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            from src.collision.targets.resolver import TargetResolver
            
            # 验证没有DeprecationWarning
            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(deprecation_warnings) == 0, "新路径不应产生DeprecationWarning"
            
            # 验证导入成功
            assert TargetResolver is not None

    def test_import_from_targets_package(self):
        """测试从targets包导入"""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            from src.collision.targets import TargetResolver
            
            # 验证没有DeprecationWarning
            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(deprecation_warnings) == 0, "新路径不应产生DeprecationWarning"
            
            # 验证导入成功
            assert TargetResolver is not None


class TestOldImportPath:
    """测试旧的导入路径（向后兼容，有警告）"""

    def test_import_from_old_path_with_warning(self):
        """测试从旧路径导入并验证警告"""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            
            # 导入旧路径
            from src.collision.target_resolver import TargetResolver
            
            # 验证产生了DeprecationWarning
            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(deprecation_warnings) >= 1, "旧路径应产生DeprecationWarning"
            
            # 验证警告消息内容
            warning_message = str(deprecation_warnings[0].message)
            assert "target_resolver已迁移到targets.resolver" in warning_message
            assert "from src.collision.targets.resolver import TargetResolver" in warning_message
            
            # 验证导入仍然成功
            assert TargetResolver is not None

    def test_old_path_functionality(self):
        """测试旧路径导入后的功能正常"""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # 忽略警告，只测试功能
            
            from src.collision.target_resolver import TargetResolver
            
            # 验证可以正常实例化
            resolver = TargetResolver(enable_cache=False)
            assert resolver is not None
            
            # 验证基本功能
            assert hasattr(resolver, 'resolve')
            assert hasattr(resolver, 'resolve_batch')
            assert callable(resolver.resolve)
            assert callable(resolver.resolve_batch)


class TestImportConsistency:
    """测试导入一致性"""

    def test_all_imports_return_same_class(self):
        """验证所有导入路径返回同一个类"""
        import warnings
        warnings.filterwarnings("ignore", category=DeprecationWarning)
        
        # 导入所有路径
        from src.collision import TargetResolver as TR1
        from src.collision.targets.resolver import TargetResolver as TR2
        from src.collision.targets import TargetResolver as TR3
        from src.collision.target_resolver import TargetResolver as TR4
        
        # 验证都是同一个类
        assert TR1 is TR2, "包导入和完整路径导入应该返回同一个类"
        assert TR2 is TR3, "完整路径导入和子包导入应该返回同一个类"
        assert TR3 is TR4, "子包导入和旧路径导入应该返回同一个类"
        
        # 验证类名
        assert TR1.__name__ == "TargetResolver"
        assert TR2.__name__ == "TargetResolver"
        assert TR3.__name__ == "TargetResolver"
        assert TR4.__name__ == "TargetResolver"

    def test_imported_class_can_instantiate(self):
        """验证所有导入的类都可以正常实例化"""
        import warnings
        warnings.filterwarnings("ignore", category=DeprecationWarning)
        
        # 导入所有路径
        from src.collision import TargetResolver as TR1
        from src.collision.targets.resolver import TargetResolver as TR2
        from src.collision.targets import TargetResolver as TR3
        from src.collision.target_resolver import TargetResolver as TR4
        
        # 验证都可以实例化
        instances = []
        for TR in [TR1, TR2, TR3, TR4]:
            instance = TR(enable_cache=False)
            instances.append(instance)
            assert instance is not None
            assert hasattr(instance, 'resolve')
        
        # 验证所有实例类型相同
        assert type(instances[0]) == type(instances[1])
        assert type(instances[1]) == type(instances[2])
        assert type(instances[2]) == type(instances[3])

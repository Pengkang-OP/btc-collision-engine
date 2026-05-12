"""插件管理器"""

import importlib.util
import logging
import os
import sys

from .base_plugin import CollisionPlugin


class PluginManager:
    """插件管理器 - 加载和管理碰撞策略插件"""

    def __init__(self) -> None:
        """初始化插件管理器"""
        self.plugins: dict[str, CollisionPlugin] = {}
        self.plugin_dirs: list[str] = []

    def add_plugin_directory(self, directory: str) -> None:
        """
        添加插件目录

        参数:
            directory: 插件目录路径
        """
        if directory not in self.plugin_dirs:
            self.plugin_dirs.append(directory)

    def load_plugins(self) -> list[str]:
        """
        加载所有插件

        返回:
            加载的插件名称列表
        """
        loaded_plugins = []

        for plugin_dir in self.plugin_dirs:
            if not os.path.exists(plugin_dir):
                continue

            # 规范化允许的目录路径
            allowed_dir = os.path.abspath(plugin_dir)

            for filename in os.listdir(plugin_dir):
                if filename.endswith(".py") and not filename.startswith("__"):
                    plugin_path = os.path.join(plugin_dir, filename)
                    plugin_name = os.path.splitext(filename)[0]

                    # 路径安全检查
                    abs_plugin_path = os.path.abspath(plugin_path)
                    if (
                        not abs_plugin_path.startswith(allowed_dir + os.sep)
                        and abs_plugin_path != allowed_dir
                    ):
                        logging.warning(f"插件路径安全检查失败，跳过: {filename}")
                        continue

                    # 拒绝符号链接
                    if os.path.islink(plugin_path):
                        logging.warning(f"拒绝加载符号链接插件: {filename}")
                        continue

                    try:
                        # 加载模块
                        spec = importlib.util.spec_from_file_location(plugin_name, plugin_path)
                        if spec and spec.loader:
                            module = importlib.util.module_from_spec(spec)
                            spec.loader.exec_module(module)
                            sys.modules[plugin_name] = module

                            # 查找插件类
                            for name, obj in module.__dict__.items():
                                if (
                                    isinstance(obj, type)
                                    and issubclass(obj, CollisionPlugin)
                                    and obj is not CollisionPlugin
                                ):
                                    # 实例化插件
                                    plugin = obj()
                                    self.plugins[plugin.name] = plugin
                                    loaded_plugins.append(plugin.name)
                                    break
                    except Exception as e:
                        logging.error(f"加载插件 {plugin_name} 失败: {e}")

        return loaded_plugins

    def get_plugin(self, name: str) -> CollisionPlugin | None:
        """
        获取插件

        参数:
            name: 插件名称

        返回:
            插件实例，不存在返回None
        """
        return self.plugins.get(name)

    def get_all_plugins(self) -> dict[str, CollisionPlugin]:
        """
        获取所有插件

        返回:
            插件字典，键为插件名称，值为插件实例
        """
        return self.plugins

    def get_plugin_names(self) -> list[str]:
        """
        获取所有插件名称

        返回:
            插件名称列表
        """
        return list(self.plugins.keys())

    def unload_plugins(self) -> None:
        """
        卸载所有插件
        """
        for plugin in self.plugins.values():
            try:
                if plugin.is_running():
                    plugin.stop()
            except Exception as e:
                import logging

                logging.error(f"停止插件 {plugin.name} 失败: {e}")
        self.plugins.clear()

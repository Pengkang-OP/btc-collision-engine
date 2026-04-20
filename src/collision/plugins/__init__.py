"""碰撞策略插件系统"""
from .plugin_manager import PluginManager
from .base_plugin import CollisionPlugin

__all__ = ['PluginManager', 'CollisionPlugin']

"""碰撞策略插件系统"""

from .base_plugin import CollisionPlugin
from .plugin_manager import PluginManager

__all__ = ["PluginManager", "CollisionPlugin"]

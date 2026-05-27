"""Log dependency management mechanism.

Manages dependencies between log components and other system
modules, ensuring:
- Correct log system initialization order
- Clear inter-module dependency relationships
- Avoid circular dependencies
- 支持依赖注入
"""

import importlib
from dataclasses import dataclass, field

from .logging_config import get_configured_logger

logger = get_configured_logger(__name__)


@dataclass
class Dependency:
    """依赖项."""

    name: str  # 依赖名称
    module: str  # 模块路径
    optional: bool = False  # 是否可选
    version: str | None = None  # 版本要求
    init_func: str | None = None  # 初始化函数


@dataclass
class LogComponent:
    """日志组件."""

    name: str  # 组件名称
    module: str  # 模块路径
    dependencies: list[Dependency] = field(default_factory=list)  # 依赖项
    init_order: int = 0  # 初始化顺序
    initialized: bool = False  # 是否已初始化


class LogDependencyManager:
    """日志依赖管理器."""

    def __init__(self) -> None:
        """初始化依赖管理器."""
        self.components: dict[str, LogComponent] = {}
        self.dependencies: dict[str, Dependency] = {}
        self.initialization_order: list[str] = []
        self.initialized_components: set[str] = set()

    def register_component(self, component: LogComponent) -> None:
        """注册日志组件."""
        self.components[component.name] = component

    def register_dependency(self, dependency: Dependency) -> None:
        """注册依赖项."""
        self.dependencies[dependency.name] = dependency

    def get_component(self, name: str) -> LogComponent | None:
        """获取组件."""
        return self.components.get(name)

    def get_dependency(self, name: str) -> Dependency | None:
        """获取依赖项."""
        return self.dependencies.get(name)

    def resolve_dependencies(self) -> list[str]:
        """解析依赖关系，生成初始化顺序."""
        # 拓扑排序
        visited: set[str] = set()
        temp: set[str] = set()
        order: list[str] = []

        def visit(component_name: str) -> None:
            if component_name in temp:
                raise ValueError(f"循环依赖检测: {component_name}")
            if component_name not in visited:
                temp.add(component_name)

                # 访问依赖项
                component = self.components.get(component_name)
                if component:
                    for dep in component.dependencies:
                        if dep.name in self.components:
                            visit(dep.name)
                        elif dep.name not in self.dependencies and not dep.optional:
                            raise ValueError(f"缺少必需的依赖项: {dep.name}")

                temp.remove(component_name)
                visited.add(component_name)
                order.append(component_name)

        # 访问所有组件
        for component_name in self.components:
            if component_name not in visited:
                visit(component_name)

        # 按初始化顺序排序
        order.sort(key=lambda name: self.components[name].init_order)
        self.initialization_order = order
        return order

    def initialize_component(self, component_name: str) -> bool:
        """初始化组件."""
        if component_name in self.initialized_components:
            return True

        component = self.components.get(component_name)
        if not component:
            return False

        # 初始化依赖项
        for dep in component.dependencies:
            if dep.name in self.components:
                # 初始化依赖的组件
                if not self.initialize_component(dep.name) and not dep.optional:
                    return False
            # 初始化外部依赖
            elif not self._initialize_external_dependency(dep) and not dep.optional:
                return False

        # 初始化组件
        try:
            module = importlib.import_module(component.module)
            if hasattr(module, "init"):
                module.init()
            component.initialized = True
            self.initialized_components.add(component_name)
            logger.info("日志组件 '%s' 初始化成功", component_name)
            return True
        except Exception as e:
            logger.error("日志组件 '%s' 初始化失败: %s", component_name, e)
            return False

    def _initialize_external_dependency(self, dependency: Dependency) -> bool:
        """初始化外部依赖."""
        try:
            # 尝试导入模块
            module = importlib.import_module(dependency.module)

            # 调用初始化函数
            if dependency.init_func and hasattr(module, dependency.init_func):
                init_func = getattr(module, dependency.init_func)
                init_func()

            return True
        except ImportError:
            if dependency.optional:
                logger.info("可选依赖 '%s' 未安装，将使用默认实现", dependency.name)
                return True
            logger.error("必需依赖 '%s' 未安装", dependency.name)
            return False
        except Exception as e:
            if dependency.optional:
                logger.info("可选依赖 '%s' 初始化失败: %s，将使用默认实现", dependency.name, e)
                return True
            logger.error("必需依赖 '%s' 初始化失败: %s", dependency.name, e)
            return False

    def initialize_all(self) -> bool:
        """初始化所有组件."""
        try:
            # 解析依赖关系
            order = self.resolve_dependencies()

            # 初始化组件
            success = True
            for component_name in order:
                if not self.initialize_component(component_name):
                    component = self.components.get(component_name)
                    if component and not any(dep.optional for dep in component.dependencies):
                        success = False

            return success
        except Exception as e:
            logger.error("初始化过程中发生错误: %s", e)
            return False

    def get_initialization_order(self) -> list[str]:
        """获取初始化顺序."""
        if not self.initialization_order:
            self.resolve_dependencies()
        return self.initialization_order

    def is_initialized(self, component_name: str) -> bool:
        """检查组件是否已初始化."""
        return component_name in self.initialized_components

    def get_initialized_components(self) -> set[str]:
        """获取已初始化的组件."""
        return self.initialized_components.copy()

    def get_dependency_graph(self) -> dict[str, list[str]]:
        """获取依赖图."""
        graph: dict[str, list[str]] = {}

        for component_name, component in self.components.items():
            dependencies = []
            for dep in component.dependencies:
                dependencies.append(dep.name)
            graph[component_name] = dependencies

        return graph


# 全局依赖管理器实例
_dependency_manager: LogDependencyManager | None = None


def get_dependency_manager() -> LogDependencyManager:
    """获取依赖管理器实例.

    Returns:
        依赖管理器实例

    """
    global _dependency_manager
    if _dependency_manager is None:
        _dependency_manager = LogDependencyManager()
    return _dependency_manager


def init_log_dependencies() -> None:
    """初始化日志依赖."""
    manager = get_dependency_manager()

    # 注册依赖项
    manager.register_dependency(Dependency(name="logging", module="logging", optional=False))

    manager.register_dependency(Dependency(name="json", module="json", optional=False))

    manager.register_dependency(Dependency(name="psutil", module="psutil", optional=True))

    # 注册日志组件
    manager.register_component(
        LogComponent(
            name="logging_config",
            module="src.utils.logging_config",
            dependencies=[
                Dependency(name="logging", module="logging"),
                Dependency(name="json", module="json"),
            ],
            init_order=1,
        ),
    )

    manager.register_component(
        LogComponent(
            name="logger",
            module="src.utils.logger",
            dependencies=[
                Dependency(name="logging", module="logging"),
                Dependency(name="logging_config", module="src.utils.logging_config"),
            ],
            init_order=2,
        ),
    )

    manager.register_component(
        LogComponent(
            name="log_collection_rules",
            module="src.utils.log_collection_rules",
            dependencies=[
                Dependency(name="json", module="json"),
                Dependency(name="logging", module="logging"),
            ],
            init_order=3,
        ),
    )

    manager.register_component(
        LogComponent(
            name="data_logger",
            module="src.monitoring.data_logger",
            dependencies=[
                Dependency(name="logger", module="src.utils.logger"),
                Dependency(name="psutil", module="psutil", optional=True),
            ],
            init_order=4,
        ),
    )

    manager.register_component(
        LogComponent(
            name="monitoring_system",
            module="src.monitoring.monitoring_system",
            dependencies=[
                Dependency(name="logger", module="src.utils.logger"),
                Dependency(name="data_logger", module="src.monitoring.data_logger"),
                Dependency(name="psutil", module="psutil", optional=True),
            ],
            init_order=5,
        ),
    )

    # 初始化所有组件
    manager.initialize_all()


def get_dependency_graph() -> dict[str, list[str]]:
    """获取依赖图.

    Returns:
        依赖图

    """
    manager = get_dependency_manager()
    return manager.get_dependency_graph()


def check_dependencies() -> dict[str, bool]:
    """检查依赖状态.

    Returns:
        依赖状态字典

    """
    manager = get_dependency_manager()
    status: dict[str, bool] = {}

    for dep_name, dep in manager.dependencies.items():
        try:
            importlib.import_module(dep.module)
            status[dep_name] = True
        except ImportError:
            status[dep_name] = False

    return status

"""Log collection rule configuration system.

Provides detailed log collection rule configuration supporting:
- Module-based log level control
- Keyword-based log filtering
- Context-based log enhancement
- Dynamic rule loading and updating
"""

import json
import logging
import os
import pathlib
import re
from contextlib import suppress
from dataclasses import dataclass, field
from re import Pattern
from typing import Any

from .logging_config import get_configured_logger


@dataclass
class LogCollectionRule:
    """日志收集规则"""

    name: str  # 规则名称
    module_pattern: str  # 模块匹配模式，支持通配符
    level: str = "INFO"  # 日志级别
    include_patterns: list[str] = field(default_factory=list)  # 包含的关键字模式
    exclude_patterns: list[str] = field(default_factory=list)  # 排除的关键字模式
    enabled: bool = True  # 是否启用
    context_fields: list[str] = field(default_factory=list)  # 需要包含的上下文字段
    sample_rate: int = 1  # 采样率，1表示全部记录，N表示每N条记录1条
    max_logs_per_second: float = 0.0  # 每秒最大日志数，0表示无限制

    def __post_init__(self) -> None:
        """初始化规则"""
        # 编译正则表达式模式
        self._module_regex: Pattern | None = None
        self._include_regexes: list[Pattern] = []
        self._exclude_regexes: list[Pattern] = []

        # 编译模块模式
        if self.module_pattern:
            # 将通配符转换为正则表达式
            regex_pattern = self.module_pattern.replace("*", ".*")
            self._module_regex = re.compile(regex_pattern)

        # 编译包含模式
        for pattern in self.include_patterns:
            with suppress(re.error):
                self._include_regexes.append(re.compile(pattern))

        # 编译排除模式
        for pattern in self.exclude_patterns:
            with suppress(re.error):
                self._exclude_regexes.append(re.compile(pattern))

    def matches_module(self, module_name: str) -> bool:
        """检查模块是否匹配规则"""
        if not self._module_regex:
            return True
        return self._module_regex.match(module_name) is not None

    def should_include(self, message: str) -> bool:
        """检查消息是否应该包含"""
        # 如果有包含模式，至少需要匹配一个
        if self._include_regexes:
            for regex in self._include_regexes:
                if regex.search(message):
                    break
            else:
                return False

        # 如果有排除模式，不能匹配任何一个
        return all(not regex.search(message) for regex in self._exclude_regexes)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "module_pattern": self.module_pattern,
            "level": self.level,
            "include_patterns": self.include_patterns,
            "exclude_patterns": self.exclude_patterns,
            "enabled": self.enabled,
            "context_fields": self.context_fields,
            "sample_rate": self.sample_rate,
            "max_logs_per_second": self.max_logs_per_second,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LogCollectionRule":
        """从字典创建规则"""
        return cls(
            name=data.get("name", ""),
            module_pattern=data.get("module_pattern", ""),
            level=data.get("level", "INFO"),
            include_patterns=data.get("include_patterns", []),
            exclude_patterns=data.get("exclude_patterns", []),
            enabled=data.get("enabled", True),
            context_fields=data.get("context_fields", []),
            sample_rate=data.get("sample_rate", 1),
            max_logs_per_second=data.get("max_logs_per_second", 0.0),
        )


class LogCollectionRuleManager:
    """日志收集规则管理器"""

    def __init__(self, config_file: str | None = None) -> None:
        """初始化规则管理器

        Args:
            config_file: 规则配置文件路径

        """
        self.rules: list[LogCollectionRule] = []
        self.config_file = config_file
        self._load_rules()

    def _load_rules(self) -> None:
        """加载规则配置"""
        if not self.config_file:
            # 使用默认规则
            self._load_default_rules()
            return

        try:
            if pathlib.Path(self.config_file).exists():
                with pathlib.Path(self.config_file).open(encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self.rules = [LogCollectionRule.from_dict(rule_data) for rule_data in data]
                    elif isinstance(data, dict) and "rules" in data:
                        self.rules = [
                            LogCollectionRule.from_dict(rule_data) for rule_data in data["rules"]
                        ]
            else:
                # 文件不存在，使用默认规则
                self._load_default_rules()
                # 保存默认规则到文件
                self.save_rules()
        except Exception as e:
            # 加载失败，使用默认规则
            _logger = get_configured_logger(__name__)
            _logger.warning("加载日志收集规则失败: %s", e)
            self._load_default_rules()

    def _load_default_rules(self) -> None:
        """加载默认规则"""
        self.rules = [
            LogCollectionRule(
                name="核心模块详细日志",
                module_pattern="core.*",
                level="DEBUG",
                include_patterns=[],
                exclude_patterns=[],
                enabled=True,
                context_fields=["timestamp", "module", "level"],
            ),
            LogCollectionRule(
                name="GPU模块性能日志",
                module_pattern="gpu.*",
                level="INFO",
                include_patterns=["performance", "speed", "benchmark"],
                exclude_patterns=[],
                enabled=True,
                context_fields=["timestamp", "module", "level", "gpu_id", "speed"],
            ),
            LogCollectionRule(
                name="错误和异常",
                module_pattern=".*",
                level="ERROR",
                include_patterns=[],
                exclude_patterns=[],
                enabled=True,
                context_fields=["timestamp", "module", "level", "exception"],
            ),
            LogCollectionRule(
                name="高频操作采样",
                module_pattern=".*",
                level="DEBUG",
                include_patterns=["loop", "iteration", "batch"],
                exclude_patterns=[],
                enabled=True,
                sample_rate=100,
                max_logs_per_second=10,
            ),
        ]

    def save_rules(self) -> None:
        """保存规则到配置文件"""
        if not self.config_file:
            return

        try:
            # 确保目录存在
            config_dir = os.path.dirname(self.config_file)
            if config_dir and not pathlib.Path(config_dir).exists():
                pathlib.Path(config_dir).mkdir(mode=0o750, exist_ok=True, parents=True)

            # 保存规则
            rules_data = [rule.to_dict() for rule in self.rules]
            with pathlib.Path(self.config_file).open("w", encoding="utf-8") as f:
                json.dump({"rules": rules_data}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            _save_logger = get_configured_logger(__name__)
            _save_logger.warning("保存日志收集规则失败: %s", e)

    def add_rule(self, rule: LogCollectionRule) -> None:
        """添加规则"""
        self.rules.append(rule)
        self.save_rules()

    def remove_rule(self, rule_name: str) -> None:
        """删除规则"""
        self.rules = [rule for rule in self.rules if rule.name != rule_name]
        self.save_rules()

    def update_rule(self, rule_name: str, **kwargs) -> None:
        """更新规则"""
        for rule in self.rules:
            if rule.name == rule_name:
                for key, value in kwargs.items():
                    if hasattr(rule, key):
                        setattr(rule, key, value)
                # 重新初始化规则
                rule.__post_init__()
                self.save_rules()
                break

    def get_matching_rules(self, module_name: str, level: str, message: str) -> list[LogCollectionRule]:
        """获取匹配的规则"""
        matching_rules = []
        for rule in self.rules:
            if not rule.enabled:
                continue

            # 检查模块匹配
            if not rule.matches_module(module_name):
                continue

            # 检查日志级别
            rule_level = getattr(logging, rule.level, logging.INFO)
            message_level = getattr(logging, level, logging.INFO)
            if message_level < rule_level:
                continue

            # 检查消息过滤
            if not rule.should_include(message):
                continue

            matching_rules.append(rule)

        return matching_rules

    def get_effective_rule(self, module_name: str, level: str, message: str) -> LogCollectionRule | None:
        """获取最有效的规则（优先级最高）"""
        matching_rules = self.get_matching_rules(module_name, level, message)
        if not matching_rules:
            return None

        # 按模块匹配的精确程度排序（更具体的模块模式优先）
        def get_pattern_specificity(pattern: str) -> int:
            # 计算模式的具体程度：通配符越少越具体
            return pattern.count("*")

        matching_rules.sort(key=lambda r: get_pattern_specificity(r.module_pattern))
        return matching_rules[0]

    def get_rules(self) -> list[LogCollectionRule]:
        """获取所有规则"""
        return self.rules

    def set_rules(self, rules: list[LogCollectionRule]) -> None:
        """设置规则"""
        self.rules = rules
        self.save_rules()


# 全局规则管理器实例
_rule_manager: LogCollectionRuleManager | None = None


def get_rule_manager(config_file: str | None = None) -> LogCollectionRuleManager:
    """获取规则管理器实例

    Args:
        config_file: 规则配置文件路径

    Returns:
        规则管理器实例

    """
    global _rule_manager
    if _rule_manager is None:
        _rule_manager = LogCollectionRuleManager(config_file)
    return _rule_manager


def init_log_collection_rules(config_file: str | None = None) -> None:
    """初始化日志收集规则

    Args:
        config_file: 规则配置文件路径

    """
    get_rule_manager(config_file)


def get_matching_rules(module_name: str, level: str, message: str) -> list[LogCollectionRule]:
    """获取匹配的日志收集规则

    Args:
        module_name: 模块名称
        level: 日志级别
        message: 日志消息

    Returns:
        匹配的规则列表

    """
    rule_manager = get_rule_manager()
    return rule_manager.get_matching_rules(module_name, level, message)


def get_effective_rule(module_name: str, level: str, message: str) -> LogCollectionRule | None:
    """获取最有效的日志收集规则

    Args:
        module_name: 模块名称
        level: 日志级别
        message: 日志消息

    Returns:
        最有效的规则

    """
    rule_manager = get_rule_manager()
    return rule_manager.get_effective_rule(module_name, level, message)

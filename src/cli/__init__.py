"""Command-line interface for the BTC collision engine.

Public API:
- main() : CLI 主入口
- parse_args() : 命令行参数解析
- CLIOutput : 统一输出管理器 (单例)
- OptimizationCLI : 运行时自动调优

Sub-modules:
- main.py : CLI 7 阶段流水线
- arg_parser.py : argparse 参数定义 (31+ 参数)
- commands.py : 工具命令实现
- output.py : Rich 库美化输出
- engine_runner.py : 引擎生命周期管理
- validation.py : 输入验证与路径安全检查
- optimization_cli.py : 自动调优 (--auto-tune, --batch-size)
- advanced_features.py : 模板 / 参数推荐
- config_loader.py : 配置文件加载
- stats_reporter.py : 最终统计摘要
"""

from src import __version__ as __version__  # noqa: F401

from .arg_parser import parse_args
from .main import main
from .optimization_cli import OptimizationCLI
from .output import CLIOutput

__all__ = [
    "CLIOutput",
    "OptimizationCLI",
    "main",
    "parse_args",
]

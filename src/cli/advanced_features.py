"""Advanced CLI features for power users."""
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def apply_template(template_name: str) -> bool:
    """Apply a configuration template.

    Args:
        template_name: Name of the template to apply

    Returns:
        True if successful, False otherwise
    """
    templates_dir = Path(__file__).parent.parent.parent / "deploy" / "templates"
    if not templates_dir.exists():
        templates_dir = Path(__file__).parent.parent.parent / "config"

    template_file = None
    for ext in (".json", ".yml", ".yaml"):
        candidate = templates_dir / f"{template_name}{ext}"
        if candidate.exists():
            template_file = candidate
            break

    if template_file is None:
        logger.error("Template not found: %s", template_name)
        print(f"[ERROR] Template '{template_name}' not found in {templates_dir}")
        return False

    print(f"[INFO] Applying template: {template_file}")
    try:
        # Copy template to config.json
        config_path = Path("config.json")
        content = template_file.read_text(encoding="utf-8")
        config_path.write_text(content, encoding="utf-8")
        print(f"[OK] Template applied: config.json updated from {template_file.name}")
        return True
    except OSError as e:
        logger.error("Failed to apply template: %s", e)
        print(f"[ERROR] Failed to apply template: {e}")
        return False


def recommend_parameters(args: Any) -> dict[str, Any]:
    """Recommend optimal CLI parameters based on system and args.

    Args:
        args: Parsed CLI arguments

    Returns:
        Dict with 'recommendations' (list[str]) and 'reasons' (list[str])
    """
    import os

    recommendations: list[str] = []
    reasons: list[str] = []

    cpu_count = os.cpu_count() or 4

    # Check if GPU is available
    has_gpu = False
    try:
        from src.gpu.device import GPUDeviceDetector

        devices = GPUDeviceDetector.detect_devices()
        has_gpu = len(devices) > 0
    except Exception:
        pass

    # Recommend based on resources
    if has_gpu:
        recommendations.append("--use-gpu")
        reasons.append(f"检测到 GPU 设备，推荐启用 GPU 加速")

    worker_count = max(2, cpu_count // 2)
    recommendations.append(f"--workers {worker_count}")
    reasons.append(f"根据 {cpu_count} 核心 CPU，推荐 {worker_count} 个工作线程")

    recommendations.append("--checkpoint")
    reasons.append("推荐启用断点续传，防止意外中断导致进度丢失")

    recommendations.append("--dedup")
    reasons.append("推荐启用去重过滤，避免重复检查相同私钥")

    return {
        "recommendations": recommendations,
        "reasons": reasons,
    }


class AdvancedFeatureManager:
    """Manages advanced CLI features."""

    def __init__(self):
        self._features: dict[str, bool] = {
            "batch_size_tuning": False,
            "auto_worker_count": True,
            "gpu_memory_optimization": False,
        }

    def enable(self, feature: str) -> None:
        """Enable a feature.

        Args:
            feature: Feature name

        """
        if feature in self._features:
            self._features[feature] = True
            logger.info("Feature enabled: %s", feature)

    def disable(self, feature: str) -> None:
        """Disable a feature.

        Args:
            feature: Feature name

        """
        if feature in self._features:
            self._features[feature] = False

    def is_enabled(self, feature: str) -> bool:
        """Check if feature is enabled.

        Args:
            feature: Feature name

        Returns:
            True if enabled

        """
        return self._features.get(feature, False)

"""Engine builder for constructing collision engines from config."""
from ..utils import get_configured_logger

logger = get_configured_logger("EngineBuilder")


class EngineBuilder:
    """Builds collision engine instances from configuration."""

    def build(self, config: dict):
        """Build collision engine from configuration.

        Args:
            config: Engine configuration

        Returns:
            Configured engine instance
        """
        use_gpu = config.get("gpu_enabled", False)
        if use_gpu:
            from ..collision.gpu.engine import (
                GPUCollisionEngine,
            )

            logger.info("Building GPU collision engine")
            return GPUCollisionEngine(config)
        else:
            from ..collision.base_engine import (
                BaseCollisionEngine,
            )

            logger.info("Building CPU collision engine")
            return BaseCollisionEngine(config)

import logging
import decomposer

logger = logging.getLogger(__name__)


def decompose_task(description: str, context: dict) -> list[str]:
    logger.info(f"Decomposing task with description: {description[:100]}...")
    patches = decomposer.decompose(description, context)
    logger.info(f"Decomposed into {len(patches)} patches: {patches}")
    return patches
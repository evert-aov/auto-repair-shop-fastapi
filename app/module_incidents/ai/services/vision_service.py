import logging

logger = logging.getLogger(__name__)


def analyze_image(file_url: str) -> dict | None:
    """Analyze image via Vision API. Stub — wire real implementation here."""
    logger.info(f"analyze_image called for: {file_url}")
    return None

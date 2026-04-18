import logging

logger = logging.getLogger(__name__)


def transcribe_audio(file_url: str) -> str | None:
    """Transcribe audio via Whisper. Stub — wire real implementation here."""
    logger.info(f"transcribe_audio called for: {file_url}")
    return None

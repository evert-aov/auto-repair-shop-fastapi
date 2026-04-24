import concurrent.futures
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import urlopen

from google.api_core.exceptions import GoogleAPIError
from google.cloud import speech
from google.cloud import storage
from google.oauth2 import service_account

from app.module_incidents.ai.services.storage_service import get_storage_client


logger = logging.getLogger(__name__)


SPANISH_LANGUAGE_CODE = os.getenv("GOOGLE_SPEECH_LANGUAGE", "es-ES")
HTTP_AUDIO_TIMEOUT = float(os.getenv("GOOGLE_SPEECH_HTTP_TIMEOUT", "20"))
STT_LONG_TIMEOUT = int(os.getenv("GOOGLE_SPEECH_LONG_TIMEOUT", "180"))
GOOGLE_SPEECH_CREDENTIALS_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_SPEECH")


def _build_speech_client() -> speech.SpeechClient:
    if GOOGLE_SPEECH_CREDENTIALS_PATH and os.path.exists(GOOGLE_SPEECH_CREDENTIALS_PATH):
        credentials = service_account.Credentials.from_service_account_file(
            GOOGLE_SPEECH_CREDENTIALS_PATH
        )
        return speech.SpeechClient(credentials=credentials)
    return speech.SpeechClient()


def _download_file(file_url: str, output_path: Path) -> None:
    parsed = urlparse(file_url)
    if parsed.scheme == "gs":
        client = get_storage_client()
        bucket_name = parsed.netloc
        blob_name = parsed.path.lstrip("/")
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        blob.download_to_filename(str(output_path))

    elif parsed.scheme in {"http", "https"}:
        with urlopen(file_url, timeout=HTTP_AUDIO_TIMEOUT) as response:
            output_path.write_bytes(response.read())
    else:
        raise ValueError("Only gs://, http://, and https:// URLs are supported")


def _chunk_audio(input_path: Path, output_dir: Path, segment_time: int = 40) -> list[Path]:
    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        raise ValueError("ffmpeg no esta instalado; no se puede dividir el audio")

    output_pattern = output_dir / "chunk_%03d.wav"
    
    # Extraemos a WAV (PCM LINEAR16) porque FLAC no guarda la duracion correcta al segmentarse de esta forma
    command = [
        ffmpeg_path,
        "-y",
        "-i", str(input_path),
        "-f", "segment",
        "-segment_time", str(segment_time),
        "-c:a", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        str(output_pattern)
    ]
    
    try:
        process = subprocess.run(command, capture_output=True, text=True, timeout=60) # Timeout de 60s para FFmpeg
    except subprocess.TimeoutExpired:
        raise ValueError("FFmpeg tardó demasiado en procesar el audio")
    if process.returncode != 0:
        raise ValueError(f"Fallo al dividir el audio en chunks: {process.stderr.strip() or 'error desconocido'}")

    chunks = sorted(output_dir.glob("chunk_*.wav"))
    return chunks


def _extract_transcript(response: speech.RecognizeResponse) -> str:
    chunks: list[str] = []
    for result in response.results:
        if result.alternatives:
            chunks.append(result.alternatives[0].transcript)
    return " ".join(chunks).strip()


def _build_config_chunk(language_code: str) -> speech.RecognitionConfig:
    return speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=16000,
        language_code=language_code,
        enable_automatic_punctuation=True,
        model="latest_short",
    )


def _transcribe_chunk(chunk_content: bytes, language_code: str) -> str:
    client = _build_speech_client()
    config = _build_config_chunk(language_code)
    audio = speech.RecognitionAudio(content=chunk_content)
    # Utilizamos el metodo síncrono que procesa hasta 60s en pocos segundos
    response = client.recognize(config=config, audio=audio)
    return _extract_transcript(response)


def transcribe_audio(file_url: str) -> str | None:
    logger.info("Transcribing audio evidence with Google STT in fast parallel chunking mode")
    
    try:
        with tempfile.TemporaryDirectory(prefix="stt-chunking-") as tmp_dir:
            tmp_path = Path(tmp_dir)
            # No forzamos extensión para que FFmpeg detecte el contenedor original
            input_file = tmp_path / "original_audio"
            
            logger.info("Downloading audio for processing: %s", file_url)
            _download_file(file_url, input_file)
            
            chunk_paths = _chunk_audio(input_file, tmp_path, segment_time=40)
            logger.info("Audio splitted into %d chunks", len(chunk_paths))
            
            if not chunk_paths:
                return None

            language_code = SPANISH_LANGUAGE_CODE
            chunk_results = [""] * len(chunk_paths)
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                future_to_index = {
                    executor.submit(_transcribe_chunk, cp.read_bytes(), language_code): i 
                    for i, cp in enumerate(chunk_paths)
                }
                
                for future in concurrent.futures.as_completed(future_to_index, timeout=120): # Timeout total de 2 min
                    idx = future_to_index[future]
                    try:
                        transcript_chunk = future.result(timeout=30) # Cada trozo tiene 30s
                        chunk_results[idx] = transcript_chunk
                    except concurrent.futures.TimeoutError:
                        logger.error("Timeout transcribing chunk %d", idx)
                    except Exception as e:
                        logger.error("Error transcribing chunk %d: %s", idx, e)
            
            full_transcript = " ".join(filter(None, chunk_results)).strip()
            
            if not full_transcript:
                logger.warning("Google STT returned empty transcript for '%s' after checking all chunks", file_url)
                return None
                
            return full_transcript

    except (ValueError, URLError) as exc:
        logger.warning("Audio source error for '%s': %s", file_url, exc)
        return None
    except GoogleAPIError as exc:
        logger.error("Google STT request failed for '%s': %s", file_url, exc)
        return None
    except Exception as exc:
        logger.exception("Unexpected audio transcription error for '%s': %s", file_url, exc)
        return None

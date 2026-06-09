import os
import shutil
import subprocess
import tempfile
import uuid
import io
import logging
from dataclasses import dataclass
from pathlib import Path
from PIL import Image, ImageEnhance, ImageOps

from fastapi import UploadFile
from google.cloud import storage

logger = logging.getLogger(__name__)

GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME", "")
GCS_AUDIO_PREFIX = os.getenv("GCS_AUDIO_PREFIX", "incident-audio")
GCS_VISION_PREFIX = os.getenv("GCS_VISION_PREFIX", "incident-image")



@dataclass
class UploadAudioResult:
    file_url: str
    converted_to_flac: bool
    stored_content_type: str


def get_storage_client():
    """Inicializa el cliente de Storage usando la llave específica si existe."""
    key_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_STORAGE")
    if key_path and os.path.exists(key_path):
        return storage.Client.from_service_account_json(key_path)
    return storage.Client()




def _build_object_name(suffix: str = ".flac") -> str:
    return f"{GCS_AUDIO_PREFIX}/{uuid.uuid4()}{suffix}"


def _convert_to_flac(content: bytes, filename: str | None) -> bytes:
    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        raise ValueError("ffmpeg no esta instalado; no se puede convertir el audio a FLAC")

    input_suffix = Path(filename or "audio.bin").suffix or ".bin"

    with tempfile.TemporaryDirectory(prefix="audio-convert-") as tmp_dir:
        input_path = Path(tmp_dir) / f"input{input_suffix}"
        output_path = Path(tmp_dir) / "output.flac"
        input_path.write_bytes(content)

        command = [
            ffmpeg_path,
            "-y",
            "-i",
            str(input_path),
            "-ac",
            "1",
            "-ar",
            "16000",
            "-sample_fmt",
            "s16",
            str(output_path),
        ]
        process = subprocess.run(command, capture_output=True, text=True)
        if process.returncode != 0 or not output_path.exists():
            raise ValueError(f"fallo la conversion a FLAC: {process.stderr.strip() or 'error desconocido'}")

        return output_path.read_bytes()


def enhance_image(image_bytes: bytes) -> tuple[bytes, dict]:
    with Image.open(io.BytesIO(image_bytes)) as img:
        img = ImageOps.exif_transpose(img).convert("RGB")
        original_size = img.size

        max_side = 1600
        img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        img = ImageEnhance.Contrast(img).enhance(1.12)
        img = ImageEnhance.Sharpness(img).enhance(1.08)

        out = io.BytesIO()
        img.save(out, format="JPEG", quality=88, optimize=True)
        enhanced_bytes = out.getvalue()

    preprocessing = {
        "original_size": {"width": original_size[0], "height": original_size[1]},
        "enhanced_size": {"width": img.size[0], "height": img.size[1]},
        "output_format": "image/jpeg",
    }
    return enhanced_bytes, preprocessing



def upload_audio_file(file: UploadFile) -> UploadAudioResult:
    if not GCS_BUCKET_NAME:
        raise ValueError("GCS_BUCKET_NAME is not configured")

    original_content = file.file.read()
    flac_content = _convert_to_flac(original_content, file.filename)

    object_name = _build_object_name(".flac")
    client = get_storage_client()
    bucket = client.bucket(GCS_BUCKET_NAME)


    blob = bucket.blob(object_name)
    blob.upload_from_string(flac_content, content_type="audio/flac")

    return UploadAudioResult(
        file_url=f"gs://{GCS_BUCKET_NAME}/{object_name}",
        converted_to_flac=True,
        stored_content_type="audio/flac",
    )


def upload_image_file(file: UploadFile) -> str:
    if not GCS_BUCKET_NAME:
        raise ValueError("GCS_BUCKET_NAME is not configured")

    original_content = file.file.read()
    
    # Refinamiento de imagen antes de subir
    enhanced_content, _ = enhance_image(original_content)

    object_name = f"{GCS_VISION_PREFIX}/{uuid.uuid4()}.jpg"

    client = get_storage_client()
    bucket = client.bucket(GCS_BUCKET_NAME)

    blob = bucket.blob(object_name)
    blob.upload_from_string(enhanced_content, content_type="image/jpeg")

    return f"gs://{GCS_BUCKET_NAME}/{object_name}"

def generate_signed_url(gs_uri: str, expiration_minutes: int = 60) -> str:
    from datetime import timedelta
    if not gs_uri.startswith("gs://"):
        return gs_uri

    path = gs_uri[5:]
    if "/" not in path:
        logger.warning("URI de GCS invalido para firmado: %s", gs_uri)
        return gs_uri

    bucket_name, object_name = path.split("/", 1)
    public_fallback = f"https://storage.googleapis.com/{bucket_name}/{object_name}"

    try:
        client = get_storage_client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(object_name)
        signed_url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=expiration_minutes),
            method="GET",
        )
        logger.info("Signed URL generada para %s", gs_uri)
        return signed_url
    except Exception as e:
        logger.error(
            "generate_signed_url fallo para %s: %s: %s",
            gs_uri,
            type(e).__name__,
            e,
            exc_info=True,
        )
        logger.warning("Usando fallback HTTP sin firma para %s", gs_uri)
        return public_fallback
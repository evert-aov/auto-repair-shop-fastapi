from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Any

_JOB_STORE: dict[str, dict[str, Any]] = {}
_LOCK = threading.Lock()


def create_job(
    *,
    file_url: str,
    converted_to_flac: bool,
    stored_content_type: str,
) -> dict[str, Any]:
    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    job = {
        "job_id": job_id,
        "status": "queued",
        "file_url": file_url,
        "transcript": None,
        "error": None,
        "converted_to_flac": converted_to_flac,
        "stored_content_type": stored_content_type,
        "created_at": now,
        "updated_at": now,
    }
    with _LOCK:
        _JOB_STORE[job_id] = job
    return job


def get_job(job_id: str) -> dict[str, Any] | None:
    with _LOCK:
        return _JOB_STORE.get(job_id)


def mark_processing(job_id: str) -> None:
    with _LOCK:
        job = _JOB_STORE.get(job_id)
        if not job:
            return
        job["status"] = "processing"
        job["updated_at"] = datetime.now(timezone.utc)


def mark_completed(job_id: str, transcript: str | None) -> None:
    with _LOCK:
        job = _JOB_STORE.get(job_id)
        if not job:
            return
        job["status"] = "completed"
        job["transcript"] = transcript
        job["updated_at"] = datetime.now(timezone.utc)


def mark_failed(job_id: str, error: str) -> None:
    with _LOCK:
        job = _JOB_STORE.get(job_id)
        if not job:
            return
        job["status"] = "failed"
        job["error"] = error
        job["updated_at"] = datetime.now(timezone.utc)

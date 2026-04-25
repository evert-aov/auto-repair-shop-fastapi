from pydantic import BaseModel, Field


class ClassificationResult(BaseModel):
    category: str
    priority: str
    confidence: float
    summary: str


class AudioTranscriptionRequest(BaseModel):
    file_url: str = Field(..., min_length=1)


class AudioTranscriptionResponse(BaseModel):
    transcript: str | None
    stt_mode: str = "quality"


class AudioUploadResponse(BaseModel):
    file_url: str
    transcript: str | None = None
    stt_mode: str = "quality"
    converted_to_flac: bool = True
    stored_content_type: str = "audio/flac"


class AudioUploadAsyncResponse(BaseModel):
    job_id: str
    status: str
    file_url: str
    stt_mode: str = "quality"
    converted_to_flac: bool = True
    stored_content_type: str = "audio/flac"


class TranscriptionJobStatusResponse(BaseModel):
    job_id: str
    status: str
    file_url: str
    stt_mode: str = "quality"
    transcript: str | None = None
    error: str | None = None
    converted_to_flac: bool = True
    stored_content_type: str = "audio/flac"


class ImageUploadResponse(BaseModel):
    file_url: str


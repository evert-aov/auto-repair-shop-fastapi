from pydantic import BaseModel


class ClassificationResult(BaseModel):
    category: str
    priority: str
    confidence: float
    summary: str

# app/schemas.py
from pydantic import BaseModel
from typing import Optional, List, Dict

class Token(BaseModel):
    access_token: str
    token_type: str
    role: Optional[str]

class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None

class LoginRequest(BaseModel):
    username: str
    password: str
    role: str   # ✅ REQUIRED


class UploadRequest(BaseModel):
    text: str
    filename: Optional[str] = None

class PHIDetectItem(BaseModel):
    field: str
    value: str
    start: int
    end: int

class PHIDetectResponse(BaseModel):
    items: List[PHIDetectItem]

class CleanResponse(BaseModel):
    cleaned: str
    redacted_count: int

class EmbeddingResponse(BaseModel):
    vector_id: str
    encrypted: bool

from pydantic import BaseModel

class AskRequest(BaseModel):
    question: str
    patient_id: str


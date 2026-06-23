"""
Pydantic schemas for API request/response contracts.
All FastAPI endpoints MUST return one of these models.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


# ─── Request Models ───────────────────────────────────────────────

class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    message: str


# ─── Nested Data Models ──────────────────────────────────────────

class PaperResult(BaseModel):
    rank: int
    title: str
    url: str
    journal: Optional[str] = None
    publication_year: Optional[int] = None
    citation_count: Optional[int] = None
    similarity_score: Optional[float] = None
    composite_score: Optional[float] = None


class RetrievalConfig(BaseModel):
    similarity: float
    recency: float
    citation: float


class ReferenceResult(BaseModel):
    title: str
    pmid: str
    url: str
    year: Optional[int] = None


# ─── Response Models ─────────────────────────────────────────────
# Field is serialized as "type" in JSON to match the frontend contract,
# but accessed as "response_type" in Python to avoid shadowing the builtin.

class PaperSearchResponse(BaseModel):
    type: str = Field(default="paper_search", alias="type")
    conversation_id: str
    response: str
    papers_found: bool
    papers: List[PaperResult]
    retrieval_config: Optional[RetrievalConfig] = None

    model_config = {"populate_by_name": True}


class QAResponse(BaseModel):
    type: str = Field(default="qa", alias="type")
    conversation_id: str
    response: str
    references: List[ReferenceResult]

    model_config = {"populate_by_name": True}


class ChatResponse(BaseModel):
    type: str = Field(default="chat", alias="type")
    conversation_id: str
    response: str

    model_config = {"populate_by_name": True}


class ErrorResponse(BaseModel):
    type: str = Field(default="error", alias="type")
    conversation_id: Optional[str] = None
    message: str

    model_config = {"populate_by_name": True}


# ─── Conversation Lifecycle Models ───────────────────────────────

class ConversationCreatedResponse(BaseModel):
    conversation_id: str
    status: str = "created"


class ConversationInfoResponse(BaseModel):
    conversation_id: str
    message_count: int
    papers_found: bool
    created_at: str
    updated_at: str


class ConversationDeletedResponse(BaseModel):
    conversation_id: str
    status: str = "deleted"


class HealthResponse(BaseModel):
    status: str
    database: str
    qdrant: str
    llm: str

# ─── Auth and Settings Models ────────────────────────────────────

class SignupRequest(BaseModel):
    email: str
    username: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

class AuthResponse(BaseModel):
    user_id: str
    token: str
    refresh_token: str

class UserProfile(BaseModel):
    id: str
    email: str
    username: str

class SettingsSchema(BaseModel):
    alpha: float
    beta: float
    gamma: float


"""
FastAPI application — thin routing layer.
All business logic lives in ChatService.
"""

import os
import uuid
import logging
from typing import Union

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from src.api.schemas import (
    ChatRequest,
    ChatResponse,
    PaperSearchResponse,
    QAResponse,
    ErrorResponse,
    ConversationCreatedResponse,
    ConversationInfoResponse,
    ConversationDeletedResponse,
    HealthResponse,
)
from src.services.chat_service import ChatService
from src.services.conversation_manager import get_conversation_manager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ─── App ─────────────────────────────────────────────────────────

app = FastAPI(
    title="Biomedical Literature Retrieval API",
    version="2.0.0",
)

# ─── CORS ────────────────────────────────────────────────────────

_default_origins = [
    "http://localhost:3000",
    "http://localhost:5173",
]
_extra = os.environ.get("CORS_ORIGINS", "")
_origins = _default_origins + [o.strip() for o in _extra.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Singletons ──────────────────────────────────────────────────

chat_service = ChatService()
conversation_manager = get_conversation_manager()


# ─── Health ──────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
def health():
    # Database check
    db_status = "connected"
    try:
        from src.storage.conversation_repository import get_conversation_repository
        repo = get_conversation_repository()
        import sqlite3
        with sqlite3.connect(repo.db_path) as conn:
            conn.execute("SELECT 1")
    except Exception:
        db_status = "disconnected"

    # Qdrant check
    qdrant_status = "connected"
    try:
        from src.storage.paper_manager import get_paper_store
        store = get_paper_store()
        store.get_store_stats()
    except Exception:
        qdrant_status = "disconnected"

    # LLM check
    llm_status = "connected"
    try:
        from src.config import llm
        # Just check the object exists and has an API key configured
        if llm is None:
            llm_status = "disconnected"
    except Exception:
        llm_status = "disconnected"

    overall = "healthy" if all(
        s == "connected" for s in [db_status, qdrant_status, llm_status]
    ) else "degraded"

    return HealthResponse(
        status=overall,
        database=db_status,
        qdrant=qdrant_status,
        llm=llm_status,
    )


# ─── Conversation Lifecycle ─────────────────────────────────────

@app.post("/conversation/new", response_model=ConversationCreatedResponse)
def create_conversation():
    new_id = str(uuid.uuid4())
    conversation_manager.create_conversation(new_id)
    return ConversationCreatedResponse(conversation_id=new_id)


@app.get("/conversation/{conversation_id}", response_model=ConversationInfoResponse)
def get_conversation(conversation_id: str):
    conv = conversation_manager.repo.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return ConversationInfoResponse(
        conversation_id=conversation_id,
        message_count=len(conv["messages"]),
        papers_found=conv["papers_found"],
        created_at=conv["created_at"],
        updated_at=conv["updated_at"],
    )


@app.delete("/conversation/{conversation_id}", response_model=ConversationDeletedResponse)
def delete_conversation(conversation_id: str):
    conv = conversation_manager.repo.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # 1. Delete SQLite history
    conversation_manager.clear_conversation(conversation_id)

    # 2. Clear in-memory paper cache
    from src.services.paper_store import get_conversation_paper_store
    get_conversation_paper_store().clear_papers(conversation_id)

    logger.info(f"Deleted conversation {conversation_id}")
    return ConversationDeletedResponse(conversation_id=conversation_id)


# ─── Chat ────────────────────────────────────────────────────────

ChatResponseUnion = Union[PaperSearchResponse, QAResponse, ChatResponse, ErrorResponse]


@app.post("/chat", response_model=ChatResponseUnion)
def chat(request: ChatRequest):
    conv_id = request.conversation_id
    if not conv_id:
        conv_id = str(uuid.uuid4())
        conversation_manager.create_conversation(conv_id)

    result = chat_service.chat(conv_id, request.message)
    return result
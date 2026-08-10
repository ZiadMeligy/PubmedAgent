"""Authenticated APIs for summaries and structured paper comparisons."""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from src.api.schemas import (
    PaperComparisonRequest,
    PaperComparisonResponse,
    PaperSummaryRequest,
    PaperSummaryResponse,
)
from src.auth.dependencies import get_current_user
from src.services.paper_qa_service import (
    compare_ranked_papers,
    summarize_ranked_paper,
)
from src.storage.conversation_repository import get_conversation_repository


router = APIRouter(prefix="/api/papers", tags=["paper-qa"])


def _require_owned_conversation(
    conversation_id: str,
    current_user: Dict[str, Any],
) -> None:
    conversation = get_conversation_repository().get_conversation(conversation_id)
    if not conversation or conversation.get("user_id") != current_user["id"]:
        raise HTTPException(status_code=404, detail="Conversation not found")


@router.post(
    "/rank/{rank}/summary",
    response_model=PaperSummaryResponse,
)
def summarize_paper(
    rank: int,
    request: PaperSummaryRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    _require_owned_conversation(request.conversation_id, current_user)
    try:
        return summarize_ranked_paper(
            request.conversation_id,
            rank,
            refresh=request.refresh,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/compare", response_model=PaperComparisonResponse)
def compare_papers(
    request: PaperComparisonRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    _require_owned_conversation(request.conversation_id, current_user)
    try:
        return compare_ranked_papers(
            request.conversation_id,
            request.ranks,
            request.question,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

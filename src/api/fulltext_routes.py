from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
import httpx
from src.fulltext.service import check_multiple_papers, check_paper_availability
from src.fulltext.index_service import get_fulltext_store, index_paper
from src.fulltext.pdf_extractor import (
    ARTIFACT_ROOT,
    get_paper_artifact_dir,
)
from src.api.schemas import EvidenceDetail, PaperArtifactListResponse
from src.auth.dependencies import get_current_user
from src.llm.reranker import get_evidence_id, get_evidence_url
from src.services.paper_store import get_conversation_paper_store
from src.storage.conversation_repository import get_conversation_repository
from src.storage.paper_manager import get_paper_store

router = APIRouter(prefix="/api/fulltext", tags=["fulltext"])

class PaperInput(BaseModel):
    pmid: str
    doi: Optional[str] = None
    title: Optional[str] = None

class FullTextCheckRequest(BaseModel):
    papers: List[PaperInput]

class PaperStatus(BaseModel):
    pmid: str
    available: bool
    provider: Optional[str] = None
    pdf_url: Optional[str] = None

class FullTextCheckResponse(BaseModel):
    papers: List[PaperStatus]


def _require_paper_access(
    conversation_id: str,
    pmid: str,
    current_user: Dict[str, Any],
) -> Dict[str, Any]:
    conversation = get_conversation_repository().get_conversation(conversation_id)
    if not conversation or conversation.get("user_id") != current_user["id"]:
        raise HTTPException(status_code=404, detail="Conversation not found")
    for paper in get_conversation_paper_store().get_papers(conversation_id):
        paper_pmid = str(paper.get("pubmed_id") or paper.get("pmid") or "")
        if paper_pmid == str(pmid):
            return paper
    raise HTTPException(status_code=404, detail="Paper not found in conversation")


def _find_evidence_payload(pmid: str, evidence_id: str) -> Optional[Dict[str, Any]]:
    stores = (get_fulltext_store(), get_paper_store().vector_store)
    for store in stores:
        try:
            for payload in store.scroll_payloads(pmids=[pmid], limit=512):
                if get_evidence_id(payload) == evidence_id:
                    return payload
        except Exception:
            continue
    return None

@router.post("/check", response_model=FullTextCheckResponse)
async def check_fulltext_availability(request: FullTextCheckRequest):
    papers_dicts = [p.dict() for p in request.papers]
    results = await check_multiple_papers(papers_dicts)
    return {"papers": results}

@router.get("/download/{pmid}")
async def download_pdf(pmid: str, doi: Optional[str] = None):
    # Check availability again to get the URL since we don't trust client-provided URLs
    result = await check_paper_availability({"pmid": pmid, "doi": doi})
    if not result["available"] or not result["pdf_url"]:
        raise HTTPException(status_code=404, detail="PDF not available")
        
    pdf_url = result["pdf_url"]
    
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            response = await client.get(pdf_url, headers=headers)
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=f"Failed to fetch PDF from provider (HTTP {response.status_code})")
            pdf_bytes = response.content
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Error connecting to PDF provider: {str(e)}")

    from fastapi.responses import Response
    return Response(
        content=pdf_bytes, 
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=paper_{pmid}.pdf"}
    )

@router.get("/index/stream")
async def index_fulltext_stream(
    pmid: str, 
    doi: Optional[str] = None, 
    title: Optional[str] = None,
    journal: Optional[str] = None,
    year: Optional[int] = None
):
    """Stream full-text indexing progress via Server-Sent Events (SSE)."""
    return StreamingResponse(
        index_paper(pmid, doi, title, journal, year),
        media_type="text/event-stream"
    )


@router.get("/artifacts/{pmid}/{filename}")
async def get_paper_artifact(pmid: str, filename: str):
    """Serve an extracted figure while preventing path traversal."""
    artifact_root = ARTIFACT_ROOT.resolve()
    requested = (artifact_root / pmid / filename).resolve()
    if not requested.is_relative_to(artifact_root) or not requested.is_file():
        raise HTTPException(status_code=404, detail="Artifact not found")
    return FileResponse(requested)


@router.get(
    "/papers/{pmid}/artifacts",
    response_model=PaperArtifactListResponse,
)
async def list_paper_artifacts(
    pmid: str,
    conversation_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    paper = _require_paper_access(conversation_id, pmid, current_user)
    payloads = get_fulltext_store().scroll_payloads(
        pmids=[pmid],
        content_types=["table", "image"],
        limit=512,
    )
    artifacts = []
    seen = set()
    for payload in payloads:
        evidence_id = get_evidence_id(payload)
        artifact_id = str(payload.get("artifact_id") or evidence_id)
        if artifact_id in seen:
            continue
        seen.add(artifact_id)
        artifacts.append(
            {
                "artifact_id": artifact_id,
                "type": payload.get("content_type") or "text",
                "pmid": str(pmid),
                "rank": paper.get("rank"),
                "title": paper.get("title") or payload.get("title") or "",
                "label": payload.get("label") or payload.get("section") or "Paper artifact",
                "page_number": payload.get("page_number"),
                "url": payload.get("artifact_url"),
                "evidence_id": evidence_id,
                "text": payload.get("text") or "",
                "evidence_url": get_evidence_url(payload, conversation_id),
            }
        )
    artifacts.sort(
        key=lambda item: (
            item.get("page_number") or 0,
            item.get("type") or "",
            item.get("label") or "",
        )
    )
    return {
        "pmid": str(pmid),
        "rank": int(paper.get("rank")),
        "title": paper.get("title") or "",
        "artifacts": artifacts,
    }


@router.get(
    "/papers/{pmid}/evidence/{evidence_id}",
    response_model=EvidenceDetail,
)
async def get_paper_evidence(
    pmid: str,
    evidence_id: str,
    conversation_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    paper = _require_paper_access(conversation_id, pmid, current_user)
    payload = _find_evidence_payload(pmid, evidence_id)
    if not payload:
        raise HTTPException(status_code=404, detail="Evidence not found")

    source_pdf = get_paper_artifact_dir(pmid) / "source.pdf"
    pdf_available = source_pdf.is_file()
    return {
        "evidence_id": evidence_id,
        "conversation_id": conversation_id,
        "pmid": str(pmid),
        "rank": int(paper.get("rank")),
        "title": paper.get("title") or payload.get("title") or "",
        "text": payload.get("text") or "",
        "content_type": payload.get("content_type") or "text",
        "section": payload.get("section"),
        "page_number": payload.get("page_number"),
        "pdf_available": pdf_available,
        "pdf_url": (
            f"/api/fulltext/papers/{pmid}/pdf"
            f"?conversation_id={conversation_id}"
            if pdf_available
            else None
        ),
    }


@router.get("/papers/{pmid}/pdf")
async def get_indexed_paper_pdf(
    pmid: str,
    conversation_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    _require_paper_access(conversation_id, pmid, current_user)
    source_pdf = get_paper_artifact_dir(pmid) / "source.pdf"
    if not source_pdf.is_file():
        raise HTTPException(
            status_code=404,
            detail="Indexed source PDF is unavailable; re-index this paper",
        )
    return FileResponse(
        source_pdf,
        media_type="application/pdf",
        filename=f"paper_{pmid}.pdf",
        content_disposition_type="inline",
    )

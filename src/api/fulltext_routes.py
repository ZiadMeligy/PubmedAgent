from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
import httpx
from src.fulltext.service import check_multiple_papers, check_paper_availability
from src.fulltext.index_service import index_paper

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

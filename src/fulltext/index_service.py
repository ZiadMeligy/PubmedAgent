import asyncio
import logging
import httpx
from typing import AsyncGenerator

from langchain_text_splitters import RecursiveCharacterTextSplitter
from src.fulltext.pdf_extractor import extract_pdf_structure
from src.fulltext.service import check_paper_availability
from src.storage import QdrantVectorStore
from qdrant_client.models import Filter, FieldCondition, MatchValue

logger = logging.getLogger(__name__)
INDEX_VERSION = 3

# Global vector store for full text
_fulltext_store = None

def get_fulltext_store() -> QdrantVectorStore:
    global _fulltext_store
    if _fulltext_store is None:
        _fulltext_store = QdrantVectorStore(collection_name="pubmed_fulltext")
    return _fulltext_store

async def index_paper(pmid: str, doi: str = None, title: str = None, journal: str = None, year: int = None) -> AsyncGenerator[str, None]:
    """
    Downloads, extracts, chunks, and indexes a full text paper.
    Yields progress updates (SSE compatible).
    """
    store = get_fulltext_store()
    
    # 1. Duplicate Detection
    try:
        # Only the structure-aware schema counts as current. Papers indexed by
        # the old text-only pipeline are transparently rebuilt.
        query_filter = Filter(
            must=[
                FieldCondition(
                    key="pmid",
                    match=MatchValue(value=pmid)
                ),
                FieldCondition(
                    key="index_version",
                    match=MatchValue(value=INDEX_VERSION),
                ),
            ]
        )
        # Search with a dummy query just to trigger the filter
        # Since we just want to know if it exists, we can use scroll
        scroll_res, _ = store.client.scroll(
            collection_name=store.collection_name,
            scroll_filter=query_filter,
            limit=1
        )
        if scroll_res:
            yield "data: {\"status\": \"ALREADY_INDEXED\", \"message\": \"Paper already indexed\"}\n\n"
            return
        store.delete_by_filter(pmid=pmid)
    except Exception as e:
        logger.warning(f"Error checking duplicates: {e}")
        # Proceed if check fails
        pass

    yield "data: {\"status\": \"DOWNLOADING\", \"message\": \"Downloading PDF...\"}\n\n"
    
    # 2. Check availability to get URL
    paper_dict = {"pmid": pmid, "doi": doi, "title": title}
    availability = await check_paper_availability(paper_dict)
    
    if not availability["available"] or not availability["pdf_url"]:
        yield "data: {\"status\": \"ERROR\", \"message\": \"PDF not available from any provider\"}\n\n"
        return
        
    pdf_url = availability["pdf_url"]
    
    # Download the PDF
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            response = await client.get(pdf_url, headers=headers)
            response.raise_for_status()
            pdf_bytes = response.content
    except Exception as e:
        logger.error(f"Failed to download PDF for {pmid}: {e}")
        yield f"data: {{\"status\": \"ERROR\", \"message\": \"Failed to download PDF: {str(e)}\"}}\n\n"
        return

    yield "data: {\"status\": \"EXTRACTING\", \"message\": \"Extracting text, tables, and figures from PDF...\"}\n\n"
    
    # 3. Structure-aware PDF extraction
    try:
        extracted = await asyncio.to_thread(extract_pdf_structure, pdf_bytes, pmid)
        if not any(page["text"].strip() for page in extracted["pages"]):
            yield "data: {\"status\": \"ERROR\", \"message\": \"No text could be extracted from the PDF\"}\n\n"
            return
            
    except Exception as e:
        logger.error(f"Failed to extract text for {pmid}: {e}")
        yield f"data: {{\"status\": \"ERROR\", \"message\": \"Text extraction failed: {str(e)}\"}}\n\n"
        return
        
    yield "data: {\"status\": \"CHUNKING\", \"message\": \"Chunking document...\"}\n\n"
    
    # 4. Chunking
    try:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", ".", " ", ""]
        )
        
        chunks = []
        for page in extracted["pages"]:
            page_number = page["page_number"]
            for page_chunk_index, text in enumerate(
                splitter.split_text(page["text"]),
                1,
            ):
                chunks.append(
                    {
                        "text": text,
                        "page_number": page_number,
                        "page_chunk_index": page_chunk_index,
                        "content_type": "text",
                        "section": f"PDF page {page_number}",
                    }
                )

        chunks.extend(extracted["tables"])
        chunks.extend(extracted["images"])
        
        if not chunks:
            yield "data: {\"status\": \"ERROR\", \"message\": \"Chunking resulted in 0 chunks\"}\n\n"
            return
            
    except Exception as e:
        logger.error(f"Failed to chunk text for {pmid}: {e}")
        yield f"data: {{\"status\": \"ERROR\", \"message\": \"Chunking failed: {str(e)}\"}}\n\n"
        return
        
    yield f"data: {{\"status\": \"EMBEDDING\", \"message\": \"Generating embeddings for {len(chunks)} chunks...\"}}\n\n"
    
    # 5. Generate Embeddings & Upsert
    try:
        chunk_dicts = []
        total_chunks = len(chunks)
        
        for i, chunk in enumerate(chunks):
            chunk_dicts.append({
                **chunk,
                "pmid": pmid,
                "doi": doi,
                "title": title,
                "journal": journal,
                "year": year,
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                "chunk_index": i + 1,
                "chunk_id": f"{pmid}_fulltext_{i + 1}",
                "total_chunks": total_chunks,
                "source": "fulltext",
                "index_version": INDEX_VERSION,
            })
            
        # We can just use the store's add_chunks method which generates embeddings synchronously.
        # Run it in a thread to prevent blocking the async event loop for long embedding tasks.
        def upsert_chunks():
            return store.add_chunks(chunk_dicts)
            
        yield "data: {\"status\": \"UPLOADING\", \"message\": \"Storing chunks in Qdrant...\"}\n\n"
        
        chunks_added = await asyncio.to_thread(upsert_chunks)
        
    except Exception as e:
        logger.error(f"Failed to embed/store chunks for {pmid}: {e}")
        yield f"data: {{\"status\": \"ERROR\", \"message\": \"Vector storage failed: {str(e)}\"}}\n\n"
        return
        
    # Success!
    table_count = len(extracted["tables"])
    image_count = len(extracted["images"])
    yield (
        f"data: {{\"status\": \"INDEXED\", "
        f"\"message\": \"✅ Indexed text, {table_count} tables, and {image_count} figures\", "
        f"\"chunks_created\": {chunks_added}, "
        f"\"tables_created\": {table_count}, "
        f"\"images_created\": {image_count}}}\n\n"
    )

"""Structure-aware PDF extraction for text, tables, and figures."""

from pathlib import Path
import re
from typing import Any, Dict, List

import fitz


ARTIFACT_ROOT = Path(__file__).resolve().parents[2] / "data" / "paper_artifacts"


def _safe_component(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "unknown"))
    return cleaned.strip("._") or "unknown"


def _nearby_context(page: fitz.Page, rect: fitz.Rect | None, max_chars: int = 1800) -> str:
    blocks = page.get_text("blocks")
    if not blocks:
        return page.get_text("text")[:max_chars].strip()

    if rect is None:
        selected = blocks[:8]
    else:
        center_y = (rect.y0 + rect.y1) / 2
        selected = sorted(
            blocks,
            key=lambda block: abs(((block[1] + block[3]) / 2) - center_y),
        )[:6]
        selected.sort(key=lambda block: (block[1], block[0]))

    context = " ".join(str(block[4]).strip() for block in selected if block[4])
    return " ".join(context.split())[:max_chars]


def _caption_from_context(context: str, kind: str, fallback: str) -> str:
    prefix = r"fig(?:ure)?\.?" if kind == "figure" else kind
    match = re.search(
        rf"(?i)\b{prefix}\s*[A-Za-z0-9.-]*\s*[:.]?\s*(.{{0,320}})",
        context,
    )
    if match:
        caption = " ".join(match.group(0).split())
        if caption:
            return caption
    return fallback


def _markdown_table(rows: List[List[Any]]) -> str:
    normalized = [
        [
            " ".join(str(cell or "").replace("|", "\\|").split())
            for cell in row
        ]
        for row in rows
        if row
    ]
    if not normalized:
        return ""

    width = max(len(row) for row in normalized)
    normalized = [row + [""] * (width - len(row)) for row in normalized]
    header = normalized[0]
    body = normalized[1:]
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(["---"] * width) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in body)
    return "\n".join(lines)


def _markdown_table_parts(rows: List[List[Any]], max_chars: int = 6000) -> List[str]:
    full_table = _markdown_table(rows)
    if len(full_table) <= max_chars:
        return [full_table] if full_table else []
    if len(rows) < 2:
        return [full_table[:max_chars]]

    header = rows[0]
    parts = []
    current_rows = [header]
    for row in rows[1:]:
        candidate = _markdown_table(current_rows + [row])
        if len(candidate) > max_chars and len(current_rows) > 1:
            parts.append(_markdown_table(current_rows))
            current_rows = [header, row]
        else:
            current_rows.append(row)
    if len(current_rows) > 1:
        parts.append(_markdown_table(current_rows))
    return parts


def extract_pdf_structure(pdf_bytes: bytes, pmid: str) -> Dict[str, List[Dict]]:
    """
    Extract page text plus searchable table/figure artifacts.

    Image bytes are stored on disk; Qdrant receives only paths, URLs, captions,
    and nearby textual context.
    """
    safe_pmid = _safe_component(pmid)
    paper_dir = ARTIFACT_ROOT / safe_pmid
    paper_dir.mkdir(parents=True, exist_ok=True)

    pages: List[Dict] = []
    tables: List[Dict] = []
    images: List[Dict] = []
    seen_xrefs = set()

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        for page_index, page in enumerate(doc):
            page_number = page_index + 1
            page_text = page.get_text("text").strip()
            pages.append({"page_number": page_number, "text": page_text})

            tables_before_page = len(tables)
            if hasattr(page, "find_tables"):
                try:
                    found_tables = page.find_tables()
                    for table_index, table in enumerate(found_tables.tables, 1):
                        rows = table.extract()
                        markdown_parts = _markdown_table_parts(rows)
                        if not markdown_parts:
                            continue
                        rect = fitz.Rect(table.bbox) if table.bbox else None
                        context = _nearby_context(page, rect)
                        label = _caption_from_context(
                            context,
                            "table",
                            f"Table {table_index} on page {page_number}",
                        )
                        for part_index, markdown in enumerate(markdown_parts, 1):
                            artifact_id = (
                                f"{safe_pmid}_table_p{page_number}_{table_index}"
                                f"_part{part_index}"
                            )
                            part_label = (
                                label
                                if len(markdown_parts) == 1
                                else f"{label} (part {part_index}/{len(markdown_parts)})"
                            )
                            tables.append(
                                {
                                    "artifact_id": artifact_id,
                                    "content_type": "table",
                                    "page_number": page_number,
                                    "label": part_label,
                                    "context": context,
                                    "text": (
                                        f"{part_label}\n"
                                        f"Paper PMID: {pmid}; PDF page: {page_number}\n"
                                        f"Nearby context: {context}\n\n{markdown}"
                                    ),
                                }
                            )
                except Exception:
                    # Table detection is best-effort; text indexing must continue.
                    pass

            # Many journal tables have no ruling lines, so find_tables() cannot
            # detect them. Preserve captioned table text as structured evidence
            # rather than relying only on a generic page chunk.
            if len(tables) == tables_before_page:
                caption_match = re.search(
                    r"(?im)^\s*Table\s+\d+[A-Za-z]?\s*$",
                    page_text,
                )
                if caption_match:
                    table_text = page_text[caption_match.start():].strip()
                    lines = [line.strip() for line in table_text.splitlines() if line.strip()]
                    label = " ".join(lines[:2])[:320] or (
                        f"Table on page {page_number}"
                    )
                    tables.append(
                        {
                            "artifact_id": f"{safe_pmid}_table_text_p{page_number}",
                            "content_type": "table",
                            "page_number": page_number,
                            "label": label,
                            "context": table_text[:1800],
                            "text": (
                                f"{label}\n"
                                f"Paper PMID: {pmid}; PDF page: {page_number}\n\n"
                                f"{table_text[:6000]}"
                            ),
                        }
                    )

            for image_index, image_info in enumerate(page.get_images(full=True), 1):
                xref = image_info[0]
                if xref in seen_xrefs:
                    continue
                seen_xrefs.add(xref)
                try:
                    extracted = doc.extract_image(xref)
                    width = int(extracted.get("width") or 0)
                    height = int(extracted.get("height") or 0)
                    image_bytes = extracted.get("image") or b""
                    if width < 180 or height < 120 or len(image_bytes) < 8_000:
                        continue

                    extension = _safe_component(
                        extracted.get("ext") or "png"
                    ).lower()
                    if extension not in {"png", "jpg", "jpeg", "webp"}:
                        pixmap = fitz.Pixmap(doc, xref)
                        if pixmap.colorspace and pixmap.colorspace.n > 3:
                            pixmap = fitz.Pixmap(fitz.csRGB, pixmap)
                        image_bytes = pixmap.tobytes("png")
                        extension = "png"
                    filename = f"figure_p{page_number}_{image_index}.{extension}"
                    path = paper_dir / filename
                    path.write_bytes(image_bytes)

                    rects = page.get_image_rects(xref)
                    rect = rects[0] if rects else None
                    context = _nearby_context(page, rect)
                    label = _caption_from_context(
                        context,
                        "figure",
                        f"Figure on page {page_number}",
                    )
                    artifact_id = f"{safe_pmid}_image_p{page_number}_{image_index}"
                    images.append(
                        {
                            "artifact_id": artifact_id,
                            "content_type": "image",
                            "page_number": page_number,
                            "label": label,
                            "context": context,
                            "artifact_path": str(path),
                            "artifact_url": (
                                f"/api/fulltext/artifacts/{safe_pmid}/{filename}"
                            ),
                            "mime_type": (
                                "image/jpeg"
                                if extension in {"jpg", "jpeg"}
                                else f"image/{extension}"
                            ),
                            "text": (
                                f"{label}\n"
                                f"Paper PMID: {pmid}; PDF page: {page_number}\n"
                                f"Nearby context: {context}"
                            ),
                        }
                    )
                except Exception:
                    continue
    finally:
        doc.close()

    return {"pages": pages, "tables": tables, "images": images}

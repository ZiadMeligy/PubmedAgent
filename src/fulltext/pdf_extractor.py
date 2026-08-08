"""Structure-aware PDF extraction for text, tables, and figures."""

from pathlib import Path
import re
from typing import Any, Dict, List

import fitz


ARTIFACT_ROOT = Path(__file__).resolve().parents[2] / "data" / "paper_artifacts"


def _safe_component(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "unknown"))
    return cleaned.strip("._") or "unknown"


def get_paper_artifact_dir(pmid: str) -> Path:
    """Return the traversal-safe artifact directory for a paper."""
    return ARTIFACT_ROOT / _safe_component(pmid)


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
        if row and any(str(cell or "").strip() for cell in row)
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


TABLE_CAPTION_PATTERN = re.compile(
    r"(?im)^[ \t]*Table\s+(\d+[A-Za-z]?)\s*[:.]?\s*([^\n]*)$"
)


def _captioned_table_regions(
    page: fitz.Page,
    page_text: str,
) -> List[Dict[str, Any]]:
    """Locate individual caption-bounded regions for borderless tables."""
    captions = []
    for match in TABLE_CAPTION_PATTERN.finditer(page_text):
        table_number = match.group(1)
        label = " ".join(match.group(0).split())[:320]
        rectangles = page.search_for(label)
        if not rectangles:
            continue
        caption_rect = rectangles[0]
        captions.append(
            {
                "number": table_number,
                "label": label,
                "match": match,
                "rect": caption_rect,
            }
        )

    for index, caption in enumerate(captions):
        end_y = page.rect.y1 - 25
        if index + 1 < len(captions):
            end_y = min(end_y, captions[index + 1]["rect"].y0 - 1)

        # Notes normally sit immediately below a table and provide a reliable
        # lower boundary when this is the final table on a page.
        for marker in ("Note:", "Notes:"):
            for note_rect in page.search_for(marker):
                if caption["rect"].y1 < note_rect.y0 < end_y:
                    end_y = note_rect.y0
                    break

        caption["clip"] = fitz.Rect(
            page.rect.x0 + 35,
            caption["rect"].y1 + 1,
            page.rect.x1 - 35,
            max(caption["rect"].y1 + 2, end_y),
        )
        text_end = (
            captions[index + 1]["match"].start()
            if index + 1 < len(captions)
            else len(page_text)
        )
        caption["raw_text"] = page_text[caption["match"].start():text_end].strip()
    return captions


def extract_pdf_structure(pdf_bytes: bytes, pmid: str) -> Dict[str, List[Dict]]:
    """
    Extract page text plus searchable table/figure artifacts.

    Image bytes are stored on disk; Qdrant receives only paths, URLs, captions,
    and nearby textual context.
    """
    safe_pmid = _safe_component(pmid)
    paper_dir = get_paper_artifact_dir(pmid)
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

            page_table_numbers = set()
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
                        number_match = re.search(
                            r"(?i)\bTable\s+(\d+[A-Za-z]?)",
                            label,
                        )
                        if number_match:
                            page_table_numbers.add(number_match.group(1).lower())
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

            # Borderless journal tables are often invisible to line-based table
            # detection. Detect every full caption, bound its region by the next
            # caption / note, then use text alignment to reconstruct the cells.
            for caption in _captioned_table_regions(page, page_text):
                table_number = str(caption["number"])
                if table_number.lower() in page_table_numbers:
                    continue

                rows = []
                if hasattr(page, "find_tables"):
                    try:
                        candidates = page.find_tables(
                            clip=caption["clip"],
                            vertical_strategy="text",
                            horizontal_strategy="text",
                        ).tables
                        candidates = [
                            table
                            for table in candidates
                            if table.row_count >= 2 and table.col_count >= 2
                        ]
                        if candidates:
                            best = max(
                                candidates,
                                key=lambda table: table.row_count * table.col_count,
                            )
                            rows = best.extract()
                    except Exception:
                        rows = []

                label = caption["label"]
                context = str(caption["raw_text"])[:1800]
                markdown_parts = _markdown_table_parts(rows) if rows else []
                if markdown_parts:
                    for part_index, markdown in enumerate(markdown_parts, 1):
                        part_label = (
                            label
                            if len(markdown_parts) == 1
                            else f"{label} (part {part_index}/{len(markdown_parts)})"
                        )
                        tables.append(
                            {
                                "artifact_id": (
                                    f"{safe_pmid}_table_caption_p{page_number}_"
                                    f"{_safe_component(table_number)}_part{part_index}"
                                ),
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
                else:
                    # Even if cell reconstruction fails, make each captioned
                    # table independently retrievable instead of losing the page.
                    raw_text = str(caption["raw_text"])[:6000]
                    tables.append(
                        {
                            "artifact_id": (
                                f"{safe_pmid}_table_text_p{page_number}_"
                                f"{_safe_component(table_number)}"
                            ),
                            "content_type": "table",
                            "page_number": page_number,
                            "label": label,
                            "context": context,
                            "text": (
                                f"{label}\n"
                                f"Paper PMID: {pmid}; PDF page: {page_number}\n\n"
                                f"{raw_text}"
                            ),
                        }
                    )
                page_table_numbers.add(table_number.lower())

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

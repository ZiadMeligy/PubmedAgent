"""Build Groq-compatible multimodal QA messages from retrieved figures."""

import base64
from pathlib import Path
from typing import Dict, List

from langchain_core.messages import HumanMessage
from src.fulltext.pdf_extractor import ARTIFACT_ROOT


MAX_QA_IMAGES = 3
MAX_IMAGE_BYTES = 5 * 1024 * 1024


def build_qa_message(
    context: str,
    question: str,
    evidence_chunks: List[Dict],
) -> HumanMessage:
    text = f"CONTEXT:\n{context}\n\nQUESTION: {question}"
    image_chunks = []
    seen = set()
    for chunk in evidence_chunks:
        if chunk.get("content_type") != "image":
            continue
        artifact_id = chunk.get("artifact_id") or chunk.get("artifact_path")
        if not artifact_id or artifact_id in seen:
            continue
        seen.add(artifact_id)
        image_chunks.append(chunk)
        if len(image_chunks) >= MAX_QA_IMAGES:
            break

    if not image_chunks:
        return HumanMessage(content=text)

    content = [{"type": "text", "text": text}]
    for chunk in image_chunks:
        path = Path(str(chunk.get("artifact_path", ""))).resolve()
        if (
            not path.is_relative_to(ARTIFACT_ROOT.resolve())
            or not path.is_file()
            or path.stat().st_size > MAX_IMAGE_BYTES
        ):
            continue
        mime_type = chunk.get("mime_type") or "image/png"
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        content.append(
            {
                "type": "text",
                "text": (
                    f"Figure from ranked paper #{chunk.get('rank', '?')}, "
                    f"PDF page {chunk.get('page_number', '?')}: "
                    f"{chunk.get('label', 'Extracted figure')}"
                ),
            }
        )
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:{mime_type};base64,{encoded}"},
            }
        )

    return HumanMessage(content=content)

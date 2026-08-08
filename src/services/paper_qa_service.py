"""Dedicated, rank-safe paper summarization and structured comparison."""

import json
import re
from typing import Any, Dict, Iterable, List, Sequence

from langchain_core.messages import HumanMessage, SystemMessage

from src.llm.qa_model import invoke_qa_model
from src.llm.reranker import (
    format_chunks_for_qa,
    get_evidence_id,
    get_evidence_url,
    rerank_chunks,
)
from src.services.paper_store import get_conversation_paper_store
from src.storage.conversation_repository import get_conversation_repository
from src.storage.paper_manager import get_paper_store


COMPARISON_FIELDS: Sequence[tuple[str, str]] = (
    ("study_design", "Study design"),
    ("population", "Population"),
    ("disease", "Disease/condition"),
    ("methods", "Methods"),
    ("intervention", "Intervention/exposure"),
    ("comparator", "Comparator"),
    ("primary_outcomes", "Primary outcomes"),
    ("key_results", "Key results"),
    ("limitations", "Limitations"),
)

SUMMARY_QUERY = (
    "Summarize the study design, population, disease, methods, interventions, "
    "comparators, primary outcomes, important numerical results, limitations, "
    "and clinically relevant tables or figures."
)


def _response_text(response: Any) -> str:
    """Normalize LangChain messages and provider-native content to text."""
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("text"):
                parts.append(str(block["text"]))
        return "\n".join(parts).strip()
    return str(content).strip()


def _bounded_chunks(
    chunks: Iterable[Dict[str, Any]],
    *,
    max_chars: int = 22_000,
    max_chunk_chars: int = 5_000,
) -> List[Dict[str, Any]]:
    """Bound prompt size while keeping metadata and evidence identity intact."""
    candidates = list(chunks)
    if not candidates:
        return []
    per_chunk_budget = min(
        max_chunk_chars,
        max(500, max_chars // len(candidates)),
    )
    selected: List[Dict[str, Any]] = []
    used = 0
    for original in candidates:
        chunk = dict(original)
        text = str(chunk.get("text") or "")
        remaining = max_chars - used
        if remaining <= 0:
            break
        text = text[: min(per_chunk_budget, remaining)]
        if not text.strip():
            continue
        chunk["text"] = text
        selected.append(chunk)
        used += len(text)
    return selected


def _retrieve_balanced_evidence(
    conversation_id: str,
    papers: Sequence[Dict[str, Any]],
    query: str,
    *,
    chunks_per_paper: int,
) -> List[Dict[str, Any]]:
    pmids = [
        str(paper.get("pubmed_id") or paper.get("pmid"))
        for paper in papers
        if paper.get("pubmed_id") or paper.get("pmid")
    ]
    candidates = get_paper_store().search_for_answer(
        query,
        conversation_id=conversation_id,
        top_k=6,
        pmids=pmids,
        lexical_query=query,
    )
    rank_by_pmid = {
        str(paper.get("pubmed_id") or paper.get("pmid")): paper.get("rank")
        for paper in papers
    }
    for chunk in candidates:
        chunk["rank"] = rank_by_pmid.get(str(chunk.get("pmid")))

    reranked = rerank_chunks(
        query,
        candidates,
        top_k=chunks_per_paper,
        selected_pmids=pmids,
    )
    return _bounded_chunks(reranked)


def _paper_by_rank(conversation_id: str, rank: int) -> Dict[str, Any]:
    papers = get_conversation_paper_store().get_papers(conversation_id)
    for paper in papers:
        if int(paper.get("rank", -1)) == int(rank):
            return paper
    raise ValueError(f"Ranked paper #{rank} is not available in this conversation")


def summarize_ranked_paper(
    conversation_id: str,
    rank: int,
    *,
    refresh: bool = False,
) -> Dict[str, Any]:
    paper = _paper_by_rank(conversation_id, rank)
    pmid = str(paper.get("pubmed_id") or paper.get("pmid"))
    repo = get_conversation_repository()
    if not refresh:
        cached = repo.get_paper_summary(conversation_id, pmid)
        if cached:
            return {
                "rank": rank,
                "pmid": pmid,
                "title": paper.get("title") or "Unknown title",
                "summary": cached,
                "cached": True,
            }

    evidence = _retrieve_balanced_evidence(
        conversation_id,
        [paper],
        SUMMARY_QUERY,
        chunks_per_paper=6,
    )
    if not evidence:
        raise ValueError("No indexed evidence is available for this paper")

    context = format_chunks_for_qa(evidence, conversation_id=conversation_id)
    prompt = HumanMessage(
        content=(
            f"{context}\n\n"
            f"Create a concise evidence-grounded summary of ranked paper #{rank}.\n"
            "Use these headings: Overview, Study design and population, Methods, "
            "Key findings, Important tables and figures, and Limitations.\n"
            "Preserve numerical values and units. Cite every factual bullet using "
            f"[{rank}](the exact EVIDENCE URL supplied with that evidence). "
            "Do not cite PubMed when an evidence URL is available. Do not infer "
            "information absent from the evidence."
        )
    )
    summary = _response_text(
        invoke_qa_model(
            [
                SystemMessage(
                    content=(
                        "You summarize one fixed biomedical paper from retrieved "
                        "evidence. Never mix papers and never invent citations."
                    )
                ),
                prompt,
            ]
        )
    )
    repo.save_paper_summary(conversation_id, pmid, summary)
    return {
        "rank": rank,
        "pmid": pmid,
        "title": paper.get("title") or "Unknown title",
        "summary": summary,
        "cached": False,
    }


def _extract_json(text: str) -> Dict[str, Any]:
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", cleaned, re.DOTALL)
    candidate = fenced.group(1) if fenced else cleaned
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("The comparison model did not return structured JSON")
    return json.loads(candidate[start : end + 1])


def _escape_table_cell(value: str) -> str:
    return " ".join(str(value).replace("|", "\\|").split())


def compare_ranked_papers(
    conversation_id: str,
    ranks: Sequence[int],
    question: str | None = None,
) -> Dict[str, Any]:
    normalized_ranks: List[int] = []
    for rank in ranks:
        value = int(rank)
        if value not in normalized_ranks:
            normalized_ranks.append(value)
    if len(normalized_ranks) < 2:
        raise ValueError("Choose at least two distinct ranked papers")
    if len(normalized_ranks) > 4:
        raise ValueError("Compare no more than four papers at once")

    papers = [_paper_by_rank(conversation_id, rank) for rank in normalized_ranks]
    comparison_query = question or (
        "Compare study design, population, disease, methods, interventions, "
        "comparators, primary outcomes, key numerical results, and limitations."
    )
    evidence = _retrieve_balanced_evidence(
        conversation_id,
        papers,
        comparison_query,
        chunks_per_paper=3,
    )
    if not evidence:
        raise ValueError("No indexed evidence is available for these papers")

    context = format_chunks_for_qa(evidence, conversation_id=conversation_id)
    schema_example = {
        "papers": [
            {
                "rank": rank,
                "fields": {
                    key: {
                        "value": "Evidence-backed text or Not reported in retrieved evidence",
                        "evidence_ids": ["an EVIDENCE ID from the same ranked paper"],
                    }
                    for key, _ in COMPARISON_FIELDS
                },
            }
            for rank in normalized_ranks
        ]
    }
    raw = _response_text(
        invoke_qa_model(
            [
                SystemMessage(
                    content=(
                        "Extract a structured comparison from biomedical evidence. "
                        "Paper ranks are immutable. Return JSON only. Every reported "
                        "value must name supporting EVIDENCE IDs from the same paper."
                    )
                ),
                HumanMessage(
                    content=(
                        f"{context}\n\nUSER COMPARISON REQUEST:\n{comparison_query}\n\n"
                        "Return exactly this JSON structure and no Markdown:\n"
                        f"{json.dumps(schema_example, indent=2)}"
                    )
                ),
            ]
        )
    )
    parsed = _extract_json(raw)

    evidence_by_id = {get_evidence_id(chunk): chunk for chunk in evidence}
    parsed_by_rank = {
        int(item.get("rank")): item
        for item in parsed.get("papers", [])
        if str(item.get("rank", "")).isdigit()
    }

    header = ["Comparison field"] + [
        f"Ranked paper #{rank}" for rank in normalized_ranks
    ]
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(["---"] * len(header)) + " |",
    ]
    for key, label in COMPARISON_FIELDS:
        row = [f"**{label}**"]
        for rank, paper in zip(normalized_ranks, papers):
            field = (
                parsed_by_rank.get(rank, {})
                .get("fields", {})
                .get(key, {})
            )
            if isinstance(field, str):
                field = {"value": field, "evidence_ids": []}
            value = str(field.get("value") or "Not reported in retrieved evidence")
            valid_citations = []
            paper_pmid = str(paper.get("pubmed_id") or paper.get("pmid"))
            for evidence_id in field.get("evidence_ids") or []:
                chunk = evidence_by_id.get(str(evidence_id))
                if not chunk or str(chunk.get("pmid")) != paper_pmid:
                    continue
                citation = f"[{rank}]({get_evidence_url(chunk, conversation_id)})"
                if citation not in valid_citations:
                    valid_citations.append(citation)
            if (
                value.lower() != "not reported in retrieved evidence"
                and not valid_citations
            ):
                value = "Not reported in retrieved evidence"
            cell = _escape_table_cell(value)
            if valid_citations:
                cell += " " + " ".join(valid_citations)
            row.append(cell)
        lines.append("| " + " | ".join(row) + " |")

    title_map = "\n".join(
        f"- **Ranked paper #{paper.get('rank')}**: {paper.get('title', 'Unknown title')}"
        for paper in papers
    )
    comparison = (
        f"## Structured comparison\n\n{title_map}\n\n"
        + "\n".join(lines)
    )

    references = [
        {
            "title": paper.get("title") or "Unknown title",
            "pmid": str(paper.get("pubmed_id") or paper.get("pmid")),
            "url": paper.get("url")
            or f"https://pubmed.ncbi.nlm.nih.gov/{paper.get('pubmed_id') or paper.get('pmid')}/",
            "year": paper.get("publication_year") or paper.get("year"),
            "rank": paper.get("rank"),
        }
        for paper in papers
    ]
    artifacts = []
    seen_artifacts = set()
    for chunk in evidence:
        artifact_id = chunk.get("artifact_id")
        if not artifact_id or artifact_id in seen_artifacts:
            continue
        seen_artifacts.add(artifact_id)
        artifacts.append(
            {
                "artifact_id": artifact_id,
                "type": chunk.get("content_type"),
                "pmid": str(chunk.get("pmid") or ""),
                "rank": chunk.get("rank"),
                "title": chunk.get("title") or "",
                "label": chunk.get("label") or chunk.get("section") or "Paper artifact",
                "page_number": chunk.get("page_number"),
                "url": chunk.get("artifact_url"),
            }
        )

    return {
        "comparison": comparison,
        "ranks": normalized_ranks,
        "references": references,
        "artifacts": artifacts,
    }

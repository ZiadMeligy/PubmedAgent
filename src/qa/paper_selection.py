"""Deterministic resolution of ordinal paper references."""

from dataclasses import dataclass
import re
from typing import Dict, List


ORDINAL_WORDS = {
    "first": 1,
    "second": 2,
    "third": 3,
    "fourth": 4,
    "fifth": 5,
    "1st": 1,
    "2nd": 2,
    "3rd": 3,
    "4th": 4,
    "5th": 5,
}
ORDINAL_PATTERN = "|".join(sorted(ORDINAL_WORDS, key=len, reverse=True))


@dataclass(frozen=True)
class PaperSelection:
    papers: List[Dict]
    requested_ranks: List[int]
    missing_ranks: List[int]
    explicit: bool

    @property
    def pmids(self) -> List[str]:
        return [
            str(p.get("pubmed_id") or p.get("pmid"))
            for p in self.papers
            if p.get("pubmed_id") or p.get("pmid")
        ]


def _mentioned_ranks(question: str) -> List[int]:
    text = question.lower()
    mentions: List[tuple[int, int]] = []

    # "paper 3", "ranked paper #3", "rank 3"
    for match in re.finditer(
        r"\b(?:(?:ranked?\s+)?papers?|rank)\s*(?:number\s*)?#?\s*(\d{1,2})\b",
        text,
    ):
        mentions.append((match.start(), int(match.group(1))))

    # "3rd paper", "first ranked paper", including the common
    # singular/plural typo "first ranked papers".
    for match in re.finditer(
        rf"\b({ORDINAL_PATTERN}|\d{{1,2}}(?:st|nd|rd|th))\s+(?:ranked\s+)?papers?\b",
        text,
    ):
        token = match.group(1)
        value = ORDINAL_WORDS.get(token)
        if value is None:
            value = int(re.match(r"\d+", token).group())
        mentions.append((match.start(), value))

    # "first and third ranked papers" / "papers 1 and 3"
    for match in re.finditer(
        rf"\b((?:{ORDINAL_PATTERN}|\d{{1,2}}(?:st|nd|rd|th)?)(?:\s*(?:,|and|&)\s*(?:{ORDINAL_PATTERN}|\d{{1,2}}(?:st|nd|rd|th)?))+)\s+(?:ranked\s+)?papers\b",
        text,
    ):
        for token_match in re.finditer(
            rf"{ORDINAL_PATTERN}|\d{{1,2}}(?:st|nd|rd|th)?",
            match.group(1),
        ):
            token = token_match.group()
            value = ORDINAL_WORDS.get(token)
            if value is None:
                value = int(re.match(r"\d+", token).group())
            mentions.append((match.start() + token_match.start(), value))

    # "papers 1 and 3" / "ranked papers #1, #3"
    for match in re.finditer(
        r"\b(?:ranked\s+)?papers?\s+((?:#?\d{1,2})(?:\s*(?:,|and|&)\s*#?\d{1,2})+)",
        text,
    ):
        for token_match in re.finditer(r"\d{1,2}", match.group(1)):
            mentions.append(
                (match.start(1) + token_match.start(), int(token_match.group()))
            )

    mentions.sort(key=lambda item: item[0])
    ranks: List[int] = []
    for _, rank in mentions:
        if rank not in ranks:
            ranks.append(rank)
    return ranks


def resolve_paper_selection(question: str, ranked_papers: List[Dict]) -> PaperSelection:
    """
    Map ordinal references to the latest composite-score ranked set.

    With no explicit ordinal, all papers remain eligible for semantic QA.
    """
    requested = _mentioned_ranks(question)
    by_rank = {
        int(paper.get("rank", index)): paper
        for index, paper in enumerate(ranked_papers, 1)
    }

    if not requested:
        return PaperSelection(
            papers=list(ranked_papers),
            requested_ranks=[],
            missing_ranks=[],
            explicit=False,
        )

    selected = [by_rank[rank] for rank in requested if rank in by_rank]
    missing = [rank for rank in requested if rank not in by_rank]
    return PaperSelection(
        papers=selected,
        requested_ranks=requested,
        missing_ranks=missing,
        explicit=True,
    )

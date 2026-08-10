import json
import unittest
from unittest.mock import patch
from langchain_core.messages import AIMessage

from src.services.paper_qa_service import (
    compare_ranked_papers,
    summarize_ranked_paper,
)


PAPERS = [
    {
        "rank": 1,
        "pubmed_id": "111",
        "title": "First study",
        "url": "https://pubmed.ncbi.nlm.nih.gov/111/",
        "publication_year": 2024,
    },
    {
        "rank": 3,
        "pubmed_id": "333",
        "title": "Third study",
        "url": "https://pubmed.ncbi.nlm.nih.gov/333/",
        "publication_year": 2022,
    },
]

EVIDENCE = [
    {
        "pmid": "111",
        "rank": 1,
        "chunk_id": "111_fulltext_1",
        "page_number": 4,
        "content_type": "text",
        "section": "Methods",
        "text": "Randomized trial with 100 participants.",
        "rerank_score": 0.9,
    },
    {
        "pmid": "333",
        "rank": 3,
        "chunk_id": "333_fulltext_2",
        "page_number": 7,
        "content_type": "text",
        "section": "Methods",
        "text": "Prospective cohort with 80 participants.",
        "rerank_score": 0.8,
    },
]


class PaperStoreStub:
    def get_papers(self, _conversation_id):
        return PAPERS


class SummaryRepositoryStub:
    def __init__(self):
        self.saved = None

    def get_paper_summary(self, _conversation_id, _pmid):
        return None

    def save_paper_summary(self, conversation_id, pmid, summary):
        self.saved = (conversation_id, pmid, summary)


class PaperQAFeatureTests(unittest.TestCase):
    @patch(
        "src.services.paper_qa_service.get_conversation_paper_store",
        return_value=PaperStoreStub(),
    )
    @patch(
        "src.services.paper_qa_service._retrieve_balanced_evidence",
        return_value=EVIDENCE,
    )
    @patch("src.services.paper_qa_service.invoke_qa_model")
    def test_structured_comparison_builds_validated_evidence_links(
        self,
        invoke_model,
        _retrieve,
        _paper_store,
    ):
        invoke_model.return_value = AIMessage(
            content=json.dumps({
                "papers": [
                    {
                        "rank": 1,
                        "fields": {
                            "study_design": {
                                "value": "Randomized trial",
                                "evidence_ids": ["111_fulltext_1"],
                            }
                        },
                    },
                    {
                        "rank": 3,
                        "fields": {
                            "study_design": {
                                "value": "Prospective cohort",
                                "evidence_ids": ["333_fulltext_2"],
                            }
                        },
                    },
                ]
            })
        )

        result = compare_ranked_papers("conversation-1", [1, 3])

        self.assertIn("Structured comparison", result["comparison"])
        self.assertIn("Randomized trial", result["comparison"])
        self.assertIn("/evidence/111?chunk_id=111_fulltext_1", result["comparison"])
        self.assertIn("/evidence/333?chunk_id=333_fulltext_2", result["comparison"])
        self.assertEqual(result["ranks"], [1, 3])

    @patch(
        "src.services.paper_qa_service.get_conversation_paper_store",
        return_value=PaperStoreStub(),
    )
    @patch(
        "src.services.paper_qa_service._retrieve_balanced_evidence",
        return_value=EVIDENCE[:1],
    )
    @patch("src.services.paper_qa_service.get_conversation_repository")
    @patch(
        "src.services.paper_qa_service.invoke_qa_model",
        return_value=AIMessage(content="## Overview\n\nEvidence-backed summary."),
    )
    def test_summary_is_saved_for_reuse(
        self,
        _invoke_model,
        repository_factory,
        _retrieve,
        _paper_store,
    ):
        repository = SummaryRepositoryStub()
        repository_factory.return_value = repository

        result = summarize_ranked_paper("conversation-1", 1)

        self.assertFalse(result["cached"])
        self.assertEqual(repository.saved[0:2], ("conversation-1", "111"))
        self.assertIn("Evidence-backed summary", repository.saved[2])


if __name__ == "__main__":
    unittest.main()

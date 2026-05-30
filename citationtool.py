import re
import requests


class PubMedCitationFinder:
    PUBMED_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    OPENALEX_BASE = "https://api.openalex.org"
    SEMANTIC_SCHOLAR_BASE = "https://api.semanticscholar.org/graph/v1"

    def __init__(self):
        self.session = requests.Session()

    # ---------------------------------------------------------
    # PUBMED
    # ---------------------------------------------------------

    def get_pmid_from_url(self, pubmed_url: str) -> str:
        match = re.search(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d+)", pubmed_url)

        if not match:
            raise ValueError("Could not extract PMID from URL")

        return match.group(1)

    def search_pmid_by_title(self, title: str) -> str:
        url = f"{self.PUBMED_BASE}/esearch.fcgi"

        params = {
            "db": "pubmed",
            "term": f'"{title}"[Title]',
            "retmode": "json",
            "retmax": 1,
        }

        response = self.session.get(url, params=params)
        response.raise_for_status()

        ids = response.json()["esearchresult"]["idlist"]

        if not ids:
            raise ValueError(f"No PubMed paper found for title: {title}")

        return ids[0]

    def get_paper_info_from_pmid(self, pmid: str) -> dict:
        url = f"{self.PUBMED_BASE}/esummary.fcgi"

        params = {
            "db": "pubmed",
            "id": pmid,
            "retmode": "json",
        }

        response = self.session.get(url, params=params)
        response.raise_for_status()

        article = response.json()["result"][str(pmid)]

        doi = None

        for item in article.get("articleids", []):
            if item.get("idtype") == "doi":
                doi = item["value"]
                break

        if not doi:
            raise ValueError("DOI not found")

        return {
            "pmid": pmid,
            "title": article.get("title"),
            "doi": doi,
        }

    # ---------------------------------------------------------
    # OPENALEX
    # ---------------------------------------------------------

    def get_openalex_metrics(self, doi: str) -> dict:
        doi = doi.lower().replace("https://doi.org/", "")

        url = f"{self.OPENALEX_BASE}/works/https://doi.org/{doi}"

        response = self.session.get(url)

        if response.status_code != 200:
            return None

        data = response.json()

        return {
            "openalex_id": data.get("id"),
            "openalex_citations": data.get("cited_by_count"),
            "openalex_references": data.get("referenced_works_count"),
            "publication_year": data.get("publication_year"),
        }

    # ---------------------------------------------------------
    # SEMANTIC SCHOLAR
    # ---------------------------------------------------------

    def get_semantic_scholar_metrics(self, doi: str) -> dict:
        url = f"{self.SEMANTIC_SCHOLAR_BASE}/paper/DOI:{doi}"

        params = {
            "fields": "title,citationCount,referenceCount"
        }

        response = self.session.get(url, params=params)

        if response.status_code != 200:
            return None

        data = response.json()

        return {
            "semantic_scholar_citations": data.get("citationCount"),
            "semantic_scholar_references": data.get("referenceCount"),
        }

    # ---------------------------------------------------------
    # MAIN FUNCTIONS
    # ---------------------------------------------------------

    def from_pmid(self, pmid: str) -> dict:
        paper = self.get_paper_info_from_pmid(pmid)

        openalex = self.get_openalex_metrics(paper["doi"]) or {}
        semantic = self.get_semantic_scholar_metrics(paper["doi"]) or {}

        return {
            **paper,
            **openalex,
            **semantic,
        }

    def from_url(self, pubmed_url: str) -> dict:
        pmid = self.get_pmid_from_url(pubmed_url)
        return self.from_pmid(pmid)

    def from_title(self, title: str) -> dict:
        pmid = self.search_pmid_by_title(title)
        return self.from_pmid(pmid)


# ---------------------------------------------------------
# EXAMPLES
# ---------------------------------------------------------

if __name__ == "__main__":
    finder = PubMedCitationFinder()

    paper1 = finder.from_url(
        "https://pubmed.ncbi.nlm.nih.gov/31452104/"
    )

    print("\nPaper 1")
    for k, v in paper1.items():
        print(f"{k}: {v}")

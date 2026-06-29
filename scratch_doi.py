import json
from pymed import PubMed

pubmed = PubMed(tool="pubmed", email="your_email@example.com")
results = list(pubmed.query("Research Progress of Natural Products Targeting Macrophages in the Treatment of Diabetic Kidney Disease", max_results=1))

for article in results:
    print(f"Title: {article.title}")
    print(f"DOI Raw: {getattr(article, 'doi', None)}")
    print(f"Type of DOI: {type(getattr(article, 'doi', None))}")
    print(vars(article))

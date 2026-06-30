import json
from pymed import PubMed
import re

def normalize_journal_name(name: str) -> str:
    if not name:
        return ""
    name = name.lower()
    name = re.sub(r'[^\w\s]', '', name)
    return re.sub(r'\s+', ' ', name).strip()

def main():
    pubmed = PubMed(tool="pubmed_test", email="test@example.com")
    results = list(pubmed.query("prostate cancer", max_results=10))
    
    with open("src/data/journal_sjr.json", "r") as f:
        lookup = json.load(f)
        
    print(f"Loaded {len(lookup)} entries from SJR lookup.")
    
    for article in results:
        journal = getattr(article, "journal", "N/A")
        issn = getattr(article, "issn", "N/A")
        print(f"Title: {article.title[:50]}...")
        print(f"Journal: {journal}")
        print(f"ISSN: {issn}")
        
        norm_journal = normalize_journal_name(journal)
        print(f"Normalized Journal: '{norm_journal}'")
        
        found = False
        if issn != "N/A" and issn in lookup:
            print(f"-> Found by ISSN! SJR: {lookup[issn]['sjr']}")
            found = True
        elif norm_journal in lookup:
            print(f"-> Found by Normalized Name! SJR: {lookup[norm_journal]['sjr']}")
            found = True
        else:
            print("-> Not found in lookup.")
        print("-" * 30)

if __name__ == "__main__":
    main()

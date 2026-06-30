import csv
import json
import os
import re

def normalize_title(title: str) -> str:
    # Lowercase
    title = title.lower()
    # Remove punctuation
    title = re.sub(r'[^\w\s]', '', title)
    # Collapse multiple spaces and trim
    title = re.sub(r'\s+', ' ', title).strip()
    return title

def main():
    csv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "scimagojr 2025.csv")
    json_path = os.path.join(os.path.dirname(__file__), "journal_sjr.json")

    lookup = {}

    print(f"Reading from {csv_path}...")
    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        
        for row in reader:
            issn_str = row.get("Issn", "")
            title = row.get("Title", "")
            sjr_str = row.get("SJR", "")
            quartile = row.get("SJR Best Quartile", "")
            h_index_str = row.get("H index", "")
            
            # Skip entries without SJR
            if not sjr_str:
                continue
                
            try:
                # SJR values use comma for decimals in this dataset (e.g., 104,065)
                sjr_val = float(sjr_str.replace(",", "."))
            except ValueError:
                continue
                
            try:
                h_index_val = int(h_index_str) if h_index_str else 0
            except ValueError:
                h_index_val = 0
                
            entry = {
                "journal": title,
                "sjr": sjr_val,
                "quartile": quartile,
                "h_index": h_index_val
            }
            
            # Split multiple ISSNs (e.g. "15424863, 00079235")
            issns = [i.strip() for i in issn_str.split(",") if i.strip()]
            
            for issn in issns:
                # Add dash to 8-digit ISSNs if not present to match typical format
                if len(issn) == 8 and "-" not in issn:
                    formatted_issn = f"{issn[:4]}-{issn[4:]}"
                    lookup[formatted_issn] = entry
                else:
                    lookup[issn] = entry
            
            # Also store by normalized title as fallback
            norm_title = normalize_title(title)
            if norm_title and norm_title not in lookup:
                lookup[norm_title] = entry

    print(f"Writing {len(lookup)} entries to {json_path}...")
    with open(json_path, mode="w", encoding="utf-8") as f:
        json.dump(lookup, f, separators=(',', ':'))
        
    print("Done!")

if __name__ == "__main__":
    main()

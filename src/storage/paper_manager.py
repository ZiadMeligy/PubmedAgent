"""
Vector store management for paper abstracts and Q&A retrieval.
"""

import re
from typing import List, Dict, Optional
from src.storage import QdrantVectorStore
from src.processing import chunk_abstract
from src.fulltext.index_service import get_fulltext_store


_LEXICAL_STOPWORDS = {
    "about", "after", "also", "and", "are", "can", "could", "does", "for",
    "from", "have", "into", "paper", "ranked", "show", "that", "the", "their",
    "this", "was", "were", "what", "when", "with",
}


def _lexical_candidates(query: str, chunks: List[Dict], limit: int = 8) -> List[Dict]:
    """Rank scoped payloads by exact terms, numbers, and phrase coverage."""
    query_lower = query.lower()
    query_terms = [
        token
        for token in re.findall(r"[a-z]+|\d+(?:\.\d+)?", query_lower)
        if token not in _LEXICAL_STOPWORDS and (len(token) > 2 or token[0].isdigit())
    ]
    if not query_terms:
        return []

    ranked = []
    for chunk in chunks:
        text = str(chunk.get("text") or "")
        text_lower = text.lower()
        score = 0.0
        for term in set(query_terms):
            occurrences = text_lower.count(term)
            if not occurrences:
                continue
            weight = 3.0 if term[0].isdigit() else 1.0
            if term in {"psa", "figure", "table", "outcome", "method"}:
                weight += 1.0
            score += weight * min(occurrences, 3)
        for phrase in re.findall(r"\b\d+\s+(?:day|week|month|year)s?\b", query_lower):
            if phrase in text_lower:
                score += 5.0
        if score > 0:
            candidate = dict(chunk)
            candidate["lexical_score"] = score
            ranked.append(candidate)

    ranked.sort(key=lambda item: item["lexical_score"], reverse=True)
    return ranked[:limit]


class PaperAbstractStore:
    """Manages chunking and storage of paper abstracts in Qdrant."""
    
    def __init__(self):
        """Initialize the vector store."""
        self.vector_store = QdrantVectorStore()
    
    def add_papers_to_store(self, papers: List[Dict], conversation_id: Optional[str] = None) -> int:
        """
        Chunk abstracts from papers and add to vector store.
        
        Args:
            papers: List of paper dictionaries with abstract, title, pmid, year, journal
            conversation_id: Optional conversation ID to associate with the chunks
        
        Returns:
            Total number of chunks added
        """
        total_chunks_added = 0

        if conversation_id:
            # A new PubMed search replaces the active ranked set. Remove its
            # stale abstract vectors so they cannot leak into later QA.
            try:
                self.vector_store.delete_by_filter(conversation_id=conversation_id)
            except Exception:
                pass
        
        for rank, paper in enumerate(papers, 1):
            abstract = paper.get('abstract')
            if not abstract or abstract == "No abstract available":
                continue
            
            pmid = str(paper.get('pubmed_id', 'Unknown'))
            title = paper.get('title', 'Unknown')
            year = paper.get('publication_year')
            journal = paper.get('journal', 'Unknown')
            url = paper.get('url', f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/")
            
            # Chunk the abstract (2-4 sentences per chunk)
            chunks = chunk_abstract(abstract, sentences_per_chunk=3)
            
            # Create chunk dictionaries with metadata
            chunk_dicts = []
            for i, chunk_text in enumerate(chunks):
                chunk_dicts.append({
                    'text': chunk_text,
                    'pmid': pmid,
                    'title': title,
                    'year': year,
                    'journal': journal,
                    'url': url,
                    'section': 'Abstract',
                    'chunk_id': f"{pmid}_chunk_{i}",
                    'conversation_id': conversation_id,
                    'rank': rank,
                    'content_type': 'abstract',
                    'source': 'abstract',
                })
            
            # Add chunks to vector store
            if chunk_dicts:
                chunks_added = self.vector_store.add_chunks(chunk_dicts)
                total_chunks_added += chunks_added
        
        return total_chunks_added
    
    def search_for_answer(
        self,
        query: str,
        conversation_id: Optional[str] = None,
        top_k: int = 5,
        pmids: Optional[List[str]] = None,
        lexical_query: Optional[str] = None,
    ) -> List[Dict]:
        """
        Search vector store for chunks relevant to query from both abstracts and full text.
        
        Args:
            query: Question/query text
            conversation_id: Optional conversation ID to filter by
            top_k: Number of chunks to retrieve
        
        Returns:
            List of relevant chunks with scores and metadata
        """
        selected_pmids = [str(pmid) for pmid in (pmids or [])]

        # Retrieve a balanced candidate pool per selected paper. A comparison
        # must not lose one paper merely because another has more chunks.
        paper_scopes = selected_pmids or [None]
        abstract_results = []
        fulltext_results = []
        fulltext_store = get_fulltext_store()

        for scoped_pmid in paper_scopes:
            scope = [scoped_pmid] if scoped_pmid else None
            abstract_results.extend(
                self.vector_store.search(
                    query,
                    limit=top_k,
                    score_threshold=0.0,
                    conversation_id=conversation_id,
                    pmids=scope,
                )
            )
            try:
                fulltext_results.extend(
                    fulltext_store.search(
                        query,
                        limit=max(top_k * 2, 8),
                        score_threshold=0.0,
                        pmids=scope,
                    )
                )
            except Exception:
                # The full-text collection may not exist until a PDF is indexed.
                pass

            # Dense retrieval can miss exact time points, dosages, table rows,
            # and identifiers. Add a lexical pool from every chunk belonging
            # to the already-selected PMID.
            lexical_text = lexical_query or query
            try:
                scoped_abstracts = self.vector_store.scroll_payloads(
                    conversation_id=conversation_id,
                    pmids=scope,
                )
                abstract_results.extend(
                    _lexical_candidates(lexical_text, scoped_abstracts, limit=top_k)
                )
                scoped_fulltext = fulltext_store.scroll_payloads(pmids=scope)
                fulltext_results.extend(
                    _lexical_candidates(
                        lexical_text,
                        scoped_fulltext,
                        limit=max(top_k * 2, 12),
                    )
                )
            except Exception:
                pass
            
        # Deduplicate exact chunks and preserve a broad pool for the cross-encoder.
        all_results = abstract_results + fulltext_results
        all_results.sort(key=lambda x: x.get('score', 0), reverse=True)
        unique_results = []
        seen = set()
        for result in all_results:
            key = (
                result.get("pmid"),
                result.get("chunk_id") or result.get("artifact_id"),
                result.get("text"),
            )
            if key in seen:
                continue
            seen.add(key)
            unique_results.append(result)

        candidate_limit = max(top_k * len(paper_scopes) * 3, top_k)
        return unique_results[:candidate_limit]
    
    def clear_store(self):
        """Clear all chunks from the vector store."""
        self.vector_store.clear_collection()
    
    def get_store_stats(self) -> Dict:
        """Get vector store statistics."""
        return self.vector_store.get_stats()


# Global instance for managing paper abstracts
_paper_store = None


def get_paper_store() -> PaperAbstractStore:
    """Get or create the global paper abstract store instance."""
    global _paper_store
    if _paper_store is None:
        _paper_store = PaperAbstractStore()
    return _paper_store

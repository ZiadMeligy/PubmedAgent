"""
Vector store management for paper abstracts and Q&A retrieval.
"""

from typing import List, Dict, Optional
from src.storage import QdrantVectorStore
from src.processing import chunk_abstract
from src.processing.semantic_chunker import SemanticChunker


class PaperAbstractStore:
    """Manages chunking and storage of paper abstracts in Qdrant."""
    
    def __init__(self):
        """Initialize the vector store."""
        self.vector_store = QdrantVectorStore()
    
    def add_papers_to_store(self, papers: List[Dict]) -> int:
        """
        Chunk abstracts from papers and add to vector store.
        
        Args:
            papers: List of paper dictionaries with abstract, title, pmid, year, journal
        
        Returns:
            Total number of chunks added
        """
        total_chunks_added = 0
        
        for paper in papers:
            abstract = paper.get('abstract')
            if not abstract or abstract == "No abstract available":
                continue
            
            pmid = paper.get('pubmed_id', 'Unknown')
            title = paper.get('title', 'Unknown')
            year = paper.get('publication_year')
            journal = paper.get('journal', 'Unknown')
            
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
                    'section': 'Abstract',
                    'chunk_id': f"{pmid}_chunk_{i}"
                })
            
            # Add chunks to vector store
            if chunk_dicts:
                chunks_added = self.vector_store.add_chunks(chunk_dicts)
                total_chunks_added += chunks_added
        
        return total_chunks_added
    
    def search_for_answer(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        Search vector store for chunks relevant to query.
        
        Args:
            query: Question/query text
            top_k: Number of chunks to retrieve
        
        Returns:
            List of relevant chunks with scores and metadata
        """
        results = self.vector_store.search(query, limit=top_k, score_threshold=0.0)
        return results
    
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

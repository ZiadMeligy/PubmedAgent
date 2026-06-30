"""
Semantic chunking for scientific papers.
Preserves section structure and scientific coherence.
"""

import re
from typing import List, Dict
from nltk.tokenize import sent_tokenize
import nltk

# Download required NLTK data
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt', quiet=True)


class SemanticChunker:
    """Chunk scientific papers while preserving meaning and structure."""
    
    # Common medical/scientific section headers
    SECTION_PATTERNS = {
        'abstract': r'(?i)^abstract',
        'introduction': r'(?i)^(introduction|background)',
        'methods': r'(?i)^(methods|methodology|participants|study design)',
        'results': r'(?i)^results',
        'discussion': r'(?i)^discussion',
        'conclusion': r'(?i)^(conclusion|conclusions)',
        'references': r'(?i)^references',
    }
    
    def __init__(self, max_tokens_per_chunk: int = 500):
        """
        Initialize chunker.
        
        Args:
            max_tokens_per_chunk: Maximum tokens per chunk (approximate)
        """
        self.max_tokens = max_tokens_per_chunk
        self.avg_tokens_per_word = 1.3  # Rough estimate
        self.max_words = int(max_tokens_per_chunk / self.avg_tokens_per_word)
    
    def chunk_sections(self, sections: Dict[str, str]) -> List[Dict]:
        """
        Chunk paper sections while preserving structure.
        
        Args:
            sections: Dict with section names and text
        
        Returns:
            List of chunks with metadata
        """
        chunks = []
        chunk_id = 0
        
        for section_name, section_text in sections.items():
            if not section_text or section_text.strip() == "":
                continue
            
            # Chunk the section
            section_chunks = self._chunk_section(
                section_text, 
                section_name,
                chunk_id
            )
            
            chunks.extend(section_chunks)
            chunk_id += len(section_chunks)
        
        return chunks
    
    def _chunk_section(self, text: str, section_name: str, start_chunk_id: int) -> List[Dict]:
        """
        Chunk a single section using semantic boundaries.
        
        Tries to break at sentence boundaries, respecting paragraph structure.
        """
        chunks = []
        
        # Split into paragraphs
        paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
        
        if not paragraphs:
            return []
        
        current_chunk = ""
        current_chunk_id = start_chunk_id
        
        for para in paragraphs:
            # Split paragraph into sentences
            try:
                sentences = sent_tokenize(para)
            except:
                # Fallback if tokenization fails
                sentences = para.split('. ')
            
            for sentence in sentences:
                sentence = sentence.strip()
                if not sentence:
                    continue
                
                # Check if adding this sentence would exceed limit
                test_chunk = current_chunk + " " + sentence if current_chunk else sentence
                word_count = len(test_chunk.split())
                
                if word_count > self.max_words and current_chunk:
                    # Save current chunk and start new one
                    chunks.append({
                        'text': current_chunk.strip(),
                        'section': section_name,
                        'chunk_id': current_chunk_id
                    })
                    current_chunk_id += 1
                    current_chunk = sentence
                else:
                    # Add to current chunk
                    current_chunk = test_chunk if current_chunk else sentence
            
            # Add paragraph break for readability
            current_chunk += "\n"
        
        # Save final chunk
        if current_chunk.strip():
            chunks.append({
                'text': current_chunk.strip(),
                'section': section_name,
                'chunk_id': current_chunk_id
            })
        
        return chunks
    
    def chunk_text(self, text: str, section_name: str = "full_text") -> List[Dict]:
        """
        Chunk arbitrary text (fallback for papers without section structure).
        
        Args:
            text: Full text to chunk
            section_name: Name of section
        
        Returns:
            List of chunks with metadata
        """
        chunks = []
        
        # Try to split into sentences first
        try:
            sentences = sent_tokenize(text)
        except:
            # Fallback: split by periods
            sentences = text.split('. ')
        
        current_chunk = ""
        chunk_id = 0
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            test_chunk = current_chunk + " " + sentence if current_chunk else sentence
            word_count = len(test_chunk.split())
            
            if word_count > self.max_words and current_chunk:
                chunks.append({
                    'text': current_chunk.strip(),
                    'section': section_name,
                    'chunk_id': chunk_id
                })
                chunk_id += 1
                current_chunk = sentence
            else:
                current_chunk = test_chunk if current_chunk else sentence
        
        if current_chunk.strip():
            chunks.append({
                'text': current_chunk.strip(),
                'section': section_name,
                'chunk_id': chunk_id
            })
        
        return chunks


def create_chunks_with_metadata(
    pmid: str,
    title: str,
    year: int,
    journal: str,
    sections: Dict[str, str],
    max_tokens: int = 500
) -> List[Dict]:
    """
    Create chunks with full metadata.
    
    Args:
        pmid: PubMed ID
        title: Paper title
        year: Publication year
        journal: Journal name
        sections: Dictionary of section name -> text
        max_tokens: Max tokens per chunk
    
    Returns:
        List of chunks with full metadata
    """
    chunker = SemanticChunker(max_tokens_per_chunk=max_tokens)
    chunks = chunker.chunk_sections(sections)
    
    # Add metadata to each chunk
    for chunk in chunks:
        chunk['pmid'] = pmid
        chunk['title'] = title
        chunk['year'] = year
        chunk['journal'] = journal
    
    return chunks

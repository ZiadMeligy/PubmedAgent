"""
Semantic text chunking for medical papers.
Splits papers into meaningful chunks based on section structure and semantic boundaries.
"""

import re
from typing import List, Dict


class SemanticChunker:
    """Split text into semantic chunks while preserving structure."""
    
    @staticmethod
    def chunk_by_sections(sections: Dict[str, str], max_chunk_size: int = 1000) -> List[Dict]:
        """
        Chunk text by document sections.
        
        Args:
            sections: Dictionary of section_name -> section_text
            max_chunk_size: Maximum size of chunk in characters
        
        Returns:
            List of chunks with section metadata
        """
        chunks = []
        
        for section_name, section_text in sections.items():
            if not section_text or section_text.isspace():
                continue
            
            # If section is small, add as single chunk
            if len(section_text) <= max_chunk_size:
                chunks.append({
                    'section': section_name,
                    'text': section_text.strip(),
                    'size': len(section_text)
                })
            else:
                # Split large sections into subsections
                subsections = SemanticChunker._split_paragraphs(
                    section_text, 
                    max_chunk_size
                )
                for i, chunk_text in enumerate(subsections):
                    chunks.append({
                        'section': f"{section_name} (Part {i+1})",
                        'text': chunk_text.strip(),
                        'size': len(chunk_text)
                    })
        
        return chunks
    
    @staticmethod
    def _split_paragraphs(text: str, max_chunk_size: int) -> List[str]:
        """Split text into paragraphs, respecting max_chunk_size."""
        # Split by double newlines (paragraphs)
        paragraphs = re.split(r'\n\n+', text)
        
        chunks = []
        current_chunk = ""
        
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            
            # If adding this paragraph exceeds max size and we have content
            if current_chunk and len(current_chunk) + len(paragraph) > max_chunk_size:
                chunks.append(current_chunk.strip())
                current_chunk = paragraph
            else:
                if current_chunk:
                    current_chunk += "\n\n" + paragraph
                else:
                    current_chunk = paragraph
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    @staticmethod
    def chunk_by_sentences(text: str, sentences_per_chunk: int = 3) -> List[str]:
        """
        Split text into chunks of sentences.
        
        Args:
            text: Text to chunk
            sentences_per_chunk: Number of sentences per chunk
        
        Returns:
            List of chunks
        """
        # Simple sentence splitter (handles most cases)
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        
        chunks = []
        for i in range(0, len(sentences), sentences_per_chunk):
            chunk = ' '.join(sentences[i:i+sentences_per_chunk])
            if chunk.strip():
                chunks.append(chunk.strip())
        
        return chunks if chunks else [text]
    
    @staticmethod
    def prepare_paper_chunks(
        pmid: str,
        title: str,
        year: int,
        journal: str,
        sections: Dict[str, str]
    ) -> List[Dict]:
        """
        Prepare chunks from full paper with metadata.
        
        Args:
            pmid: PubMed ID
            title: Paper title
            year: Publication year
            journal: Journal name
            sections: Dictionary of section_name -> section_text
        
        Returns:
            List of chunks with complete metadata
        """
        chunks = SemanticChunker.chunk_by_sections(sections)
        
        # Add paper-level metadata to each chunk
        for chunk in chunks:
            chunk.update({
                'pmid': pmid,
                'title': title,
                'year': year,
                'journal': journal
            })
        
        return chunks

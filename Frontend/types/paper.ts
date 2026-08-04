export interface Paper {
  rank: number;
  title: string;
  url: string;
  journal?: string;
  publication_year: number;
  citation_count: number;
  similarity_score: number;
  composite_score: number;
  pubmed_id: string;
  doi?: string;
  fullTextStatus?: 'UNKNOWN' | 'CHECKING' | 'AVAILABLE' | 'NOT_AVAILABLE';
  pdfUrl?: string;
  indexStatus?: 'NONE' | 'INDEXING' | 'INDEXED' | 'ALREADY_INDEXED' | 'ERROR';
  indexMessage?: string;
}

export interface Reference {
  title: string;
  pmid: string;
  url: string;
  year?: number;
  rank?: number;
}

export interface PaperArtifact {
  artifact_id: string;
  type: 'image' | 'table' | string;
  pmid: string;
  rank?: number;
  title: string;
  label: string;
  page_number?: number;
  url?: string;
}

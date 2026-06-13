export interface Paper {
  rank: number;
  title: string;
  url: string;
  publication_year: number;
  citation_count: number;
  similarity_score: number;
  composite_score: number;
}

export interface Reference {
  title: string;
  pmid: string;
  url: string;
}

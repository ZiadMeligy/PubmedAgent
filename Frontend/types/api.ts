import { Paper, PaperArtifact, Reference } from './paper';

export interface ChatRequest {
  conversation_id: string | null;
  message: string;
}

export interface RetrievalConfig {
  similarity: number;
  recency: number;
  citation: number;
  journal_quality_enabled?: boolean;
  minimum_sjr?: number;
}

export interface PaperSearchResponse {
  type: 'paper_search';
  conversation_id: string;
  papers_found: boolean;
  papers: Paper[];
  retrieval_config?: RetrievalConfig;
}

export interface QAResponse {
  type: 'qa';
  conversation_id: string;
  response: string;
  references: Reference[];
  artifacts: PaperArtifact[];
}

export interface ChatResponse {
  type: 'chat';
  conversation_id: string;
  response: string;
}

export interface ErrorResponse {
  type: 'error';
  message: string;
}

export type APIResponse = PaperSearchResponse | QAResponse | ChatResponse | ErrorResponse;

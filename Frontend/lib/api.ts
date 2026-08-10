import {
  ChatRequest,
  APIResponse,
  EvidenceDetail,
  PaperArtifactList,
  PaperSummary,
} from '@/types';
import { useAuthStore } from './store';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export class APIError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'APIError';
  }
}

function authHeaders(includeJson = true): HeadersInit {
  const token = useAuthStore.getState().token;
  const headers: HeadersInit = {};
  if (includeJson) headers['Content-Type'] = 'application/json';
  if (token) headers['Authorization'] = `Bearer ${token}`;
  return headers;
}

async function apiError(response: Response, fallback: string): Promise<APIError> {
  try {
    const data = await response.json();
    return new APIError(data.detail || data.message || fallback);
  } catch {
    return new APIError(fallback);
  }
}

export async function sendMessage(
  conversationId: string | null,
  message: string
): Promise<APIResponse> {
  const request: ChatRequest = {
    conversation_id: conversationId,
    message,
  };

  const headers = authHeaders();

  const response = await fetch(`${API_BASE_URL}/chat`, {
    method: 'POST',
    headers,
    body: JSON.stringify(request),
  });

  if (response.status === 401) {
    useAuthStore.getState().logout();
    throw new APIError('Unauthorized. Please log in again.');
  }

  if (!response.ok) {
    throw new APIError(`Failed to send message: ${response.status} ${response.statusText}`);
  }

  const data: APIResponse = await response.json();
  return data;
}

export async function checkFullText(papers: any[]): Promise<any> {
  const headers = authHeaders();

  const response = await fetch(`${API_BASE_URL}/api/fulltext/check`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ papers: papers.map(p => ({ pmid: p.pubmed_id, doi: p.doi, title: p.title })) }),
  });

  if (!response.ok) {
    throw new APIError(`Failed to check full text: ${response.status}`);
  }

  return response.json();
}

export async function summarizePaper(
  conversationId: string,
  rank: number,
  refresh = false
): Promise<PaperSummary> {
  const response = await fetch(`${API_BASE_URL}/api/papers/rank/${rank}/summary`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({
      conversation_id: conversationId,
      refresh,
    }),
  });
  if (!response.ok) {
    throw await apiError(response, `Failed to summarize ranked paper #${rank}`);
  }
  return response.json();
}

export async function getPaperArtifacts(
  conversationId: string,
  pmid: string
): Promise<PaperArtifactList> {
  const params = new URLSearchParams({ conversation_id: conversationId });
  const response = await fetch(
    `${API_BASE_URL}/api/fulltext/papers/${encodeURIComponent(pmid)}/artifacts?${params}`,
    { headers: authHeaders(false) }
  );
  if (!response.ok) {
    throw await apiError(response, 'Failed to load tables and figures');
  }
  return response.json();
}

export async function getEvidence(
  conversationId: string,
  pmid: string,
  evidenceId: string
): Promise<EvidenceDetail> {
  const params = new URLSearchParams({ conversation_id: conversationId });
  const response = await fetch(
    `${API_BASE_URL}/api/fulltext/papers/${encodeURIComponent(pmid)}/evidence/${encodeURIComponent(evidenceId)}?${params}`,
    { headers: authHeaders(false) }
  );
  if (!response.ok) {
    throw await apiError(response, 'Failed to load cited evidence');
  }
  return response.json();
}

export async function getIndexedPaperPdf(
  conversationId: string,
  pmid: string
): Promise<Blob> {
  const params = new URLSearchParams({ conversation_id: conversationId });
  const response = await fetch(
    `${API_BASE_URL}/api/fulltext/papers/${encodeURIComponent(pmid)}/pdf?${params}`,
    { headers: authHeaders(false) }
  );
  if (!response.ok) {
    throw await apiError(response, 'Failed to load the indexed PDF');
  }
  return response.blob();
}
